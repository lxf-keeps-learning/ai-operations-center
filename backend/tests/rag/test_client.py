"""RagClient 单元测试。

与 app/runtime/llm/client.py 的测试风格一致，使用 monkeypatch 模拟 httpx。
测试重点：
  1. 正常返回结果。
  2. 返回空结果。
  3. HTTP 超时/连接失败/非 200。
  4. JSON 解析失败。
  5. 未配置 base_url 时跳过调用。
  6. 缺少 source_id 的结果被过滤。
"""

import json
from typing import Any

import httpx
import pytest

from app.config.settings import settings
from app.rag.client import RagClient
from app.rag.schemas import RagSearchFilters, RagSearchRequest


def _make_request() -> RagSearchRequest:
    return RagSearchRequest(
        query="缺陷处置流程",
        scene="essential_safety",
        top_k=3,
        filters=RagSearchFilters(doc_type=["制度", "标准"]),
    )


def _fake_response_json(status: int = 200, body: dict[str, Any] | None = None) -> httpx.Response:
    """构造一个模拟的 httpx.Response。"""
    content = json.dumps(body or {}).encode()
    return httpx.Response(status_code=status, content=content)


class TestRagClientSearch:
    """RagClient.search() 的各类场景测试。"""

    def test_unconfigured_url_returns_empty(self) -> None:
        client = RagClient(base_url="")
        resp = client.search(_make_request())
        assert resp.success is True
        assert resp.results == []
        assert resp.total == 0

    def test_default_client_reads_settings(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """未显式传参时，RagClient 从 settings 读取 URL、API Key 和 timeout。"""
        captured: dict[str, Any] = {}
        body = {
            "results": [
                {
                    "source_id": "DOC_001",
                    "document_title": "测试文档",
                    "content": "测试内容",
                }
            ]
        }

        def fake_post(self: httpx.Client, url: str, **kwargs: Any) -> httpx.Response:
            captured["url"] = url
            captured["headers"] = kwargs.get("headers", {})
            captured["json"] = kwargs.get("json", {})
            return _fake_response_json(200, body)

        monkeypatch.setattr(settings, "rag_search_url", "http://settings-rag:8000")
        monkeypatch.setattr(settings, "rag_search_api_key", "test-key")
        monkeypatch.setattr(settings, "rag_search_timeout_seconds", 3.0)
        monkeypatch.setattr(httpx.Client, "post", fake_post)

        client = RagClient()
        resp = client.search(_make_request())

        assert resp.success is True
        assert captured["url"] == "http://settings-rag:8000/api/rag/search"
        assert captured["headers"]["Authorization"] == "Bearer test-key"
        assert captured["json"]["query"] == "缺陷处置流程"

    def test_returns_results(self, monkeypatch: pytest.MonkeyPatch) -> None:
        body = {
            "results": [
                {
                    "source_id": "DOC_001",
                    "document_title": "测试文档",
                    "content": "测试内容",
                    "score": 0.95,
                    "metadata": {"doc_type": "制度"},
                },
                {
                    "source_id": "DOC_002",
                    "document_title": "标准文档",
                    "content": "标准内容",
                    "score": 0.85,
                    "metadata": {"doc_type": "标准"},
                },
            ]
        }

        def fake_post(*args: Any, **kwargs: Any) -> httpx.Response:
            return _fake_response_json(200, body)

        monkeypatch.setattr(httpx.Client, "post", fake_post)
        client = RagClient(base_url="http://mock-rag:8000")
        resp = client.search(_make_request())

        assert resp.success is True
        assert len(resp.results) == 2
        assert resp.total == 2
        assert resp.results[0].source_id == "DOC_001"
        assert resp.results[1].document_title == "标准文档"

    def test_returns_empty_results(self, monkeypatch: pytest.MonkeyPatch) -> None:
        body = {"results": []}

        def fake_post(*args: Any, **kwargs: Any) -> httpx.Response:
            return _fake_response_json(200, body)

        monkeypatch.setattr(httpx.Client, "post", fake_post)
        client = RagClient(base_url="http://mock-rag:8000")
        resp = client.search(_make_request())

        assert resp.success is True
        assert resp.results == []
        assert resp.total == 0

    def test_returns_no_results_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        body = {"message": "no results"}

        def fake_post(*args: Any, **kwargs: Any) -> httpx.Response:
            return _fake_response_json(200, body)

        monkeypatch.setattr(httpx.Client, "post", fake_post)
        client = RagClient(base_url="http://mock-rag:8000")
        resp = client.search(_make_request())

        assert resp.success is True
        assert resp.results == []

    def test_returns_non_dict(self, monkeypatch: pytest.MonkeyPatch) -> None:
        body = ["not", "a", "dict"]

        def fake_post(*args: Any, **kwargs: Any) -> httpx.Response:
            return _fake_response_json(200, body)

        monkeypatch.setattr(httpx.Client, "post", fake_post)
        client = RagClient(base_url="http://mock-rag:8000")
        resp = client.search(_make_request())

        assert resp.success is True
        assert resp.results == []

    def test_filters_result_without_source_id(self, monkeypatch: pytest.MonkeyPatch) -> None:
        body = {
            "results": [
                {"source_id": "DOC_001", "document_title": "有效", "content": "内容"},
                {"document_title": "无 source_id", "content": "应被过滤"},
            ]
        }

        def fake_post(*args: Any, **kwargs: Any) -> httpx.Response:
            return _fake_response_json(200, body)

        monkeypatch.setattr(httpx.Client, "post", fake_post)
        client = RagClient(base_url="http://mock-rag:8000")
        resp = client.search(_make_request())

        assert resp.success is True
        assert len(resp.results) == 1
        assert resp.results[0].source_id == "DOC_001"

    def test_sanitizes_malformed_result_fields(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """单条 RAG 结果字段不规范时，应清洗后返回，不让 Graph 崩溃。"""
        body = {
            "results": [
                {
                    "source_id": "DOC_001",
                    "document_title": 123,
                    "content": None,
                    "score": "not-a-number",
                    "metadata": "bad-metadata",
                }
            ]
        }

        def fake_post(*args: Any, **kwargs: Any) -> httpx.Response:
            return _fake_response_json(200, body)

        monkeypatch.setattr(httpx.Client, "post", fake_post)
        client = RagClient(base_url="http://mock-rag:8000")
        resp = client.search(_make_request())

        assert resp.success is True
        assert resp.results[0].document_title == "123"
        assert resp.results[0].content == ""
        assert resp.results[0].score is None
        assert resp.results[0].metadata == {}

    def test_timeout_returns_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def fake_post(*args: Any, **kwargs: Any) -> httpx.Response:
            msg = "connect timed out"
            raise httpx.TimeoutException(msg)

        monkeypatch.setattr(httpx.Client, "post", fake_post)
        client = RagClient(base_url="http://mock-rag:8000")
        resp = client.search(_make_request())

        assert resp.success is False
        assert resp.results == []
        assert "超时" in (resp.error_message or "")

    def test_connect_error_returns_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def fake_post(*args: Any, **kwargs: Any) -> httpx.Response:
            msg = "[Errno 8] Name or service not known"
            raise httpx.ConnectError(msg)

        monkeypatch.setattr(httpx.Client, "post", fake_post)
        client = RagClient(base_url="http://mock-rag:8000")
        resp = client.search(_make_request())

        assert resp.success is False
        assert resp.results == []
        assert "连接失败" in (resp.error_message or "")

    def test_http_error_returns_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def fake_post(*args: Any, **kwargs: Any) -> httpx.Response:
            raise httpx.HTTPError("generic HTTP error")

        monkeypatch.setattr(httpx.Client, "post", fake_post)
        client = RagClient(base_url="http://mock-rag:8000")
        resp = client.search(_make_request())

        assert resp.success is False
        assert resp.results == []
        assert "HTTP 请求异常" in (resp.error_message or "")

    def test_non_200_response_returns_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def fake_post(*args: Any, **kwargs: Any) -> httpx.Response:
            return _fake_response_json(500, {"error": "internal"})

        monkeypatch.setattr(httpx.Client, "post", fake_post)
        client = RagClient(base_url="http://mock-rag:8000")
        resp = client.search(_make_request())

        assert resp.success is False
        assert resp.results == []
        assert "HTTP 500" in (resp.error_message or "")

    def test_non_200_with_empty_body(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def fake_post(*args: Any, **kwargs: Any) -> httpx.Response:
            return _fake_response_json(503, {})

        monkeypatch.setattr(httpx.Client, "post", fake_post)
        client = RagClient(base_url="http://mock-rag:8000")
        resp = client.search(_make_request())

        assert resp.success is False
        assert resp.results == []

    def test_json_decode_error_returns_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        content = b"not json"

        def fake_post(*args: Any, **kwargs: Any) -> httpx.Response:
            return httpx.Response(status_code=200, content=content)

        monkeypatch.setattr(httpx.Client, "post", fake_post)
        client = RagClient(base_url="http://mock-rag:8000")
        resp = client.search(_make_request())

        assert resp.success is False
        assert resp.results == []
        assert "JSON 解析失败" in (resp.error_message or "")
