# Report Chat Semantic Micro-Compaction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add post-answer incremental semantic micro-compaction to Report Chat while preserving complete MySQL message history and keeping compaction failures non-blocking.

**Architecture:** A new `micro_compact` LangGraph node runs after `save_chat_memory`, checks deterministic message/token thresholds, and summarizes only older uncompressed messages together with the previous summary. The node keeps the most recent four raw messages, stores the compacted summary and observability metadata in Checkpointer state, and exposes that summary as a separately budgeted input to the next answer prompt.

**Tech Stack:** Python 3.11+, FastAPI Settings via Pydantic, LangGraph StateGraph/Checkpointer, LangChain-compatible `LlmClient`, pytest.

## Global Constraints

- Scope is Report Chat only; do not modify the generic Runtime conversation path.
- MySQL user and assistant messages remain complete and unchanged.
- Defaults are: enabled `true`, token threshold `1200`, message threshold `6`, keep recent `4`, target summary tokens `600`.
- A compaction failure must preserve the prior summary and all current raw `chat_history` messages.
- Only apply a new summary when it is non-empty, safe, at most 600 estimated tokens, and smaller than its source input.
- Reuse `context_budget.estimate_tokens`, the existing Report Chat model, and `operation_llm_timeout_seconds`.
- Keep `memory_context` explicit-only and separate from automatic `compaction_summary`.
- Do not touch the user's existing `frontend/src/pages/error-code/IndexPage.vue` changes.

---

### Task 1: Configuration and State Contracts

**Files:**
- Modify: `backend/app/config/settings.py`
- Modify: `backend/.env.example`
- Modify: `backend/app/report_chat_agent/state.py`
- Create: `backend/tests/report_chat_agent/test_micro_compaction_settings.py`

**Interfaces:**
- Produces: `settings.report_chat_micro_compaction_enabled: bool`
- Produces: `settings.report_chat_micro_compaction_token_threshold: int`
- Produces: `settings.report_chat_micro_compaction_message_threshold: int`
- Produces: `settings.report_chat_micro_compaction_keep_recent: int`
- Produces: `settings.report_chat_micro_compaction_target_tokens: int`
- Produces state fields: `compaction_summary: dict[str, Any]` and `micro_compaction: dict[str, Any]`

- [ ] **Step 1: Write failing default and validation tests**

Create `backend/tests/report_chat_agent/test_micro_compaction_settings.py`:

```python
import pytest
from pydantic import ValidationError

from app.config.settings import Settings


def test_micro_compaction_settings_have_safe_defaults():
    configured = Settings(_env_file=None)

    assert configured.report_chat_micro_compaction_enabled is True
    assert configured.report_chat_micro_compaction_token_threshold == 1200
    assert configured.report_chat_micro_compaction_message_threshold == 6
    assert configured.report_chat_micro_compaction_keep_recent == 4
    assert configured.report_chat_micro_compaction_target_tokens == 600


def test_message_threshold_must_exceed_keep_recent():
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            report_chat_micro_compaction_message_threshold=4,
            report_chat_micro_compaction_keep_recent=4,
        )
```

- [ ] **Step 2: Run tests and confirm the missing fields fail**

Run:

```bash
cd backend
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/report_chat_agent/test_micro_compaction_settings.py -q
```

Expected: FAIL because the five settings fields do not exist.

- [ ] **Step 3: Add settings fields and cross-field validation**

Import `model_validator` and add fields to `Settings`:

```python
from pydantic import Field, model_validator

report_chat_micro_compaction_enabled: bool = Field(
    default=True,
    description="是否启用 Report Chat 回答后的语义微压缩。",
)
report_chat_micro_compaction_token_threshold: int = Field(default=1200, gt=0)
report_chat_micro_compaction_message_threshold: int = Field(default=6, gt=0)
report_chat_micro_compaction_keep_recent: int = Field(default=4, gt=0)
report_chat_micro_compaction_target_tokens: int = Field(default=600, gt=0)

@model_validator(mode="after")
def validate_micro_compaction_window(self) -> "Settings":
    if (
        self.report_chat_micro_compaction_message_threshold
        <= self.report_chat_micro_compaction_keep_recent
    ):
        raise ValueError(
            "REPORT_CHAT_MICRO_COMPACTION_MESSAGE_THRESHOLD must exceed "
            "REPORT_CHAT_MICRO_COMPACTION_KEEP_RECENT"
        )
    return self
```

Add corresponding examples to `backend/.env.example`, and add these fields to `ReportChatState`:

```python
compaction_summary: dict[str, Any]
micro_compaction: dict[str, Any]
```

- [ ] **Step 4: Run settings tests**

Run the command from Step 2. Expected: 2 passed.

- [ ] **Step 5: Commit the configuration contract**

```bash
git add backend/app/config/settings.py backend/.env.example \
  backend/app/report_chat_agent/state.py \
  backend/tests/report_chat_agent/test_micro_compaction_settings.py
git commit -m "feat: configure report chat micro compaction"
```

---

### Task 2: Incremental Micro-Compaction Node

**Files:**
- Create: `backend/app/report_chat_agent/nodes/micro_compact_node.py`
- Create: `backend/app/report_chat_agent/prompts/micro_compaction.md`
- Create: `backend/tests/report_chat_agent/test_micro_compact_node.py`

**Interfaces:**
- Consumes: the five Settings fields from Task 1, `estimate_tokens(text: str) -> int`, `llm_client.chat(prompt_content: str | None, user_message: str, timeout_seconds: float | None = None) -> LlmResult`, and `content_moderator.moderate_output(text: str) -> ModerationResult`.
- Produces: `micro_compact_node(state: ReportChatState) -> ReportChatState`.
- Produces successful `compaction_summary` and most-recent `micro_compaction` dictionaries matching the design spec.

- [ ] **Step 1: Write failing skip and threshold tests**

Create tests that monkeypatch the module-level settings and LLM call:

```python
def test_below_threshold_skips_without_calling_llm(monkeypatch):
    monkeypatch.setattr(settings, "report_chat_micro_compaction_enabled", True)
    monkeypatch.setattr(settings, "report_chat_micro_compaction_token_threshold", 9999)
    monkeypatch.setattr(settings, "report_chat_micro_compaction_message_threshold", 6)
    monkeypatch.setattr(settings, "report_chat_micro_compaction_keep_recent", 4)
    monkeypatch.setattr(
        "app.report_chat_agent.nodes.micro_compact_node.llm_client.chat",
        lambda **_: pytest.fail("LLM must not be called"),
    )

    result = micro_compact_node({"chat_history": _messages(4), "errors": [], "llm_usages": []})

    assert result["chat_history"] == _messages(4)
    assert result["micro_compaction"]["status"] == "skipped"
    assert result["micro_compaction"]["reason"] == "below_threshold"


def test_message_threshold_compacts_old_messages_and_keeps_recent_four(monkeypatch):
    history = _messages(8)
    _configure_thresholds(monkeypatch, token_threshold=9999, message_threshold=6)
    _stub_success(monkeypatch, "用户已确认高风险项应优先整改。")

    result = micro_compact_node({"chat_history": history, "errors": [], "llm_usages": []})

    assert result["chat_history"] == history[-4:]
    assert result["compaction_summary"]["version"] == 1
    assert result["compaction_summary"]["covered_message_count"] == 4
    assert result["micro_compaction"]["status"] == "success"
```

Include helpers `_messages`, `_configure_thresholds`, and `_stub_success` in the test file, with `_stub_success` returning a complete `LlmResult`.

- [ ] **Step 2: Run focused tests and confirm import failure**

```bash
cd backend
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest \
  tests/report_chat_agent/test_micro_compact_node.py -q
```

Expected: collection FAIL because `micro_compact_node` does not exist.

- [ ] **Step 3: Add the prompt and minimal skip/compact implementation**

Create `prompts/micro_compaction.md` with an explicit contract:

```markdown
你负责压缩报告追问的较早对话。请将“上一版摘要”和“本次待压缩消息”合并成一份紧凑摘要。

必须保留：用户意图与约束、已确认结论、关键数值/时间/对象、证据引用、未解决问题和有效偏好。
可以删除：寒暄、重复内容、被后续结论覆盖的讨论、无关过程描述。
当前报告和新证据永远高于本摘要；不要新增原文中不存在的事实。
只输出摘要正文，不要输出代码块、标题说明或额外解释。目标不超过 {target_tokens} 个 Token。

上一版摘要：
{previous_summary}

本次待压缩消息：
{messages}
```

Implement helpers in `micro_compact_node.py`:

```python
def _serialize_messages(messages: list[dict[str, Any]]) -> str:
    return json.dumps(messages, ensure_ascii=False, separators=(",", ":"), default=str)


def _source_digest(previous_summary: str, messages: list[dict[str, Any]]) -> str:
    source = json.dumps(
        {"previous_summary": previous_summary, "messages": messages},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(source.encode("utf-8")).hexdigest()
```

The node must always construct a fresh `micro_compaction` result and must copy `errors`/`llm_usages` before appending so restored state is not mutated unexpectedly.

- [ ] **Step 4: Run focused tests and make them pass**

Run the Step 2 command. Expected: initial tests pass.

- [ ] **Step 5: Add failing incremental, safety, and rollback tests**

Add explicit tests for:

```python
def test_incremental_compaction_uses_previous_summary_and_increments_version(monkeypatch):
    history = _messages(8)
    captured = {}
    _configure_thresholds(monkeypatch, token_threshold=9999, message_threshold=6)

    def capture_chat(**kwargs):
        captured.update(kwargs)
        return _result("更新后的紧凑摘要")

    monkeypatch.setattr(
        "app.report_chat_agent.nodes.micro_compact_node.llm_client.chat",
        capture_chat,
    )
    result = micro_compact_node({
        "chat_history": history,
        "compaction_summary": {
            "version": 2,
            "summary": "旧摘要内容",
            "covered_message_count": 10,
        },
        "errors": [],
        "llm_usages": [],
    })

    assert "旧摘要内容" in captured["user_message"]
    assert result["compaction_summary"]["version"] == 3
    assert result["compaction_summary"]["covered_message_count"] == 14


def test_exception_preserves_summary_and_history(monkeypatch):
    history = _messages(8)
    old = {"version": 1, "summary": "原摘要", "covered_message_count": 2}
    _configure_thresholds(monkeypatch, token_threshold=9999, message_threshold=6)
    monkeypatch.setattr(
        "app.report_chat_agent.nodes.micro_compact_node.llm_client.chat",
        lambda **_: (_ for _ in ()).throw(RuntimeError("provider unavailable")),
    )

    result = micro_compact_node({
        "chat_history": history,
        "compaction_summary": old,
        "errors": [],
        "llm_usages": [],
    })

    assert result["chat_history"] == history
    assert result["compaction_summary"] == old
    assert result["micro_compaction"]["status"] == "failed"
    assert result["errors"][-1]["node"] == "micro_compact"


@pytest.mark.parametrize("summary", ["", "摘要" * 700])
def test_empty_or_over_target_summary_is_rejected(monkeypatch, summary):
    history = _messages(8, content="a")
    _configure_thresholds(monkeypatch, token_threshold=1, message_threshold=6)
    _stub_success(monkeypatch, summary)

    result = micro_compact_node({"chat_history": history, "errors": [], "llm_usages": []})

    assert result["chat_history"] == history
    assert result["micro_compaction"]["status"] == "failed"


def test_summary_without_token_gain_is_rejected(monkeypatch):
    history = _messages(8, content="")
    _configure_thresholds(monkeypatch, token_threshold=1, message_threshold=6)
    _stub_success(monkeypatch, "摘要" * 50)

    result = micro_compact_node({"chat_history": history, "errors": [], "llm_usages": []})

    assert result["chat_history"] == history
    assert result["micro_compaction"]["status"] == "failed"


def test_blocked_output_preserves_history(monkeypatch):
    history = _messages(8)
    _configure_thresholds(monkeypatch, token_threshold=9999, message_threshold=6)
    _stub_success(monkeypatch, "待审核摘要")
    monkeypatch.setattr(
        "app.report_chat_agent.nodes.micro_compact_node.content_moderator.moderate_output",
        lambda _text: SimpleNamespace(action=ModerationAction.BLOCK, masked_text=None),
    )
    result = micro_compact_node({"chat_history": history, "errors": [], "llm_usages": []})
    assert result["chat_history"] == history
    assert result["micro_compaction"]["status"] == "failed"


def test_masked_output_uses_safe_masked_summary(monkeypatch):
    _configure_thresholds(monkeypatch, token_threshold=9999, message_threshold=6)
    _stub_success(monkeypatch, "原始摘要")
    monkeypatch.setattr(
        "app.report_chat_agent.nodes.micro_compact_node.content_moderator.moderate_output",
        lambda _text: SimpleNamespace(action=ModerationAction.MASK, masked_text="脱敏摘要"),
    )
    result = micro_compact_node({"chat_history": _messages(8), "errors": [], "llm_usages": []})
    assert result["compaction_summary"]["summary"] == "脱敏摘要"


def test_disabled_setting_skips_with_disabled_reason(monkeypatch):
    monkeypatch.setattr(settings, "report_chat_micro_compaction_enabled", False)
    result = micro_compact_node({"chat_history": _messages(8), "errors": [], "llm_usages": []})
    assert result["micro_compaction"]["status"] == "skipped"
    assert result["micro_compaction"]["reason"] == "disabled"


def test_source_digest_is_stable_for_same_normalized_input():
    messages = _messages(2)
    assert _source_digest("摘要", messages) == _source_digest("摘要", messages)
```

Also assert that every real model call appends an `llm_usages` record with `action_type == "report_chat_micro_compaction"`, including failed model results.

- [ ] **Step 6: Complete validation and non-blocking error handling**

Implement the success gate exactly:

```python
safe_summary = (moderation.masked_text or raw_summary).strip()
tokens_after = estimate_tokens(safe_summary)
valid = (
    bool(safe_summary)
    and moderation.action != ModerationAction.BLOCK
    and tokens_after <= settings.report_chat_micro_compaction_target_tokens
    and tokens_after < tokens_before
)
```

On success, set `version`, cumulative `covered_message_count`, `source_digest`, token metrics, and `updated_at=now_local().isoformat()`. On any failure, append `{ "node": "micro_compact", "message": failure_message }`, record latency and reason, and return the unchanged old summary/history.

- [ ] **Step 7: Run node tests**

Run the Step 2 command. Expected: all tests pass.

- [ ] **Step 8: Commit the node**

```bash
git add backend/app/report_chat_agent/nodes/micro_compact_node.py \
  backend/app/report_chat_agent/prompts/micro_compaction.md \
  backend/tests/report_chat_agent/test_micro_compact_node.py
git commit -m "feat: add incremental report chat compaction"
```

---

### Task 3: Feed the Summary into the Answer Budget and Prompts

**Files:**
- Modify: `backend/app/report_chat_agent/context_budget.py`
- Modify: `backend/app/report_chat_agent/nodes/generate_report_answer_node.py`
- Modify: `backend/app/report_chat_agent/prompts/report_answer.md`
- Modify: `backend/app/report_chat_agent/prompts/rag_answer.md`
- Modify: `backend/tests/report_chat_agent/test_context_budget.py`
- Modify: `backend/tests/report_chat_agent/test_generate_answer_with_rag.py`

**Interfaces:**
- Consumes: `state["compaction_summary"]["summary"]` from Task 2.
- Changes: `build_context_budget(*, user_question: str, report_context: Any, evidence: Any, retrieved_context: Any, merged_context: Any, compaction_summary: Any, memory_context: Any, rag_results: Any, chat_history: Any, input_budget: int) -> dict[str, Any]`.
- Produces: `context_budget["compaction_summary"]` with a 600-token section cap and an observable context name.

- [ ] **Step 1: Write failing context-budget test**

Update every existing `build_context_budget` call to pass `compaction_summary`, then add:

```python
def test_context_budget_includes_compaction_before_memory_and_history():
    result = build_context_budget(
        user_question="继续说明整改顺序",
        report_context={"summary": "当前报告"},
        evidence=[],
        retrieved_context=[],
        merged_context=[],
        compaction_summary="用户此前确认优先整改高风险项",
        memory_context=[],
        rag_results=[],
        chat_history=[],
        input_budget=1000,
    )

    assert result["compaction_summary"]
    assert result["contexts"].index("compaction_summary") < result["contexts"].index("memory_context")
    assert result["contexts"].index("compaction_summary") < result["contexts"].index("chat_history")
```

- [ ] **Step 2: Run the budget tests and confirm signature failure**

```bash
cd backend
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest \
  tests/report_chat_agent/test_context_budget.py -q
```

Expected: FAIL because `compaction_summary` is not accepted or returned.

- [ ] **Step 3: Add the separately budgeted summary section**

Add the argument and section in `build_context_budget`:

```python
("merged_context", merged_context, 1000),
("compaction_summary", compaction_summary, 600),
("memory_context", memory_context, 500),
```

Keep current report/evidence ordering unchanged.

- [ ] **Step 4: Add failing answer-prompt integration tests**

Extend `_base_state` in `test_generate_answer_with_rag.py` with a `compaction_summary` argument, capture `user_message`, and assert both report and RAG templates include the summary text while current report content remains present.

- [ ] **Step 5: Wire state into answer generation and both prompt templates**

In `generate_report_answer_node`:

```python
compaction_summary = state.get("compaction_summary", {}).get("summary", "")
```

Pass it to `build_context_budget` and `template.format`. Add this section to both templates before recent history:

```markdown
## 较早会话的微压缩摘要
以下内容仅用于保持对话连续性；如与当前报告或证据冲突，以当前报告和证据为准。
{compaction_summary}
```

- [ ] **Step 6: Run budget and answer tests**

```bash
cd backend
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest \
  tests/report_chat_agent/test_context_budget.py \
  tests/report_chat_agent/test_generate_answer_with_rag.py -q
```

Expected: all tests pass.

- [ ] **Step 7: Commit answer-context integration**

```bash
git add backend/app/report_chat_agent/context_budget.py \
  backend/app/report_chat_agent/nodes/generate_report_answer_node.py \
  backend/app/report_chat_agent/prompts/report_answer.md \
  backend/app/report_chat_agent/prompts/rag_answer.md \
  backend/tests/report_chat_agent/test_context_budget.py \
  backend/tests/report_chat_agent/test_generate_answer_with_rag.py
git commit -m "feat: include compacted history in report answers"
```

---

### Task 4: Graph Ordering, Checkpoint Restoration, and Usage Persistence

**Files:**
- Modify: `backend/app/report_chat_agent/graph.py`
- Modify: `backend/tests/report_chat_agent/test_langgraph_persistence.py`
- Modify: `backend/tests/report_chat_agent/test_report_chat_stream.py`

**Interfaces:**
- Consumes: `micro_compact_node(state)` from Task 2.
- Produces Graph edge: `save_chat_memory -> micro_compact -> END`.
- Preserves existing sync and async `save_report_chat_usage` handling; compaction usage is appended to the same `llm_usages` list.

- [ ] **Step 1: Write failing graph structure assertions**

In `test_langgraph_persistence.py`, inspect the compiled graph and assert:

```python
graph_view = build_report_chat_graph(checkpointer=InMemorySaver(), store=InMemoryStore()).get_graph()
edges = {(edge.source, edge.target) for edge in graph_view.edges}

assert ("save_chat_memory", "micro_compact") in edges
assert ("micro_compact", "__end__") in edges
assert ("save_chat_memory", "__end__") not in edges
```

- [ ] **Step 2: Run the graph test and confirm failure**

```bash
cd backend
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest \
  tests/report_chat_agent/test_langgraph_persistence.py -q
```

Expected: FAIL because `micro_compact` is absent.

- [ ] **Step 3: Register the node and metadata**

Import `micro_compact_node`, add metadata and the node tuple:

```python
"micro_compact": {
    "name": "微压缩对话历史",
    "message_started": "正在检查对话上下文",
    "message_completed": "对话上下文检查完成",
},
```

Replace the final edge with:

```python
graph.add_edge("persist_chat_message", "save_chat_memory")
graph.add_edge("save_chat_memory", "micro_compact")
graph.add_edge("micro_compact", END)
```

- [ ] **Step 4: Add checkpoint restoration test**

Build a focused two-node graph using the production memory and compaction nodes, invoke the same `thread_id` four times, and inspect the saved state:

```python
from langgraph.graph import END, START, StateGraph

from app.report_chat_agent.memory import save_chat_memory_node
from app.report_chat_agent.nodes.micro_compact_node import micro_compact_node
from app.report_chat_agent.state import ReportChatState


def test_checkpointer_restores_compacted_summary_and_recent_messages(monkeypatch):
    _configure_compaction_for_test(monkeypatch)
    monkeypatch.setattr(
        "app.report_chat_agent.nodes.micro_compact_node.llm_client.chat",
        lambda **_: _compaction_result("历史结论：持续关注高风险项。"),
    )
    builder = StateGraph(ReportChatState)
    builder.add_node("save_chat_memory", save_chat_memory_node)
    builder.add_node("micro_compact", micro_compact_node)
    builder.add_edge(START, "save_chat_memory")
    builder.add_edge("save_chat_memory", "micro_compact")
    builder.add_edge("micro_compact", END)
    graph = builder.compile(checkpointer=InMemorySaver())
    config = {"configurable": {"thread_id": "micro-compaction-test"}}

    for turn in range(4):
        graph.invoke(
            {
                "user_question": f"问题 {turn}",
                "final_answer": f"回答 {turn}",
                "errors": [],
                "llm_usages": [],
            },
            config=config,
        )

    state = graph.get_state(config).values
assert state["compaction_summary"]["version"] >= 1
assert len(state["chat_history"]) == 4
assert state["compaction_summary"]["covered_message_count"] >= 2
```

Keep the existing `test_persist_chat_message_saves_user_and_assistant_messages` assertion unchanged as the MySQL audit regression. Do not add a compaction column or delete rows.

- [ ] **Step 5: Extend stream regression coverage**

In `test_report_chat_stream.py`, add a capture around the existing service boundary:

```python
captured_usages = []
monkeypatch.setattr(
    "app.report_chat_agent.stream_service.save_report_chat_usage",
    lambda state: captured_usages.extend(state.get("llm_usages", [])),
)
```

Make the fake final `values` state include a usage record whose `action_type` is `report_chat_micro_compaction`, then assert:

```python
assert [event["event_type"] for event in events][-2:] == ["message_completed", "stream_closed"]
assert events[-2]["answer"] == "第一段回答"
assert captured_usages[-1]["action_type"] == "report_chat_micro_compaction"
```

- [ ] **Step 6: Run persistence and stream tests**

```bash
cd backend
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest \
  tests/report_chat_agent/test_langgraph_persistence.py \
  tests/report_chat_agent/test_report_chat_stream.py \
  tests/report_chat_agent/test_report_chat_nodes.py -q
```

Expected: all tests pass and original MySQL message tests remain unchanged.

- [ ] **Step 7: Commit Graph integration**

```bash
git add backend/app/report_chat_agent/graph.py \
  backend/tests/report_chat_agent/test_langgraph_persistence.py \
  backend/tests/report_chat_agent/test_report_chat_stream.py
git commit -m "feat: run report compaction after each answer"
```

---

### Task 5: Regression Verification and Documentation Alignment

**Files:**
- Modify only if test evidence exposes a defect: files already listed in Tasks 1–4.
- Verify: `docs/superpowers/specs/2026-08-17-report-chat-micro-compaction-design.md`
- Verify: `docs/superpowers/plans/2026-08-17-report-chat-micro-compaction.md`

**Interfaces:**
- Verifies the complete Report Chat behavior from configuration through Graph state, answer prompt, MySQL persistence, SSE completion, and usage accounting.
- Produces no new public API or database schema.

- [ ] **Step 1: Run all Report Chat tests**

```bash
cd backend
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/report_chat_agent -q
```

Expected: all Report Chat tests pass.

- [ ] **Step 2: Run configuration, security, and Runtime regressions**

```bash
cd backend
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest \
  tests/security \
  tests/runtime \
  tests/test_api.py -q
```

Expected: all selected regression tests pass; generic Runtime behavior remains unchanged.

- [ ] **Step 3: Run static diff and repository checks**

```bash
git diff --check
git status --short
git diff -- frontend/src/pages/error-code/IndexPage.vue
```

Expected: no whitespace errors; the pre-existing frontend change is still present and contains no implementation edits from this feature.

- [ ] **Step 4: Confirm spec coverage in the implementation**

Use `rg` to verify exact integration points:

```bash
rg -n "micro_compact|compaction_summary|report_chat_micro_compaction" \
  backend/app backend/tests/report_chat_agent backend/.env.example
```

Expected: matches exist for settings, state, node, Graph edge, budget, both prompts, tests, and usage action type. There must be no changes under `backend/app/runtime`.

- [ ] **Step 5: Commit any test-driven corrections**

If Steps 1–4 required corrections, stage only the affected feature files and commit:

```bash
git commit -m "test: verify report chat micro compaction"
```

If no correction was necessary, do not create an empty commit.
