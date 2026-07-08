"""RAG 本地 Mock 客户端。

用于开发和单元测试，不发起真实 HTTP 调用。
数据来源为内存中的 mock_data，可直接验证 RagService 和后续 Node 层行为。

与 integrations/ioc/mock_client.py 模式一致：
  - 不调用数据库、不调用 LLM、不做业务分析。
  - 只模拟外部 RAG API 的数据访问契约。
"""

from app.rag.client import RagClient
from app.rag.schemas import RagSearchRequest, RagSearchResponse, RagSearchResult

# Mock 知识库数据：制度、标准、案例、规范四类。
MOCK_RAG_DOCUMENTS: list[dict] = [
    {
        "source_id": "DOC_REG_001",
        "document_title": "本质安全隐患治理规范",
        "content": "对于超期未处理缺陷，应按照隐患等级进行闭环整改。一般隐患由车间主任负责，"
        "重大隐患由安全总监负责，特大隐患由企业主要负责人挂牌督办。整改完成后需进行验收确认。",
        "score": 0.92,
        "metadata": {"doc_type": "制度", "version": "2026", "source": "安全管理制度库"},
    },
    {
        "source_id": "DOC_STD_002",
        "document_title": "GB/T 34567-2026 生产过程安全标准",
        "content": "生产过程中的安全隐患应当建立分级管理制度。对于可能导致人身伤害的重大隐患，"
        "应在发现后24小时内启动整改流程，整改方案需经安全管理部门审批。",
        "score": 0.87,
        "metadata": {"doc_type": "标准", "version": "2026", "source": "国家标准库"},
    },
    {
        "source_id": "DOC_CASE_003",
        "document_title": "某化工企业缺陷整改案例",
        "content": "2025年某化工企业因超期未处理缺陷导致生产安全事故，事故直接原因是安全阀未按期校验。"
        "该企业整改措施包括：建立缺陷台账、落实责任人限期整改、每月由安全部门复查。",
        "score": 0.81,
        "metadata": {"doc_type": "案例", "source": "事故案例库"},
    },
    {
        "source_id": "DOC_REG_004",
        "document_title": "安全风险分级管控和隐患排查治理双重预防机制实施指南",
        "content": "企业应建立安全风险分级管控和隐患排查治理双重预防机制。重大风险应当编制专项管控方案，"
        "并定期进行风险评估和隐患排查。隐患排查治理应当实行闭环管理。",
        "score": 0.78,
        "metadata": {"doc_type": "制度", "version": "2026", "source": "安全管理制度库"},
    },
    {
        "source_id": "DOC_CASE_005",
        "document_title": "电力行业设备超期运行分析报告",
        "content": "电力行业设备超期运行是常见的风险类型。统计显示，超期运行设备故障率比正常周期设备高47%。"
        "建议建立设备全生命周期管理系统，实现到期预警、超期督办、整改闭环。",
        "score": 0.73,
        "metadata": {"doc_type": "案例", "source": "行业分析库"},
    },
    {
        "source_id": "DOC_REG_006",
        "document_title": "本质安全判断规则与分级标准",
        "content": "本质安全判断应遵循以下规则：一、风险等级分为一般、重大、特大三级；"
        "二、一般隐患指不会立即导致事故但需限期整改的问题；三、重大隐患指可能导"
        "致人身伤害或重大财产损失，需立即停工整改的问题；四、特大隐患指可能引发"
        "群死群伤或巨大经济损失，需企业主要负责人挂牌督办。",
        "score": 0.95,
        "metadata": {"doc_type": "制度", "version": "2026", "source": "安全管理制度库"},
    },
    {
        "source_id": "DOC_REG_007",
        "document_title": "安全环保监督检查管理规定",
        "content": "安全环保监督检查实行分级负责制。企业安全环保部负责制定检查计划和标准，"
        "各生产单位负责日常自查自纠。检查内容包括：安全制度执行情况、隐患排查"
        "整改情况、设备设施安全状态、作业人员安全操作规范。对发现的问题应当"
        "建立台账，明确责任人和整改时限，实行闭环管理。",
        "score": 0.90,
        "metadata": {"doc_type": "制度", "version": "2026", "source": "安全管理制度库"},
    },
]

_DOMAIN_KEYWORDS = [
    "本质安全", "判断规则", "判定规则", "判断", "判定", "规则", "分级",
    "标准", "制度", "规范", "规定", "指南", "办法", "隐患", "治理",
    "整改", "闭环", "超期", "缺陷", "设备", "风险", "重大隐患",
    "一般隐患", "双重预防", "安全环保", "检查", "案例", "经验",
]


def _match_keywords(text: str, keywords: list[str]) -> bool:
    text_lower = text.lower()
    return any(kw.lower() in text_lower for kw in keywords)


def _score_document(doc: dict, query_keywords: list[str]) -> float:
    """简单关键词匹配得分，用于 Mock 数据排序。"""
    score = 0.0
    for kw in query_keywords:
        if kw.lower() in doc["content"].lower():
            score += 0.3
        if kw.lower() in doc["document_title"].lower():
            score += 0.5
    return min(score, 1.0)


class MockRagClient(RagClient):
    """本地开发和单元测试使用的 RAG Client。

    不发起 HTTP 调用，基于关键词匹配返回内存中的 Mock 数据。
    用于让后续 Node 层开发不依赖真实 RAG 服务。
    """

    def __init__(self, documents: list[dict] | None = None) -> None:
        super().__init__(base_url="")
        self._documents = documents if documents is not None else MOCK_RAG_DOCUMENTS

    def _extract_keywords(self, query: str) -> list[str]:
        """从查询中提取有实际含义的关键词，用于匹配。

        将中文查询按常见标点和停用词切分，过滤掉无意义的短词。
        """
        import re
        parts = re.split(r"[，。、；：？?！!\s,;:]+", query)
        keywords = []
        for p in parts:
            p = p.strip()
            # 过滤太短或纯场景前缀词。
            if len(p) < 2:
                continue
            if p in ("本质安全场景", "设备运维场景", "经营改善场景", "能力提升场景"):
                continue
            keywords.append(p.lower())
        for kw in _DOMAIN_KEYWORDS:
            if kw in query and kw.lower() not in keywords:
                keywords.append(kw.lower())
        return keywords

    def search(self, request: RagSearchRequest) -> RagSearchResponse:
        query = request.query.strip()
        if not query:
            return RagSearchResponse(success=True, results=[], total=0)

        keywords = self._extract_keywords(query)
        matched = []
        for doc in self._documents:
            content_lower = doc["content"].lower()
            title_lower = doc["document_title"].lower()
            if any(kw in content_lower or kw in title_lower for kw in keywords):
                matched.append(doc)

        if request.filters.doc_type:
            matched = [
                doc
                for doc in matched
                if doc.get("metadata", {}).get("doc_type") in request.filters.doc_type
            ]

        matched.sort(key=lambda d: _score_document(d, keywords), reverse=True)
        top_k = request.top_k or 5
        matched = matched[:top_k]

        results = []
        for doc in matched:
            results.append(
                RagSearchResult(
                    source_id=doc["source_id"],
                    document_title=doc["document_title"],
                    content=doc["content"],
                    score=doc.get("score"),
                    metadata=doc.get("metadata", {}),
                )
            )

        return RagSearchResponse(success=True, results=results, total=len(results))
