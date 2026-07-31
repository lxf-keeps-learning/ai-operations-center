"""Supervisor domain normalization and routing."""

from app.operation_agent.multi_agent.agents import DOMAIN_AGENT_SPECS
from app.operation_agent.state import OperationDomain, OperationState


def normalize_domain(state: OperationState) -> str:
    """Normalize the requested domain and record invalid-domain errors."""

    requested = state.get("domain")
    if requested is None:
        requested = state.get("page_context", {}).get("domain")

    errors = state.setdefault("errors", [])
    if requested not in DOMAIN_AGENT_SPECS:
        errors.append(
            {
                "node": "supervisor",
                "message": f"暂不支持的领域: {requested}，已回退到 safety。",
            }
        )
        normalized: OperationDomain = "safety"
    else:
        normalized = requested

    state["domain"] = normalized
    return normalized


def route_domain_agent(state: OperationState) -> str:
    """Route the state to its normalized domain agent."""

    domain = normalize_domain(state)
    state["supervisor_route"] = domain
    state["active_agent"] = domain
    return domain
