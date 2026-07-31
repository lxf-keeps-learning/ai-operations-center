from app.operation_agent.multi_agent.agent_graph import run_domain_agent
from app.operation_agent.multi_agent.agents import DOMAIN_AGENT_SPECS


def test_domain_agent_uses_domain_prompts_and_preserves_result_fields(monkeypatch):
    calls = []

    def fake_reason(state, **kwargs):
        calls.append(("reason", kwargs["prompt_name"]))
        state["reason_analysis"] = "设备分析结果"
        return state

    def fake_advice(state, **kwargs):
        calls.append(("advice", kwargs["prompt_name"]))
        state["advice_items"] = [{"title": "建立维修闭环"}]
        return state

    monkeypatch.setattr("app.operation_agent.multi_agent.agent_graph.analyze_reason_node", fake_reason)
    monkeypatch.setattr("app.operation_agent.multi_agent.agent_graph.generate_advice_node", fake_advice)
    state = {"domain": "maintenance", "metrics": [], "abnormal_items": [], "evidence": [], "errors": []}
    result = run_domain_agent(state, DOMAIN_AGENT_SPECS["maintenance"])

    assert result["reason_analysis"] == "设备分析结果"
    assert result["advice_items"][0]["title"] == "建立维修闭环"
    assert calls == [("reason", "domains/maintenance_analysis.md"), ("advice", "domains/maintenance_advice.md")]
