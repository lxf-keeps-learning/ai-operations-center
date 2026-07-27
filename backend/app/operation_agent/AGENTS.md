# Repository Guidelines

## Project Structure & Module Organization

This directory contains the backend Operation Agent. `graph.py` defines the six-node LangGraph pipeline; `state.py` is the shared `TypedDict` contract. Keep orchestration in `service.py` and `stream_service.py`, HTTP handlers in `api/`, persistence behind `repositories/` and `services/`, and request/response DTOs in `schemas/`. Each graph step belongs in `nodes/`; prompt text belongs in `prompts/`, not inline Python strings. SQLAlchemy records live in `models/`. Package tests are in `backend/tests/operation_agent/test_operation_graph.py`; broader integration tests are under `backend/tests/`.

## Build, Test, and Development Commands

Run backend commands from the repository's `backend/` directory:

```bash
pip install -e '.[dev]'                 # install runtime and test dependencies
uvicorn app.main:app --reload           # serve the API locally
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest tests/operation_agent -q
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q
.venv/bin/python -m compileall app/operation_agent
.venv/bin/python scripts/debug_operation_agent.py
```

Use the repository virtual environment; system Python may lack packages such as `pymysql`. Apply database migrations with `.venv/bin/alembic upgrade head` when model or schema changes require them.

## Coding Style & Naming Conventions

Target Python 3.11+, use four-space indentation, type annotations, and a 100-character line limit. Follow the Ruff configuration in `pyproject.toml` and group imports as standard library, third-party, then `app.*`. Use `snake_case` for files, functions, and state fields; `PascalCase` for classes and Pydantic/SQLAlchemy models; `UPPER_SNAKE_CASE` for constants. Name graph nodes `<action>_node.py` and node callables `<action>_node`. Keep `OperationState` JSON-serializable and preserve the boundary between graph state, API schemas, and ORM models.

## Testing Guidelines

Tests use pytest, `pytest.mark.anyio` for async APIs, and `test_<behavior>` naming. Add focused tests for node output, state contracts, failure fallbacks, trace propagation, persistence/cache behavior, and API/SSE payloads. Mock LLM and external IOC calls so tests remain deterministic. No coverage threshold is configured; every behavior change should include a regression test and pass the focused suite before the full backend suite.

## Commit & Pull Request Guidelines

History follows Conventional Commit prefixes such as `feat:`, `fix:`, `refactor:`, and `chore:`; keep subjects concise and describe one logical change. Pull requests should explain the user-visible outcome, list affected graph nodes/contracts, note configuration or migration changes, and include exact verification commands and results. Link the relevant issue or Sprint document. Include screenshots only when frontend rendering changes; include representative SSE/API payloads when contracts change. Never commit `.env` secrets, API keys, database credentials, generated reports, or local caches.
