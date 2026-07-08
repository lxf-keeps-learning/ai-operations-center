"""调用外部 RAG 服务，将检索结果写入 State。

职责边界（Sprint6）：
  只负责调用 RAG、解析结果、写入 State，不构造 query，不生成回答。

运行时机：紧接在 BuildRagQueryNode 之后，此时 State 中已有：
  - need_rag=True
  - rag_query（RagSearchRequest 格式的查询请求）

核心设计原则：
  1. 如果 need_rag=False，直接跳过，不调用任何服务。
  2. 通过 RagService.retrieve() 调用外部 RAG，不直接操作 HTTP。
  3. 所有异常由 RagService 层消化，Node 层面无需 try/except。
  4. RAG 无结果时不编造，RAG 失败时不阻塞 Graph。
  5. 每次调用都写 errors 记录，便于链路追踪。
"""

import logging

from app.rag.schemas import RagSearchRequest, RagSearchResponse
from app.rag.service import rag_service
from app.report_chat_agent.state import ReportChatState

logger = logging.getLogger(__name__)


def call_rag_node(state: ReportChatState) -> ReportChatState:
    """调用外部 RAG 服务，将检索结果写入 State。

    该 Node 不生成最终回答，只负责获取 RAG 检索结果并写入：
      - rag_results
      - rag_source_refs
      - used_rag
      - errors（失败时记录）

    Args:
        state: 当前 State，应包含 need_rag 和 rag_query。

    Returns:
        更新了 rag_results、rag_source_refs、used_rag 的 State。
    """
    errors: list[dict] = state.get("errors", [])
    need_rag = state.get("need_rag", False)
    rag_query_raw = state.get("rag_query", {})

    # 不需要 RAG 时直接跳过。
    if not need_rag:
        state["rag_results"] = []
        state["rag_source_refs"] = []
        state["rag_sources"] = []
        state["used_rag"] = False
        state["errors"] = errors
        return state

    # rag_query 为空或无效时，记录错误并降级。
    query_str = (rag_query_raw or {}).get("query", "").strip()
    if not query_str:
        errors.append({
            "node": "call_rag",
            "message": "rag_query 为空，跳过 RAG 调用。",
        })
        state["rag_results"] = []
        state["rag_source_refs"] = []
        state["rag_sources"] = []
        state["used_rag"] = False
        state["errors"] = errors
        return state

    # 构造 RagSearchRequest 并调用服务。
    request = _build_request(rag_query_raw)
    response = _do_retrieve(request)

    state["rag_query"] = rag_query_raw

    if response.success and response.results:
        # 正常返回结果。
        rag_results = _results_to_dicts(response)
        state["rag_results"] = rag_results
        state["rag_source_refs"] = [r.source_id for r in response.results]
        state["rag_sources"] = rag_results
        state["used_rag"] = True
        logger.info(
            "RAG 检索成功: query=%s, results=%s",
            query_str[:60], len(response.results),
        )
    elif response.success and not response.results:
        # RAG 返回空结果，不编造。
        errors.append({
            "node": "call_rag",
            "message": "RAG 检索无结果，跳过知识库补充。",
            "detail": {"query": query_str[:60]},
        })
        state["rag_results"] = []
        state["rag_source_refs"] = []
        state["rag_sources"] = []
        state["used_rag"] = False
        logger.info("RAG 检索无结果: query=%s", query_str[:60])
    else:
        # RAG 服务调用失败，降级。
        err_msg = response.error_message or "RAG 服务调用失败"
        errors.append({
            "node": "call_rag",
            "message": err_msg,
            "detail": {"query": query_str[:60]},
        })
        state["rag_results"] = []
        state["rag_source_refs"] = []
        state["rag_sources"] = []
        state["used_rag"] = False
        logger.warning("RAG 检索失败: %s", err_msg)

    state["errors"] = errors
    return state


def _build_request(rag_query_raw: dict) -> RagSearchRequest:
    """从 State 中的 rag_query 字典构建 RagSearchRequest。"""
    filters_raw = rag_query_raw.get("filters", {}) or {}
    return RagSearchRequest(
        query=rag_query_raw.get("query", ""),
        scene=rag_query_raw.get("scene"),
        top_k=rag_query_raw.get("top_k", 5),
        filters={
            "doc_type": filters_raw.get("doc_type", []),
            "permission_scope": filters_raw.get("permission_scope", "current_user_allowed"),
            "scene": filters_raw.get("scene"),
        },
    )


def _do_retrieve(request: RagSearchRequest) -> RagSearchResponse:
    """执行 RAG 检索，支持测试时通过依赖注入替换底层 Client。"""
    return rag_service.retrieve(request)


def _results_to_dicts(response: RagSearchResponse) -> list[dict]:
    """将 RagSearchResult 列表转为字典列表，方便存入 State。"""
    return [
        {
            "source_id": r.source_id,
            "document_title": r.document_title,
            "content": r.content,
            "score": r.score,
            "metadata": r.metadata,
        }
        for r in response.results
    ]
