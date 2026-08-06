# Session Memory Trace Platform Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first platform-grade Session, Memory, and Trace capabilities on top of the existing Runtime and Report Chat implementations, without replacing LangGraph or breaking existing APIs.

**Architecture:** Treat `AiConversation` as the platform Session and `AiSession` as one execution Run. Add a unified read/write service layer that both Runtime Chat and Report Chat use, keep LangGraph checkpoints/stores for graph state and memory, and persist platform-facing memory and trace records in the existing relational database. Expose stable platform APIs and a Vue console that can browse sessions, memories, runs, and trace timelines.

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy 2, Alembic, MySQL for platform records, PostgreSQL-backed LangGraph Store/Checkpointer for Report Chat persistence, Vue 3, TypeScript, Pinia, existing SSE event adapters, and existing LangSmith integration.

## Global Constraints

- Preserve existing `/api/v1/runtime/*`, `/api/v1/chat/*`, and legacy `/api/v1/agent/*` contracts.
- Use `Conversation = platform Session`, `AiSession = platform Run` consistently in new code and API documentation.
- Do not expose raw LangGraph state as the public platform contract.
- Keep LangSmith as an observability integration, not the only source of local audit data.
- Treat memory read/write failures as non-fatal to the primary answer path.
- Do not add vector search to the MVP; support explicit memory, session summaries, and relational filtering first.
- Redact secrets and sensitive content before storing trace input/output or memory content.
- Every new persistence change must have an Alembic migration and repository/service tests.
- Do not add new external channels, TTS, browser tools, Cron, or multi-tenant RBAC in this scope.

---

## Current Code Map

The implementation must build on these existing units:

- Runtime models: `backend/app/runtime/models/conversation_model.py`, `backend/app/runtime/models/session_model.py`, `backend/app/runtime/models/trace_model.py`
- Runtime services: `backend/app/runtime/services/conversation_service.py`, `backend/app/runtime/services/session_service.py`, `backend/app/runtime/services/trace_service.py`
- Runtime graph: `backend/app/runtime/graph.py`, `backend/app/runtime/nodes/init_session_node.py`, `backend/app/runtime/nodes/call_llm_node.py`, `backend/app/runtime/nodes/finalize_node.py`
- Report Chat persistence: `backend/app/report_chat_agent/persistence.py`, `backend/app/report_chat_agent/memory.py`, `backend/app/report_chat_agent/service.py`, `backend/app/report_chat_agent/stream_service.py`
- Existing trace adapters: `backend/app/analysis_stream/`, `backend/app/runtime/runtime_event_adapter.py`, `backend/app/report_chat_agent/report_chat_event_adapter.py`
- Frontend shell: `frontend/src/layouts/DefaultLayout.vue`, `frontend/src/router/index.ts`, `frontend/src/api/runtime.ts`, `frontend/src/types/`

## Target Contracts

```text
Conversation / platform Session
  └── AiSession / platform Run
        └── TraceEvent / local execution span

Memory
  ├── user scope
  ├── session scope
  └── report scope
```

Every Run must expose `run_id`, `session_id`, `conversation_id`, `trace_id`, `agent_key`, `status`, timestamps, token usage, and cost where available. Every trace record must expose `trace_id`, `span_id`, `parent_span_id`, `run_id`, `span_type`, status, timing, and redacted input/output metadata.

## Implementation Tasks

### Task 1: Establish the platform identity and persistence contracts

**Files:**
- Create: `backend/app/platform/__init__.py`
- Create: `backend/app/platform/contracts/identifiers.py`
- Create: `backend/app/platform/schemas/session_schema.py`
- Create: `backend/app/platform/schemas/run_schema.py`
- Create: `backend/app/platform/schemas/trace_schema.py`
- Create: `backend/app/platform/schemas/memory_schema.py`
- Modify: `backend/app/runtime/schemas/session_schema.py`
- Modify: `backend/app/runtime/schemas/trace_schema.py`
- Test: `backend/tests/platform/test_platform_contracts.py`

**Interfaces:**
- `PlatformSessionSummary`: `session_id`, `conversation_id`, `user_id`, `agent_key`, `channel`, `title`, `status`, `created_at`, `last_active_at`, `run_count`.
- `PlatformRunSummary`: `run_id`, `session_id`, `conversation_id`, `trace_id`, `agent_key`, `task_type`, `status`, `started_at`, `finished_at`, `duration_ms`, `total_tokens`, `cost`.
- `PlatformTraceEvent`: `trace_id`, `span_id`, `parent_span_id`, `run_id`, `span_type`, `status`, `node_name`, `tool_name`, `model_name`, `input_data`, `output_data`, `cost_ms`, token fields, timestamps.
- `MemoryRecord`: `id`, `scope`, `owner_id`, `session_id`, `report_id`, `memory_type`, `content`, `source_trace_id`, `source_run_id`, `confidence`, `importance`, `status`, `created_at`, `updated_at`.

- [ ] **Step 1: Write contract tests** asserting that the new response models accept existing Runtime and Report Chat identifiers and reject missing `session_id`, `run_id`, or `trace_id` where required.
- [ ] **Step 2: Run the focused tests**

  Run: `cd backend && PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/platform/test_platform_contracts.py -q`

  Expected: FAIL until the platform schema module exists.

- [ ] **Step 3: Implement the schemas and identifier helpers** using Pydantic v2 and existing ID/time utilities; do not change database behavior in this task.
- [ ] **Step 4: Run the focused tests again**

  Run: `cd backend && PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/platform/test_platform_contracts.py -q`

  Expected: PASS.

- [ ] **Step 5: Commit the contract layer**

  Run: `git add backend/app/platform backend/app/runtime/schemas backend/tests/platform/test_platform_contracts.py && git commit -m "feat: define platform session run trace memory contracts"`

### Task 2: Add durable platform Memory records and a memory service

**Files:**
- Create: `backend/app/platform/models/memory_model.py`
- Create: `backend/app/platform/repositories/memory_repository.py`
- Create: `backend/app/platform/services/memory_service.py`
- Create: `backend/alembic/versions/20260806_0001_create_platform_memory.py`
- Modify: `backend/app/db/base.py` or the existing model import registry as required for Alembic discovery
- Test: `backend/tests/platform/test_memory_service.py`
- Test: `backend/tests/platform/test_memory_migration_model.py`

**Interfaces:**
- `MemoryService.list(db, owner_id, scope=None, session_id=None, report_id=None, status="active", limit=50, offset=0)`
- `MemoryService.create(db, payload)`
- `MemoryService.update(db, memory_id, payload)`
- `MemoryService.delete(db, memory_id)` as a soft delete that sets `status="deleted"`
- `MemoryService.load_for_run(db, user_id, session_id, report_id, query, limit=5)`
- `MemoryService.save_explicit(db, user_id, session_id, report_id, trace_id, run_id, content, memory_type, scope)`

- [ ] **Step 1: Write repository/service tests** covering user memory isolation, report memory isolation, session-scoped memory, soft deletion, duplicate explicit memory keys, and non-fatal empty results.
- [ ] **Step 2: Run tests to verify the new behavior is absent**

  Run: `cd backend && PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/platform/test_memory_service.py tests/platform/test_memory_migration_model.py -q`

  Expected: FAIL because the model and service are not implemented.

- [ ] **Step 3: Add the migration and SQLAlchemy model** with indexed `owner_id`, `scope`, `session_id`, `report_id`, `status`, and `updated_at`; store only moderated content and source identifiers.
- [ ] **Step 4: Implement repository filtering and service methods** with explicit scope predicates so user memories cannot cross users and report memories cannot cross reports.
- [ ] **Step 5: Run the focused tests**

  Run: `cd backend && PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/platform/test_memory_service.py tests/platform/test_memory_migration_model.py -q`

  Expected: PASS.

- [ ] **Step 6: Commit the durable Memory layer**

  Run: `git add backend/app/platform backend/alembic/versions/20260806_0001_create_platform_memory.py backend/tests/platform && git commit -m "feat: add durable platform memory records"`

### Task 3: Unify Runtime Chat and Report Chat with platform Session/Run services

**Files:**
- Create: `backend/app/platform/services/session_service.py`
- Create: `backend/app/platform/services/run_service.py`
- Create: `backend/app/platform/repositories/session_repository.py`
- Create: `backend/app/platform/repositories/run_repository.py`
- Modify: `backend/app/runtime/nodes/init_session_node.py`
- Modify: `backend/app/runtime/nodes/finalize_node.py`
- Modify: `backend/app/report_chat_agent/service.py`
- Modify: `backend/app/report_chat_agent/stream_service.py`
- Modify: `backend/app/report_chat_agent/repositories/chat_repository.py`
- Test: `backend/tests/platform/test_session_run_service.py`
- Test: `backend/tests/runtime/test_platform_run_linkage.py`
- Test: `backend/tests/report_chat_agent/test_platform_run_linkage.py`

**Interfaces:**
- `PlatformSessionService.get_or_create(...)` returns the existing `AiConversation` identity without duplicating a conversation.
- `PlatformRunService.start(...)` creates or reuses the existing `AiSession` row and returns `PlatformRunSummary`.
- `PlatformRunService.complete(...)` records output, status, finish time, usage, and error state.
- `PlatformRunService.fail(...)` records a failed terminal state without losing the original input.

- [ ] **Step 1: Write linkage tests** asserting that Runtime Chat and Report Chat both produce a `conversation_id`, `session_id`/`run_id`, and `trace_id`, and that Report Chat’s `runtime_session_id` points to the same `AiSession` represented by the platform Run.
- [ ] **Step 2: Run the linkage tests before implementation**

  Run: `cd backend && PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/platform/test_session_run_service.py tests/runtime/test_platform_run_linkage.py tests/report_chat_agent/test_platform_run_linkage.py -q`

  Expected: FAIL for the new platform linkage assertions.

- [ ] **Step 3: Implement platform services as facades over the existing Runtime repositories** so legacy services remain compatible and no duplicate Session/Run rows are created.
- [ ] **Step 4: Replace direct lifecycle updates in Runtime and Report Chat entry points** with `PlatformRunService.start/complete/fail`, preserving existing response fields and status values.
- [ ] **Step 5: Run the focused linkage tests**

  Run: `cd backend && PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/platform/test_session_run_service.py tests/runtime/test_platform_run_linkage.py tests/report_chat_agent/test_platform_run_linkage.py -q`

  Expected: PASS.

- [ ] **Step 6: Commit the unified Session/Run lifecycle**

  Run: `git add backend/app/platform backend/app/runtime backend/app/report_chat_agent backend/tests/platform backend/tests/runtime backend/tests/report_chat_agent && git commit -m "feat: unify platform session and run lifecycle"`

### Task 4: Normalize local Trace persistence and event coverage

**Files:**
- Create: `backend/app/platform/services/trace_service.py`
- Create: `backend/app/platform/repositories/trace_repository.py`
- Create: `backend/app/platform/trace_redaction.py`
- Modify: `backend/app/runtime/nodes/load_prompt_node.py`
- Modify: `backend/app/runtime/nodes/call_llm_node.py`
- Modify: `backend/app/runtime/nodes/finalize_node.py`
- Modify: `backend/app/tool_center/telemetry.py`
- Modify: `backend/app/report_chat_agent/graph.py`
- Modify: `backend/app/report_chat_agent/report_chat_event_adapter.py`
- Create: `backend/alembic/versions/20260806_0002_normalize_platform_trace_fields.py`
- Test: `backend/tests/platform/test_trace_service.py`
- Test: `backend/tests/platform/test_trace_redaction.py`
- Test: `backend/tests/operation_agent/test_platform_trace_coverage.py`
- Test: `backend/tests/report_chat_agent/test_platform_trace_coverage.py`

**Interfaces:**
- `PlatformTraceService.start_span(...)`
- `PlatformTraceService.complete_span(...)`
- `PlatformTraceService.fail_span(...)`
- `PlatformTraceService.list_tree(db, trace_id)` returns spans ordered by parent relationship and creation time.
- `PlatformTraceService.list_timeline(db, run_id)` returns a stable chronological event list.
- `redact_trace_payload(payload)` removes API keys, authorization headers, credentials, and configured sensitive fields before persistence.

- [ ] **Step 1: Write tests for parent/child tree reconstruction, chronological timeline ordering, failed spans, token/cost fields, and payload redaction.**
- [ ] **Step 2: Run trace tests before implementation**

  Run: `cd backend && PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/platform/test_trace_service.py tests/platform/test_trace_redaction.py -q`

  Expected: FAIL for the new service and redaction behavior.

- [ ] **Step 3: Implement the platform trace facade over `AiTrace`** and keep the existing `TraceService` methods as compatibility wrappers.
- [ ] **Step 4: Add missing Report Chat and Tool Center local spans** for graph start/end, memory load/write, LLM calls, Tool calls, RAG calls, and failures; preserve LangSmith metadata with the same `ioc_trace_id`.
- [ ] **Step 5: Add stable `run_id` linkage** to trace writes through the existing `session_id` relationship, using a migration only if a direct indexed column is needed by the query workload.
- [ ] **Step 6: Run Runtime, Operation Agent, Report Chat, and trace tests**

  Run: `cd backend && PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/platform tests/runtime tests/operation_agent tests/report_chat_agent -q`

  Expected: PASS with existing regression tests preserved.

- [ ] **Step 7: Commit normalized Trace persistence**

  Run: `git add backend/app/platform backend/app/runtime backend/app/tool_center backend/app/report_chat_agent backend/alembic/versions/20260806_0002_normalize_platform_trace_fields.py backend/tests && git commit -m "feat: normalize local agent trace persistence"`

### Task 5: Make Report Chat memory durable and expose a unified Memory adapter

**Files:**
- Create: `backend/app/platform/memory_adapter.py`
- Modify: `backend/app/report_chat_agent/persistence.py`
- Modify: `backend/app/report_chat_agent/memory.py`
- Modify: `backend/app/report_chat_agent/graph.py`
- Modify: `backend/app/runtime/runtime_service.py`
- Modify: `backend/app/runtime/graph.py`
- Create: `backend/app/platform/api/memory_api.py`
- Test: `backend/tests/platform/test_memory_api.py`
- Test: `backend/tests/report_chat_agent/test_durable_memory_config.py`
- Test: `backend/tests/runtime/test_runtime_memory_adapter.py`

**Interfaces:**
- `PlatformMemoryAdapter.load_for_run(...)` merges relational explicit memories with Report Chat Store results, applying scope and limit rules.
- `PlatformMemoryAdapter.save_after_run(...)` saves explicit memories and a bounded session summary.
- `PlatformMemoryAdapter.status()` reports relational memory status, LangGraph Store backend, and whether persistence is durable.

- [ ] **Step 1: Write tests** for Postgres-backed durability, in-memory development fallback, user/report namespace isolation, Runtime Chat memory loading, and failure fallback.
- [ ] **Step 2: Run the memory integration tests before implementation**

  Run: `cd backend && PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/platform/test_memory_api.py tests/report_chat_agent/test_durable_memory_config.py tests/runtime/test_runtime_memory_adapter.py -q`

  Expected: FAIL for the unified adapter assertions.

- [ ] **Step 3: Make the configured PostgreSQL Store/Checkpointer the documented production path** and expose an explicit status when the application is using `InMemoryStore`.
- [ ] **Step 4: Route Report Chat memory nodes through the adapter** while retaining the existing namespace behavior and moderation rules.
- [ ] **Step 5: Add Runtime Chat memory load/save around the existing history-message path** without changing the current prompt format or token budget behavior.
- [ ] **Step 6: Add Memory CRUD and status APIs** with soft deletion and source trace/run fields.
- [ ] **Step 7: Run all memory, Runtime, and Report Chat tests**

  Run: `cd backend && PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/platform tests/runtime tests/report_chat_agent -q`

  Expected: PASS.

- [ ] **Step 8: Commit the unified durable Memory integration**

  Run: `git add backend/app/platform backend/app/runtime backend/app/report_chat_agent backend/tests && git commit -m "feat: unify durable agent memory"`

### Task 6: Expose platform Session, Run, Trace, and Memory APIs

**Files:**
- Create: `backend/app/platform/api/session_api.py`
- Create: `backend/app/platform/api/run_api.py`
- Create: `backend/app/platform/api/trace_api.py`
- Create: `backend/app/platform/schemas/query_schema.py`
- Modify: `backend/app/main.py` or the existing API router registration module
- Test: `backend/tests/platform/test_platform_api.py`

**Interfaces:**
- `GET /api/v1/platform/sessions`
- `GET /api/v1/platform/sessions/{session_id}`
- `GET /api/v1/platform/sessions/{session_id}/messages`
- `GET /api/v1/platform/sessions/{session_id}/runs`
- `GET /api/v1/platform/runs/{run_id}`
- `GET /api/v1/platform/runs/{run_id}/timeline`
- `GET /api/v1/platform/runs/{run_id}/tree`
- `GET /api/v1/platform/memories`
- `POST /api/v1/platform/memories`
- `PATCH /api/v1/platform/memories/{memory_id}`
- `DELETE /api/v1/platform/memories/{memory_id}`
- `GET /api/v1/platform/health/memory`

- [ ] **Step 1: Write API tests** for pagination, filtering by user/status/agent, 404 handling, authorization scope placeholders based on the existing user context, memory soft deletion, timeline ordering, and stable response envelopes.
- [ ] **Step 2: Run API tests before implementation**

  Run: `cd backend && PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/platform/test_platform_api.py -q`

  Expected: FAIL because the platform router is not registered.

- [ ] **Step 3: Implement query schemas, service calls, and API routers** using the existing `ApiResponse` envelope and error handling conventions.
- [ ] **Step 4: Register the platform router under `/api/v1/platform`** without changing existing route paths.
- [ ] **Step 5: Run API and regression tests**

  Run: `cd backend && PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/platform tests/test_api.py -q`

  Expected: PASS.

- [ ] **Step 6: Commit the platform APIs**

  Run: `git add backend/app/platform backend/app/main.py backend/tests/platform && git commit -m "feat: expose session memory and trace platform APIs"`

### Task 7: Build the first console views

**Files:**
- Create: `frontend/src/pages/platform/sessions/IndexPage.vue`
- Create: `frontend/src/pages/platform/sessions/DetailPage.vue`
- Create: `frontend/src/pages/platform/runs/DetailPage.vue`
- Create: `frontend/src/pages/platform/memories/IndexPage.vue`
- Create: `frontend/src/components/platform/SessionTable.vue`
- Create: `frontend/src/components/platform/RunTimeline.vue`
- Create: `frontend/src/components/platform/TraceTree.vue`
- Create: `frontend/src/components/platform/MemoryTable.vue`
- Create: `frontend/src/components/platform/StatusBadge.vue`
- Create: `frontend/src/api/platform.ts`
- Create: `frontend/src/types/platform.ts`
- Modify: `frontend/src/router/index.ts`
- Modify: `frontend/src/layouts/DefaultLayout.vue`
- Test: `frontend/src/api/platform.test.ts` or the existing frontend test location

**Interfaces:**
- API client methods mirror the platform endpoints from Task 6.
- `RunTimeline` accepts ordered `PlatformTraceEvent[]` and renders running, success, failed, and skipped states.
- `TraceTree` accepts a flat span list and builds the tree using `parent_span_id`.
- `MemoryTable` supports active/deleted filtering and source-session navigation.

- [ ] **Step 1: Add typed frontend API and domain models** for Session, Run, TraceEvent, and Memory.
- [ ] **Step 2: Add route entries and navigation labels** for Session, Run detail, Trace, and Memory.
- [ ] **Step 3: Implement Session list/detail** with loading, empty, error, pagination, status filters, and links to Runs.
- [ ] **Step 4: Implement Run detail** with summary metrics, timeline, trace tree, token/cost fields, and expandable input/output sections.
- [ ] **Step 5: Implement Memory list/detail actions** with source trace/run links and soft-delete confirmation.
- [ ] **Step 6: Run frontend checks**

  Run: `cd frontend && npm run type-check && npm run build`

  Expected: PASS.

- [ ] **Step 7: Commit the console views**

  Run: `git add frontend/src && git commit -m "feat: add session memory and trace console"`

### Task 8: End-to-end verification and operational handoff

**Files:**
- Modify: `README.md`
- Modify: `backend/README.md`
- Create: `docs/observability/session-memory-trace-runbook.md`
- Test: `backend/tests/platform/test_platform_e2e.py`

- [ ] **Step 1: Add an end-to-end test** that creates a conversation, sends a Runtime Chat message, verifies the Run and local Trace tree, writes explicit memory, reloads memory, and reads the Session detail payload.
- [ ] **Step 2: Add a Report Chat integration test** verifying the same platform identifiers and durable memory status when PostgreSQL Store is configured.
- [ ] **Step 3: Run backend verification**

  Run: `cd backend && PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q`

  Expected: PASS.

- [ ] **Step 4: Run frontend verification**

  Run: `cd frontend && npm run type-check && npm run build`

  Expected: PASS.

- [ ] **Step 5: Update documentation** with the Session/Run naming rule, environment requirements for durable LangGraph memory, platform API examples, and trace redaction behavior.
- [ ] **Step 6: Commit the operational handoff**

  Run: `git add README.md backend/README.md docs/observability/session-memory-trace-runbook.md backend/tests/platform/test_platform_e2e.py && git commit -m "docs: add session memory trace operations runbook"`

## Verification Checklist

- A Runtime Chat request creates one platform Session if needed and one Run per user turn.
- A Report Chat request reuses its existing Conversation and links its runtime turn to the same platform Run model.
- A Run can be opened from the console and shows a chronological trace timeline.
- Trace tree parent/child relationships are reconstructable from local records.
- LangSmith and local `trace_id` values remain correlated.
- Explicit user memory is stored with source Session, Run, and Trace identifiers.
- User, Session, and Report memory scopes cannot cross their isolation boundaries.
- Memory is durable when the configured persistent Store is available and visibly marked as in-memory in development fallback mode.
- Memory failure does not fail the user’s primary response.
- Existing Runtime, Operation Agent, Report Chat, and legacy API tests remain green.

## Scope Boundary

This plan deliberately stops after a working Session/Memory/Trace control console. Agent registry, Agent Team orchestration, Channel integrations, MCP management, Skill management, Cron, TTS, and production RBAC should be planned as separate follow-up work after this foundation is verified.
