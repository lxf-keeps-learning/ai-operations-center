from __future__ import annotations

import pytest

from app.observability import langsmith_runs
from app.rag.schemas import RagSearchRequest, RagSearchResponse
from app.tool_center.base_tool import BaseTool
from app.tool_center.contracts import BaseToolInput, Evidence


class _FakeRun:
    created: list[dict] = []
    instances: list["_FakeRun"] = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.outputs = None
        self.error = None
        self.posted = False
        self.__class__.created.append(kwargs)
        self.__class__.instances.append(self)

    def end(self, *, outputs=None, error=None, **_kwargs):
        self.outputs = outputs
        self.error = error

    def post(self, **_kwargs):
        self.posted = True


def test_run_observed_records_redacted_child_run(monkeypatch: pytest.MonkeyPatch) -> None:
    _FakeRun.created.clear()
    _FakeRun.instances.clear()
    monkeypatch.setattr(langsmith_runs, "RunTree", _FakeRun)
    monkeypatch.setattr(langsmith_runs, "get_current_run_tree", lambda: None)
    monkeypatch.setattr(langsmith_runs, "_get_langsmith_client", lambda: object())

    result = langsmith_runs.run_observed(
        "kpi_query",
        "tool",
        lambda: {"answer": "手机号 13800138000"},
        inputs={"api_key": "never-send", "query": "邮箱 user@example.com"},
        metadata={"ioc_trace_id": "trace_001"},
    )

    assert result == {"answer": "手机号 13800138000"}
    assert _FakeRun.created[0]["name"] == "kpi_query"
    assert _FakeRun.created[0]["run_type"] == "tool"
    assert _FakeRun.created[0]["inputs"]["api_key"] == "[REDACTED:credential]"
    assert "13800138000" not in str(_FakeRun.instances[0].outputs)


def test_run_observed_reraises_business_error_without_replacing_it(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(langsmith_runs, "RunTree", _FakeRun)
    monkeypatch.setattr(langsmith_runs, "get_current_run_tree", lambda: None)
    monkeypatch.setattr(langsmith_runs, "_get_langsmith_client", lambda: object())

    with pytest.raises(ValueError, match="business failure"):
        langsmith_runs.run_observed(
            "rag_search",
            "retriever",
            lambda: (_ for _ in ()).throw(ValueError("business failure")),
        )


def test_run_observed_converts_model_outputs_to_json_safe_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    _FakeRun.instances.clear()
    monkeypatch.setattr(langsmith_runs, "RunTree", _FakeRun)
    monkeypatch.setattr(langsmith_runs, "get_current_run_tree", lambda: None)
    monkeypatch.setattr(langsmith_runs, "_get_langsmith_client", lambda: object())

    langsmith_runs.run_observed(
        "tool",
        "tool",
        lambda: ({"items": ["ok"]}, [Evidence(source="ioc", source_type="kpi")], {}),
    )

    output = _FakeRun.instances[-1].outputs
    assert output["value"][1][0]["source"] == "ioc"


def test_run_observed_is_noop_when_langsmith_is_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(langsmith_runs, "_get_langsmith_client", lambda: None)
    called = []

    result = langsmith_runs.run_observed(
        "local_operation",
        "chain",
        lambda: called.append(True) or "ok",
    )

    assert result == "ok"
    assert called == [True]


def test_base_tool_wraps_execution_as_tool_run(monkeypatch: pytest.MonkeyPatch) -> None:
    observed = []

    def fake_observed(name, run_type, operation, **kwargs):
        observed.append((name, run_type, kwargs))
        return operation()

    monkeypatch.setattr("app.tool_center.base_tool.run_observed", fake_observed)

    class DemoTool(BaseTool):
        name = "demo_tool"

        def _execute(self, tool_input):
            return {"items": [{"id": "1"}]}, []

    result = DemoTool().run(BaseToolInput(filters={"query": "安全"}))

    assert result.success is True
    assert observed[0][0:2] == ("demo_tool", "tool")


def test_rag_service_wraps_search_as_retriever_run(monkeypatch: pytest.MonkeyPatch) -> None:
    observed = []

    def fake_observed(name, run_type, operation, **kwargs):
        observed.append((name, run_type, kwargs))
        return operation()

    monkeypatch.setattr("app.rag.service.run_observed", fake_observed)

    class DemoClient:
        def search(self, _request):
            return RagSearchResponse(success=True, results=[], total=0)

    from app.rag.service import RagService

    RagService(client=DemoClient()).retrieve(
        RagSearchRequest(query="安全制度", scene="essential_safety")
    )

    assert observed[0][0:2] == ("rag_search", "retriever")
