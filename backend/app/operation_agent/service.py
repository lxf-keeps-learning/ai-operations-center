from app.operation_agent.graph import operation_graph
from app.operation_agent.schemas.request import OperationAnalyzeRequest
from app.operation_agent.state import OperationState


def analyze_operation(request: OperationAnalyzeRequest, user_context: dict | None = None) -> OperationState:
    initial_state: OperationState = {
        "trigger_type": request.trigger_type,
        "user_question": request.user_question,
        "user_context": user_context or {},
        "page_context": {
            "domain": request.domain,
            "active_tab": request.active_tab,
            "time_dimension": request.time_dimension,
            "date": request.date,
            "company_id": request.company_id,
            "project_id": request.project_id,
        },
    }

    result = operation_graph.invoke(initial_state)
    return result
