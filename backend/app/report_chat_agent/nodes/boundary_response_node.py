from app.report_chat_agent.state import ReportChatState

_OUT_OF_SCOPE_MSG = (
    "这个问题与当前报告无关，和当前本质安全分析报告关联不大，我先不直接展开，"
    "避免给你一个看起来完整但没有依据的回答。"
    "你可以继续追问本次风险原因、异常清单、排序依据、判断规则或整改建议，"
    "我会基于报告和可检索到的知识库依据来回答。"
)

_IOC_GLOBAL_MSG = (
    "这个问题属于 IOC 全局分析，已经超出当前单份报告的上下文。"
    "为了保证结论可靠，我不会直接用本报告去推断全公司情况。"
    "可以切换到全局 IOC 分析模式，或继续围绕这份报告追问原因、风险排序和建议动作。"
)

_REPORT_RELATED_MSG = (
    "这个问题与当前报告相关，但需要查询报告之外的历史或同类数据。"
    "当前版本支持报告内追问，你可以继续追问本次风险原因、"
    "异常清单、排序依据或整改建议。"
)


def boundary_response_node(state: ReportChatState) -> ReportChatState:
    scope = state.get("question_scope", "")

    if scope == "out_of_scope":
        state["final_answer"] = _OUT_OF_SCOPE_MSG
        state["answer_type"] = "boundary"
    elif scope == "ioc_global":
        state["final_answer"] = _IOC_GLOBAL_MSG
        state["answer_type"] = "boundary"
    elif scope == "report_related":
        state["final_answer"] = _REPORT_RELATED_MSG
        state["answer_type"] = "boundary"
    else:
        state["final_answer"] = (
            "当前会话用于围绕本质安全分析报告进行解释和追问，"
            "请继续追问本次风险原因、异常清单、排序依据或整改建议。"
        )
        state["answer_type"] = "boundary"

    return state
