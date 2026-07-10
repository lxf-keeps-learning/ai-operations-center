"""SSE Stream API 集成测试。"""

import json

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


class TestAnalysisStreamApi:
    def test_stream_endpoint_returns_200(self):
        response = client.post(
            "/api/v1/operation/analyze/stream",
            json={"domain": "safety"},
        )
        assert response.status_code == 200

    def test_stream_content_type_is_event_stream(self):
        response = client.post(
            "/api/v1/operation/analyze/stream",
            json={"domain": "safety"},
        )
        assert "text/event-stream" in response.headers.get("content-type", "")

    def test_stream_contains_analysis_started(self):
        response = client.post(
            "/api/v1/operation/analyze/stream",
            json={"domain": "safety"},
        )
        assert "analysis_started" in response.text

    def test_stream_contains_node_started(self):
        response = client.post(
            "/api/v1/operation/analyze/stream",
            json={"domain": "safety"},
        )
        assert "node_started" in response.text

    def test_stream_contains_node_completed(self):
        response = client.post(
            "/api/v1/operation/analyze/stream",
            json={"domain": "safety"},
        )
        assert "node_completed" in response.text

    def test_stream_contains_report_completed(self):
        response = client.post(
            "/api/v1/operation/analyze/stream",
            json={"domain": "safety"},
        )
        assert "report_completed" in response.text

    def test_stream_contains_stream_closed(self):
        response = client.post(
            "/api/v1/operation/analyze/stream",
            json={"domain": "safety"},
        )
        assert "stream_closed" in response.text

    def test_stream_report_completed_has_payload(self):
        trace_id = "trace_stream_contract_001"
        response = client.post(
            "/api/v1/operation/analyze/stream",
            headers={"X-Trace-Id": trace_id},
            json={"domain": "safety"},
        )
        assert response.headers["X-Trace-Id"] == trace_id
        # 提取 report_completed 事件
        blocks = response.text.strip().split("\n\n")
        for block in blocks:
            if "event: report_completed" in block:
                data_line = [l for l in block.split("\n") if l.startswith("data:")]
                if data_line:
                    payload = json.loads(data_line[0][5:])
                    assert payload["run_id"] == trace_id
                    assert "payload" in payload
                    assert payload["payload"]["trace_id"] == trace_id
                    assert payload["payload"]["status"] in {"success", "partial", "failed"}
                    return
        pytest.fail("report_completed 事件未找到")

    def test_stream_rejects_invalid_contract_values(self):
        response = client.post(
            "/api/v1/operation/analyze/stream",
            json={"domain": "unsupported", "time_dimension": "hour"},
        )

        assert response.status_code == 422
        payload = response.json()
        assert payload["success"] is False

    def test_stream_uses_real_graph_node_keys(self):
        response = client.post(
            "/api/v1/operation/analyze/stream",
            json={"domain": "safety"},
        )
        data_items = []
        for block in response.text.strip().split("\n\n"):
            data_line = [line for line in block.split("\n") if line.startswith("data:")]
            if data_line:
                data_items.append(json.loads(data_line[0][5:]))

        node_keys = [
            item.get("node_key")
            for item in data_items
            if item.get("event_type") == "node_started"
        ]
        assert node_keys == [
            "init_context",
            "query_operation_data",
            "detect_abnormal",
            "analyze_reason",
            "generate_advice",
            "summary",
        ]
