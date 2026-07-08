"""RAG 检索服务封装层。

对 Report Chat Graph 的 Node 层提供统一调用入口，不暴露 HTTP 细节。

分层职责：
  RagClient   — HTTP 调用，只处理网络和解析。
  RagService  — 业务封装，处理异常、兜底、日志。
  CallRagNode — Graph 节点，读取 State、调用 Service、写回 State。

核心设计原则：
  1. 所有异常在 Service 层被吞掉并转为 RagSearchResponse(success=False)。
  2. Service 层不抛出任何异常，Graph Node 调用时无需 try/except。
  3. 未配置 RAG_SEARCH_URL 时自动降级为 MockRagClient，保证演示/开发环境可感知 RAG 效果。
"""

import logging

from app.config.settings import settings
from app.rag.client import RagClient
from app.rag.schemas import RagSearchRequest, RagSearchResponse

logger = logging.getLogger(__name__)


class RagService:
    """RAG 检索服务，统一封装调用逻辑、异常处理和结果兜底。

    Graph 的 Node 层只调用 RagService.retrieve()，不关心底层是真实 Client 还是 Mock。
    测试时通过 client 参数注入 MockRagClient。
    """

    def __init__(self, client: RagClient | None = None) -> None:
        """初始化 RAG 服务。

        Args:
            client: RAG HTTP 客户端。不传时自动选择：
                    - RAG_SEARCH_URL 已配置 → 真实 RagClient
                    - RAG_SEARCH_URL 未配置 → MockRagClient（内置演示数据）
                    测试时可通过 MockRagClient 注入。
        """
        if client is not None:
            self._client = client
        elif settings.rag_search_url:
            self._client = RagClient(
                base_url=settings.rag_search_url,
                api_key=settings.rag_search_api_key,
                timeout_seconds=settings.rag_search_timeout_seconds,
            )
        else:
            from app.rag.mock_client import MockRagClient
            self._client = MockRagClient()
            logger.info("RAG_SEARCH_URL 未配置，使用 MockRagClient 返回演示数据。")

    def retrieve(self, request: RagSearchRequest) -> RagSearchResponse:
        """执行 RAG 检索，统一处理调用异常和兜底。

        这是 Graph Node 层的唯一调用入口。无论 RAG 服务是否可用，
        都返回有效的 RagSearchResponse，不会抛出异常。

        Args:
            request: 由 BuildRagQueryNode 构造的检索请求。

        Returns:
            RagSearchResponse:
                success=True  + results  — 正常返回，results 可能为空列表。
                success=False + error    — 调用失败，CallRagNode 应写 errors 并降级。
        """
        try:
            return self._client.search(request)
        except Exception as e:
            logger.exception("RAG 检索发生未知异常: %s", e)
            return RagSearchResponse(
                success=False,
                results=[],
                total=0,
                error_message=f"RAG 检索未知异常: {e}",
            )


# 全局单例，供 Graph CallRagNode 使用。
# 测试时通过 client 参数替换底层实现：RagService(client=MockRagClient())。
rag_service = RagService()
