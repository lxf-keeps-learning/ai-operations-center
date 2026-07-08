from functools import cached_property

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.config.env import find_env_files


class Settings(BaseSettings):
    app_name: str = "智能运营中心 AI Agent Runtime"
    app_env: str = "local"
    api_v1_prefix: str = "/api/v1"
    backend_cors_origins: str = Field(
        default="http://localhost:5173,http://127.0.0.1:5173",
        description="Comma-separated CORS origins.",
    )
    database_url: str = "mysql+pymysql://ioc_user:ioc_password@localhost:3306/ioc_ai"
    app_timezone: str = "Asia/Shanghai"
    log_level: str = "INFO"
    redis_enabled: bool = False
    redis_url: str = "redis://localhost:6379/0"
    operation_llm_timeout_seconds: float = Field(
        default=20.0,
        description="Operation Agent 调用 DeepSeek 生成报告片段的单次超时时间。",
    )
    rag_search_url: str = Field(
        default="",
        description="外部 RAG 服务的 API 地址。为空时不调用 RAG，返回空结果。",
    )
    rag_search_api_key: str = Field(
        default="",
        description="外部 RAG 服务的 API 鉴权密钥。",
    )
    rag_search_timeout_seconds: float = Field(
        default=15.0,
        description="RAG 检索请求超时秒数。",
    )

    # Sprint6.1: RAG Decision & Query Rewrite Optimization.
    # 默认关闭 LLM 优化，走原有规则逻辑。
    rag_use_llm_decision: bool = Field(
        default=False,
        description="是否启用 LLM 进行 RAG 需求判断。关闭时走原有规则匹配。",
    )
    rag_use_query_rewrite: bool = Field(
        default=False,
        description="是否启用 LLM 进行 RAG Query 改写。关闭时走原有规则拼接。",
    )
    rag_decision_confidence_threshold: float = Field(
        default=0.65,
        ge=0.0,
        le=1.0,
        description="RAG 决策置信度阈值。LLM 判断置信度低于此值时 fallback 到规则。",
    )
    rag_query_rewrite_confidence_threshold: float = Field(
        default=0.65,
        ge=0.0,
        le=1.0,
        description="Query 改写置信度阈值。LLM 改写置信度低于此值时 fallback 到规则。",
    )

    model_config = SettingsConfigDict(
        env_file=find_env_files(),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @cached_property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.backend_cors_origins.split(",") if origin.strip()]

    @cached_property
    def sqlalchemy_database_url(self) -> str:
        return self.database_url


settings = Settings()
