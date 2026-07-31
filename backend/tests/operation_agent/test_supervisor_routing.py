from app.operation_agent.multi_agent.supervisor import normalize_domain, route_domain_agent


def test_route_domain_agent_maps_each_business_domain():
    for domain in ("safety", "maintenance", "business", "capability", "all"):
        state = {"domain": domain, "errors": []}
        assert route_domain_agent(state) == domain
        assert state["supervisor_route"] == domain


def test_invalid_domain_falls_back_to_safety_and_records_error():
    state = {"domain": "unknown", "errors": []}
    assert normalize_domain(state) == "safety"
    assert state["errors"][0]["node"] == "supervisor"
    assert route_domain_agent(state) == "safety"
    assert state["supervisor_route"] == "safety"
