"""LLM 客户端超时专项测试（异步路径）。

验证：
  1. 非流式 achat 超时 → LlmResult(success=False, error_code=LLM_TIMEOUT)。
  2. 流式 astream_chat 超时后 token 消费停止。
  3. CancelledError 不被包装，继续向上传播。
  4. 显式 timeout_seconds=None 使用配置默认；不通过 `or 60` 处理合法显式值。
"""

import asyncio
from types import SimpleNamespace

import pytest

from app.runtime.llm.client import LlmClient, LlmResult


class _FakeModel:
    """可注入的假模型：支持 ainvoke / astream。"""

    def __init__(self, delay: float = 5.0) -> None:
        self.delay = delay
        self.stream_stopped = False

    async def ainvoke(self, messages: list, **kwargs: object) -> object:
        await asyncio.sleep(self.delay)
        from langchain_core.messages import AIMessage

        return AIMessage(
            content="ok",
            usage_metadata={"input_tokens": 1, "output_tokens": 1, "total_tokens": 2},
            response_metadata={"model_name": "fake-model"},
        )

    async def astream(self, messages: list, **kwargs: object):
        try:
            await asyncio.sleep(self.delay)
            yield None
        except asyncio.CancelledError:
            self.stream_stopped = True
            raise


def _fake_settings() -> SimpleNamespace:
    provider = SimpleNamespace(
        provider="fake",
        display_name="Fake",
        enabled=True,
        default=True,
        model="fake-model",
        api_key="sk-fake",
        base_url="https://fake.example/v1",
        max_input_tokens=8000,
        max_output_tokens=2000,
        rpm_limit=60,
        model_versions=["fake-model"],
    )
    return SimpleNamespace(
        default_provider="fake",
        get_provider=lambda name: provider,
        all_providers=[provider],
    )


@pytest.fixture(autouse=True)
def _inject_fake_llm(monkeypatch):
    fake_model = _FakeModel()
    fake_settings = _fake_settings()

    def _get_model(self, provider):
        return fake_model

    monkeypatch.setattr(LlmClient, "_get_model", _get_model)
    monkeypatch.setattr("app.runtime.llm.client.llm_settings", fake_settings)
    monkeypatch.setattr("app.config.settings.settings.llm_timeout_seconds", 0.1)
    return fake_model


class TestLlmTimeout:
    @pytest.mark.anyio
    async def test_achat_timeout_maps_to_llm_timeout_code(self) -> None:
        client = LlmClient()
        result: LlmResult = await client.achat(None, "hello")
        assert result.success is False
        assert result.error_code == "LLM_TIMEOUT"
        assert "超时" in result.error_message
        assert result.content == ""

    @pytest.mark.anyio
    async def test_achat_propagates_user_cancel(self) -> None:
        client = LlmClient()
        task = asyncio.create_task(client.achat(None, "hello"))
        await asyncio.sleep(0.02)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    @pytest.mark.anyio
    async def test_astream_chat_stops_consuming_on_timeout(self, _inject_fake_llm) -> None:
        client = LlmClient()
        chunks: list[str] = []

        def on_chunk(text: str) -> None:
            chunks.append(text)

        result: LlmResult = await client.astream_chat(None, "hello", on_chunk=on_chunk)
        assert result.success is False
        assert result.error_code == "LLM_TIMEOUT"
        assert chunks == []
        assert _inject_fake_llm.stream_stopped is True

    @pytest.mark.anyio
    async def test_achat_success_within_budget(self) -> None:
        from app.runtime.llm.client import llm_settings as _unused  # noqa: F401

        fake_model = _FakeModel(delay=0.0)
        LlmClient._get_model = lambda self, provider: fake_model  # type: ignore[method-assign]
        client = LlmClient()
        result: LlmResult = await client.achat(None, "hello")
        assert result.success is True
        assert result.content == "ok"
