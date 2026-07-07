from app.operation_agent.graph import operation_graph
from app.operation_agent.state import OperationState
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


class TestOperationGraph:
    _result: OperationState | None = None

    @classmethod
    def setup_class(cls):
        register_all_tools()
        cls._result = operation_graph.invoke(_safety_state())

    def test_graph_can_invoke(self):
        assert self._result is not None

    def test_safety_returns_final_answer(self):
        assert len(self._result["final_answer"]) > 0

    def test_final_answer_is_markdown(self):
        md = self._result["final_answer"]
        assert md.startswith("##")
        assert "###" in md

    def test_evidence_not_empty(self):
        assert len(self._result.get("evidence", [])) > 0

    def test_abnormal_items_field_exists(self):
        assert "abnormal_items" in self._result
        assert isinstance(self._result["abnormal_items"], list)

    def test_advice_items_field_exists(self):
        assert "advice_items" in self._result
        assert isinstance(self._result["advice_items"], list)

    def test_trace_id_generated(self):
        assert self._result.get("trace_id", "").startswith("trace_")

    def test_risk_items_field_exists(self):
        assert "risk_items" in self._result
        assert isinstance(self._result["risk_items"], list)

    def test_all_sections_in_final_answer(self):
        md = self._result["final_answer"]
        assert "总体判断" in md
        assert "关键发现" in md
        assert "异常与风险" in md
        assert "建议动作" in md
        assert "数据依据" in md

    def test_errors_does_not_crash_graph(self):
        state = _safety_state()
        state["page_context"] = {"domain": "unknown_domain"}
        result = operation_graph.invoke(state)
        assert result is not None
        assert "final_answer" in result
