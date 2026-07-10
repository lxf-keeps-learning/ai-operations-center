"""
runtime services — 业务逻辑层

介于 API 层和 Repository 层之间，负责：
  1. 调用 Repository 完成数据存取
  2. ORM 模型 → Pydantic 响应体的转换（model_validate）
  3. 简单的业务聚合（如最近消息拼接、状态变更等）

Service 层遵循单一职责原则，每个 Service 只关注对应模型的业务封装，
不跨模型调用其他 Service 或 Repository。跨模型的编排逻辑统一在
RuntimeService（runtime_service.py）中完成。
"""
