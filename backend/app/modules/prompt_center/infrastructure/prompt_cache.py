from functools import lru_cache
from typing import Any

from app.modules.prompt_center.domain.entities import PromptRenderResult


class PromptCache:
    def __init__(self, maxsize: int = 128) -> None:
        self._maxsize = maxsize

    def get(self, key: str) -> PromptRenderResult | None:
        return self._cache.get(key) if hasattr(self, '_cache') else None

    def set(self, key: str, value: PromptRenderResult) -> None:
        if not hasattr(self, '_cache'):
            self._cache: dict[str, PromptRenderResult] = {}
        if len(self._cache) >= self._maxsize:
            first_key = next(iter(self._cache))
            del self._cache[first_key]
        self._cache[key] = value

    def invalidate(self, prompt_key: str) -> None:
        if hasattr(self, '_cache'):
            keys_to_delete = [k for k in self._cache if k.startswith(prompt_key)]
            for k in keys_to_delete:
                del self._cache[k]

    def make_key(self, prompt_key: str, environment: str, version: str | None, var_hash: str) -> str:
        return f"{prompt_key}:{environment}:{version}:{var_hash}"


prompt_cache = PromptCache()
