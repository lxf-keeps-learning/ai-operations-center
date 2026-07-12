"""Stream Service 单元测试：验证事件序列和节点顺序。"""

import json

from app.analysis_stream.event_emitter import SseEventEmitter
from app.operation_agent.schemas.request import OperationAnalyzeRequest
from app.operation_agent.stream_service import stream_operation_analysis


def _collect_events(request, run_id: str) -> list[dict]:
    """同步收集流式事件，返回解析后的事件列表。"""
    emitter = SseEventEmitter(run_id=run_id)
    collected: list[str] = []

    async def _run():
        async for event_str in stream_operation_analysis(request, emitter):
            collected.append(event_str)

    import anyio
    anyio.run(_run)

    # 解析 SSE 字符串为事件 dict
    events = []
    for ev in collected:
        event_type = ""
        data = {}
        for line in ev.strip().split("\n"):
            if line.startswith("event: "):
                event_type = line[7:]
            elif line.startswith("data: "):
                try:
                    data = json.loads(line[6:])
                except json.JSONDecodeError:
                    pass
        if event_type and data:
            events.append(data)
    return events


def test_event_log_contains_started_and_completed():
    """事件序列应包含 node_started 和 node_completed。"""
    request = OperationAnalyzeRequest(
        trigger_type="tab_analysis",
        domain="safety",
        time_dimension="month",
    )
    events = _collect_events(request, "test_event_log_002")

    event_types = {e["event_type"] for e in events}
    assert "node_started" in event_types
    assert "node_completed" in event_types
    assert "report_completed" in event_types


def test_node_order_matches_graph():
    """node_started 的顺序应与 Graph 节点一致。"""
    request = OperationAnalyzeRequest(
        trigger_type="tab_analysis",
        domain="safety",
    )
    events = _collect_events(request, "test_order_002")

    node_keys = [e["node_key"] for e in events if e["event_type"] == "node_started" and "node_key" in e]
    expected = [
        "init_context",
        "query_operation_data",
        "detect_abnormal",
        "analyze_reason",
        "generate_advice",
        "summary",
    ]
    assert node_keys == expected


def test_report_completed_contains_total_duration():
    """report_completed 应包含 total_duration_ms。"""
    request = OperationAnalyzeRequest(trigger_type="tab_analysis", domain="safety")
    events = _collect_events(request, "test_duration_001")

    report_events = [e for e in events if e["event_type"] == "report_completed"]
    assert len(report_events) == 1

    payload = report_events[0].get("payload", {})
    assert "total_duration_ms" in payload
    assert isinstance(payload["total_duration_ms"], int)
    assert payload["total_duration_ms"] > 0


def test_report_delta_reconstructs_completed_summary():
    """报告增量拼接结果必须与最终权威 summary 完全一致。"""
    request = OperationAnalyzeRequest(trigger_type="tab_analysis", domain="safety")
    events = _collect_events(request, "test_report_delta_001")

    deltas = [
        event.get("payload", {}).get("delta", "")
        for event in events
        if event["event_type"] == "report_delta"
    ]
    report_event = next(
        event for event in events if event["event_type"] == "report_completed"
    )

    assert len(deltas) > 1
    assert "".join(deltas) == report_event["payload"]["summary"]
    assert events.index(next(e for e in events if e["event_type"] == "report_delta")) \
        < events.index(report_event)


def test_stream_sequence_is_replayable():
    """事件应可按 sequence 完整回放。"""
    request = OperationAnalyzeRequest(trigger_type="tab_analysis", domain="business")
    events = _collect_events(request, "test_replay_sequence_001")

    sequences = [e["sequence"] for e in events]
    assert sequences == list(range(1, len(events) + 1))
    assert events[0]["event_type"] == "analysis_started"
    assert events[-1]["event_type"] == "stream_closed"


def test_node_completed_contains_duration():
    """节点完成事件应保留耗时，便于审计慢节点。"""
    request = OperationAnalyzeRequest(trigger_type="tab_analysis", domain="business")
    events = _collect_events(request, "test_node_duration_001")

    completed_events = [e for e in events if e["event_type"] == "node_completed"]
    assert completed_events
    assert all(isinstance(e.get("duration_ms"), int) for e in completed_events)
