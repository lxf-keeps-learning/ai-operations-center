"""LangGraph 官方持久化组件的进程级生命周期管理。"""

from contextlib import AsyncExitStack, ExitStack, asynccontextmanager
from functools import lru_cache
import logging
from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.base import BaseStore
from langgraph.store.memory import InMemoryStore

from app.config.settings import settings

logger = logging.getLogger(__name__)


class ReportChatPersistence:
    def __init__(self) -> None:
        self._stack = ExitStack()
        self._initialized = False
        self.checkpointer: BaseCheckpointSaver
        self.store: BaseStore
        if settings.langgraph_postgres_url:
            from langgraph.checkpoint.postgres import PostgresSaver
            from langgraph.store.postgres import PostgresStore

            self.checkpointer = self._stack.enter_context(
                PostgresSaver.from_conn_string(settings.langgraph_postgres_url)
            )
            self.store = self._stack.enter_context(
                PostgresStore.from_conn_string(settings.langgraph_postgres_url)
            )
        else:
            self.checkpointer = InMemorySaver()
            self.store = InMemoryStore()

    @property
    def enabled(self) -> bool:
        return bool(settings.langgraph_postgres_url)

    def setup(self) -> None:
        if self._initialized:
            return
        if self.enabled:
            self.checkpointer.setup()
            self.store.setup()
        self._initialized = True

    def close(self) -> None:
        self._stack.close()


@lru_cache(maxsize=1)
def get_report_chat_persistence() -> ReportChatPersistence:
    return ReportChatPersistence()


def report_chat_persistence_status() -> dict[str, Any]:
    persistence = get_report_chat_persistence()
    return {
        "backend": "postgres" if persistence.enabled else "memory",
        "official_checkpointer": True,
        "official_store": True,
        "initialized": persistence._initialized,
    }


def prepare_sync_report_chat_graph(default_graph: Any) -> Any:
    """初始化持久化失败时降级为无记忆图，避免阻断报告回答。"""
    try:
        get_report_chat_persistence().setup()
        return default_graph
    except Exception:
        logger.exception("初始化 LangGraph 持久化失败，降级为无持久化报告问答")
        from app.report_chat_agent.graph import build_report_chat_graph
        return build_report_chat_graph()


@asynccontextmanager
async def async_report_chat_graph(fallback_graph: Any = None):
    """为 SSE 使用官方 AsyncPostgresSaver/AsyncPostgresStore。"""
    persistence = get_report_chat_persistence()
    if not persistence.enabled:
        if fallback_graph is None:
            from app.report_chat_agent.graph import report_chat_graph
            fallback_graph = report_chat_graph
        yield fallback_graph
        return

    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
    from langgraph.store.postgres.aio import AsyncPostgresStore
    from app.report_chat_agent.graph import build_report_chat_graph

    async with AsyncExitStack() as stack:
        checkpointer = await stack.enter_async_context(
            AsyncPostgresSaver.from_conn_string(settings.langgraph_postgres_url)
        )
        store = await stack.enter_async_context(
            AsyncPostgresStore.from_conn_string(settings.langgraph_postgres_url)
        )
        try:
            await checkpointer.setup()
            await store.setup()
            yield build_report_chat_graph(checkpointer=checkpointer, store=store)
        except Exception:
            logger.exception("初始化异步 LangGraph 持久化失败，降级为无持久化报告问答")
            yield build_report_chat_graph()
