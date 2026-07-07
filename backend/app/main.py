from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from app.api.routes import cache, items
from app.api.router import api_router
from app.api.v1.router import v1_router
from app.config.settings import settings
from app.core.exception.exception_handler import register_exception_handlers
from app.core.logging.logger import setup_logging
from app.core.middleware.trace_middleware import register_trace_middleware
from app.runtime.api.router import runtime_router
from app.tools.api import router as tools_router
from app.tools.register import register_all_tools


def create_app() -> FastAPI:
    setup_logging(level=settings.log_level)
    app = FastAPI(
        title=settings.app_name,
        summary="智能运营中心 AI Agent Runtime 后端接口",
        description=(
            "提供健康检查、AI 对话、运营分析、SSE 流式输出、会话查询、"
            "Prompt 查询和用户反馈接口。"
        ),
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url=f"{settings.api_v1_prefix}/openapi.json",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_trace_middleware(app)
    register_exception_handlers(app)
    register_all_tools()

    app.include_router(api_router, prefix=settings.api_v1_prefix)
    app.include_router(v1_router, prefix=settings.api_v1_prefix)
    app.include_router(runtime_router, prefix=settings.api_v1_prefix)
    app.include_router(tools_router, prefix=settings.api_v1_prefix)
    app.include_router(cache.router, prefix="/api/cache", tags=["Cache"])
    app.include_router(items.router, prefix=f"{settings.api_v1_prefix}/items", tags=["Items"])

    @app.get("/", include_in_schema=False)
    async def root() -> RedirectResponse:
        return RedirectResponse(url="/docs")

    @app.get("/api/v1/docs", include_in_schema=False)
    async def api_docs() -> RedirectResponse:
        return RedirectResponse(url="/docs")

    return app


app = create_app()
