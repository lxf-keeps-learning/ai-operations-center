"""
API 主路由聚合 — 将各业务模块的路由注册到统一 APIRouter

目前注册的模块：
  - /health             服务健康检查
  - /agent               AI 对话/分析/流式输出
  - /conversations       会话管理
  - /prompts             Prompt 查询
  - /feedback            用户反馈
"""

from fastapi import APIRouter

from app.api.routes import agent, conversations, feedback, health, items, prompts

api_router = APIRouter()
api_router.include_router(health.router, tags=["Health"])
api_router.include_router(agent.router, prefix="/agent", tags=["Agent"])
api_router.include_router(conversations.router, prefix="/conversations", tags=["Conversations"])
api_router.include_router(prompts.router, prefix="/prompts", tags=["Prompts"])
api_router.include_router(feedback.router, prefix="/feedback", tags=["Feedback"])
