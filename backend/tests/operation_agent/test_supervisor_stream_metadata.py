"""Supervisor routing metadata must be preserved in LangSmith configurations."""

import json
from types import SimpleNamespace

import pytest

from app.analysis_stream.event_emitter import SseEventEmitter
from app.operation_agent import service, stream_service
from app.operation_agent.schemas.request import OperationAnalyzeRequest


class _RecordingStreamGraph:
    def __init__(self) -> None:
        self.config: dict | None = None

    async def astream(self, _state, *, config, stream_mode):
        self.config = config
        assert stream_mode == ["values", "updates", "custom"]
        yield (
            "values",
            {
                "trace_id": "trace_stream_metadata",
                "active_agent": "maintenance",
                "final_answer": "maintenance report",
                "errors": [],
            },
        )


class _RecordingSyncGraph:
    def __init__(self) -> None:
        self.config: dict | None = None

    async def ainvoke(self, _state, *, config):
        self.config = config
        return {
            "trace_id": "trace_sync_metadata",
            "active_agent": "maintenance",
            "final_answer": "maintenance report",
            "errors": [],
        }


def _capture_langsmith_config(captured: list[dict]):
    def build_config(*, metadata, **_kwargs):
        captured.append(metadata)
        return {"metadata": metadata}

    return build_config


@pytest.mark.anyio
async def test_supervisor_route_is_in_sync_and_stream_langsmith_metadata(
    monkeypatch,
) -> None:
    request = OperationAnalyzeRequest(
        domain="maintenance",
        trigger_type="tab_analysis",
        force_refresh=True,
    )
    stream_graph = _RecordingStreamGraph()
    sync_graph = _RecordingSyncGraph()
    captured_metadata: list[dict] = []

    monkeypatch.setattr(stream_service, "operation_graph", stream_graph)
    monkeypatch.setattr(
        stream_service,
        "build_langsmith_config",
        _capture_langsmith_config(captured_metadata),
    )
    monkeypatch.setattr(stream_service, "_persist_event", lambda *_args: None)
    monkeypatch.setattr(stream_service, "get_session_local", lambda: lambda: _Session())
    monkeypatch.setattr(
        stream_service,
        "save_analysis_result",
        lambda *_args, **_kwargs: SimpleNamespace(id=1),
    )
    monkeypatch.setattr(service, "operation_graph", sync_graph)
    monkeypatch.setattr(
        service,
        "build_langsmith_config",
        _capture_langsmith_config(captured_metadata),
    )
    monkeypatch.setattr(service, "get_session_local", lambda: lambda: _Session())
    monkeypatch.setattr(
        service,
        "save_analysis_result",
        lambda *_args, **_kwargs: SimpleNamespace(id=1),
    )

    stream_events: list[dict] = []

    emitter = SseEventEmitter(run_id="trace_stream_metadata")
    async for event in stream_service.stream_operation_analysis(request, emitter):
        data_line = next(line for line in event.splitlines() if line.startswith("data: "))
        stream_events.append(json.loads(data_line.removeprefix("data: ")))

    await service.analyze_operation(request)

    assert stream_graph.config is not None
    assert sync_graph.config is not None
    report_completed = next(
        event for event in stream_events if event["event_type"] == "report_completed"
    )
    assert report_completed["payload"]["agent_key"] == "maintenance"
    assert captured_metadata == [
        {
            "domain": "maintenance",
            "trigger_type": "tab_analysis",
            "company_ref": None,
            "project_ref": None,
            "streaming": True,
            "agent_key": "maintenance",
        },
        {
            "domain": "maintenance",
            "trigger_type": "tab_analysis",
            "company_ref": None,
            "project_ref": None,
            "streaming": False,
            "agent_key": "maintenance",
        },
    ]


class _Session:
    def close(self) -> None:
        pass
