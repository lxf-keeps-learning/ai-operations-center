import json

import pytest
from httpx import ASGITransport, AsyncClient

from app.config.settings import settings
from app.main import app
from app.operation_agent.graph import operation_graph
from app.operation_agent.state import OperationState
from app.runtime.llm.client import LlmResult
from app.tools.register import register_all_tools


def _safety_state() -> OperationState:
    return {
        "trigger_type": "tab_analysis",
        "user_question": None,
        "user_context": {"user_id": "demo_user", "role": "operation_manager"},
        "page_context": {
            "domain": "safety",
            "active_tab": "本质安全",
            "time_dimension": "month",
            "date": "2026-07",
        },
    }


@pytest.fixture
def fake_operation_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_chat(
        prompt_content: str | None,
        user_message: str,
        history: list[dict[str, str]] | None = None,
        timeout_seconds: float | None = None,
    ) -> LlmResult:
        assert timeout_seconds == settings.operation_llm_timeout_seconds
        if "请只输出 JSON 数组" in user_message:
            content = json.dumps(
                [
                    {
                        "title": "闭环高等级运营风险",
                        "priority": "P1",
                        "owner_role": "安全运营负责人",
                        "action": "核查高等级告警、待整改隐患和待处理工单，明确责任人与完成时间。",
                        "expected_result": "高等级风险进入闭环处置。",
                        "evidence": [],
                    }
                ],
                ensure_ascii=False,
            )
        else:
            content = "当前风险主要来自高等级未闭环告警、待整改隐患和待处理工单。"
        return LlmResult(
            content=content,
            model="deepseek-chat",
            prompt_tokens=8,
            completion_tokens=6,
            total_tokens=14,
            cost_ms=5,
            success=True,
            system_prompt=prompt_content or "",
        )

    monkeypatch.setattr("app.operation_agent.nodes.analyze_reason_node.llm_client.chat", fake_chat)
    monkeypatch.setattr("app.operation_agent.nodes.generate_advice_node.llm_client.chat", fake_chat)


@pytest.fixture
def operation_result(fake_operation_llm: None) -> OperationState:
    register_all_tools()
    return operation_graph.invoke(_safety_state())


class TestOperationGraph:
    def test_graph_can_invoke(self, operation_result: OperationState):
        assert operation_result is not None

    def test_safety_returns_final_answer(self, operation_result: OperationState):
        assert len(operation_result["final_answer"]) > 0

    def test_final_answer_is_markdown(self, operation_result: OperationState):
        md = operation_result["final_answer"]
        assert md.startswith("## 运营分析报告")
        assert "###" in md

    def test_evidence_not_empty(self, operation_result: OperationState):
        assert len(operation_result.get("evidence", [])) > 0

    def test_abnormal_items_field_exists(self, operation_result: OperationState):
        assert "abnormal_items" in operation_result
        assert isinstance(operation_result["abnormal_items"], list)

    def test_advice_items_field_exists(self, operation_result: OperationState):
        assert "advice_items" in operation_result
        assert isinstance(operation_result["advice_items"], list)

    def test_trace_id_generated(self, operation_result: OperationState):
        assert operation_result.get("trace_id", "").startswith("trace_")

    def test_risk_items_field_exists(self, operation_result: OperationState):
        assert "risk_items" in operation_result
        assert isinstance(operation_result["risk_items"], list)

    def test_all_sections_in_final_answer(self, operation_result: OperationState):
        md = operation_result["final_answer"]
        assert "总体判断" in md
        assert "关键发现" in md
        assert "异常与风险" in md
        assert "建议动作" in md
        assert "数据依据" in md

    def test_query_node_uses_ioc_tools(self, operation_result: OperationState):
        raw_data = operation_result["raw_data"]
        assert {"kpi", "alarm", "risk", "work_order", "ioc_summary"}.issubset(raw_data)
        assert operation_result["metrics"]
        assert any(ev.get("source_type") == "alarm_api" for ev in operation_result["evidence"])
        assert any(ev.get("source_type") == "risk_api" for ev in operation_result["evidence"])
        assert any(ev.get("source_type") == "work_order_api" for ev in operation_result["evidence"])

    def test_detects_abnormal_and_risk_items(self, operation_result: OperationState):
        abnormal_types = {item.get("type") for item in operation_result["abnormal_items"]}
        assert "high_level_alarm" in abnormal_types
        assert "pending_risk" in abnormal_types
        assert operation_result["risk_items"]

    def test_errors_does_not_crash_graph(self, fake_operation_llm: None):
        register_all_tools()
        state = _safety_state()
        state["page_context"] = {"domain": "unknown_domain"}
        result = operation_graph.invoke(state)
        assert result is not None
        assert "final_answer" in result


@pytest.mark.anyio
async def test_operation_analyze_api_returns_closed_loop_payload(
    fake_operation_llm: None,
) -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/operation/analyze",
            json={
                "trigger_type": "tab_analysis",
                "domain": "safety",
                "active_tab": "本质安全",
                "time_dimension": "month",
                "date": "2026-07",
            },
        )

    payload = response.json()
    data = payload["data"]

    assert response.status_code == 200
    assert payload["success"] is True
    assert data["trace_id"].startswith("trace_")
    assert data["summary"].startswith("## 运营分析报告")
    assert data["abnormal_items"]
    assert data["risk_items"]
    assert data["advice_items"]
    assert data["evidence"]


def test_operation_report_normalizes_llm_report_shell(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_messy_chat(
        prompt_content: str | None,
        user_message: str,
        history: list[dict[str, str]] | None = None,
        timeout_seconds: float | None = None,
    ) -> LlmResult:
        if "请只输出 JSON 数组" in user_message:
            content = json.dumps(
                [
                    {
                        "title": "闭环高等级运营风险",
                        "priority": "P1",
                        "owner_role": "安全运营负责人",
                        "action": "核查高等级告警并推进闭环。",
                        "expected_result": "高等级风险进入闭环处置。",
                        "evidence": [],
                    }
                ],
                ensure_ascii=False,
            )
        else:
            content = "\n".join(
                [
                    "好的，作为企业级智能运营中心的运营分析专家，我将生成报告。",
                    "# 运营状态分析报告",
                    "报告时间：2026年7月7日",
                    "## 整体状态判断",
                    "- 当前存在高等级未闭环告警，应优先处理。",
                ]
            )
        return LlmResult(
            content=content,
            model="deepseek-chat",
            prompt_tokens=8,
            completion_tokens=6,
            total_tokens=14,
            cost_ms=5,
            success=True,
            system_prompt=prompt_content or "",
        )

    register_all_tools()
    monkeypatch.setattr(
        "app.operation_agent.nodes.analyze_reason_node.llm_client.chat",
        fake_messy_chat,
    )
    monkeypatch.setattr(
        "app.operation_agent.nodes.generate_advice_node.llm_client.chat",
        fake_messy_chat,
    )

    result = operation_graph.invoke(_safety_state())
    final_answer = result["final_answer"]

    assert "好的，作为企业级智能运营中心" not in final_answer
    assert "报告时间：" not in final_answer
    assert "# 运营状态分析报告" not in final_answer
    assert "#### 原因分析" in final_answer
    assert "**整体状态判断**" in final_answer


def test_operation_llm_failure_reports_deepseek_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_failed_chat(
        prompt_content: str | None,
        user_message: str,
        history: list[dict[str, str]] | None = None,
        timeout_seconds: float | None = None,
    ) -> LlmResult:
        return LlmResult(
            content="",
            model="deepseek-chat",
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=0,
            cost_ms=1,
            success=False,
            error_message="DeepSeek API 调用超时",
            system_prompt=prompt_content or "",
        )

    register_all_tools()
    monkeypatch.setattr(
        "app.operation_agent.nodes.analyze_reason_node.llm_client.chat",
        fake_failed_chat,
    )
    monkeypatch.setattr(
        "app.operation_agent.nodes.generate_advice_node.llm_client.chat",
        fake_failed_chat,
    )

    result = operation_graph.invoke(_safety_state())
    final_answer = result["final_answer"]

    assert "DeepSeek 分析调用触发降级" in final_answer
    assert "DeepSeek API 调用超时" in final_answer
    assert "LLM 暂不可用" not in final_answer
