"""SSE formatter 单元测试。"""

import json

from app.analysis_stream.event_types import (
    EVENT_ANALYSIS_STARTED,
    EVENT_ANALYSIS_FAILED,
    EVENT_NODE_STARTED,
    EVENT_NODE_COMPLETED,
    EVENT_NODE_FAILED,
    EVENT_REPORT_COMPLETED,
    EVENT_STREAM_CLOSED,
    STATUS_RUNNING,
    STATUS_COMPLETED,
    STATUS_FAILED,
)
from app.analysis_stream.sse_formatter import format_event


class TestSseFormatter:
    def test_event_line_format(self):
        result = format_event(
            run_id="run_001",
            event_type=EVENT_NODE_STARTED,
            status=STATUS_RUNNING,
            message="数据加载中",
            node_key="load_data",
            node_name="数据加载",
        )
        lines = result.strip().split("\n")
        assert lines[0].startswith("event: node_started")

    def test_data_line_is_valid_json(self):
        result = format_event(
            run_id="run_001",
            event_type=EVENT_ANALYSIS_STARTED,
            status=STATUS_RUNNING,
            message="分析开始",
        )
        lines = result.strip().split("\n")
        assert lines[1].startswith("data:")
        payload = json.loads(lines[1][5:])
        assert payload["run_id"] == "run_001"
        assert payload["event_type"] == "analysis_started"
        assert payload["status"] == "running"

    def test_event_ends_with_double_newline(self):
        result = format_event(
            run_id="run_001",
            event_type=EVENT_NODE_COMPLETED,
            status=STATUS_COMPLETED,
            message="完成",
            node_key="load_data",
            node_name="数据加载",
        )
        assert result.endswith("\n\n")

    def test_chinese_message_serialized_correctly(self):
        result = format_event(
            run_id="run_001",
            event_type=EVENT_NODE_STARTED,
            status=STATUS_RUNNING,
            message="正在执行本质安全分析",
            node_key="detect_abnormal",
            node_name="异常识别",
        )
        lines = result.strip().split("\n")
        payload = json.loads(lines[1][5:])
        assert payload["message"] == "正在执行本质安全分析"

    def test_analysis_started_without_node_key(self):
        result = format_event(
            run_id="run_001",
            event_type=EVENT_ANALYSIS_STARTED,
            status=STATUS_RUNNING,
            message="分析任务已启动",
        )
        data = json.loads(result.strip().split("\n")[1][5:])
        assert "node_key" not in data
        assert data["event_type"] == "analysis_started"

    def test_report_completed_with_payload(self):
        result = format_event(
            run_id="run_001",
            event_type=EVENT_REPORT_COMPLETED,
            status=STATUS_COMPLETED,
            message="报告已生成",
            payload={"report_id": "r_001", "summary": "测试报告"},
        )
        data = json.loads(result.strip().split("\n")[1][5:])
        assert data["payload"]["report_id"] == "r_001"
        assert data["payload"]["summary"] == "测试报告"

    def test_node_failed_with_error_info(self):
        result = format_event(
            run_id="run_001",
            event_type=EVENT_NODE_FAILED,
            status=STATUS_FAILED,
            message="节点执行失败",
            node_key="analyze_reason",
            node_name="原因分析",
            error_code="LLM_TIMEOUT",
            error_message="LLM request timeout",
        )
        data = json.loads(result.strip().split("\n")[1][5:])
        assert data["error_code"] == "LLM_TIMEOUT"
        assert data["error_message"] == "LLM request timeout"
        assert data["node_key"] == "analyze_reason"

    def test_stream_closed_event(self):
        result = format_event(
            run_id="run_001",
            event_type=EVENT_STREAM_CLOSED,
            status=STATUS_COMPLETED,
            message="事件流已关闭",
        )
        data = json.loads(result.strip().split("\n")[1][5:])
        assert data["event_type"] == "stream_closed"

    def test_analysis_failed_event(self):
        result = format_event(
            run_id="run_001",
            event_type=EVENT_ANALYSIS_FAILED,
            status=STATUS_FAILED,
            message="整体分析失败",
            error_code="ANALYSIS_FAILED",
            error_message="Graph 执行异常",
        )
        data = json.loads(result.strip().split("\n")[1][5:])
        assert data["event_type"] == "analysis_failed"
        assert data["error_code"] == "ANALYSIS_FAILED"

    def test_each_event_contains_run_id(self):
        result = format_event(
            run_id="run_001",
            event_type=EVENT_NODE_STARTED,
            status=STATUS_RUNNING,
            message="测试",
            node_key="test",
            node_name="测试",
        )
        data = json.loads(result.strip().split("\n")[1][5:])
        assert data["run_id"] == "run_001"

    def test_event_id_is_generated(self):
        result = format_event(
            run_id="run_001",
            event_type=EVENT_ANALYSIS_STARTED,
            status=STATUS_RUNNING,
            message="开始",
        )
        data = json.loads(result.strip().split("\n")[1][5:])
        assert len(data["event_id"]) == 16

    def test_sequence_and_duration_are_serialized(self):
        result = format_event(
            run_id="run_001",
            event_type=EVENT_NODE_COMPLETED,
            status=STATUS_COMPLETED,
            message="完成",
            sequence=3,
            node_key="summary",
            node_name="报告汇总",
            duration_ms=128,
        )
        data = json.loads(result.strip().split("\n")[1][5:])
        assert data["sequence"] == 3
        assert data["duration_ms"] == 128
