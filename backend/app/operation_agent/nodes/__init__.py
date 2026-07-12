"""Operation Graph 节点模块。

该模块包含 LangGraph 编排中的各个处理节点（Node），每个节点负责
运营分析流水线中的一个独立阶段，按顺序执行：

    1. init_context        — 初始化 State（trace_id、analysis_mode）
    2. query_operation_data — 查询业务数据（KPI / 告警 / 隐患 / 工单）
    3. detect_abnormal      — 基于规则检测异常与风险
    4. analyze_reason       — LLM 分析异常原因（含降级兜底）
    5. generate_advice      — LLM 生成处置建议（含降级兜底）
    6. summary              — 渲染最终运营分析报告
"""
