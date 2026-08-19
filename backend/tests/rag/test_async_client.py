"""RAG 异步客户端超时与取消测试。"""

import asyncio

import httpx
import pytest

from app.rag.client import RagClient
from app.rag.schemas import RagSearchRequest, RagSearchResponse


def _request() -> RagSearchRequest:
    return RagSearchRequest(query="本质安全", scene="essential_safety", top_k=3)


def _client_with_transport(handler, timeout: float = 0.5) -> RagClient:
    transport = httpx.MockTransport(handler)
    client = RagClient(base_url="http://fake-rag")
    client.timeout_seconds = timeout
    client._transport = transport
    return client


class TestRagAsyncClient:
    @pytest.mark.anyio
    async def test_asearch_timeout_returns_failure(self) -> None:
        async def _slow(request, **kwargs):
            await asyncio.sleep(5)
            return httpx.Response(200, json={"results": []})

        client = _client_with_transport(_slow, timeout=0.1)
        resp: RagSearchResponse = await client.asearch(_request())
        assert resp.success is False
        assert "超时" in (resp.error_message or "")

    @pytest.mark.anyio
    async def test_asearch_cancellation_propagates(self) -> None:
        """用户取消 asearch 任务 → CancelledError 继续向上传播，不吞掉。"""
        cancelled = False

        async def _slow(request, **kwargs):
            try:
                await asyncio.sleep(5)
            except asyncio.CancelledError:
                nonlocal cancelled
                cancelled = True
                raise
            return httpx.Response(200, json={"results": []})

        client = _client_with_transport(_slow, timeout=5.0)
        task = asyncio.create_task(client.asearch(_request()))
        await asyncio.sleep(0.05)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert cancelled is True

    @pytest.mark.anyio
    async def test_asearch_success(self) -> None:
        def _ok(request, **kwargs):
            return httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "source_id": "DOC_1",
                            "document_title": "制度",
                            "content": "内容",
                            "score": 0.9,
                        }
                    ]
                },
            )

        client = _client_with_transport(_ok)
        resp: RagSearchResponse = await client.asearch(_request())
        assert resp.success is True
        assert len(resp.results) == 1

    @pytest.mark.anyio
    async def test_asearch_http_error_degrades(self) -> None:
        def _err(request, **kwargs):
            return httpx.Response(500, text="boom")

        client = _client_with_transport(_err)
        resp: RagSearchResponse = await client.asearch(_request())
        assert resp.success is False
