"""SseEventEmitter 单元测试。"""

import json

from app.analysis_stream.event_emitter import SseEventEmitter


class TestSseEventEmitter:
    def setup_method(self):
        self.emitter = SseEventEmitter(run_id="run_test_001")

    def _parse_data(self, sse_str: str) -> dict:
        lines = sse_str.strip().split("\n")
        return json.loads(lines[1][5:])

    def test_analysis_started(self):
        result = self.emitter.emit_analysis_started("本质安全分析开始")
        data = self._parse_data(result)
        assert data["event_type"] == "analysis_started"
        assert data["status"] == "running"
        assert data["run_id"] == "run_test_001"
        assert data["message"] == "本质安全分析开始"

    def test_node_started(self):
        result = self.emitter.emit_node_started(
            node_key="load_data",
            node_name="数据加载",
            message="数据采集中",
        )
        data = self._parse_data(result)
        assert data["event_type"] == "node_started"
        assert data["status"] == "running"
        assert data["node_key"] == "load_data"
        assert data["node_name"] == "数据加载"

    def test_node_completed(self):
        result = self.emitter.emit_node_completed(
            node_key="detect_abnormal",
            node_name="异常识别",
            message="异常识别完成",
        )
        data = self._parse_data(result)
        assert data["event_type"] == "node_completed"
        assert data["status"] == "completed"
        assert data["node_key"] == "detect_abnormal"

    def test_node_failed(self):
        result = self.emitter.emit_node_failed(
            node_key="analyze_reason",
            node_name="原因分析",
            error_code="LLM_TIMEOUT",
            error_message="LLM request timeout",
        )
        data = self._parse_data(result)
        assert data["event_type"] == "node_failed"
        assert data["status"] == "failed"
        assert data["node_key"] == "analyze_reason"
        assert data["error_code"] == "LLM_TIMEOUT"
        assert data["error_message"] == "LLM request timeout"

    def test_report_completed(self):
        result = self.emitter.emit_report_completed(
            message="报告已生成",
            payload={"summary": "测试报告内容"},
        )
        data = self._parse_data(result)
        assert data["event_type"] == "report_completed"
        assert data["status"] == "completed"
        assert data["payload"]["summary"] == "测试报告内容"

    def test_analysis_failed(self):
        result = self.emitter.emit_analysis_failed(
            message="分析失败",
            error_code="GRAPH_ERROR",
            error_message="Graph 执行异常",
        )
        data = self._parse_data(result)
        assert data["event_type"] == "analysis_failed"
        assert data["status"] == "failed"
        assert data["error_code"] == "GRAPH_ERROR"

    def test_stream_closed(self):
        result = self.emitter.emit_stream_closed()
        data = self._parse_data(result)
        assert data["event_type"] == "stream_closed"
        assert data["status"] == "completed"

    def test_heartbeat(self):
        result = self.emitter.emit_heartbeat()
        data = self._parse_data(result)
        assert data["event_type"] == "heartbeat"

    def test_every_event_has_run_id(self):
        events = [
            self.emitter.emit_analysis_started(),
            self.emitter.emit_node_started("a", "A", ""),
            self.emitter.emit_node_completed("a", "A", ""),
            self.emitter.emit_report_completed(),
            self.emitter.emit_analysis_failed(),
            self.emitter.emit_stream_closed(),
        ]
        for event_str in events:
            data = self._parse_data(event_str)
            assert data["run_id"] == "run_test_001"

    def test_every_event_is_valid_sse(self):
        result = self.emitter.emit_node_started("test", "测试", "测试中")
        assert result.startswith("event: node_started\n")
        assert "\n\n" in result
        lines = result.strip().split("\n")
        assert len(lines) == 2  # event line + data line

    def test_sequence_increases_in_emit_order(self):
        events = [
            self._parse_data(self.emitter.emit_analysis_started()),
            self._parse_data(self.emitter.emit_node_started("a", "A", "")),
            self._parse_data(self.emitter.emit_node_completed("a", "A", "")),
            self._parse_data(self.emitter.emit_stream_closed()),
        ]
        assert [event["sequence"] for event in events] == [1, 2, 3, 4]
