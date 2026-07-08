"""RAG 检索服务的请求/响应数据结构。

本模块定义 Report Chat Graph 调用外部 RAG 时的数据契约。
重点是可追踪：每次 RAG 返回的 source_id、document_title、score 和 metadata
都要保留，以便 LLM 回答时生成 rag_source_refs。

边界说明（Sprint6）：
- 只定义调用结构，不做 Chunk、Embedding、向量库。
- RagSearchRequest 负责表达"Agent 要搜什么"。
- RagSearchResult 负责保留"搜到了什么、从哪来的"。
- RagSearchResponse 统一包装调用结果，支持失败标记。
"""

from typing import Any

from pydantic import BaseModel, Field


class RagSearchFilters(BaseModel):
    """RAG 检索的过滤条件。

    doc_type 控制知识库范围（制度/标准/案例/经验），由 BuildRagQueryNode
    根据用户问题和报告上下文构造；permission_scope 默认使用当前用户权限范围。
    """

    doc_type: list[str] = Field(
        default_factory=list,
        description="文档类型：制度、标准、案例、经验。由 ShouldUseRagNode 的分类决定",
    )
    permission_scope: str = Field(
        default="current_user_allowed",
        description="权限范围。默认当前用户可见范围，后续可扩展按业务域过滤",
    )
    scene: str | None = Field(
        default=None,
        description="业务场景。从 report_context.scene 中提取，如 essential_safety",
    )
    doc_ids: list[str] | None = Field(
        default=None,
        description="限定文档 ID 列表。当用户询问特定制度/规范时，可精确限定检索范围",
    )


class RagSearchRequest(BaseModel):
    """RAG 检索请求。

    由 BuildRagQueryNode 构造，核心是 query 必须融合报告锚点（scene + 异常项 + 关键词），
    不能只复制用户原问题。top_k 固定 5，第一版不做动态调整。
    """

    query: str = Field(
        description=(
            "检索查询文本。必须融合报告锚点构造，不能直接复制用户原问题。"
            "示例：'本质安全场景下，超期未处理缺陷的处置要求和整改流程'"
        ),
    )
    scene: str | None = Field(
        default=None,
        description="业务场景标识。BuildRagQueryNode 从 report_context.scene 提取",
    )
    top_k: int = Field(
        default=5,
        ge=1,
        le=50,
        description="返回结果数量。第一版固定 5，后续可根据 query 质量动态调整",
    )
    filters: RagSearchFilters = Field(
        default_factory=RagSearchFilters,
        description="检索过滤条件。控制 doc_type、permission_scope 等",
    )


class RagSearchResult(BaseModel):
    """单条 RAG 检索结果。

    每条结果必须带 source_id（知识片段唯一 ID）和 document_title（来源文档标题），
    这是回答可追踪的基础。score 和 metadata 作为辅助信息供 Answer Node 参考，
    但不能用于决策是否采纳——只要 source_id 存在就应纳入上下文，最终由 LLM 判断相关性。
    """

    source_id: str = Field(
        description="知识片段唯一 ID。用于回答中的 rag_source_refs 引用",
    )
    document_title: str = Field(
        description="来源文档标题。前端展示知识库依据时使用",
    )
    content: str = Field(
        description="知识片段内容。将进入 merged_context，作为 LLM 回答的补充依据",
    )
    score: float | None = Field(
        default=None,
        description="相关性得分。用于调试和后续重排序参考，第一版不使用分数过滤",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "额外元信息。如 doc_type、version、source、page_num 等，"
            "透传给前端知识库依据展示"
        ),
    )


class RagSearchResponse(BaseModel):
    """RAG 检索响应。

    统一包装调用结果，无论成功或失败都返回有效结构。success=False 时，
    CallRagNode 需要写 errors 并降级为仅使用报告 evidence 回答。
    """

    results: list[RagSearchResult] = Field(
        default_factory=list,
        description="检索结果列表。空列表表示 RAG 无结果，不编造",
    )
    total: int = Field(
        default=0,
        description="结果总数。用于调试和日志，Graph 层不依赖此值决策",
    )
    success: bool = Field(
        default=True,
        description="本次调用是否成功。false 时 error_message 应有值，上层应降级",
    )
    error_message: str | None = Field(
        default=None,
        description="失败时的错误信息。写入 State.errors 供链路追踪",
    )
