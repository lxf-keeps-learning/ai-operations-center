# Shared Operation Message Inbox Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a durable shared operation message pool where deep-answer tasks are queued, processed by database-backed workers, and manually claimed by one operator at a time.

**Architecture:** Keep `AiSession` as the single execution record and add an `operation_message` record for the human-review lifecycle. The report-chat request creates a queued task; a worker claims and runs the existing graph; the operation API exposes a shared inbox with atomic claim/release/resolve/retry actions. The first UI uses polling for reliable state refresh and keeps SSE only for active execution progress where applicable.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, MySQL-compatible row locking, existing LangGraph report-chat graph, Vue 3 + TypeScript, pytest.

## Global Constraints

- Use the existing API response envelope with `code`, `message`, `traceId`, and `data`.
- Do not introduce Redis, Celery, or another external queue in this iteration.
- Preserve existing `ReportChatMessage`, report context, trace, and evidence contracts.
- Do not overwrite the original user question, AI answer, or operator resolution note.
- A task must be claimed by only one worker or operator at a time.
- Existing unrelated working-tree changes must not be staged or modified.

## File Map

- Create `backend/app/operation_inbox/`: domain constants, SQLAlchemy model, repository, service, API schemas, API router, and worker entry point.
- Create `backend/alembic/versions/20260806_0001_create_operation_message.py`: `operation_message` table and indexes.
- Modify `backend/app/runtime/schemas/status.py`: add queued execution status and keep shared status constants.
- Modify `backend/app/report_chat_agent/repositories/chat_repository.py`: create queued runtime turns and expose worker-safe claim/complete/fail operations.
- Modify `backend/app/report_chat_agent/api/chat_api.py`: return an accepted task contract instead of coupling task creation to a long-running request.
- Modify `backend/app/main.py`: register the operation inbox router.
- Create `backend/tests/operation_inbox/`: repository, service, API, and concurrency tests.
- Modify `frontend/src/api/reportChat.ts`: add accepted-task and operation-inbox types/API calls.
- Create `frontend/src/api/operationInbox.ts`: list, summary, detail, claim, release, resolve, retry calls.
- Create `frontend/src/pages/operation/MessageInboxPage.vue`: shared tabs, polling, claim/release/resolve/retry actions, and detail drawer.
- Modify `frontend/src/router/index.ts`: register the operation inbox page.
- Modify `frontend/src/layouts/DefaultLayout.vue`: add the operation inbox navigation entry if the layout owns the menu.

---

### Task 1: Add explicit queue and operation-inbox state contracts

**Files:**
- Create: `backend/app/operation_inbox/__init__.py`
- Create: `backend/app/operation_inbox/status.py`
- Modify: `backend/app/runtime/schemas/status.py`
- Test: `backend/tests/operation_inbox/test_status.py`

**Interfaces:**
- Produce `AI_QUEUED`, `AI_RUNNING`, `AI_SUCCESS`, `AI_FAILED`, `AI_CANCELLED`, `AI_EXPIRED` constants.
- Produce `OP_AWAITING_REVIEW`, `OP_CLAIMED`, `OP_RESOLVED`, `OP_REOPENED`, `OP_FAILED` constants.
- Preserve existing `SESS_RUNNING`, `SESS_SUCCESS`, and `SESS_FAILED` values for existing callers.

- [ ] **Step 1: Write the failing tests**

```python
from app.operation_inbox.status import OP_AWAITING_REVIEW, OP_CLAIMED
from app.runtime.schemas.status import SESS_QUEUED


def test_queue_and_operation_statuses_are_stable() -> None:
    assert SESS_QUEUED == "queued"
    assert OP_AWAITING_REVIEW == "awaiting_review"
    assert OP_CLAIMED == "claimed"
```

- [ ] **Step 2: Run the focused test and verify it fails**

Run: `cd backend && PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/operation_inbox/test_status.py -q`
Expected: FAIL because the new constants do not exist.

- [ ] **Step 3: Implement the minimal constants**

Add the constants and status sets without changing existing string values or callers.

- [ ] **Step 4: Run the focused test and verify it passes**

Run the same command; expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/operation_inbox backend/app/runtime/schemas/status.py backend/tests/operation_inbox/test_status.py
git commit -m "feat: add operation inbox status contracts"
```

### Task 2: Add the operation message table and model

**Files:**
- Create: `backend/app/operation_inbox/models.py`
- Create: `backend/app/operation_inbox/models/__init__.py`
- Create: `backend/alembic/versions/20260806_0001_create_operation_message.py`
- Modify: `backend/alembic/env.py`
- Test: `backend/tests/operation_inbox/test_model.py`

**Interfaces:**
- Produce `OperationMessage` with `id`, `runtime_session_id`, `report_chat_message_id`, `report_id`, `priority`, `status`, `assignee_id`, `claimed_at`, `lease_expires_at`, `resolved_at`, `resolution_note`, `retry_count`, `error_message`, `created_at`, and `updated_at`.
- Add a unique index on `runtime_session_id` and indexes for `(status, priority, created_at)` and `(assignee_id, status)`.

- [ ] **Step 1: Write the failing model test**

```python
def test_operation_message_columns_are_present() -> None:
    from app.operation_inbox.models import OperationMessage

    assert OperationMessage.__tablename__ == "operation_message"
    assert "runtime_session_id" in OperationMessage.__table__.c
    assert "lease_expires_at" in OperationMessage.__table__.c
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd backend && PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/operation_inbox/test_model.py -q`
Expected: FAIL because the model is absent.

- [ ] **Step 3: Implement the model and migration**

Follow existing SQLAlchemy model and Alembic naming conventions. Import the model in `alembic/env.py` so autogeneration and metadata discovery include it. Use `String(64)` IDs, `BigInteger` for `report_id`, `Text` for notes/errors, JSON only where needed, and timezone-aware project helpers.

- [ ] **Step 4: Run model and migration checks**

Run: `cd backend && PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/operation_inbox/test_model.py -q`
Expected: PASS. Run `alembic check` against the configured test database if available; expected: no untracked model changes.

- [ ] **Step 5: Commit**

```bash
git add backend/app/operation_inbox/models.py backend/app/operation_inbox/models backend/alembic/versions/20260806_0001_create_operation_message.py backend/alembic/env.py backend/tests/operation_inbox/test_model.py
git commit -m "feat: add operation message persistence"
```

### Task 3: Implement atomic queue and operator-claim repository operations

**Files:**
- Create: `backend/app/operation_inbox/repository.py`
- Create: `backend/tests/operation_inbox/test_repository.py`
- Modify: `backend/app/report_chat_agent/repositories/chat_repository.py`

**Interfaces:**
- `enqueue_message(db, *, runtime_session_id, report_chat_message_id, report_id, priority=0) -> OperationMessage`.
- `claim_next_task(db, *, worker_id) -> OperationMessage | None`.
- `claim_for_operator(db, *, message_id, operator_id, lease_minutes=30) -> OperationMessage`.
- `release_for_operator(db, *, message_id, operator_id) -> OperationMessage`.
- `resolve_for_operator(db, *, message_id, operator_id, note) -> OperationMessage`.
- `requeue_expired_claims(db, *, now) -> int`.
- `list_messages(db, *, status=None, assignee_id=None, priority=None, offset=0, limit=50) -> list[OperationMessage]`.
- `count_by_status(db) -> dict[str, int]`.

- [ ] **Step 1: Write failing tests for duplicate enqueue and claim races**

Cover one unique task per runtime session, two operators claiming the same message with one success, releasing only by the assignee, and expired lease requeue.

```python
def test_only_one_operator_can_claim_same_message(db_session, inbox_repo):
    message = inbox_repo.create_review_message(db_session)
    first = inbox_repo.claim_for_operator(db_session, message.id, "operator-a")
    second = inbox_repo.try_claim_for_operator(db_session, message.id, "operator-b")
    assert first.assignee_id == "operator-a"
    assert second is None
```

- [ ] **Step 2: Run the repository tests to verify they fail**

Run: `cd backend && PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/operation_inbox/test_repository.py -q`
Expected: FAIL because repository operations are absent.

- [ ] **Step 3: Implement transaction-safe repository operations**

Use a transaction boundary around select-and-update. For task claiming, select the oldest highest-priority queued row with `with_for_update(skip_locked=True)`, then update it to running. For operator claim, use a conditional update or row lock requiring `status='awaiting_review'` and no assignee. Convert zero-row updates into a domain conflict result used by the API.

- [ ] **Step 4: Run repository tests and verify concurrency behavior**

Run the focused repository test; expected: PASS. Run the same tests against the project’s MySQL test database when available because SQLite does not reproduce `SKIP LOCKED` semantics.

- [ ] **Step 5: Commit**

```bash
git add backend/app/operation_inbox/repository.py backend/app/report_chat_agent/repositories/chat_repository.py backend/tests/operation_inbox/test_repository.py
git commit -m "feat: add atomic operation inbox claims"
```

### Task 4: Convert report-chat task creation into durable enqueueing

**Files:**
- Modify: `backend/app/report_chat_agent/repositories/chat_repository.py`
- Modify: `backend/app/report_chat_agent/service.py`
- Modify: `backend/app/report_chat_agent/api/chat_api.py`
- Modify: `backend/app/report_chat_agent/schemas/response.py`
- Modify: `frontend/src/api/reportChat.ts`
- Test: `backend/tests/report_chat_agent/test_queue_acceptance.py`

**Interfaces:**
- `enqueue_chat_message(session_id, report_id, question, user_id, trace_id) -> QueuedChatTask`.
- `QueuedChatTask` returns `trace_id`, `conversation_id`, `session_id`, `runtime_session_id`, `message_id`, `ai_status`, and `operation_status`.

- [ ] **Step 1: Write failing acceptance tests**

Assert that a valid report-chat request persists the user message, creates `AiSession(status='queued')`, creates one `OperationMessage(status='queued')`, and returns before graph execution. Assert a duplicate request with the same idempotency key does not create a second task.

- [ ] **Step 2: Run the acceptance test to verify it fails**

Run: `cd backend && PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/report_chat_agent/test_queue_acceptance.py -q`
Expected: FAIL because the current endpoint invokes the graph synchronously.

- [ ] **Step 3: Implement enqueue-only request behavior**

Keep content moderation and report/session validation in the request path. Persist the sanitized user question and task metadata, create the operation message, and return the accepted-task response. Do not call `graph.invoke` or `graph.astream` from the enqueue endpoint. Preserve the existing synchronous endpoint only if existing callers require it, and document the new queued path explicitly.

- [ ] **Step 4: Update frontend request types and run acceptance tests**

Make the frontend treat the response as an accepted task and poll task status rather than expecting an immediate answer. Run the focused backend test; expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/report_chat_agent backend/tests/report_chat_agent/test_queue_acceptance.py frontend/src/api/reportChat.ts
git commit -m "feat: enqueue report chat tasks"
```

### Task 5: Add the database-backed worker and recovery loop

**Files:**
- Create: `backend/app/operation_inbox/worker.py`
- Create: `backend/scripts/run_operation_worker.py`
- Modify: `backend/app/report_chat_agent/service.py`
- Modify: `backend/app/report_chat_agent/stream_service.py`
- Create: `backend/tests/operation_inbox/test_worker.py`

**Interfaces:**
- `OperationWorker(worker_id: str, poll_interval_seconds: float = 1.0, max_retries: int = 3)`.
- `run_once() -> bool` claims one queued task and processes it.
- `recover_stale_tasks(now) -> int` requeues expired running tasks or marks them failed.

- [ ] **Step 1: Write failing worker tests**

Cover no-work behavior, queued-to-running transition, successful graph completion to `success/awaiting_review`, graph failure to `failed`, retry count increment, and stale task recovery.

- [ ] **Step 2: Run worker tests to verify they fail**

Run: `cd backend && PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/operation_inbox/test_worker.py -q`
Expected: FAIL because the worker is absent.

- [ ] **Step 3: Implement one-task worker execution**

The worker opens a fresh database session per task, claims one task, reconstructs the existing report-chat state from persisted session/message/report IDs, invokes the existing graph, persists the assistant answer and trace, then transitions the operation message to `awaiting_review`. On exception, persist the error and either requeue or mark failed. Do not share SQLAlchemy sessions or LangGraph mutable state across tasks.

- [ ] **Step 4: Add recovery and executable entry point**

The script loops with bounded polling, handles SIGTERM by stopping after the current task, and runs stale-task recovery before polling. Configuration comes from explicit environment variables such as `OPERATION_WORKER_ID`, `OPERATION_WORKER_POLL_SECONDS`, and `OPERATION_WORKER_MAX_RETRIES`; do not repurpose existing global environment names.

- [ ] **Step 5: Run worker tests and commit**

Run the focused worker tests; expected: PASS.

```bash
git add backend/app/operation_inbox/worker.py backend/scripts/run_operation_worker.py backend/app/report_chat_agent/service.py backend/app/report_chat_agent/stream_service.py backend/tests/operation_inbox/test_worker.py
git commit -m "feat: process operation inbox tasks with worker"
```

### Task 6: Expose operation inbox APIs

**Files:**
- Create: `backend/app/operation_inbox/schemas.py`
- Create: `backend/app/operation_inbox/service.py`
- Create: `backend/app/operation_inbox/api.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/operation_inbox/test_api.py`

**Interfaces:**
- `GET /api/v1/operation/messages` with `status`, `assignee_id`, `priority`, `page`, and `page_size`.
- `GET /api/v1/operation/messages/{message_id}`.
- `POST /api/v1/operation/messages/{message_id}/claim`.
- `POST /api/v1/operation/messages/{message_id}/release`.
- `POST /api/v1/operation/messages/{message_id}/resolve` with `{ "note": "..." }`.
- `POST /api/v1/operation/messages/{message_id}/retry`.
- `GET /api/v1/operation/messages/summary`.

- [ ] **Step 1: Write failing API tests**

Test pagination, summary counts, successful claim, claim conflict, release/resolve ownership, retry of failed messages, and 404 for unknown IDs. Use the existing `ApiResponse` envelope and request-context user ID resolution.

- [ ] **Step 2: Run API tests to verify they fail**

Run: `cd backend && PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/operation_inbox/test_api.py -q`
Expected: FAIL because the router is absent.

- [ ] **Step 3: Implement schemas, service, and router**

Return operator-safe fields plus linked report/session/message identifiers. Translate claim conflicts to the project’s business error format. Do not allow a caller-provided operator ID to override authenticated context when a real user ID is available.

- [ ] **Step 4: Register the router and run API tests**

Register the router under the existing v1 prefix with an operation-inbox tag. Run the focused API tests; expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/operation_inbox backend/app/main.py backend/tests/operation_inbox/test_api.py
git commit -m "feat: expose operation inbox APIs"
```

### Task 7: Build the operator shared-inbox page

**Files:**
- Create: `frontend/src/api/operationInbox.ts`
- Create: `frontend/src/pages/operation/MessageInboxPage.vue`
- Modify: `frontend/src/router/index.ts`
- Modify: `frontend/src/layouts/DefaultLayout.vue`
- Verification: `frontend` TypeScript build and manual route-level behavior checks

**Interfaces:**
- `listOperationMessages(params) -> PaginatedOperationMessages`.
- `getOperationMessageSummary() -> OperationMessageSummary`.
- `claimOperationMessage(id)`, `releaseOperationMessage(id)`, `resolveOperationMessage(id, note)`, `retryOperationMessage(id)`.

- [ ] **Step 1: Add API types and define page-level behavior checks**

Define tabs `awaiting_review`, `mine`, `claimed`, `resolved`, and `failed`; verify during implementation that the selected tab maps to the correct API filter and that a claim conflict leaves the list consistent.

- [ ] **Step 2: Implement the API client**

Use the existing `request` helper, preserve the response envelope typing, and normalize pagination and summary data.

- [ ] **Step 3: Implement the page**

Show tab counts, priority, report title/ID, question summary, AI status, waiting time, assignee, and trace ID. Poll summary and the active list every 10 seconds while the page is visible. Provide claim, release, resolve-with-note, retry, and detail-drawer actions. Disable actions while pending and refresh after every mutation.

- [ ] **Step 4: Register navigation and run frontend verification**

Add the page to the operation route group and menu. Run `npm run build` from `frontend`; expected: PASS with no TypeScript errors.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/api/operationInbox.ts frontend/src/pages/operation/MessageInboxPage.vue frontend/src/router/index.ts frontend/src/layouts/DefaultLayout.vue
git commit -m "feat: add operator shared message inbox"
```

### Task 8: Run integration verification and document operations

**Files:**
- Modify: `backend/README.md`
- Modify: `frontend/README.md`
- Create: `backend/tests/operation_inbox/test_integration.py`

- [ ] **Step 1: Add integration coverage**

Exercise enqueue → worker → awaiting review → claim → resolve and enqueue → worker failure → retry. Assert the original report-chat message and runtime trace remain queryable.

- [ ] **Step 2: Run backend focused tests**

Run: `cd backend && PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/operation_inbox tests/report_chat_agent -q`
Expected: PASS.

- [ ] **Step 3: Run frontend build**

Run: `cd frontend && npm run build`
Expected: PASS.

- [ ] **Step 4: Run the full regression suite**

Run: `cd backend && PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q`
Expected: PASS, with any pre-existing unrelated failures reported separately.

- [ ] **Step 5: Document worker startup and operational recovery**

Document migration and worker commands, required environment variables, lease timeout, retry behavior, and how to inspect failed/stale tasks.

- [ ] **Step 6: Commit**

```bash
git add backend/README.md frontend/README.md backend/tests/operation_inbox/test_integration.py
git commit -m "test: verify operation inbox end to end"
```
