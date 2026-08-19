"""SSE 防卡死泵：整体期限 + 空闲心跳 + 客户端断连取消。

职责：
  - 将 producer（Graph astream 等异步生成器）放入独立 Task 执行；
  - graph_timeout_seconds 到期 → 取消 producer Task，并调用 on_graph_timeout
    发送终止事件（只发一次）；
  - 空闲心跳：等待事件超过 heartbeat_interval_seconds 时发送心跳；
    若未配置心跳间隔，则超过 idle_timeout_seconds 触发 on_idle_timeout 终止；
  - overall_timeout_seconds 是外部总预算（硬兜底）：即使 producer 无法协作取消，
    泵也会在期限内收尾并发出终止事件；
  - 客户端断连（generator 被 aclose）→ 取消 producer Task 并清理资源，
    CancelledError 原样向上传播。

终止事件只发送一次的保证：
  producer 正常结束由 pump 直接停止；graph 超时 / 空闲超时 / 整体超时
  分别走对应回调，且回调后立即 break，不会重复。
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncGenerator, Callable, Iterator
from typing import Any

logger = logging.getLogger(__name__)

_CLOSED = object()


class SsePump:
    """事件泵：生产者产生 SSE 字符串，消费者按心跳/期限规则输出。"""

    def __init__(
        self,
        producer: Callable[[], AsyncGenerator[str, None]],
        *,
        graph_timeout_seconds: float,
        overall_timeout_seconds: float,
        idle_timeout_seconds: float,
        heartbeat_interval_seconds: float | None,
        heartbeat_sse: str,
        on_graph_timeout: Callable[[], list[str]],
        on_failure: Callable[[BaseException], list[str]] | None = None,
        on_idle_timeout: Callable[[], list[str]] | None = None,
        cleanup_grace_seconds: float = 2.0,
    ) -> None:
        self._producer = producer
        self._graph_timeout_seconds = graph_timeout_seconds
        self._overall_timeout_seconds = overall_timeout_seconds
        self._idle_timeout_seconds = idle_timeout_seconds
        self._heartbeat_interval_seconds = heartbeat_interval_seconds
        self._heartbeat_sse = heartbeat_sse
        self._on_graph_timeout = on_graph_timeout
        self._on_failure = on_failure
        self._on_idle_timeout = on_idle_timeout
        self._cleanup_grace_seconds = cleanup_grace_seconds

    async def run(self) -> AsyncGenerator[str, None]:
        queue: asyncio.Queue[tuple[str, Any]] = asyncio.Queue()

        async def _drive() -> None:
            try:
                async with asyncio.timeout(self._graph_timeout_seconds):
                    iterator = self._producer()
                    if asyncio.iscoroutine(iterator):
                        # producer 是协程函数时先 await 拿到异步生成器
                        iterator = await iterator
                    async for chunk in iterator:
                        await queue.put(("event", chunk))
            except TimeoutError:
                await queue.put(("timeout", None))
            except asyncio.CancelledError:
                await queue.put(("cancelled", None))
                raise
            except Exception as exc:  # noqa: BLE001 - 兜底失败事件
                await queue.put(("failure", exc))
            else:
                await queue.put(("closed", None))

        producer_task = asyncio.create_task(_drive())
        try:
            try:
                async with asyncio.timeout(self._overall_timeout_seconds):
                    while True:
                        item = await self._next_item(queue)
                        kind, payload = item
                        if kind == "heartbeat":
                            yield self._heartbeat_sse
                            continue
                        if kind == "event":
                            yield payload
                            continue
                        if kind == "closed":
                            break
                        if kind == "timeout":
                            for evt in self._on_graph_timeout():
                                yield evt
                            break
                        if kind == "idle_timeout":
                            if self._on_idle_timeout is not None:
                                for evt in self._on_idle_timeout():
                                    yield evt
                            break
                        if kind == "failure":
                            if self._on_failure is not None:
                                for evt in self._on_failure(payload):
                                    yield evt
                            break
                        if kind == "cancelled":
                            raise asyncio.CancelledError
            except asyncio.CancelledError:
                raise
            except TimeoutError:
                # 外部总预算兜底：即使 producer 未能在 graph 期限内结束也收尾。
                for evt in self._on_graph_timeout():
                    yield evt
        finally:
            producer_task.cancel()
            try:
                await asyncio.wait_for(
                    asyncio.shield(producer_task),
                    timeout=self._cleanup_grace_seconds,
                )
            except (asyncio.TimeoutError, asyncio.CancelledError):
                logger.warning("producer 任务未能在清理宽限期内退出，已放弃等待")
            except Exception:
                logger.debug("producer 任务清理异常", exc_info=True)

    async def _next_item(
        self,
        queue: asyncio.Queue[tuple[str, Any]],
    ) -> tuple[str, Any]:
        """等待下一条消息；心跳/空闲超时由本方法判定。"""
        wait_seconds = (
            self._heartbeat_interval_seconds
            if self._heartbeat_interval_seconds is not None
            else self._idle_timeout_seconds
        )
        try:
            return await asyncio.wait_for(queue.get(), timeout=wait_seconds)
        except TimeoutError:
            pass

        if self._heartbeat_interval_seconds is not None:
            # 心跳维持连接：空闲计时在收到业务事件或心跳时都会刷新，
            # 因此配置了心跳时不会触发空闲终止（空闲超时是心跳禁用时的唯一防护）。
            return ("heartbeat", None)
        # 心跳未配置：空闲超时即终止条件。
        return ("idle_timeout", None)
