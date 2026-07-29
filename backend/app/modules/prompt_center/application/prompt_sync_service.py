from sqlalchemy.orm import Session

from app.config.settings import settings
from app.modules.prompt_center.domain.exceptions import prompt_sync_failed
from app.modules.prompt_center.infrastructure.langsmith_client import (
    LangSmithPromptClientError,
    PromptSyncResult,
    langsmith_prompt_client,
)
from app.modules.prompt_center.infrastructure.repositories import prompt_version_repo


def ensure_prompt_version_synced(
    db: Session,
    prompt,
    version,
) -> PromptSyncResult | None:
    if not settings.langsmith_prompt_sync_enabled:
        return None

    persisted_version = prompt_version_repo.get_by_id(db, version.id)
    if persisted_version is None:
        raise prompt_sync_failed("Prompt 版本不存在，无法同步")

    if persisted_version.langsmith_commit_hash:
        return PromptSyncResult(
            commit_hash=persisted_version.langsmith_commit_hash,
            tag=persisted_version.langsmith_tag or persisted_version.version,
            url=langsmith_prompt_client.get_commit_url(persisted_version.langsmith_commit_hash) or "",
        )

    try:
        result = langsmith_prompt_client.push_prompt(prompt, persisted_version)
        updated = prompt_version_repo.update(
            db,
            persisted_version.id,
            {
                "langsmith_commit_hash": result.commit_hash,
                "langsmith_tag": result.tag,
            },
        )
        if updated is None or updated.langsmith_commit_hash != result.commit_hash:
            raise RuntimeError("Prompt Commit 保存失败")
        return result
    except LangSmithPromptClientError as exc:
        raise prompt_sync_failed(str(exc)) from exc
    except Exception as exc:
        db.rollback()
        raise prompt_sync_failed("LangSmith Prompt Commit 保存失败") from exc
