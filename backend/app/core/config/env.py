import os
from functools import lru_cache
from pathlib import Path

ENV_VAR_NAME = "APP_ENV"
_VALID_ENVS = {"dev", "test", "prod", "local"}
_ENV_FILE_MAP = {
    "dev": ".env.dev",
    "test": ".env.test",
    "prod": ".env.prod",
    "local": ".env",
}
_LEGACY_MAP = {
    "development": "dev",
    "production": "prod",
    "staging": "test",
}


def _normalize_env(raw: str) -> str:
    normalized = _LEGACY_MAP.get(raw.lower(), raw.lower())
    return normalized if normalized in _VALID_ENVS else "local"


@lru_cache
def current_env() -> str:
    return _normalize_env(os.environ.get(ENV_VAR_NAME, "local"))


def is_dev() -> bool:
    return current_env() in {"dev", "local"}


def is_test() -> bool:
    return current_env() == "test"


def is_prod() -> bool:
    return current_env() == "prod"


def env_file_path() -> str:
    env = current_env()
    return _ENV_FILE_MAP.get(env, ".env")


def find_env_files() -> list[str]:
    backend_root = Path(__file__).resolve().parent.parent.parent.parent
    files = []

    env = current_env()
    specific = _ENV_FILE_MAP.get(env, ".env")
    specific_path = backend_root / specific
    if specific_path.exists():
        files.append(str(specific_path))

    default = backend_root / ".env"
    if default.exists() and str(default) not in files:
        files.append(str(default))

    return files
