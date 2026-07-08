from app.report_chat_agent.state import QuestionScope, ReportChatState

_INTERNAL_KEYWORDS = [
    "为什么", "依据", "原因", "异常", "风险", "排序", "建议",
    "动作", "哪个", "优先级", "严重", "指标", "结论", "判断",
    "解释", "说明", "依据", "根据", "怎么", "如何", "哪些",
    "是否正常", "是否异常", "是不是", "是什么", "排第",
]

_RELATED_KEYWORDS = [
    "最近7天", "近30天", "历史", "其他站点", "同类设备",
    "以前", "持续", "近一周", "近一月", "趋势", "对比",
    "去年", "上月", "上周", "之前", "过往",
    "规则", "制度", "规范", "标准", "条例", "规定", "规程",
    "法规", "指南", "案例", "经验", "先例", "本质安全判断",
    "判定规则", "判断规则",
]

_GLOBAL_KEYWORDS = [
    "全公司", "所有区域", "整体趋势", "月度分析", "全局",
    "全部站点", "所有设备", "全集团", "公司整体",
]

_OUT_OF_SCOPE_KEYWORDS = [
    "写诗", "写首诗", "一首诗", "作诗", "歌", "天气",
    "娱乐", "美食", "旅游", "体育", "股票", "电影",
    "音乐", "小说", "游戏", "明星", "足球", "篮球",
]


def classify_question_scope_node(state: ReportChatState) -> ReportChatState:
    question = state.get("user_question", "")
    if not question:
        state["question_scope"] = "out_of_scope"
        state["scope_reason"] = "用户问题为空"
        state["need_tool_query"] = False
        return state

    q = question.strip().lower()

    for kw in _OUT_OF_SCOPE_KEYWORDS:
        if kw in q:
            state["question_scope"] = "out_of_scope"
            state["scope_reason"] = f"用户问题包含无关关键词'{kw}'，判定为无关问题"
            state["need_tool_query"] = False
            return state

    for kw in _GLOBAL_KEYWORDS:
        if kw in q:
            state["question_scope"] = "ioc_global"
            state["scope_reason"] = f"用户问题包含全局关键词'{kw}'，判定为 IOC 全局问题"
            state["need_tool_query"] = False
            return state

    for kw in _RELATED_KEYWORDS:
        if kw in q:
            state["question_scope"] = "report_related"
            state["scope_reason"] = f"用户问题包含扩展关键词'{kw}'，判定为报告相关扩展问题"
            state["need_tool_query"] = True
            return state

    for kw in _INTERNAL_KEYWORDS:
        if kw in q:
            state["question_scope"] = "report_internal"
            state["scope_reason"] = f"用户问题包含报告内关键词'{kw}'，可直接基于报告回答"
            state["need_tool_query"] = False
            return state

    state["question_scope"] = "report_internal"
    state["scope_reason"] = "用户问题未匹配到特殊范围，默认按报告内问题处理"
    state["need_tool_query"] = False
    return state
