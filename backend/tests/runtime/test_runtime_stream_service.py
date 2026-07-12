"""RuntimeService Native Streaming 集成契约测试。"""

import json
from types import SimpleNamespace

import anyio

from app.runtime.runtime_service import RuntimeService


class _MockGraph:
    def __init__(self, events: list[tuple[str, object]]) -> None:
        self._events = events

    async def astream(self, *_args, **_kwargs):
        for event in self._events:
            yield event


def _collect(monkeypatch, events: list[tuple[str, object]]) -> list[dict]:
    monkeypatch.setattr(
        "app.runtime.runtime_service.runtime_graph",
        _MockGraph(events),
    )
    raw_events: list[str] = []

    async def run() -> None:
        async for raw in RuntimeService().chat_stream(
            db=SimpleNamespace(),
            user_id="tester",
            message="你好",
        ):
            raw_events.append(raw)

    anyio.run(run)
    return [
        json.loads(next(line for line in raw.splitlines() if line.startswith("data: "))[6:])
        for raw in raw_events
    ]


def test_runtime_stream_uses_graph_events_and_completes(monkeypatch) -> None:
    events = _collect(monkeypatch, [
        ("custom", {"kind": "llm_token", "token": "你"}),
        ("custom", {"kind": "llm_token", "token": "好"}),
        ("values", {
            "conversation": SimpleNamespace(id="conv_001"),
            "session_id": "session_001",
            "trace_id": "trace_001",
            "answer": "你好",
        }),
    ])

    assert [event.get("delta") for event in events if "delta" in event] == ["你", "好"]
    assert [event["answer"] for event in events if "answer" in event] == ["你好"]


def test_runtime_stream_failure_closes_once(monkeypatch) -> None:
    class _FailedGraph:
        async def astream(self, *_args, **_kwargs):
            yield ("custom", {"kind": "llm_token", "token": "部分"})
            raise RuntimeError("graph failed")

    monkeypatch.setattr("app.runtime.runtime_service.runtime_graph", _FailedGraph())
    raw_events: list[str] = []

    async def run() -> None:
        async for raw in RuntimeService().chat_stream(
            db=SimpleNamespace(), user_id="tester", message="你好",
        ):
            raw_events.append(raw)

    anyio.run(run)
    event_types = [
        next(line[7:] for line in raw.splitlines() if line.startswith("event: "))
        for raw in raw_events
    ]
    assert event_types == ["message_started", "token", "message_failed", "stream_closed"]
