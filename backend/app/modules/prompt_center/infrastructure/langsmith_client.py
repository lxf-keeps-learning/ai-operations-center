import json
import logging
from functools import lru_cache

from app.config.settings import settings

logger = logging.getLogger(__name__)


class LangSmithPromptClient:
    def __init__(self) -> None:
        self._enabled = settings.langsmith_tracing

    def push_prompt(self, prompt_key: str, version: str, messages: list[dict]) -> str | None:
        if not self._enabled:
            return None
        try:
            from langsmith import Client as LangSmithClient
            client = LangSmithClient(
                api_url=settings.langsmith_endpoint,
                api_key=settings.langsmith_api_key,
            )
            prompt = client.create_prompt(
                name=prompt_key,
                description=f"版本 {version}",
            )
            commit = client.create_commit(
                prompt_id=prompt.id,
                messages=messages,
                tags=[version, settings.app_env],
            )
            return str(commit.id) if commit else None
        except Exception:
            logger.exception("LangSmith Push Prompt 失败")
            return None

    def get_commit_url(self, commit_hash: str | None) -> str | None:
        if not commit_hash:
            return None
        return f"{settings.langsmith_endpoint}/commits/{commit_hash}"


langsmith_prompt_client = LangSmithPromptClient()
