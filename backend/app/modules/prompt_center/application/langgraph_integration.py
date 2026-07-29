"""
LangGraph Integration — LangGraph Node 通过此模块获取渲染后的 Prompt。

使用方法：
    from app.modules.prompt_center.application.langgraph_integration import get_rendered_prompt

    result = get_rendered_prompt(
        prompt_key="ioc.safety.analysis",
        environment="production",
        variables={...},
        user_question="...",
    )
    messages = result.messages
    # 然后调用 model.ainvoke(messages, ...)
"""

import logging
from typing import Any

from app.db.session import get_session_local
from app.modules.prompt_center.application.prompt_render_service import render_prompt
from app.modules.prompt_center.domain.entities import PromptRenderResult

logger = logging.getLogger(__name__)


def get_rendered_prompt(
    prompt_key: str,
    environment: str = "production",
    variables: dict[str, Any] | None = None,
    user_question: str | None = None,
    fallback_messages: list[dict] | None = None,
) -> PromptRenderResult:
    """获取渲染后的 Prompt 消息列表。

    参数:
        prompt_key: Prompt 的唯一标识
        environment: 运行环境 (development/testing/staging/production)
        variables: 运行时变量（设备数据、上下文等）
        user_question: 用户问题
        fallback_messages: 当 Prompt Center 不可用时的兜底消息

    返回:
        PromptRenderResult 包含 messages 和其他元数据
    """
    try:
        db = get_session_local()()
        try:
            result = render_prompt(
                db=db,
                prompt_key=prompt_key,
                environment=environment,
                variables=variables or {},
                user_question=user_question,
            )
            return result
        finally:
            db.close()
    except Exception as e:
        logger.exception("Prompt Center 渲染失败，使用兜底 Prompt")
        if fallback_messages:
            return PromptRenderResult(
                prompt_id=0,
                prompt_key=prompt_key,
                prompt_name=prompt_key,
                version="fallback",
                environment=environment,
                messages=fallback_messages,
                variables=variables or {},
            )
        raise


def get_prompt_metadata(
    prompt_key: str,
    environment: str = "production",
) -> dict[str, Any]:
    """获取 Prompt 元数据，用于注入 LangSmith Metadata。"""
    try:
        db = get_session_local()()
        try:
            from app.modules.prompt_center.infrastructure.repositories import prompt_def_repo, prompt_version_repo, prompt_release_repo

            prompt = prompt_def_repo.get_by_key(db, prompt_key)
            if prompt is None:
                return {}

            version_record = None
            if environment == "production":
                release = prompt_release_repo.get_active(db, prompt.id, environment)
                if release:
                    version_record = prompt_version_repo.get_by_id(db, release.version_id)
            else:
                version_records = prompt_version_repo.get_by_prompt(db, prompt.id)
                if version_records:
                    version_record = version_records[0]

            return {
                "prompt_key": prompt_key,
                "prompt_version": version_record.version if version_record else "unknown",
                "prompt_commit_hash": version_record.langsmith_commit_hash if version_record else None,
                "prompt_environment": environment,
            }
        finally:
            db.close()
    except Exception as e:
        logger.warning("获取 Prompt 元数据失败: %s", e)
        return {}
