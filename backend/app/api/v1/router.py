from fastapi import APIRouter

from app.api.v1 import config_api, context_api, error_code_api, log_api, trace_api

v1_router = APIRouter()
v1_router.include_router(config_api.router, tags=["Infrastructure"])
v1_router.include_router(error_code_api.router, tags=["Infrastructure"])
v1_router.include_router(log_api.router, tags=["Infrastructure"])
v1_router.include_router(trace_api.router, tags=["Infrastructure"])
v1_router.include_router(context_api.router, tags=["Infrastructure"])
