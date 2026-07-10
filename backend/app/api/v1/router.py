"""
v1 路由聚合 — 将基础设施控制台接口注册到统一 APIRouter

注册模块：
  - /config/models     模型配置列表
  - /config/runtime    当前运行环境
  - /errors/codes      业务错误码列表
  - /logs/recent       最近日志
  - /logs/llm-usage    LLM 使用日志
  - /traces/{id}       Trace 链路查询
  - /context/current   当前请求上下文
"""

from fastapi import APIRouter

from app.api.v1 import config_api, context_api, error_code_api, log_api, trace_api

v1_router = APIRouter()
v1_router.include_router(config_api.router, tags=["Infrastructure"])
v1_router.include_router(error_code_api.router, tags=["Infrastructure"])
v1_router.include_router(log_api.router, tags=["Infrastructure"])
v1_router.include_router(trace_api.router, tags=["Infrastructure"])
v1_router.include_router(context_api.router, tags=["Infrastructure"])
