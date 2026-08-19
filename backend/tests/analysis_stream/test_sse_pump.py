"""SSE 防卡死专项测试（SsePump）。

验证：
  1. 30 秒无业务事件触发心跳（可配置短间隔），不误触发终止。
  2. 客户端断连（generator aclose）→ producer 任务被取消。
  3. 整体 Graph 期限超时 → 调用 on_graph_timeout，终止事件只发一次。
  4. 正常完成不误触发 timeout。
  5. 空闲超时（无心跳间隔配置）→ on_idle_timeout 终止。
"""

import asyncio

import pytest

from app.analysis_stream.sse_pump import SsePump


def _heartbeat() -> str:
    return "event: heartbeat\ndata: {}\n\n"


class TestSsePump:
    @pytest.mark.anyio
    async def test_idle_emits_heartbeat_without_false_timeout(self) -> None:
        timeout_events: list[str] = []

        async def producer():
            await asyncio.sleep(0.3)
            yield "event: done\ndata: {}\n\n"

        pump = SsePump(
            producer,
            graph_timeout_seconds=5.0,
            overall_timeout_seconds=6.0,
            idle_timeout_seconds=0.25,
            heartbeat_interval_seconds=0.1,
            heartbeat_sse=_heartbeat(),
            on_graph_timeout=lambda: ["event: timeout\ndata: {}\n\n"],
        )
        events = [e async for e in pump.run()]
        heartbeats = [e for e in events if "heartbeat" in e]
        assert heartbeats, "空闲期间必须发送心跳"
        assert not any("timeout" in e for e in events)
        assert "event: done" in "".join(events)

    @pytest.mark.anyio
    async def test_graph_timeout_cancels_producer_and_fires_once(self) -> None:
        cancelled = False

        async def producer():
            nonlocal cancelled
            try:
                while True:
                    await asyncio.sleep(0.05)
            except asyncio.CancelledError:
                cancelled = True
                raise

        pump = SsePump(
            producer,
            graph_timeout_seconds=0.2,
            overall_timeout_seconds=0.4,
            idle_timeout_seconds=30.0,
            heartbeat_interval_seconds=1.0,
            heartbeat_sse=_heartbeat(),
            on_graph_timeout=lambda: ["event: timeout\ndata: {}\n\n"],
        )
        events = [e async for e in pump.run()]
        assert cancelled is True, "Graph 超时后 producer 任务必须被取消"
        assert events.count("event: timeout\ndata: {}\n\n") == 1, "终止事件只能发一次"

    @pytest.mark.anyio
    async def test_client_disconnect_cancels_producer(self) -> None:
        """generator 被 aclose（客户端断连）→ producer 收到 CancelledError。"""
        producer_cancelled = False
        producer_done = False

        async def producer():
            nonlocal producer_cancelled, producer_done
            try:
                while True:
                    await asyncio.sleep(0.05)
            except asyncio.CancelledError:
                producer_cancelled = True
                raise
            finally:
                producer_done = True

        pump = SsePump(
            producer,
            graph_timeout_seconds=30.0,
            overall_timeout_seconds=31.0,
            idle_timeout_seconds=1.0,
            heartbeat_interval_seconds=1.0,
            heartbeat_sse=_heartbeat(),
            on_graph_timeout=lambda: ["event: timeout\ndata: {}\n\n"],
        )
        gen = pump.run()
        await gen.__anext__()  # 启动 producer
        await gen.aclose()
        assert producer_cancelled is True
        assert producer_done is True

    @pytest.mark.anyio
    async def test_normal_completion_no_timeout_events(self) -> None:
        async def producer():
            yield "event: a\ndata: {}\n\n"
            yield "event: b\ndata: {}\n\n"

        pump = SsePump(
            producer,
            graph_timeout_seconds=5.0,
            overall_timeout_seconds=6.0,
            idle_timeout_seconds=0.5,
            heartbeat_interval_seconds=0.2,
            heartbeat_sse=_heartbeat(),
            on_graph_timeout=lambda: ["event: timeout\ndata: {}\n\n"],
        )
        events = [e async for e in pump.run()]
        joined = "".join(events)
        assert "event: a" in joined
        assert "event: b" in joined
        assert "timeout" not in joined

    @pytest.mark.anyio
    async def test_idle_timeout_fires_when_heartbeat_disabled(self) -> None:
        """心跳间隔未配置时，空闲超时是唯一防护，应触发 on_idle_timeout。"""
        idle_fired = False

        async def producer():
            await asyncio.sleep(5)

        def on_idle():
            nonlocal idle_fired
            idle_fired = True
            return ["event: idle_timeout\ndata: {}\n\n"]

        pump = SsePump(
            producer,
            graph_timeout_seconds=10.0,
            overall_timeout_seconds=11.0,
            idle_timeout_seconds=0.2,
            heartbeat_interval_seconds=None,
            heartbeat_sse="",
            on_graph_timeout=lambda: [],
            on_idle_timeout=on_idle,
        )
        events = [e async for e in pump.run()]
        assert idle_fired is True
        assert "event: idle_timeout" in "".join(events)

    @pytest.mark.anyio
    async def test_producer_failure_emits_on_failure_events(self) -> None:
        async def producer():
            yield "event: a\ndata: {}\n\n"
            raise RuntimeError("boom")

        pump = SsePump(
            producer,
            graph_timeout_seconds=5.0,
            overall_timeout_seconds=6.0,
            idle_timeout_seconds=0.5,
            heartbeat_interval_seconds=0.2,
            heartbeat_sse=_heartbeat(),
            on_graph_timeout=lambda: [],
            on_failure=lambda exc: ["event: failed\ndata: {}\n\n"],
        )
        events = [e async for e in pump.run()]
        joined = "".join(events)
        assert "event: a" in joined
        assert "event: failed" in joined

    @pytest.mark.anyio
    async def test_overall_timeout_is_hard_backstop(self) -> None:
        """即使 producer 无法被取消（不可协作），整体期限也必须收尾。"""

        async def producer():
            try:
                while True:
                    await asyncio.sleep(0.02)
            except asyncio.CancelledError:
                raise

        pump = SsePump(
            producer,
            graph_timeout_seconds=100.0,
            overall_timeout_seconds=0.3,
            idle_timeout_seconds=30.0,
            heartbeat_interval_seconds=1.0,
            heartbeat_sse=_heartbeat(),
            on_graph_timeout=lambda: ["event: timeout\ndata: {}\n\n"],
        )
        events = [e async for e in pump.run()]
        assert events.count("event: timeout\ndata: {}\n\n") == 1
