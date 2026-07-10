"""
runtime graph nodes — LangGraph StateGraph 的节点函数集合

每个节点是一个 Callable[[RuntimeGraphState], RuntimeGraphState]，
接收完整 State，读取自己需要的字段，处理后再写回 State。
"""
