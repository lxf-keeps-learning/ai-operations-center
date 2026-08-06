# Task 3 Report — Operation-message API and producers

## Status

Implemented the operation-message API and integrated idempotent, best-effort
review-message production into completed and failed report-chat flows and
operation-analysis record persistence.

## Delivered

- Registered the operation inbox router under `/api/v1`.
- Added typed operator-action request schemas.
- Added list filtering for `status`, `assignee_id`, `priority`, and `report_id`.
- Added summary counts for `awaiting_review`, `claimed`, `resolved`, `reopened`,
  and `failed`.
- Added explicit envelope failures for claim conflicts and invalid state
  transitions.
- Added `reopen` and `retry` transitions; reopened work can be claimed again
  and retry resets failed work to `awaiting_review` while incrementing its retry
  count.
- Added `enqueue_for_review(...)`, backed by the unique runtime-session
  constraint, and used it as a best-effort producer. Inbox write failures are
  logged and do not change the already-completed AI result.
- Used report-chat runtime session/message/report identifiers when available;
  operation-analysis records use their trace ID as the runtime identifier and
  their persisted record ID as `report_id`.
- Supports operation-analysis messages without an `AiSession`: detail and
  action responses retain the message/report fields, expose the trace ID, and
  return `null` for AI-session-only fields.
- Reopen and retry require a non-empty operator identity at both the validated
  API boundary and repository boundary.

## TDD evidence

Added `test_api.py` and `test_producers.py` before the implementation. The
initial focused run failed during collection because `enqueue_for_review` did
not exist; the TestClient fixture also revealed an import-time optional
PostgreSQL checkpoint dependency, which was disabled in the test fixture so
the API contract could run against its in-memory SQLAlchemy database.

The review-fix regression tests first failed because no-session messages were
dropped by an inner join, the operation-analysis enqueue exception handler was
missing its `logging` import, and repository reopen/retry accepted an empty
operator ID. The minimal fixes were then verified green.

## Verification

Passed:

```text
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest \
  tests/operation_inbox/test_api.py tests/operation_inbox/test_producers.py \
  tests/operation_inbox/test_repository.py tests/operation_inbox/test_model.py \
  tests/operation_inbox/test_status.py tests/report_chat_agent/test_api_rag_response.py \
  tests/report_chat_agent/test_report_chat_nodes.py -q
# 37 passed, 1 warning

LANGGRAPH_POSTGRES_URL='' MCP_ENABLED=false PYTHONDONTWRITEBYTECODE=1 \
  .venv/bin/python -m pytest tests/operation_agent/test_operation_graph.py \
  tests/operation_agent/test_supervisor_stream_metadata.py -q
# 22 passed

git diff --check
# clean
```

## Concern

`tests/analysis_stream/test_analysis_stream_api.py::TestAnalysisStreamApi::test_stream_uses_real_graph_node_keys`
still fails because it expects the old fixed node order while the shared
worktree's pre-existing supervisor-routing changes emit `supervisor_route` and
agent-specific nodes. This is unrelated to Task 3; the run also logs expected
local MySQL connection failures from that API test's unoverridden persistence
path.
