# LangSmith Prompt Test Tracing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make one synthetic Prompt Center test visible in LangSmith Prompts and Tracing with a parent `ioc_prompt_test_run`, an LLM child run, masked content, and local Prompt/version/test-run correlation.

**Architecture:** Keep explicit LangSmith callbacks and IOC local audit data. A focused `RunnableLambda` creates the Prompt-test parent boundary, passes its child callback context into `LlmClient.chat()`, and records stable Prompt/version facts as metadata; Prompt sync remains an independent, retryable mirror of the IOC database.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy, LangChain Core `RunnableLambda`, LangChain OpenAI, LangSmith SDK 0.9.8, pytest.

## Global Constraints

- Keep `LANGSMITH_MASK_INPUTS_OUTPUTS=true`.
- Do not enable global implicit tracing.
- Do not upload real IOC business data; remote acceptance uses one existing synthetic test case.
- IOC database remains the source of truth; LangSmith failures must not invalidate a successful local model call.
- Do not change evaluator semantics or connect `ioc.safety.analysis` to a production Graph.
- Run automated tests with `LANGSMITH_TRACING=false`.
- Preserve the existing uncommitted shared business-content builder fix and its regression test.

---

## File Structure

- Modify `backend/app/observability/langsmith_tracing.py`: accept optional extra tags while preserving existing callers.
- Modify `backend/app/runtime/llm/client.py`: accept an optional `RunnableConfig` and forward it to the model.
- Create `backend/app/modules/prompt_center/application/prompt_test_tracing.py`: own the parent Runnable boundary and trace configuration.
- Modify `backend/app/modules/prompt_center/application/prompt_test_service.py`: create/persist the trace ID and Prompt metadata, then call the tracing executor.
- Modify `backend/tests/observability/test_langsmith_tracing.py`: protect extra-tag behavior.
- Create `backend/tests/runtime/llm/test_llm_client_config.py`: protect config propagation into the chat model.
- Create `backend/tests/modules/prompt_center/test_prompt_test_tracing.py`: protect parent-to-child callback propagation.
- Modify `backend/tests/modules/prompt_center/test_prompt_test_service.py`: protect local trace persistence and Prompt metadata.

### Task 1: Extend the shared tracing and LLM boundaries

**Files:**
- Modify: `backend/app/observability/langsmith_tracing.py`
- Modify: `backend/app/runtime/llm/client.py`
- Modify: `backend/tests/observability/test_langsmith_tracing.py`
- Create: `backend/tests/runtime/llm/test_llm_client_config.py`

**Interfaces:**
- Produces: `build_langsmith_config(*, trace_id: str, graph_name: str, user_id: str | None = None, session_id: str | None = None, conversation_id: str | None = None, metadata: dict[str, Any] | None = None, extra_tags: list[str] | None = None) -> RunnableConfig`
- Produces: `LlmClient.chat(prompt_content: str | None, user_message: str, history: list[dict[str, str]] | None = None, timeout_seconds: float | None = None, provider_name: str | None = None, config: RunnableConfig | None = None) -> LlmResult`

- [ ] **Step 1: Write failing tests for extra tags and model config propagation**

Append the following behavior test to `test_langsmith_tracing.py`:

```python
def test_build_config_appends_unique_extra_tags(monkeypatch) -> None:
    monkeypatch.setattr(settings, "langsmith_tracing", False)
    langsmith_tracing._get_client.cache_clear()

    config = langsmith_tracing.build_langsmith_config(
        trace_id="trace_prompt_001",
        graph_name="ioc_prompt_test_run",
        extra_tags=["prompt-center", "prompt-test", "prompt-test"],
    )

    assert config["tags"] == [
        "ioc",
        settings.app_env,
        "ioc_prompt_test_run",
        "prompt-center",
        "prompt-test",
    ]
```

Create `test_llm_client_config.py` with a real `LlmClient` instance stripped only of external initialization and a fake model at the network boundary:

```python
from types import SimpleNamespace

from langchain_core.messages import AIMessage

from app.runtime.llm import client as client_module
from app.runtime.llm.client import LlmClient


def test_chat_forwards_runnable_config_to_model(monkeypatch) -> None:
    captured = {}

    class FakeModel:
        def invoke(self, messages, *, config=None, timeout=None):
            captured["config"] = config
            return AIMessage(
                content="synthetic answer",
                response_metadata={"model_name": "synthetic-model"},
                usage_metadata={
                    "input_tokens": 10,
                    "output_tokens": 4,
                    "total_tokens": 14,
                },
            )

    provider = SimpleNamespace(
        provider="deepseek",
        model="synthetic-model",
        display_name="Synthetic",
    )
    monkeypatch.setattr(client_module.llm_settings, "get_provider", lambda _name: provider)

    client = LlmClient.__new__(LlmClient)
    client._default_provider = "deepseek"
    client._models = {"deepseek": FakeModel()}
    config = {"run_name": "ioc_prompt_test_run", "metadata": {"prompt_key": "ioc.safety.analysis"}}

    result = client.chat("system", "question", config=config)

    assert result.success is True
    assert captured["config"] is config
```

- [ ] **Step 2: Run the two tests and verify RED**

Run:

```bash
cd backend
LANGSMITH_TRACING=false .venv/bin/python -m pytest \
  tests/observability/test_langsmith_tracing.py::test_build_config_appends_unique_extra_tags \
  tests/runtime/llm/test_llm_client_config.py::test_chat_forwards_runnable_config_to_model -q
```

Expected: both tests fail because `extra_tags` and `config` are not accepted.

- [ ] **Step 3: Add the minimal production parameters**

In `build_langsmith_config()`, add the `extra_tags` parameter shown below. Keep the
existing `trace_metadata` construction and sanitization, then replace the current
`config` construction with the shown `trace_tags` and `config` blocks:

```python
def build_langsmith_config(
    *,
    trace_id: str,
    graph_name: str,
    user_id: str | None = None,
    session_id: str | None = None,
    conversation_id: str | None = None,
    metadata: dict[str, Any] | None = None,
    extra_tags: list[str] | None = None,
) -> RunnableConfig:
    trace_tags = list(
        dict.fromkeys([
            "ioc",
            settings.app_env,
            graph_name,
            *(extra_tags or []),
        ])
    )
    config: RunnableConfig = {
        "run_name": graph_name,
        "tags": trace_tags,
        "metadata": trace_metadata,
    }
```

In `LlmClient.chat()`, import `RunnableConfig`, add `config`, and forward it:

```python
def chat(
    self,
    prompt_content: str | None,
    user_message: str,
    history: list[dict[str, str]] | None = None,
    timeout_seconds: float | None = None,
    provider_name: str | None = None,
    config: RunnableConfig | None = None,
) -> LlmResult:
    response: AIMessage = model.invoke(
        messages,
        config=config,
        timeout=timeout_seconds or 60,
    )
```

- [ ] **Step 4: Run targeted tests and verify GREEN**

Run the command from Step 2. Expected: `2 passed`.

- [ ] **Step 5: Commit the boundary change**

```bash
git add backend/app/observability/langsmith_tracing.py \
  backend/app/runtime/llm/client.py \
  backend/tests/observability/test_langsmith_tracing.py \
  backend/tests/runtime/llm/test_llm_client_config.py
git commit -m "feat: support prompt test trace propagation"
```

### Task 2: Add the Prompt-test parent Runnable

**Files:**
- Create: `backend/app/modules/prompt_center/application/prompt_test_tracing.py`
- Create: `backend/tests/modules/prompt_center/test_prompt_test_tracing.py`

**Interfaces:**
- Consumes: `LlmClient.chat(prompt_content: str | None, user_message: str, history: list[dict[str, str]] | None = None, timeout_seconds: float | None = None, provider_name: str | None = None, config: RunnableConfig | None = None) -> LlmResult`
- Consumes: `build_langsmith_config(*, trace_id: str, graph_name: str, user_id: str | None = None, session_id: str | None = None, conversation_id: str | None = None, metadata: dict[str, Any] | None = None, extra_tags: list[str] | None = None) -> RunnableConfig`
- Produces: `run_traced_prompt_test(invocation: PromptTestInvocation, *, trace_id: str, operator_id: str | None, metadata: dict[str, Any], tags: list[str]) -> LlmResult`

- [ ] **Step 1: Write a failing parent-to-child propagation test**

Create a test that patches only the external LLM call. Capture the config received by the call and assert that Runnable supplied a child callback manager with a parent run ID:

```python
from app.modules.prompt_center.application import prompt_test_tracing
from app.runtime.llm.client import LlmResult


def test_prompt_test_runnable_passes_child_trace_context(monkeypatch) -> None:
    captured = {}

    def fake_chat(*, config=None, **_kwargs):
        captured["config"] = config
        return LlmResult(
            content="synthetic",
            model="synthetic-model",
            prompt_tokens=3,
            completion_tokens=2,
            total_tokens=5,
            cost_ms=1,
            success=True,
            system_prompt="system",
        )

    monkeypatch.setattr(prompt_test_tracing.llm_client, "chat", fake_chat)
    monkeypatch.setattr(
        prompt_test_tracing,
        "build_langsmith_config",
        lambda **_kwargs: {"run_name": "ioc_prompt_test_run"},
    )

    result = prompt_test_tracing.run_traced_prompt_test(
        prompt_test_tracing.PromptTestInvocation(
            system_content="system",
            user_message="synthetic question",
            provider_name="deepseek",
        ),
        trace_id="prompt_test_9_abc",
        operator_id=None,
        metadata={"prompt_key": "ioc.safety.analysis"},
        tags=["prompt-center", "prompt-test"],
    )

    assert result.content == "synthetic"
    assert captured["config"]["callbacks"].parent_run_id is not None
```

- [ ] **Step 2: Write a failing model-error trace test**

Add a second test using LangChain's in-memory run collector. It verifies that an
unsuccessful `LlmResult` becomes a parent Run error instead of a misleading
successful chain:

```python
import pytest
from langchain_core.tracers.context import collect_runs


def test_prompt_test_runnable_marks_unsuccessful_model_result_as_error(monkeypatch) -> None:
    monkeypatch.setattr(
        prompt_test_tracing.llm_client,
        "chat",
        lambda **_kwargs: LlmResult(
            content="",
            model="synthetic-model",
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=0,
            cost_ms=1,
            success=False,
            error_message="synthetic model failure",
            system_prompt="system",
        ),
    )

    with collect_runs() as collector:
        monkeypatch.setattr(
            prompt_test_tracing,
            "build_langsmith_config",
            lambda **_kwargs: {
                "run_name": "ioc_prompt_test_run",
                "callbacks": [collector],
            },
        )
        with pytest.raises(
            prompt_test_tracing.PromptTestExecutionError,
            match="synthetic model failure",
        ):
            prompt_test_tracing.run_traced_prompt_test(
                prompt_test_tracing.PromptTestInvocation(
                    system_content="system",
                    user_message="synthetic question",
                    provider_name="deepseek",
                ),
                trace_id="prompt_test_10_def",
                operator_id=None,
                metadata={"prompt_key": "ioc.safety.analysis"},
                tags=["prompt-center", "prompt-test"],
            )

    assert len(collector.traced_runs) == 1
    assert "synthetic model failure" in collector.traced_runs[0].error
```

- [ ] **Step 3: Run the tests and verify RED**

Run:

```bash
cd backend
LANGSMITH_TRACING=false .venv/bin/python -m pytest \
  tests/modules/prompt_center/test_prompt_test_tracing.py -q
```

Expected: collection fails because `prompt_test_tracing` does not exist.

- [ ] **Step 4: Implement the focused Runnable**

Create a frozen invocation dataclass, an explicit failure type, a private Runnable
handler accepting the injected child `config`, and the public wrapper:

```python
from dataclasses import asdict, dataclass
from typing import Any

from langchain_core.runnables import RunnableConfig, RunnableLambda

from app.observability import build_langsmith_config
from app.runtime.llm.client import LlmResult, llm_client


@dataclass(frozen=True)
class PromptTestInvocation:
    system_content: str | None
    user_message: str
    provider_name: str | None


class PromptTestExecutionError(RuntimeError):
    pass


def _invoke_llm(payload: dict[str, Any], config: RunnableConfig) -> LlmResult:
    result = llm_client.chat(
        prompt_content=payload["system_content"],
        user_message=payload["user_message"],
        provider_name=payload["provider_name"],
        config=config,
    )
    if not result.success:
        raise PromptTestExecutionError(
            result.error_message or "Prompt 测试模型调用失败"
        )
    return result


_prompt_test_runnable = RunnableLambda(_invoke_llm)


def run_traced_prompt_test(
    invocation: PromptTestInvocation,
    *,
    trace_id: str,
    operator_id: str | None,
    metadata: dict[str, Any],
    tags: list[str],
) -> LlmResult:
    config = build_langsmith_config(
        trace_id=trace_id,
        graph_name="ioc_prompt_test_run",
        user_id=operator_id,
        metadata=metadata,
        extra_tags=tags,
    )
    return _prompt_test_runnable.invoke(asdict(invocation), config=config)
```

- [ ] **Step 5: Run the tests and verify GREEN**

Run the command from Step 3. Expected: `2 passed`.

- [ ] **Step 6: Commit the Runnable**

```bash
git add backend/app/modules/prompt_center/application/prompt_test_tracing.py \
  backend/tests/modules/prompt_center/test_prompt_test_tracing.py
git commit -m "feat: trace prompt tests as parent runs"
```

### Task 3: Integrate trace facts into Prompt test persistence

**Files:**
- Modify: `backend/app/modules/prompt_center/application/prompt_test_service.py`
- Modify: `backend/tests/modules/prompt_center/test_prompt_test_service.py`

**Interfaces:**
- Consumes: `run_traced_prompt_test(invocation: PromptTestInvocation, *, trace_id: str, operator_id: str | None, metadata: dict[str, Any], tags: list[str]) -> LlmResult`
- Persists: `PromptTestRun.trace_id`
- Emits metadata keys: `prompt_key`, `prompt_id`, `prompt_version_id`, `prompt_version`, `prompt_commit_hash`, `prompt_tag`, `prompt_environment`, `prompt_test_run_id`, `prompt_test_case_id`, `model_name`, `provider_name`

- [ ] **Step 1: Write a failing service behavior test**

Extend the existing service test with repository fakes that return Prompt ID `1`, version ID `1`, and run ID `9`. Patch `run_traced_prompt_test()` to capture arguments and patch `get_test_run()` to return the updated record. Assert observable persistence and exact metadata:

```python
from datetime import datetime
from types import SimpleNamespace

from app.modules.prompt_center.application import prompt_test_service
from app.modules.prompt_center.schemas.test_schema import TestRunRequest
from app.runtime.llm.client import LlmResult


def test_run_single_test_persists_trace_id_and_prompt_metadata(monkeypatch):
    prompt = SimpleNamespace(id=1, prompt_key="ioc.safety.analysis")
    version = SimpleNamespace(
        id=1,
        prompt_id=1,
        version="1.0.0",
        system_content="system",
        business_role_content="安全运营专家",
        business_goal_content="识别合成数据风险",
        business_rules=[],
        output_requirement="输出结论",
        positive_examples=[],
        negative_examples=[],
        langsmith_commit_hash="commit100",
        langsmith_tag="1.0.0",
    )
    run_record = SimpleNamespace(id=9)
    run_updates = []
    captured = {}
    trace_state = {"trace_id": None}

    monkeypatch.setattr(
        prompt_test_service.prompt_def_repo,
        "get_by_id",
        lambda _db, _prompt_id: prompt,
    )
    monkeypatch.setattr(
        prompt_test_service.prompt_version_repo,
        "get_by_id",
        lambda _db, _version_id: version,
    )
    monkeypatch.setattr(
        prompt_test_service.prompt_test_run_repo,
        "create",
        lambda _db, _data: run_record,
    )

    def fake_update(_db, _run_id, data):
        run_updates.append(data)
        if "trace_id" in data:
            trace_state["trace_id"] = data["trace_id"]
        return run_record

    monkeypatch.setattr(prompt_test_service.prompt_test_run_repo, "update", fake_update)
    monkeypatch.setattr(
        prompt_test_service.prompt_audit_log_repo,
        "create",
        lambda _db, _data: None,
    )

    def fake_traced_test(invocation, **kwargs):
        captured.update(kwargs)
        return LlmResult(
            content="合成结论",
            model="synthetic-model",
            prompt_tokens=5,
            completion_tokens=3,
            total_tokens=8,
            cost_ms=1,
            success=True,
            system_prompt=invocation.system_content or "",
        )

    monkeypatch.setattr(
        prompt_test_service,
        "run_traced_prompt_test",
        fake_traced_test,
    )
    monkeypatch.setattr(
        prompt_test_service,
        "get_test_run",
        lambda _db, _run_id: SimpleNamespace(
            trace_id=trace_state["trace_id"],
            created_at=datetime(2026, 7, 29),
        ),
    )

    result = prompt_test_service.run_single_test(
        db=object(),
        prompt_id=1,
        version_id=1,
        data=TestRunRequest(
            input_data={"user_question": "合成问题"},
            test_case_id=3,
            provider_name="deepseek",
        ),
        operator_id="operator-1",
    )

    assert result.trace_id.startswith("prompt_test_9_")
    assert run_updates[0]["trace_id"] == result.trace_id
    assert captured["trace_id"] == result.trace_id
    assert captured["metadata"] == {
        "prompt_key": "ioc.safety.analysis",
        "prompt_id": 1,
        "prompt_version_id": 1,
        "prompt_version": "1.0.0",
        "prompt_commit_hash": "commit100",
        "prompt_tag": "1.0.0",
        "prompt_environment": "test",
        "prompt_test_run_id": 9,
        "prompt_test_case_id": 3,
        "model_name": "deepseek-chat",
        "provider_name": "deepseek",
    }
```

- [ ] **Step 2: Write a failing local-failure persistence test**

Add a second service test that drives the real exception branch while replacing
only repositories and the external traced executor:

```python
def test_run_single_test_persists_failed_status_when_traced_executor_raises(monkeypatch):
    prompt = SimpleNamespace(id=1, prompt_key="ioc.safety.analysis")
    version = SimpleNamespace(
        id=1,
        prompt_id=1,
        version="1.0.0",
        langsmith_commit_hash="commit100",
        langsmith_tag="1.0.0",
    )
    updates = []

    monkeypatch.setattr(
        prompt_test_service.prompt_def_repo,
        "get_by_id",
        lambda _db, _prompt_id: prompt,
    )
    monkeypatch.setattr(
        prompt_test_service.prompt_version_repo,
        "get_by_id",
        lambda _db, _version_id: version,
    )
    monkeypatch.setattr(
        prompt_test_service,
        "_build_test_prompt",
        lambda _version, _input: [
            {"role": "system", "content": "system"},
            {"role": "user", "content": "synthetic question"},
        ],
    )
    monkeypatch.setattr(
        prompt_test_service.prompt_test_run_repo,
        "create",
        lambda _db, _data: SimpleNamespace(id=10),
    )
    monkeypatch.setattr(
        prompt_test_service.prompt_test_run_repo,
        "update",
        lambda _db, _run_id, data: updates.append(data),
    )
    monkeypatch.setattr(
        prompt_test_service.prompt_audit_log_repo,
        "create",
        lambda _db, _data: None,
    )
    monkeypatch.setattr(
        prompt_test_service,
        "run_traced_prompt_test",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            RuntimeError("synthetic trace failure")
        ),
    )
    monkeypatch.setattr(
        prompt_test_service,
        "get_test_run",
        lambda _db, _run_id: SimpleNamespace(
            status=next(
                item["status"]
                for item in reversed(updates)
                if "status" in item
            ),
            raw_output=next(
                item["raw_output"]
                for item in reversed(updates)
                if "raw_output" in item
            ),
        ),
    )

    result = prompt_test_service.run_single_test(
        db=object(),
        prompt_id=1,
        version_id=1,
        data=TestRunRequest(input_data={"user_question": "合成问题"}),
    )

    assert result.status == "failed"
    assert "synthetic trace failure" in result.raw_output
```

- [ ] **Step 3: Run the tests and verify RED**

Run:

```bash
cd backend
LANGSMITH_TRACING=false .venv/bin/python -m pytest \
  tests/modules/prompt_center/test_prompt_test_service.py::test_run_single_test_persists_trace_id_and_prompt_metadata \
  tests/modules/prompt_center/test_prompt_test_service.py::test_run_single_test_persists_failed_status_when_traced_executor_raises -q
```

Expected: fail because no trace ID is persisted and the service still calls `llm_client.chat()` directly.

- [ ] **Step 4: Implement trace ID persistence and executor integration**

After creating `run_record`, generate a database-correlated ID that fits the existing 64-character column:

```python
from uuid import uuid4

trace_id = f"prompt_test_{run_record.id}_{uuid4().hex[:16]}"
prompt_test_run_repo.update(db, run_record.id, {"trace_id": trace_id})
```

Replace the direct model call with:

```python
result = run_traced_prompt_test(
    PromptTestInvocation(
        system_content=system_content or None,
        user_message=user_message,
        provider_name=data.provider_name,
    ),
    trace_id=trace_id,
    operator_id=operator_id,
    metadata={
        "prompt_key": prompt.prompt_key,
        "prompt_id": prompt_id,
        "prompt_version_id": version_id,
        "prompt_version": version.version,
        "prompt_commit_hash": version.langsmith_commit_hash,
        "prompt_tag": version.langsmith_tag,
        "prompt_environment": "test",
        "prompt_test_run_id": run_record.id,
        "prompt_test_case_id": data.test_case_id,
        "model_name": data.model_name or "deepseek-chat",
        "provider_name": data.provider_name,
    },
    tags=[
        "prompt-center",
        "prompt-test",
        prompt.prompt_key,
        version.version,
    ],
)
```

Retain the existing `_build_test_prompt()` shared business-content builder fix and its test.

- [ ] **Step 5: Run Prompt Center and observability tests**

Run:

```bash
cd backend
LANGSMITH_TRACING=false .venv/bin/python -m pytest \
  tests/modules/prompt_center \
  tests/observability \
  tests/runtime/llm/test_llm_client_config.py -q
```

Expected: all selected tests pass and no remote Trace is uploaded.

- [ ] **Step 6: Commit the service integration**

```bash
git add backend/app/modules/prompt_center/application/prompt_test_service.py \
  backend/tests/modules/prompt_center/test_prompt_test_service.py
git commit -m "feat: link prompt test runs to langsmith"
```

### Task 4: Verify regression safety and one remote synthetic run

**Files:**
- No committed configuration or secret files.
- Runtime-only change: set `LANGSMITH_PROMPT_SYNC_ENABLED=true` for local execution.

**Interfaces:**
- Consumes: Prompt key `ioc.safety.analysis`, current published version, one existing synthetic test case.
- Produces: a LangSmith Prompt Commit/Tag and a remotely queryable `ioc_prompt_test_run`.

- [ ] **Step 1: Run fresh local verification**

```bash
cd backend
LANGSMITH_TRACING=false PYTHONDONTWRITEBYTECODE=1 \
  .venv/bin/python -m pytest -q
cd ..
git diff --check
```

Expected: pytest exits `0`; `git diff --check` emits no errors.

- [ ] **Step 2: Enable runtime-only Prompt sync and sync the published version**

Run a one-off process with `LANGSMITH_PROMPT_SYNC_ENABLED=true`; do not commit `.env`:

```bash
cd backend
LANGSMITH_PROMPT_SYNC_ENABLED=true .venv/bin/python - <<'PY'
from app.db.session import get_session_local
from app.modules.prompt_center.application.prompt_sync_service import ensure_prompt_version_synced
from app.modules.prompt_center.infrastructure.repositories import prompt_def_repo, prompt_version_repo

with get_session_local()() as db:
    prompt = prompt_def_repo.get_by_key(db, "ioc.safety.analysis")
    if prompt is None or prompt.current_version_id is None:
        raise SystemExit("published prompt not found")
    version = prompt_version_repo.get_by_id(db, prompt.current_version_id)
    result = ensure_prompt_version_synced(db, prompt, version)
    print({"commit_hash": result.commit_hash, "tag": result.tag})
PY
```

Expected: a real Commit Hash and Tag `1.0.0`, persisted on the local version.

- [ ] **Step 3: Start the backend with tracing and Prompt sync enabled**

```bash
cd backend
LANGSMITH_TRACING=true LANGSMITH_PROMPT_SYNC_ENABLED=true \
  .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Keep the process running in a managed terminal session.

- [ ] **Step 4: Execute exactly one synthetic Prompt test**

Use the existing synthetic case data, never a real business payload:

```bash
curl -sS -X POST \
  http://127.0.0.1:8000/api/v1/prompts/1/versions/1/test \
  -H 'Content-Type: application/json' \
  -d '{
    "input_data": {
      "device_name": "脱敏设备-A",
      "realtime_data": {"temperature": 85},
      "user_question": "请判断当前合成数据的风险"
    },
    "test_case_id": 2,
    "provider_name": "deepseek"
  }'
```

Expected: response status is `completed` and contains a non-empty
`trace_id` beginning with `prompt_test_`.

- [ ] **Step 5: Query LangSmith and prove the remote parent/child trace**

Use the returned `trace_id`:

```bash
cd backend
.venv/bin/python - <<'PY'
import os
from langsmith import Client

from app.config.settings import settings

trace_id = os.environ["PROMPT_TEST_TRACE_ID"]
client = Client(api_url=settings.langsmith_endpoint, api_key=settings.langsmith_api_key)
runs = list(client.list_runs(
    project_name=settings.langsmith_project,
    filter=f'and(eq(metadata_key, "ioc_trace_id"), eq(metadata_value, "{trace_id}"))',
))
for run in runs:
    print({
        "id": str(run.id),
        "parent_run_id": str(run.parent_run_id) if run.parent_run_id else None,
        "name": run.name,
        "run_type": run.run_type,
        "prompt_key": (run.extra or {}).get("metadata", {}).get("prompt_key"),
        "prompt_version": (run.extra or {}).get("metadata", {}).get("prompt_version"),
        "prompt_commit_hash": (run.extra or {}).get("metadata", {}).get("prompt_commit_hash"),
    })
if not runs:
    raise SystemExit("remote prompt test trace not found")
PY
```

If the installed SDK rejects the server-side metadata filter, query recent runs with
`limit=100` and filter the returned `run.extra["metadata"]["ioc_trace_id"]` locally.

Acceptance requires:

- one root named `ioc_prompt_test_run`;
- at least one LLM child with the root as parent;
- matching `prompt_key`, `prompt_version`, `prompt_commit_hash`, and local test-run ID;
- masked input/output visible;
- LangSmith Prompts contains the same Prompt Key, Commit, and Tag.

- [ ] **Step 6: Inspect final repository state**

```bash
git status --short
git log -5 --oneline --decorate
```

Report code commits separately from the runtime-only environment and remote verification.
