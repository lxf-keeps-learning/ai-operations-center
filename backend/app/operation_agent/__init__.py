"""
operation_agent — 运营分析 Agent 模块

提供基于 LangGraph 的运营分析智能体，包含：
  - graph.py / state.py      LangGraph StateGraph 编排 + 数据契约
  - service.py               同步分析入口（含 30 分钟缓存）
  - stream_service.py        SSE 流式分析入口（逐节点推送事件）
  - api/                     HTTP 接口层
  - nodes/                   6 个分析节点（初始化/数据查询/异常检测/原因分析/建议生成/汇总）
  - models/                  数据库模型（分析记录/事件日志/AI 用量等）
  - schemas/                 请求/响应 DTO
  - services/                业务逻辑（缓存/持久化）
  - repositories/            数据访问层
  - prompts/                 LLM 提示词模板
"""
