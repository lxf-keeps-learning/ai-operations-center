# 生产报告 Supervisor 多 Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将生产报告 Graph 改造为公共流程加业务域 Supervisor/Agent 路由，同时保持现有 API、SSE、持久化和 `OperationState` 兼容。

**Architecture:** 在 `operation_agent/multi_agent` 下新增业务域 Agent 定义和 Supervisor Graph。Supervisor Graph 统一执行上下文初始化、数据查询、异常检测和报告汇总，并将中间状态交给按 `domain` 选择的业务 Agent 子图。现有 `operation_graph` 导出改为指向新的 Supervisor Graph，服务层无需改调用方式。

**Tech Stack:** Python 3.11+, LangGraph 1.2+, TypedDict, pytest, FastAPI SSE。

## Global Constraints

- 保持 `OperationState` 为 Graph 与 Agent 之间唯一 JSON 可序列化数据契约。
- 保持 `safety`、`maintenance`、`business`、`capability`、`all` 五种业务域兼容。
- 缺失或非法业务域按现有默认行为路由到 `safety`，并记录 Supervisor 错误。
- 公共初始化、查询、异常检测和汇总节点每次报告只执行一次。
- 不修改报告问答 `report_chat_agent` 的图、数据库表或请求响应 DTO。
- 所有新行为先写失败测试，再写最小实现；测试命令从 `backend/` 目录执行。

---

### Task 1: 定义业务 Agent 契约和 Supervisor 路由规则

**Files:**
- Create: `backend/app/operation_agent/multi_agent/__init__.py`
- Create: `backend/app/operation_agent/multi_agent/agents.py`
- Create: `backend/app/operation_agent/multi_agent/supervisor.py`
- Modify: `backend/app/operation_agent/state.py:OperationState`
- Test: `backend/tests/operation_agent/test_supervisor_routing.py`

**Interfaces:**
- `DomainAgentSpec`: 不可变配置对象，字段为 `key`、`label`、`reason_prompt`、`advice_prompt`、`reason_action_type`、`advice_action_type`。
- `DOMAIN_AGENT_SPECS: dict[str, DomainAgentSpec]`: 包含 `safety`、`maintenance`、`business`、`capability`、`all`。
- `normalize_domain(state: OperationState) -> str`：返回有效业务域；非法值返回 `safety` 并追加 Supervisor 错误。
- `route_domain_agent(state: OperationState) -> str`：返回 Agent key，并写入 `supervisor_route` 和 `active_agent`。

- [ ] **Step 1: Write the failing test**

```python
from app.operation_agent.multi_agent.supervisor import normalize_domain, route_domain_agent


def test_route_domain_agent_maps_each_business_domain():
    for domain in ("safety", "maintenance", "business", "capability", "all"):
        state = {"domain": domain, "errors": []}
        assert route_domain_agent(state) == domain
        assert state["supervisor_route"] == domain


def test_invalid_domain_falls_back_to_safety_and_records_error():
    state = {"domain": "unknown", "errors": []}
    assert normalize_domain(state) == "safety"
    assert state["errors"][0]["node"] == "supervisor"
    assert route_domain_agent(state) == "safety"
    assert state["supervisor_route"] == "safety"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/operation_agent/test_supervisor_routing.py -q`

Expected: FAIL because the new package and routing functions do not exist.

- [ ] **Step 3: Write minimal implementation**

Add the package and five explicit `DomainAgentSpec` entries. `normalize_domain` reads `state["domain"]`, then `page_context.domain`, then `safety`; initializes `errors` with `setdefault`, preserves existing errors, and writes the normalized domain back. Add `supervisor_route: NotRequired[str]`, `active_agent: NotRequired[str]`, and `agent_events: NotRequired[list[dict[str, Any]]]` to `OperationState`.

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/operation_agent/test_supervisor_routing.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/operation_agent/multi_agent backend/app/operation_agent/state.py backend/tests/operation_agent/test_supervisor_routing.py
git commit -m "feat: add operation domain agent routing contract"
```

### Task 2: 提取可配置的业务 Agent 原因分析与建议流程

**Files:**
- Modify: `backend/app/operation_agent/nodes/analyze_reason_node.py`
- Modify: `backend/app/operation_agent/nodes/generate_advice_node.py`
- Create: `backend/app/operation_agent/multi_agent/agent_graph.py`
- Create: `backend/app/operation_agent/prompts/domains/{safety,maintenance,business,capability,all}_{analysis,advice}.md`
- Test: `backend/tests/operation_agent/test_domain_agents.py`

**Interfaces:**
- `build_domain_agent_graph(spec: DomainAgentSpec) -> CompiledStateGraph`：返回 `<agent_key>_reason` → `<agent_key>_advice` 的子图。
- `run_domain_agent(state: OperationState, spec: DomainAgentSpec) -> OperationState`。
- `analyze_reason_node(state, *, prompt_name="operation_analysis.md", action_type="analyze_reason") -> OperationState`。
- `generate_advice_node(state, *, prompt_name="operation_advice.md", action_type="generate_advice") -> OperationState`。

- [ ] **Step 1: Write the failing test**

```python
from app.operation_agent.multi_agent.agent_graph import run_domain_agent
from app.operation_agent.multi_agent.agents import DOMAIN_AGENT_SPECS


def test_domain_agent_uses_domain_prompts_and_preserves_result_fields(monkeypatch):
    calls = []

    def fake_reason(state, **kwargs):
        calls.append(("reason", kwargs["prompt_name"]))
        state["reason_analysis"] = "设备分析结果"
        return state

    def fake_advice(state, **kwargs):
        calls.append(("advice", kwargs["prompt_name"]))
        state["advice_items"] = [{"title": "建立维修闭环"}]
        return state

    monkeypatch.setattr("app.operation_agent.multi_agent.agent_graph.analyze_reason_node", fake_reason)
    monkeypatch.setattr("app.operation_agent.multi_agent.agent_graph.generate_advice_node", fake_advice)
    state = {"domain": "maintenance", "metrics": [], "abnormal_items": [], "evidence": [], "errors": []}
    result = run_domain_agent(state, DOMAIN_AGENT_SPECS["maintenance"])

    assert result["reason_analysis"] == "设备分析结果"
    assert result["advice_items"][0]["title"] == "建立维修闭环"
    assert calls == [("reason", "domains/maintenance_analysis.md"), ("advice", "domains/maintenance_advice.md")]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/operation_agent/test_domain_agents.py -q`

Expected: FAIL because configurable prompt parameters and `run_domain_agent` do not exist.

- [ ] **Step 3: Write minimal implementation**

Make prompt loading and usage labeling optional in the two existing nodes. Keep current formatting, LLM fallback, moderation, error shape, and output normalization unchanged. Add one prompt pair per domain under `prompts/domains/`, retaining the existing evidence-only constraints. Build and cache one two-node `StateGraph(OperationState)` per spec; wrappers pass the spec prompt and action type to the existing nodes.

- [ ] **Step 4: Run focused tests**

Run: `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/operation_agent/test_domain_agents.py tests/operation_agent/test_operation_graph.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/operation_agent/nodes/analyze_reason_node.py backend/app/operation_agent/nodes/generate_advice_node.py backend/app/operation_agent/multi_agent/agent_graph.py backend/app/operation_agent/prompts/domains backend/tests/operation_agent/test_domain_agents.py
git commit -m "feat: add domain-specific operation agents"
```

### Task 3: 构建 Supervisor Graph 并替换兼容入口

**Files:**
- Create: `backend/app/operation_agent/multi_agent/graph.py`
- Modify: `backend/app/operation_agent/graph.py`
- Modify: `backend/app/operation_agent/nodes/init_context_node.py`
- Test: `backend/tests/operation_agent/test_supervisor_graph.py`

**Interfaces:**
- `build_supervisor_graph() -> CompiledStateGraph`。
- `supervisor_graph`：进程级编译实例。
- `operation_graph`：兼容导出，指向 `supervisor_graph`。
- `NODE_METADATA` / `OPERATION_NODE_SPECS`：包含 Supervisor、公共节点和业务 Agent 节点元数据。

- [ ] **Step 1: Write the failing test**

```python
def test_supervisor_runs_common_steps_once_and_routes_business_agent(monkeypatch):
    calls = []
    for name in ("init_context_node", "query_operation_data_node", "detect_abnormal_node", "summary_node"):
        monkeypatch.setattr(
            f"app.operation_agent.multi_agent.graph.{name}",
            lambda state, _name=name: (calls.append(_name), state)[1],
        )
    monkeypatch.setattr(
        "app.operation_agent.multi_agent.graph.run_domain_agent",
        lambda state, spec: (calls.append(f"agent:{spec.key}"), state)[1],
    )
    result = build_supervisor_graph().invoke({"domain": "business", "errors": []})
    assert calls.count("init_context_node") == 1
    assert calls.count("query_operation_data_node") == 1
    assert calls.count("detect_abnormal_node") == 1
    assert calls.count("summary_node") == 1
    assert calls.count("agent:business") == 1
    assert result["supervisor_route"] == "business"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/operation_agent/test_supervisor_graph.py -q`

Expected: FAIL because the Supervisor Graph does not exist.

- [ ] **Step 3: Write minimal implementation**

Build this exact parent edge sequence: `START → supervisor_route → init_context → query_operation_data → detect_abnormal → dispatch_domain_agent → summary → END`. The dispatch node calls `route_domain_agent`, selects `DOMAIN_AGENT_SPECS[state["supervisor_route"]]`, and calls `run_domain_agent`. Wrap parent nodes with the existing custom `node_started` writer. Add metadata for Supervisor and Agent nodes while retaining the original six node keys. Initialize new state containers in `init_context_node` without clearing an already selected route or existing errors. Re-export the Supervisor graph from the old `graph.py`, and keep `build_operation_graph()` as a compatibility function.

- [ ] **Step 4: Run focused tests**

Run: `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/operation_agent/test_supervisor_graph.py tests/operation_agent/test_operation_graph.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/operation_agent/multi_agent/graph.py backend/app/operation_agent/graph.py backend/app/operation_agent/nodes/init_context_node.py backend/tests/operation_agent/test_supervisor_graph.py
git commit -m "feat: route operation reports through supervisor graph"
```

### Task 4: 更新 SSE 事件、进度和可观测性元数据

**Files:**
- Modify: `backend/app/analysis_stream/schemas.py`
- Modify: `backend/app/analysis_stream/langgraph_event_adapter.py`
- Modify: `backend/app/operation_agent/stream_service.py`
- Modify: `backend/app/operation_agent/service.py`
- Modify: `backend/tests/analysis_stream/test_langgraph_event_adapter.py`
- Create: `backend/tests/operation_agent/test_supervisor_stream_metadata.py`

**Interfaces:**
- `AnalysisStreamEvent.agent_key: NotRequired[str]`。
- `LangGraphEventAdapter` 继续忽略未知事件，并把 custom/state 中的 `agent_key` 作为事件 payload 的可选字段。
- 同步和流式 LangSmith metadata 保留既有键，并在路由可确定时增加 `agent_key`。

- [ ] **Step 1: Write the failing test**

```python
def test_adapter_exposes_agent_key_on_node_started():
    emitter = _make_emitter()
    adapter = LangGraphEventAdapter(emitter, NODE_METADATA, NODE_ORDER)
    events = adapter.process("custom", {
        "kind": "node_started",
        "node_key": "maintenance_agent",
        "agent_key": "maintenance",
    })
    assert events[0]["node_key"] == "maintenance_agent"
    assert events[0]["payload"]["agent_key"] == "maintenance"
```

Add a stream-service test that replaces the graph and `build_langsmith_config`, executes a `maintenance` request, and asserts the captured metadata retains `domain` and `trigger_type` while including `agent_key`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/analysis_stream/test_langgraph_event_adapter.py tests/operation_agent/test_supervisor_stream_metadata.py -q`

Expected: FAIL because Agent metadata is not represented or propagated.

- [ ] **Step 3: Write minimal implementation**

Add `agent_key` to the TypedDict. Extend adapter handling without changing old event JSON: custom `node_started` events may carry `agent_key`, and completed events may derive it from the state update. Include the route in `report_completed.payload`. Add `agent_key` to sync and stream LangSmith metadata without changing persistence columns or existing Chinese messages.

- [ ] **Step 4: Run focused tests**

Run: `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/analysis_stream/test_langgraph_event_adapter.py tests/operation_agent/test_supervisor_stream_metadata.py tests/operation_agent/test_operation_graph.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/analysis_stream/schemas.py backend/app/analysis_stream/langgraph_event_adapter.py backend/app/operation_agent/stream_service.py backend/app/operation_agent/service.py backend/tests/analysis_stream/test_langgraph_event_adapter.py backend/tests/operation_agent/test_supervisor_stream_metadata.py
git commit -m "feat: expose operation agent routing in stream metadata"
```

### Task 5: 全量回归、契约检查和交付前验证

**Files:**
- Modify: `backend/tests/operation_agent/test_operation_graph.py` only when an additive routing assertion is required.
- Modify: `backend/tests/analysis_stream/test_analysis_stream_api.py` only when an exact event assertion must accept additive Agent metadata.

**Interfaces:**
- No new production interface. This task verifies the complete graph, stream, persistence, API, and report-chat boundary.

- [ ] **Step 1: Run focused graph and stream suites**

Run:

```bash
cd backend
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/operation_agent -q
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/analysis_stream -q
```

Expected: exit code 0 with no failed tests.

- [ ] **Step 2: Run the complete backend suite**

Run: `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q`

Expected: exit code 0; no failures in report chat, tools, runtime, security, or observability suites.

- [ ] **Step 3: Run static and import verification**

Run:

```bash
.venv/bin/python -m compileall app/operation_agent app/analysis_stream
git diff --check
```

Expected: compileall completes without syntax errors and `git diff --check` reports no whitespace errors.

- [ ] **Step 4: Verify the requirements checklist**

Confirm from tests and diff that all five domains route deterministically, common nodes execute once, Agent failures retain report generation, existing API/SSE/persistence contracts remain compatible, and no unrelated dirty files were staged.

- [ ] **Step 5: Commit test-only compatibility adjustments if needed**

```bash
git add backend/tests/operation_agent backend/tests/analysis_stream
git commit -m "test: verify supervisor operation report compatibility"
```

Only create this final commit if Task 5 required test-only compatibility assertions.
