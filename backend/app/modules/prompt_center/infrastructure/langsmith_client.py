import logging
import re
from dataclasses import dataclass
from typing import Any, Callable
from urllib.parse import urlparse

from app.config.settings import settings
from app.modules.prompt_center.domain.prompt_content import build_business_content

logger = logging.getLogger(__name__)

_COMMIT_HASH_PATTERN = re.compile(r"^[A-Za-z0-9_-]{6,128}$")


class LangSmithPromptClientError(RuntimeError):
    pass


@dataclass(frozen=True)
class PromptSyncResult:
    commit_hash: str
    tag: str
    url: str | None


class LangSmithPromptClient:
    def __init__(self, client_factory: Callable[..., Any] | None = None) -> None:
        self._client_factory = client_factory

    def push_prompt(self, prompt: Any, version: Any) -> PromptSyncResult:
        if not settings.langsmith_api_key:
            raise LangSmithPromptClientError("LangSmith Prompt 同步已开启，但 API Key 未配置")

        template = self._build_template(version)
        client = self._create_client()
        try:
            url = client.push_prompt(
                prompt_identifier=prompt.prompt_key,
                object=template,
                is_public=False,
                description=prompt.description,
                tags=["ioc", "managed-prompt"],
                commit_tags=[version.version, "managed-by-ioc"],
                commit_description=version.change_reason,
            )
        except Exception as exc:
            logger.warning("LangSmith Prompt API 请求失败，异常类型=%s", type(exc).__name__)
            raise LangSmithPromptClientError("LangSmith API 请求失败") from exc

        commit_hash = self._parse_commit_hash(url)
        return PromptSyncResult(
            commit_hash=commit_hash,
            tag=version.version,
            url=url,
        )

    def _create_client(self) -> Any:
        if self._client_factory is not None:
            factory = self._client_factory
        else:
            try:
                from langsmith import Client
            except Exception as exc:
                raise LangSmithPromptClientError("LangSmith Client 初始化失败") from exc
            factory = Client

        try:
            return factory(
                api_url=settings.langsmith_endpoint,
                api_key=settings.langsmith_api_key,
            )
        except Exception as exc:
            raise LangSmithPromptClientError("LangSmith Client 初始化失败") from exc

    @staticmethod
    def _build_template(version: Any) -> Any:
        try:
            from langchain_core.prompts import ChatPromptTemplate

            system_content = _escape_literal_braces(version.system_content or "")
            business_content = _escape_literal_braces(build_business_content(version))
            human_parts = [
                part
                for part in (
                    business_content,
                    "## 当前上下文\n\n{runtime_context}",
                    "## 用户问题\n\n{user_question}",
                )
                if part
            ]
            return ChatPromptTemplate.from_messages([
                ("system", system_content),
                ("human", "\n\n".join(human_parts)),
            ])
        except Exception as exc:
            raise LangSmithPromptClientError("LangSmith Prompt 模板序列化失败") from exc

    @staticmethod
    def _parse_commit_hash(url: str) -> str:
        if not isinstance(url, str) or not url.strip():
            raise LangSmithPromptClientError("LangSmith 返回 URL 无法解析 Commit Hash")

        segments = [segment for segment in urlparse(url).path.split("/") if segment]
        commit_hash = ""
        if len(segments) >= 3 and segments[-3] == "prompts":
            commit_hash = segments[-1]
        elif len(segments) >= 3 and segments[-3] == "hub" and ":" in segments[-1]:
            commit_hash = segments[-1].rsplit(":", 1)[-1]
        if not _COMMIT_HASH_PATTERN.fullmatch(commit_hash):
            raise LangSmithPromptClientError("LangSmith 返回 URL 无法解析 Commit Hash")
        return commit_hash

def _escape_literal_braces(value: str) -> str:
    return value.replace("{", "{{").replace("}", "}}")


langsmith_prompt_client = LangSmithPromptClient()
