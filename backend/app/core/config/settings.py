"""
应用配置模块 — 统一对外暴露应用级配置项

封装底层 _legacy_settings，按功能分类暴露配置属性：
  - 基础：app_name / env / version / cors / timezone
  - 数据库：database_url
  - Redis：redis_enabled / redis_url
  - 环境判断：is_dev / is_test / is_prod
"""

from functools import lru_cache

from app.config.settings import settings as _legacy_settings
from app.core.config.env import current_env, env_file_path, is_dev, is_prod, is_test


class AppSettings:
    def __init__(self) -> None:
        self._inner = _legacy_settings

    # ── 基础 ────────────────────────────────
    @property
    def app_name(self) -> str:
        return self._inner.app_name

    @property
    def app_env(self) -> str:
        return current_env()

    @property
    def api_v1_prefix(self) -> str:
        return self._inner.api_v1_prefix

    @property
    def cors_origins(self) -> list[str]:
        return self._inner.cors_origins

    @property
    def app_timezone(self) -> str:
        return self._inner.app_timezone

    @property
    def log_level(self) -> str:
        return self._inner.log_level

    @property
    def env_file(self) -> str:
        return env_file_path()

    @property
    def version(self) -> str:
        return "0.1.0"

    # ── 数据库 ──────────────────────────────
    @property
    def database_url(self) -> str:
        return self._inner.database_url

    @property
    def sqlalchemy_database_url(self) -> str:
        return self._inner.sqlalchemy_database_url

    # ── Redis ───────────────────────────────
    @property
    def redis_enabled(self) -> bool:
        return self._inner.redis_enabled

    @property
    def redis_url(self) -> str:
        return self._inner.redis_url

    # ── 环境判断 ────────────────────────────
    @property
    def is_dev(self) -> bool:
        return is_dev()

    @property
    def is_test(self) -> bool:
        return is_test()

    @property
    def is_prod(self) -> bool:
        return is_prod()


@lru_cache
def get_settings() -> AppSettings:
    return AppSettings()


settings = get_settings()
