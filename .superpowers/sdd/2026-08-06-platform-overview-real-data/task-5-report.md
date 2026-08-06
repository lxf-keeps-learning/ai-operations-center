# Task 5 Report — Frontend API adapters, filters, and message inbox

## Delivered

- Added `frontend/src/api/platform.ts` with typed `getPlatformOverview()` support for `/platform/overview`.
- Extended `frontend/src/api/operationInbox.ts` with typed message list/query/action shapes and claim, release, resolve, reopen, and retry adapters.
- Added `/platform/messages` backed by `MessageInboxPage.vue`; the platform sidebar now links to it with a live `RouterLink`.
- Added the message inbox’s pending (awaiting review + reopened), mine, all claimed, resolved, and failed tabs; loading, error, empty, manual refresh, ten-second polling, detail drawer, and all message actions are supported. The stable local operator is `operator_local`.
- Extended runtime adapters to forward session `status`, `date_from`, `date_to`, and `page_size`, and trace `session_id` plus existing filters.
- Added backend Session filtering through the API, service, and repository for `session_id`, `date_from`, and `date_to`; the end date includes its full calendar day.
- Added backend Trace `session_id` and `trace_id` filtering through the API, service, and repository.
- Updated Session and Trace pages to initialize filter controls from route query parameters and pass filter values to their API calls. Session now forwards `session_id` from the Message Inbox link; Trace ID is now sent to the backend instead of filtering already-loaded rows.
- The summary API accepts `assignee_id` and returns an unpaginated `mine` count while retaining every existing summary key. The “我领取的” tab renders that server-side count.
- The summary contract now also always includes `processing`, matching the frontend type and operation-message records created while AI work is still running.
- Added the compile-time `frontend/src/api/platform.test.ts` API contract assertion.

## TDD / validation evidence

1. `frontend/npm run type-check` initially exited zero before implementation because the root project-reference config does not include `src` files.
2. After adding the red compile-time contract, `cd frontend && npx vue-tsc -p tsconfig.app.json --noEmit` failed as expected: `Cannot find module './platform'`.
3. After implementation, the explicit app check passed: `cd frontend && npx vue-tsc -p tsconfig.app.json --noEmit`.
4. The required command passed: `cd frontend && npm run type-check`.
5. `cd frontend && npm run build` passed.
6. `git diff --check` passed.
7. `cd backend && .venv/bin/python -m pytest tests/runtime/test_runtime_list_filters.py tests/operation_inbox/test_api.py -q` passed: 7 tests cover Session/Trace filters and the inbox summary contract.

## Workspace context

- The existing platform pages, layout, App, and `/infra` routing changes are user workspace context in the directly preceding `feat: complete agent operations console` commit. They are required by the Task 5 frontend but are not restaged or modified by this follow-up.

## Limitations / concerns

- The frontend package has no test-runner script, so the API contract assertion is compile-time only.
- Build output warns that Node `20.13.1` is below Vite’s required `20.19+`/`22.12+`, and reports non-fatal Rolldown annotation warnings from `@vueuse/core` plus a large-chunk warning.
