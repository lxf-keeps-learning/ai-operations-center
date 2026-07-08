"""RagService 单元测试。

测试重点：
  1. 正常检索返回 results。
  2. 检索结果为空。
  3. Client 抛出异常时 Service 吞掉并返回 error。
  4. 未配置 URL 时返回空结果（通过 MockRagClient）。
"""

import pytest

from app.rag.mock_client import MockRagClient
from app.rag.schemas import RagSearchFilters, RagSearchRequest
from app.rag.service import RagService


@pytest.fixture
def mock_service() -> RagService:
    return RagService(client=MockRagClient())


@pytest.fixture
def empty_service() -> RagService:
    """使用无数据的 MockRagClient。"""
    return RagService(client=MockRagClient(documents=[]))


def _make_request(query: str = "缺陷处置流程") -> RagSearchRequest:
    return RagSearchRequest(
        query=query,
        scene="essential_safety",
        top_k=3,
        filters=RagSearchFilters(doc_type=["制度", "标准"]),
    )


class TestRagServiceRetrieve:
    """RagService.retrieve() 的各类场景测试。"""

    def test_returns_results(self, mock_service: RagService) -> None:
        resp = mock_service.retrieve(_make_request("缺陷"))
        assert resp.success is True
        assert len(resp.results) > 0
        assert all(r.source_id for r in resp.results)
        assert all(r.document_title for r in resp.results)
        assert all(r.content for r in resp.results)

    def test_filters_doc_type(self, mock_service: RagService) -> None:
        req = RagSearchRequest(
            query="缺陷",
            scene="essential_safety",
            top_k=10,
            filters=RagSearchFilters(doc_type=["案例"]),
        )
        resp = mock_service.retrieve(req)
        assert resp.success is True
        for r in resp.results:
            assert r.metadata.get("doc_type") == "案例"

    def test_rule_question_returns_mock_basis(self, mock_service: RagService) -> None:
        """口语化询问本质安全判断规则时，应返回 mock 知识库依据。"""
        resp = mock_service.retrieve(_make_request("本质安全场景，这次能查到本质安全判断的规则不"))
        assert resp.success is True
        assert any(r.source_id == "DOC_REG_006" for r in resp.results)
        assert any("本质安全判断规则" in r.document_title for r in resp.results)

    def test_returns_empty_when_no_match(self, mock_service: RagService) -> None:
        resp = mock_service.retrieve(_make_request("完全不相关的内容xxxxxxxx"))
        assert resp.success is True
        assert resp.results == []
        assert resp.total == 0

    def test_returns_empty_with_empty_query(self, mock_service: RagService) -> None:
        resp = mock_service.retrieve(_make_request(""))
        assert resp.success is True
        assert resp.results == []

    def test_empty_database_returns_empty(self, empty_service: RagService) -> None:
        resp = empty_service.retrieve(_make_request("缺陷"))
        assert resp.success is True
        assert resp.results == []

    def test_respects_top_k(self, mock_service: RagService) -> None:
        req = RagSearchRequest(query="缺陷", scene="essential_safety", top_k=2)
        resp = mock_service.retrieve(req)
        assert resp.success is True
        assert len(resp.results) <= 2

    def test_service_swallows_client_exception(self) -> None:
        class BrokenClient:
            def search(self, request: object) -> object:
                msg = "unexpected crash"
                raise RuntimeError(msg)

        service = RagService(client=BrokenClient())  # type: ignore[arg-type]
        resp = service.retrieve(_make_request())
        assert resp.success is False
        assert resp.results == []
        assert resp.error_message is not None
