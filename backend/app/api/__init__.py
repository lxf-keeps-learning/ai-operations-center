"""
API 接口包 — 统一管理所有对外 HTTP 接口

目录结构：
  api/
  ├── router.py           主路由聚合（health/agent/conversations/prompts/feedback）
  ├── routes/             业务路由模块
  │   ├── health.py       健康检查
  │   ├── items.py        Demo CRUD
  │   ├── cache.py        Redis 健康检查
  │   ├── agent.py        AI 对话/分析/SSE 流式
  │   ├── conversations.py 会话列表/详情/删除
  │   ├── prompts.py      Prompt 查询
  │   └── feedback.py     用户反馈
  └── v1/                 基础设施控制台 API（v1 版本）
      ├── router.py       v1 路由聚合
      ├── config_api.py   模型配置/运行环境
      ├── error_code_api.py 业务错误码列表
      ├── log_api.py      最近日志/LLM 使用日志
      ├── trace_api.py    Trace 链路查询
      └── context_api.py  当前请求上下文
"""
