"""Supervisor domain normalization and routing."""

from typing import cast

from app.operation_agent.multi_agent.agents import DOMAIN_AGENT_SPECS
from app.operation_agent.state import OperationDomain, OperationState


def normalize_domain(state: OperationState) -> OperationDomain:
    """Normalize the requested domain and record invalid-domain errors."""

    page_context = state.setdefault("page_context", {})
    requested = state.get("domain")
    if requested is None:
        requested = page_context.get("domain")

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
        normalized = cast(OperationDomain, requested)

    state["domain"] = normalized
    page_context["domain"] = normalized
    return normalized


def route_domain_agent(state: OperationState) -> OperationDomain:
    """Route the state to its normalized domain agent."""

    domain = normalize_domain(state)
    state["supervisor_route"] = domain
    state["active_agent"] = domain
    return domain
