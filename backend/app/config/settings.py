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

    model_config = SettingsConfigDict(env_file=find_env_files(), env_file_encoding="utf-8", extra="ignore")

    @cached_property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.backend_cors_origins.split(",") if origin.strip()]

    @cached_property
    def sqlalchemy_database_url(self) -> str:
        return self.database_url


settings = Settings()
