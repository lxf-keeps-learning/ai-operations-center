# LangSmith Agent 可观测性 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Enable production-configured LangSmith reporting and add reliable, redacted Agent-level child runs for business nodes, Tool calls, and RAG calls.

**Architecture:** Keep `build_langsmith_config` as the root LangGraph callback factory. Add a small optional child-run helper that uses the configured LangSmith client when available and otherwise executes as a no-op wrapper. Instrument only stable domain boundaries so observability failures cannot change Agent results.

**Tech Stack:** Python 3.11, LangGraph, LangChain, LangSmith SDK, pytest, Pydantic settings.

## Global Constraints

- API keys must come only from environment variables or secret management; never commit secrets.
- Inputs and outputs sent to LangSmith must pass the existing sensitive-data sanitizer.
- User/session/tenant/company identifiers sent as metadata must be hashed references.
- LangSmith initialization or upload failures must not block Agent execution.
- Preserve the local `ai_trace` and existing REST/SSE contracts.

---

### Task 1: Add the child-run observability helper

**Files:**
- Create: `backend/app/observability/langsmith_runs.py`
- Test: `backend/tests/observability/test_langsmith_runs.py`

**Interfaces:**
- `run_observed(name: str, run_type: str, operation: Callable[..., T], *, inputs: Any = None, metadata: dict[str, Any] | None = None, tags: list[str] | None = None, trace_id: str | None = None) -> T`
- The helper must return the wrapped operation result unchanged, re-raise the original exception, and never fail because LangSmith is unavailable.

- [ ] Write a failing test for a successful child run with sanitized inputs/outputs and metadata.
- [ ] Write a failing test for an operation exception: original exception is re-raised and the tracing client failure is swallowed.
- [ ] Write a failing test for disabled tracing: operation executes and no run is created.
- [ ] Run `cd backend && PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/observability/test_langsmith_runs.py -q`; expect failure because the helper does not exist.
- [ ] Implement a minimal helper using the LangSmith `Client.create_run`/`update_run` lifecycle or the SDK's supported run context, with `sanitize_trace_payload` applied to inputs, outputs, and metadata.
- [ ] Run the focused test and confirm it passes.

### Task 2: Make production enabling explicit and observable

**Files:**
- Modify: `backend/app/config/settings.py`
- Modify: `backend/.env.example`
- Modify: `backend/app/observability/langsmith_tracing.py`
- Test: `backend/tests/observability/test_langsmith_tracing.py`

**Interfaces:**
- Preserve `build_langsmith_config` and add a clear `langsmith_enabled`/effective-enabled check that requires the feature flag, API key, and positive sampling rate.

- [ ] Add a failing test proving missing API key yields no callback and a diagnostic reason without exposing the key.
- [ ] Add a failing test proving enabled configuration creates the configured project/endpoint callback.
- [ ] Implement the effective-enabled check and structured warning for disabled/misconfigured environments.
- [ ] Update `.env.example` with production-oriented configuration comments, keeping the local default safe.
- [ ] Run `tests/observability/test_langsmith_tracing.py -q` and confirm it passes.

### Task 3: Instrument Operation Agent business boundaries

**Files:**
- Modify: `backend/app/operation_agent/nodes/query_operation_data_node.py`
- Modify: `backend/app/operation_agent/nodes/detect_abnormal_node.py`
- Modify: `backend/app/operation_agent/nodes/analyze_reason_node.py`
- Modify: `backend/app/operation_agent/nodes/generate_advice_node.py`
- Modify: `backend/app/operation_agent/nodes/summary_node.py`
- Test: `backend/tests/observability/test_agent_boundaries.py`

**Interfaces:**
- Each node continues to accept and return `OperationState`; tracing wraps existing work and does not alter state contracts.
- Child run metadata includes `ioc_trace_id`, `agent=operation`, and the node key.

- [ ] Add failing tests around one representative node and verify the state result is unchanged while a child run is recorded.
- [ ] Add failing test proving a child-run recording error does not turn a successful node into a failed node.
- [ ] Instrument stable node boundaries with `run_observed`, keeping payloads summarized and sanitized.
- [ ] Run focused Operation Agent tests plus the new observability tests.

### Task 4: Instrument Report Chat Tool/RAG boundaries

**Files:**
- Modify: `backend/app/report_chat_agent/nodes/call_rag_node.py`
- Modify: `backend/app/report_chat_agent/nodes/should_use_rag_node.py`
- Modify: `backend/app/report_chat_agent/nodes/generate_report_answer_node.py`
- Modify: `backend/app/tool_center/base_tool.py`
- Modify: `backend/app/rag/service.py`
- Test: `backend/tests/observability/test_agent_boundaries.py`

**Interfaces:**
- Tool and RAG behavior, return schemas, and fallback semantics remain unchanged.
- Run metadata identifies `agent`, `tool_name` or `rag_operation`, `report_id` where available, and `ioc_trace_id`.

- [ ] Add failing tests for a Tool success, RAG success, and RAG failure producing child-run metadata while preserving existing fallback behavior.
- [ ] Implement wrappers at the Tool Center and RAG service boundaries, avoiding per-record payloads and secrets.
- [ ] Instrument report answer generation so model invocation is identifiable even when the surrounding node completes partially.
- [ ] Run Report Chat, Tool Center, RAG, and observability tests.

### Task 5: Runtime metadata and operational documentation

**Files:**
- Modify: `backend/app/runtime/runtime_service.py`
- Modify: `backend/README.md`
- Modify: `README.md`
- Create: `docs/observability/langsmith-runbook.md`

- [ ] Add a failing test asserting Runtime sync and streaming calls include project, graph, environment, and prompt metadata.
- [ ] Implement only missing metadata propagation; do not duplicate existing root callback setup.
- [ ] Document required production environment variables, project naming, sampling, privacy behavior, and how to correlate LangSmith `ioc_trace_id` with the local Trace viewer.
- [ ] Run the focused Runtime and observability tests.

### Task 6: Full verification

**Files:**
- No additional production files.

- [ ] Run `cd backend && PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q`.
- [ ] Run `cd frontend && npm run type-check`.
- [ ] Run `cd frontend && npm run build`.
- [ ] Inspect `git diff --check` and `git status --short`; preserve unrelated `backend/scripts/check_langsmith.py`.
- [ ] If credentials are available only in deployment, report that live LangSmith delivery requires setting them in the runtime environment; never add a key to the repository.
