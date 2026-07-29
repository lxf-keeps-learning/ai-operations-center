from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.config.settings import settings
from app.core.exception.base_exception import AppException
from app.db.base import Base
from app.modules.prompt_center.application import (
    prompt_release_service,
    prompt_service,
    prompt_sync_service,
    prompt_version_service,
)
from app.modules.prompt_center.infrastructure.langsmith_client import (
    LangSmithPromptClientError,
    PromptSyncResult,
)
from app.modules.prompt_center.infrastructure.models import (
    PromptAuditLog,
    PromptDefinition,
    PromptRelease,
    PromptVersion,
)
from app.modules.prompt_center.schemas.prompt_schema import PromptCreate
from app.modules.prompt_center.schemas.release_schema import ReleaseRequest, RollbackRequest
from app.modules.prompt_center.schemas.version_schema import VersionCreate


class FakePromptClient:
    def __init__(self, error: Exception | None = None):
        self.error = error
        self.calls: list[tuple[str, str]] = []

    def push_prompt(self, prompt, version) -> PromptSyncResult:
        self.calls.append((prompt.prompt_key, version.version))
        if self.error is not None:
            raise self.error
        return PromptSyncResult(
            commit_hash=f"commit{version.version.replace('.', '')}",
            tag=version.version,
            url=f"https://smith.langchain.com/prompts/{prompt.prompt_key}/commit123",
        )

    @staticmethod
    def get_commit_url(commit_hash: str) -> str:
        return f"https://smith.langchain.com/commits/{commit_hash}"


@pytest.fixture
def db() -> Iterator[Session]:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def _create_approved_version(db: Session, key: str = "ioc.sync.release"):
    prompt = prompt_service.create_prompt(
        db,
        PromptCreate(
            prompt_key=key,
            prompt_name="同步发布测试",
            description="用于离线验收的脱敏 Prompt",
        ),
        operator_id="creator",
    )
    version = prompt_version_service.create_version(
        db,
        prompt.id,
        VersionCreate(
            system_content="system",
            business_goal_content="goal",
            change_reason="test change",
        ),
        operator_id="creator",
    )
    prompt_version_service.submit_version(db, version.id, operator_id="creator")
    prompt_version_service.approve_version(db, version.id, operator_id="reviewer")
    return prompt, version


def _create_next_approved_version(db: Session, prompt_id: int):
    version = prompt_version_service.create_version(
        db,
        prompt_id,
        VersionCreate(
            business_goal_content="goal-v2",
            change_reason="second version",
        ),
        operator_id="creator",
    )
    prompt_version_service.submit_version(db, version.id, operator_id="creator")
    prompt_version_service.approve_version(db, version.id, operator_id="reviewer")
    return version


def test_sync_disabled_does_not_call_remote_client(db, monkeypatch):
    prompt, version = _create_approved_version(db)
    fake = FakePromptClient()
    monkeypatch.setattr(settings, "langsmith_prompt_sync_enabled", False)
    monkeypatch.setattr(prompt_sync_service, "langsmith_prompt_client", fake)

    result = prompt_sync_service.ensure_prompt_version_synced(db, prompt, version)

    assert result is None
    assert fake.calls == []


def test_first_sync_persists_commit_and_second_sync_reuses_it(db, monkeypatch):
    prompt, version = _create_approved_version(db)
    fake = FakePromptClient()
    monkeypatch.setattr(settings, "langsmith_prompt_sync_enabled", True)
    monkeypatch.setattr(settings, "langsmith_api_key", "test-key")
    monkeypatch.setattr(prompt_sync_service, "langsmith_prompt_client", fake)

    first = prompt_sync_service.ensure_prompt_version_synced(db, prompt, version)
    second = prompt_sync_service.ensure_prompt_version_synced(db, prompt, version)

    assert first.commit_hash == "commit100"
    assert first.tag == "1.0.0"
    assert second.commit_hash == first.commit_hash
    assert second.tag == first.tag
    assert fake.calls == [("ioc.sync.release", "1.0.0")]
    persisted = db.get(PromptVersion, version.id)
    assert persisted.langsmith_commit_hash == "commit100"
    assert persisted.langsmith_tag == "1.0.0"


def test_gray_then_production_release_syncs_once_and_audits_commit(db, monkeypatch):
    prompt, version = _create_approved_version(db)
    fake = FakePromptClient()
    monkeypatch.setattr(settings, "langsmith_prompt_sync_enabled", True)
    monkeypatch.setattr(settings, "langsmith_api_key", "test-key")
    monkeypatch.setattr(prompt_sync_service, "langsmith_prompt_client", fake)

    prompt_release_service.gray_release(
        db,
        prompt.id,
        version.id,
        ReleaseRequest(
            environment="staging",
            release_type="gray",
            traffic_ratio=20,
            approved_by="reviewer",
            released_by="publisher",
        ),
    )
    prompt_release_service.production_release(
        db,
        prompt.id,
        version.id,
        ReleaseRequest(
            environment="production",
            release_type="full",
            approved_by="reviewer",
            released_by="publisher",
        ),
    )

    assert fake.calls == [("ioc.sync.release", "1.0.0")]
    releases = list(db.scalars(select(PromptRelease)).all())
    assert {(item.environment, item.status) for item in releases} == {
        ("staging", "active"),
        ("production", "active"),
    }
    publish_audits = list(
        db.scalars(
            select(PromptAuditLog).where(
                PromptAuditLog.action.in_(["gray_release", "publish"]),
            )
        ).all()
    )
    assert len(publish_audits) == 2
    assert all(item.after_data["langsmith_commit_hash"] == "commit100" for item in publish_audits)
    assert all(item.after_data["langsmith_tag"] == "1.0.0" for item in publish_audits)


def test_sync_failure_keeps_current_release_and_candidate_status_unchanged(db, monkeypatch):
    prompt, version1 = _create_approved_version(db)
    monkeypatch.setattr(settings, "langsmith_prompt_sync_enabled", False)
    prompt_release_service.production_release(
        db,
        prompt.id,
        version1.id,
        ReleaseRequest(environment="production", released_by="publisher"),
    )
    version2 = _create_next_approved_version(db, prompt.id)
    definition_version_before = db.get(PromptDefinition, prompt.id).current_version_id
    active_before = db.scalar(
        select(PromptRelease).where(
            PromptRelease.prompt_id == prompt.id,
            PromptRelease.environment == "production",
            PromptRelease.status == "active",
        )
    )

    monkeypatch.setattr(settings, "langsmith_prompt_sync_enabled", True)
    monkeypatch.setattr(settings, "langsmith_api_key", "test-key")
    fake = FakePromptClient(LangSmithPromptClientError("LangSmith API 请求失败"))
    monkeypatch.setattr(prompt_sync_service, "langsmith_prompt_client", fake)

    with pytest.raises(AppException) as exc:
        prompt_release_service.production_release(
            db,
            prompt.id,
            version2.id,
            ReleaseRequest(environment="production", released_by="publisher"),
        )

    assert exc.value.http_status == 502
    assert exc.value.message == "LangSmith API 请求失败"
    db.expire_all()
    active_after = db.scalar(
        select(PromptRelease).where(
            PromptRelease.prompt_id == prompt.id,
            PromptRelease.environment == "production",
            PromptRelease.status == "active",
        )
    )
    assert active_after.id == active_before.id
    assert active_after.version_id == version1.id
    assert db.get(PromptDefinition, prompt.id).current_version_id == definition_version_before
    assert db.get(PromptVersion, version2.id).status == "approved"
    assert len(list(db.scalars(select(PromptRelease)).all())) == 1


def test_rollback_never_calls_prompt_sync(db, monkeypatch):
    prompt, version1 = _create_approved_version(db)
    monkeypatch.setattr(settings, "langsmith_prompt_sync_enabled", False)
    prompt_release_service.production_release(
        db,
        prompt.id,
        version1.id,
        ReleaseRequest(environment="production", released_by="publisher"),
    )
    version2 = _create_next_approved_version(db, prompt.id)
    prompt_release_service.production_release(
        db,
        prompt.id,
        version2.id,
        ReleaseRequest(environment="production", released_by="publisher"),
    )

    fake = FakePromptClient(AssertionError("rollback must not sync"))
    monkeypatch.setattr(settings, "langsmith_prompt_sync_enabled", True)
    monkeypatch.setattr(prompt_sync_service, "langsmith_prompt_client", fake)

    prompt_release_service.rollback(
        db,
        prompt.id,
        RollbackRequest(environment="production", released_by="publisher"),
    )

    assert fake.calls == []
    active = db.scalar(
        select(PromptRelease).where(
            PromptRelease.prompt_id == prompt.id,
            PromptRelease.environment == "production",
            PromptRelease.status == "active",
        )
    )
    assert active.version_id == version1.id
