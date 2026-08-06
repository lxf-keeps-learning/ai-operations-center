# Platform Overview Real Data Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the `/platform` overview page’s static metrics and Session rows with real backend data, add the project-designed shared operation message inbox, and make every metric navigate to the corresponding filtered list.

**Architecture:** Add a backend platform read service that aggregates `AiSession`, LLM `AiTrace`, and `OperationMessage` data into one overview response. Add the durable operation-message model, repository, service, and list/state APIs required by the existing shared-inbox design. Update Vue API adapters and platform pages to render the aggregate response, parse query filters, and navigate through typed route links.

**Tech Stack:** FastAPI, SQLAlchemy 2, Alembic, Pydantic, pytest, Vue 3, TypeScript, Vue Router 4, existing `ApiResponse` envelope.

## Global Constraints

- Preserve existing Runtime Session, Trace, Graph, and Report Chat response fields and routes.
- Use the existing `{ code, message, traceId, success, data }` response envelope.
- Use `app.utils.timezone` for local-day boundaries; do not compare local dates using UTC string slicing.
- Count tokens only from `AiTrace.span_type == "llm"`; never sum non-LLM spans.
- Treat `queued` and `running` as running tasks; treat `awaiting_review` and `reopened` as pending operation messages.
- Return numeric zero and an empty list when no records exist; do not retain static demo values as production fallbacks.
- Do not introduce Redis, Celery, a new cache, or a new frontend state library.
- Existing unrelated working-tree modifications must not be staged, reformatted, reverted, or included in commits.
- Every implementation change starts with a failing test and ends with the focused test passing before refactoring.

---

### Task 1: Define overview and operation-inbox status contracts

**Files:**
- Create: `backend/app/platform/__init__.py`
- Create: `backend/app/platform/schemas/__init__.py`
- Create: `backend/app/platform/schemas/overview_schema.py`
- Create: `backend/app/operation_inbox/__init__.py`
- Create: `backend/app/operation_inbox/status.py`
- Modify: `backend/app/runtime/schemas/status.py`
- Test: `backend/tests/platform/test_overview_schema.py`
- Test: `backend/tests/operation_inbox/test_status.py`

**Interfaces:**
- `OverviewMetrics`: `today_requests`, `running_tasks`, `pending_messages`, `failed_tasks`, `total_tokens`, `agent_success_rate`, `average_response_ms`.
- `OverviewSession`: `id`, `conversation_id`, `title`, `agent`, `channel`, `runs`, `total_tokens`, `status`, `updated_at`.
- `PlatformOverviewResponse`: `metrics: OverviewMetrics`, `recent_sessions: list[OverviewSession]`.
- Status constants: `SESS_QUEUED = "queued"`, `OP_AWAITING_REVIEW = "awaiting_review"`, `OP_CLAIMED = "claimed"`, `OP_RESOLVED = "resolved"`, `OP_REOPENED = "reopened"`, `OP_FAILED = "failed"`.

- [ ] **Step 1: Write the failing schema and status tests**

```python
from app.operation_inbox.status import OP_AWAITING_REVIEW, OP_REOPENED
from app.platform.schemas.overview_schema import OverviewMetrics, PlatformOverviewResponse
from app.runtime.schemas.status import SESS_QUEUED


def test_overview_response_accepts_zero_metrics_and_empty_sessions() -> None:
    result = PlatformOverviewResponse(
        metrics=OverviewMetrics(
            today_requests=0,
            running_tasks=0,
            pending_messages=0,
            failed_tasks=0,
            total_tokens=0,
            agent_success_rate=0,
            average_response_ms=0,
        ),
        recent_sessions=[],
    )
    assert result.metrics.total_tokens == 0


def test_overview_status_contracts_are_stable() -> None:
    assert SESS_QUEUED == "queued"
    assert OP_AWAITING_REVIEW == "awaiting_review"
    assert OP_REOPENED == "reopened"
```

- [ ] **Step 2: Run the focused tests and verify they fail**

Run: `cd backend && PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/platform/test_overview_schema.py tests/operation_inbox/test_status.py -q`

Expected: FAIL because the new schema and status modules do not exist.

- [ ] **Step 3: Implement the minimal contracts**

Use existing `IocBaseModel` conventions, keep response field names snake_case for the current frontend adapter, and add `queued` to the execution status set without changing existing status strings.

- [ ] **Step 4: Run the focused tests and verify they pass**

Run the same pytest command; expected: PASS.

- [ ] **Step 5: Commit only the task files**

```bash
git add backend/app/platform backend/app/operation_inbox backend/app/runtime/schemas/status.py backend/tests/platform/test_overview_schema.py backend/tests/operation_inbox/test_status.py
git commit -m "feat: define platform overview contracts"
```

### Task 2: Add durable operation-message persistence and read queries

**Files:**
- Create: `backend/app/operation_inbox/models.py`
- Create: `backend/app/operation_inbox/repository.py`
- Create: `backend/app/operation_inbox/service.py`
- Create: `backend/alembic/versions/20260806_0003_create_operation_message.py`
- Modify: `backend/alembic/env.py`
- Test: `backend/tests/operation_inbox/test_model.py`
- Test: `backend/tests/operation_inbox/test_repository.py`

**Interfaces:**
- `OperationMessage` table `operation_message` with `id`, `runtime_session_id`, `report_chat_message_id`, `report_id`, `priority`, `status`, `assignee_id`, `claimed_at`, `lease_expires_at`, `resolved_at`, `resolution_note`, `retry_count`, `error_message`, `created_at`, `updated_at`.
- `OperationMessageRepository.enqueue(db, *, runtime_session_id, report_chat_message_id=None, report_id=None, priority=0, status="awaiting_review") -> OperationMessage`.
- `OperationMessageRepository.list(db, *, status=None, assignee_id=None, priority=None, report_id=None, offset=0, limit=50) -> list[OperationMessage]`.
- `OperationMessageRepository.count_by_status(db) -> dict[str, int]`.
- `OperationMessageRepository.get_by_id(db, message_id) -> OperationMessage | None`.
- `OperationMessageService.list_messages(...)`, `.summary(...)`, `.enqueue(...)` return Pydantic response models.

- [ ] **Step 1: Write failing model and repository tests**

Cover required columns, the unique runtime-session association, status filtering, priority ordering, report filtering, and counts for `awaiting_review`, `reopened`, `claimed`, `resolved`, and `failed`.

```python
def test_operation_message_has_unique_runtime_session_index() -> None:
    from app.operation_inbox.models import OperationMessage

    assert OperationMessage.__tablename__ == "operation_message"
    assert "runtime_session_id" in OperationMessage.__table__.c
    assert any(index.unique for index in OperationMessage.__table__.indexes if "runtime" in index.name)
```

- [ ] **Step 2: Run the focused tests and verify they fail**

Run: `cd backend && PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/operation_inbox/test_model.py tests/operation_inbox/test_repository.py -q`

Expected: FAIL because the model and repository are absent.

- [ ] **Step 3: Implement the model, Alembic migration, and metadata import**

Use the project’s `Base`, `now_local`, string IDs, nullable foreign identifiers, and indexes for `(status, priority, created_at)`, `(assignee_id, status)`, `report_id`, and `runtime_session_id`. Import the model in `backend/alembic/env.py`. Set the migration `down_revision` to the actual current Alembic head discovered immediately before implementation rather than assuming a numeric filename order.

- [ ] **Step 4: Implement repository read/enqueue operations**

Make enqueue idempotent by first looking up `runtime_session_id`; return the existing row instead of inserting a duplicate. Order list results by priority descending then created time ascending. Use `count` queries grouped by status for summary data.

- [ ] **Step 5: Run the focused tests and verify they pass**

Run the same pytest command; expected: PASS. If a configured MySQL test database is available, run the migration and model tests against it as a second check.

- [ ] **Step 6: Commit only the task files**

```bash
git add backend/app/operation_inbox backend/alembic/env.py backend/alembic/versions/20260806_0003_create_operation_message.py backend/tests/operation_inbox/test_model.py backend/tests/operation_inbox/test_repository.py
git commit -m "feat: persist operation inbox messages"
```

### Task 3: Add operation-message API and producer integration

**Files:**
- Create: `backend/app/operation_inbox/schemas.py`
- Create: `backend/app/operation_inbox/api.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/report_chat_agent/repositories/chat_repository.py`
- Modify: `backend/app/report_chat_agent/service.py`
- Modify: `backend/app/operation_agent/services/record_service.py`
- Test: `backend/tests/operation_inbox/test_api.py`
- Test: `backend/tests/operation_inbox/test_producers.py`

**Interfaces:**
- `GET /api/v1/operation/messages`: accepts `status`, `assignee_id`, `priority`, `report_id`, `page`, and `page_size`; returns `ApiResponse[list[OperationMessageResponse]]`.
- `GET /api/v1/operation/messages/summary`: returns `ApiResponse[OperationMessageSummary]` with `awaiting_review`, `claimed`, `resolved`, `reopened`, and `failed` counts.
- `POST /api/v1/operation/messages/{message_id}/claim`: conditionally changes `awaiting_review`/`reopened` to `claimed` for the supplied operator.
- `POST /api/v1/operation/messages/{message_id}/release`: changes the operator’s `claimed` message back to `awaiting_review`.
- `POST /api/v1/operation/messages/{message_id}/resolve`: changes the operator’s `claimed` message to `resolved` and stores a resolution note.
- `POST /api/v1/operation/messages/{message_id}/reopen`: changes `resolved` to `reopened`.
- `POST /api/v1/operation/messages/{message_id}/retry`: changes `failed` to `awaiting_review` and increments `retry_count`.
- `enqueue_for_review(...)`: called after a completed or failed runtime/report task that requires operator attention; failures are logged and do not change the AI task result.

- [ ] **Step 1: Write failing API and producer tests**

Use `TestClient(create_app())` with an overridden `get_db` and an in-memory SQLAlchemy database. Assert the response envelope, status filtering, summary counts, conditional claim conflict, and idempotent producer behavior for one runtime session.

```python
def test_summary_counts_pending_review_messages(client, seeded_messages):
    response = client.get("/api/v1/operation/messages/summary")
    assert response.status_code == 200
    assert response.json()["data"]["awaiting_review"] == 2
    assert response.json()["data"]["reopened"] == 1
```

- [ ] **Step 2: Run the tests and verify they fail**

Run: `cd backend && PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/operation_inbox/test_api.py tests/operation_inbox/test_producers.py -q`

Expected: FAIL because the routes, schemas, and producer hook are absent.

- [ ] **Step 3: Implement API schemas and routes**

Follow existing `ApiResponse` and `AppException` patterns. Use a stable business error for missing messages, invalid transitions, and claim conflicts. Keep operator identity explicit in the request body until authentication provides a shared identity dependency.

- [ ] **Step 4: Integrate idempotent producer hooks**

Call the inbox service from existing report-chat and operation-record completion/failure paths using the already available runtime session, report/message, status, and trace identifiers. Do not convert existing synchronous execution into a worker in this overview scope; the inbox record represents the human-review lifecycle of a completed/failed task and remains independent from the AI execution status.

- [ ] **Step 5: Run the focused tests and verify they pass**

Run the same pytest command; expected: PASS. Run the existing report-chat and operation-agent API tests to verify no response contract changed.

- [ ] **Step 6: Commit only the task files**

```bash
git add backend/app/operation_inbox backend/app/main.py backend/app/report_chat_agent/repositories/chat_repository.py backend/app/report_chat_agent/service.py backend/app/operation_agent/services/record_service.py backend/tests/operation_inbox
git commit -m "feat: expose operation inbox APIs"
```

### Task 4: Implement the platform overview aggregation API

**Files:**
- Create: `backend/app/platform/repositories/overview_repository.py`
- Create: `backend/app/platform/services/overview_service.py`
- Create: `backend/app/platform/api.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/platform/test_overview_service.py`
- Test: `backend/tests/platform/test_overview_api.py`

**Interfaces:**
- `OverviewService.get_overview(db, *, now: datetime | None = None, recent_limit: int = 10) -> PlatformOverviewResponse`.
- `GET /api/v1/platform/overview` returns `ApiResponse[PlatformOverviewResponse]`.
- Repository helpers: `count_today_sessions`, `count_running_sessions`, `count_today_failed_sessions`, `sum_today_llm_tokens`, `get_success_rate`, `get_average_response_ms`, `list_recent_sessions`.

- [ ] **Step 1: Write failing service tests with fixed local time**

Seed sessions before/inside/after the local-day boundary, queued/running/success/failed records, traces with both `llm` and non-LLM spans, and sessions with missing timing fields. Assert exact values for all seven metrics and the ten-row recent-session limit.

```python
def test_overview_uses_llm_tokens_and_excludes_other_spans(db_session):
    seed_session_and_traces(db_session, llm_total=120, graph_total=999)
    result = overview_service.get_overview(db_session, now=FIXED_LOCAL_NOW)
    assert result.metrics.total_tokens == 120
```

- [ ] **Step 2: Run service tests and verify they fail**

Run: `cd backend && PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/platform/test_overview_service.py -q`

Expected: FAIL because the repository and service are absent.

- [ ] **Step 3: Implement local-day boundaries and aggregate queries**

Derive `[start_of_day, start_of_next_day)` from `now_local()` or the injected `now`. Use SQL aggregates for counts and sums. Calculate response duration from `finished_at - started_at` only for terminal successful/failed sessions with both timestamps. Calculate success rate from successful and failed terminal sessions only. Join recent sessions to conversations and traces without changing existing model fields.

- [ ] **Step 4: Implement API serialization and route registration**

Return ISO timestamps and frontend-ready strings/integers through the platform schema. Register the platform router under the existing `/api/v1` prefix without changing the legacy runtime router.

- [ ] **Step 5: Run service and API tests and verify they pass**

Run: `cd backend && PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/platform/test_overview_service.py tests/platform/test_overview_api.py -q`

Expected: PASS. Then run the existing Runtime API tests; expected: PASS.

- [ ] **Step 6: Commit only the task files**

```bash
git add backend/app/platform backend/app/main.py backend/tests/platform
git commit -m "feat: add platform overview aggregation API"
```

### Task 5: Add frontend API adapters, filters, and message list page

**Files:**
- Create: `frontend/src/api/platform.ts`
- Create: `frontend/src/api/operationInbox.ts`
- Create: `frontend/src/pages/platform/MessageInboxPage.vue`
- Modify: `frontend/src/api/runtime.ts`
- Modify: `frontend/src/pages/platform/SessionListPage.vue`
- Modify: `frontend/src/pages/platform/TraceListPage.vue`
- Modify: `frontend/src/router/index.ts`
- Modify: `frontend/src/layouts/PlatformLayout.vue`
- Test: `frontend/src/api/platform.test.ts`
- Test: `frontend/src/pages/platform/platformNavigation.test.ts`

**Interfaces:**
- `getPlatformOverview(): Promise<PlatformOverview>`.
- `listOperationMessages(params): Promise<OperationMessage[]>`.
- `getOperationMessageSummary(): Promise<OperationMessageSummary>`.
- `claimOperationMessage`, `releaseOperationMessage`, `resolveOperationMessage`, `reopenOperationMessage`, `retryOperationMessage` use the API paths from Task 3.
- `listRuntimeSessions(params)` accepts `status`, `date_from`, `date_to`, and `page_size` while preserving existing calls.
- `listRuntimeTraces(params)` accepts `session_id` in addition to existing filters.

- [ ] **Step 1: Write failing frontend adapter/navigation tests**

Assert the overview adapter targets `/platform/overview`, serializes the response shape, and route definitions include `/platform/messages`. Assert that the sidebar item is a `RouterLink` and not an unavailable button.

- [ ] **Step 2: Run the focused frontend tests/type check and verify the new assertions fail**

Run: `cd frontend && npm run type-check`

Expected: FAIL on missing types, API adapter, or message route. If the repository has no test runner configured, keep these checks as type-level tests and document that limitation in the implementation handoff.

- [ ] **Step 3: Implement typed API adapters and query parsing**

Use the existing `request` helper and `ApiResponse` unwrapping. Update Session and Trace pages to initialize filters from `useRoute().query` and send them to the existing endpoints. Keep filtering server-side for counts and list consistency.

- [ ] **Step 4: Implement the message inbox page**

Create tabs for pending (`awaiting_review` + `reopened`), my claimed, all claimed, resolved, and failed messages. Add loading/error/empty states, refresh/polling, claim/release/resolve/reopen/retry actions, and a detail drawer showing Session, Report, priority, status, assignee, timestamps, error, and resolution note.

- [ ] **Step 5: Register the route and enable navigation**

Register `/platform/messages` with `PlatformLayout`, update active-route matching, and point the “待处理消息” sidebar entry to it with no “待开发” badge.

- [ ] **Step 6: Run the focused frontend check and verify it passes**

Run: `cd frontend && npm run type-check`; expected: PASS.

- [ ] **Step 7: Commit only the task files**

```bash
git add frontend/src/api/platform.ts frontend/src/api/operationInbox.ts frontend/src/api/runtime.ts frontend/src/pages/platform/MessageInboxPage.vue frontend/src/pages/platform/SessionListPage.vue frontend/src/pages/platform/TraceListPage.vue frontend/src/router/index.ts frontend/src/layouts/PlatformLayout.vue frontend/src/api/platform.test.ts frontend/src/pages/platform/platformNavigation.test.ts
git commit -m "feat: add platform operation inbox navigation"
```

### Task 6: Replace the platform overview with real data and clickable metrics

**Files:**
- Modify: `frontend/src/pages/platform/IndexPage.vue`
- Test: `frontend/src/pages/platform/IndexPage.test.ts`

**Interfaces:**
- Page state: `overview: Ref<PlatformOverview | null>`, `loading`, `error`, and `activeFilter`.
- Metric definition: label, icon/tone, formatted value, optional detail, and `to: RouteLocationRaw` generated from current overview/date context.
- `loadOverview()` calls `getPlatformOverview()` and preserves the previous successful response while a refresh is in flight.

- [ ] **Step 1: Write failing component tests**

Cover rendering API-returned values, seven metric labels, recent Session rows from the response, loading and error/retry states, and the exact route targets for each metric.

```ts
it('renders real metrics and links them to filtered lists', async () => {
  mockGetPlatformOverview.mockResolvedValue(fixtureOverview)
  const wrapper = mount(PlatformOverview)
  await flushPromises()
  expect(wrapper.text()).toContain('今日请求数')
  expect(wrapper.text()).toContain('128')
  expect(wrapper.find('a[href="/platform/messages?status=awaiting_review"]').exists()).toBe(true)
})
```

- [ ] **Step 2: Run the component test/type check and verify it fails**

Run: `cd frontend && npm run type-check`

Expected: FAIL because the page still uses hard-coded arrays and does not expose the new links/types.

- [ ] **Step 3: Implement the minimal data-driven page**

Remove the static `sessions` array and hard-coded metric values. Load the overview on mount, render API values with stable formatting (`toLocaleString`, `%`, `ms`, and compact Token units), and show an error with a retry button. Keep the existing overview/usage tabs; the usage tab may link to the real Trace list until a separate usage chart is required.

- [ ] **Step 4: Implement metric navigation**

Use `RouterLink` for all seven metric cards. Route today requests and failures to Session filters, running tasks to a status query covering queued/running, pending messages to `/platform/messages?status=awaiting_review`, Token usage to LLM Trace filters, Agent success rate to `/platform/agents`, and average response time to completed Session filters. Ensure cards remain keyboard accessible and do not rely on click-only article handlers.

- [ ] **Step 5: Implement real recent Session rendering**

Map `recent_sessions` into the existing table shape, retain all/running/failed local filters, display the API status labels in Chinese, and link the Session row detail actions to the existing Session/Trace/Graph pages.

- [ ] **Step 6: Run focused checks and verify they pass**

Run: `cd frontend && npm run type-check && npm run build`; expected: PASS. Run the component/navigation tests if a test runner is available; expected: PASS.

- [ ] **Step 7: Commit only the task files**

```bash
git add frontend/src/pages/platform/IndexPage.vue frontend/src/pages/platform/IndexPage.test.ts
git commit -m "feat: connect platform overview to real metrics"
```

### Task 7: Run regression verification and inspect the final diff

**Files:**
- No new production files.
- Test: `backend/tests/operation_inbox/`, `backend/tests/platform/`, existing Runtime/Report Chat tests.
- Test: frontend type check and build.

- [ ] **Step 1: Run focused backend tests**

Run: `cd backend && PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/platform tests/operation_inbox -q`

Expected: PASS.

- [ ] **Step 2: Run affected backend regressions**

Run: `cd backend && PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/runtime tests/report_chat_agent tests/operation_agent -q`

Expected: PASS with existing API response contracts unchanged.

- [ ] **Step 3: Run frontend verification**

Run: `cd frontend && npm run type-check && npm run build`

Expected: PASS with no TypeScript or Vite errors.

- [ ] **Step 4: Inspect scope and working-tree safety**

Run: `git diff --check` and `git status --short`.

Confirm only the intended task files are staged in each feature commit and all pre-existing user modifications remain unstaged/unmodified. Do not run reset, checkout, clean, or broad formatting commands.

- [ ] **Step 5: Record the final verification result**

Summarize the endpoint, page routes, test commands, and any environment-dependent checks that could not run. Do not claim completion without the command output confirming the relevant checks.
