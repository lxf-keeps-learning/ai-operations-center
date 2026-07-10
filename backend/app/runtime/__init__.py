"""
runtime — AI Runtime 运行时模块

提供数据库持久化的 AI 会话管理能力，包含：
  - api/        HTTP 接口层（会话/Prompt/Trace/反馈 CRUD）
  - models/     SQLAlchemy ORM 模型
  - schemas/    Pydantic 请求/响应 DTO
  - services/   业务逻辑层
  - repositories/ 数据访问层
  - llm/        大模型调用客户端
  - in_memory_store.py  内存存储（用于 SSE 流式对话）
  - runtime_service.py  运行时编排入口
"""
