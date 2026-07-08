"""RAG 外部服务的 HTTP 客户端。

职责边界：
  只做 HTTP 调用和响应解析，不掺杂业务判断逻辑。
  不做 Chunk、Embedding、向量库、索引管理。

与 integrations/ioc/client.py 的关系：
  IOC Client 是"向业务系统查数据"；
  RAG Client 是"向知识库查依据"。
  两者都是外部 API 调用，但查询目的和数据结构不同，因此分独立模块。

调用风格与 app/runtime/llm/client.py 一致，使用 httpx.Client 同步调用。
"""

import json
import logging
from typing import Any

import httpx

from app.config.settings import settings
from app.rag.schemas import RagSearchRequest, RagSearchResponse

logger = logging.getLogger(__name__)


class RagClient:
    """封装外部 RAG Search API 的 HTTP 调用。

    这是 RAG 调用链的最底层。职责只有三个：
      1. 构造 HTTP 请求（POST /api/rag/search）。
      2. 处理网络层面异常（超时、断连、非 200 响应）。
      3. 把 JSON 响应解析为 RagSearchResponse。

    不做的事：
      - 不判断是否需要调用 RAG（那是 ShouldUseRagNode 的事）。
      - 不构造 query（那是 BuildRagQueryNode 的事）。
      - 不包装业务异常（那是 RagService 的事）。

    当 base_url 为空时（未配置 RAG 服务），search() 直接返回空结果，
    不会尝试 HTTP 调用。
    """

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout_seconds: float | None = None,
    ) -> None:
        """初始化 RAG HTTP 客户端。

        Args:
            base_url: 外部 RAG 服务的 base URL，如 "http://rag-api:8000"。
                      None 时读取 settings.rag_search_url；空字符串表示显式禁用 RAG 调用。
            api_key: API 鉴权密钥，通过 Authorization: Bearer 请求头发送。
            timeout_seconds: 请求超时秒数，默认 15s。
        """
        resolved_base_url = settings.rag_search_url if base_url is None else base_url
        resolved_api_key = settings.rag_search_api_key if api_key is None else api_key
        resolved_timeout = (
            settings.rag_search_timeout_seconds
            if timeout_seconds is None
            else timeout_seconds
        )

        self.base_url = resolved_base_url.rstrip("/")
        self.api_key = resolved_api_key
        self.timeout_seconds = resolved_timeout

    def search(self, request: RagSearchRequest) -> RagSearchResponse:
        """调用外部 RAG 检索服务。

        预期外部 API：
            POST {base_url}/api/rag/search
            Content-Type: application/json
            Authorization: Bearer {api_key}

        Args:
            request: 检索请求（query、top_k、filters 等）。

        Returns:
            RagSearchResponse:
                success=True  + results  — 正常返回。
                success=True  + []       — RAG 无结果或未配置 URL，不编造。
                success=False + error    — 调用失败，上层应降级。
        """
        if not self.base_url:
            logger.info("RAG_SEARCH_URL 未配置，跳过 RAG 检索，返回空结果。")
            return RagSearchResponse(success=True, results=[], total=0)

        url = f"{self.base_url}/api/rag/search"
        headers = self._build_headers()
        payload = self._build_payload(request)

        try:
            with httpx.Client(timeout=self.timeout_seconds) as http:
                resp = http.post(url, headers=headers, json=payload)
        except httpx.TimeoutException:
            logger.warning("RAG 检索超时 (timeout=%ss, url=%s)", self.timeout_seconds, url)
            return RagSearchResponse(
                success=False,
                results=[],
                total=0,
                error_message=f"RAG 检索超时 (timeout={self.timeout_seconds}s)",
            )
        except httpx.ConnectError as e:
            logger.warning("RAG 服务连接失败 (url=%s): %s", url, e)
            return RagSearchResponse(
                success=False,
                results=[],
                total=0,
                error_message=f"RAG 服务连接失败: {e}",
            )
        except httpx.HTTPError as e:
            logger.warning("RAG HTTP 请求异常 (url=%s): %s", url, e)
            return RagSearchResponse(
                success=False,
                results=[],
                total=0,
                error_message=f"RAG HTTP 请求异常: {e}",
            )

        if resp.status_code != 200:
            detail = resp.text[:500]
            logger.warning("RAG 服务返回非 200 (status=%s, url=%s): %s", resp.status_code, url, detail)
            return RagSearchResponse(
                success=False,
                results=[],
                total=0,
                error_message=f"RAG 服务返回 HTTP {resp.status_code}: {detail}",
            )

        return self._parse_response(resp, url)

    def _build_headers(self) -> dict[str, str]:
        headers: dict[str, str] = {
            "Content-Type": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _build_payload(self, request: RagSearchRequest) -> dict[str, Any]:
        return {
            "query": request.query,
            "scene": request.scene,
            "top_k": request.top_k,
            "filters": request.filters.model_dump(exclude_none=True),
        }

    def _parse_response(self, resp: httpx.Response, url: str) -> RagSearchResponse:
        """把外部 RAG 的 JSON 响应解析为 RagSearchResponse。

        外部响应期望结构（与 Sprint6 文档一致）：
        {
            "results": [
                {
                    "source_id": "DOC_001_CHUNK_003",
                    "document_title": "本质安全隐患治理规范",
                    "content": "...",
                    "score": 0.86,
                    "metadata": { "doc_type": "制度" }
                }
            ]
        }
        """
        try:
            body = resp.json()
        except json.JSONDecodeError as e:
            logger.warning("RAG 响应 JSON 解析失败 (url=%s): %s", url, e)
            return RagSearchResponse(
                success=False,
                results=[],
                total=0,
                error_message=f"RAG 响应 JSON 解析失败: {e}",
            )

        raw_results = body.get("results") if isinstance(body, dict) else None
        if not raw_results or not isinstance(raw_results, list):
            return RagSearchResponse(success=True, results=[], total=0)

        results = []
        for raw in raw_results:
            if not isinstance(raw, dict):
                continue
            source_id = raw.get("source_id") or raw.get("id") or ""
            if not source_id:
                # 没有 source_id 的结果不能作为正式知识依据，直接跳过。
                continue
            results.append(
                {
                    "source_id": source_id,
                    "document_title": _safe_str(
                        raw.get("document_title") or raw.get("title") or "",
                    ),
                    "content": _safe_str(raw.get("content") or ""),
                    "score": _safe_score(raw.get("score")),
                    "metadata": _safe_metadata(raw.get("metadata")),
                }
            )

        return RagSearchResponse(
            success=True,
            results=results,
            total=len(results),
        )


def _safe_str(value: Any) -> str:
    return value if isinstance(value, str) else str(value)


def _safe_score(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_metadata(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}
