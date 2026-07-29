import logging

from sqlalchemy.orm import Session

from app.modules.prompt_center.domain.enums import AuditAction, Environment, PromptStatus, ReleaseType
from app.core.exception.base_exception import AppException
from app.core.exception.error_code import ErrorCode
from app.modules.prompt_center.domain.exceptions import (
    invalid_status_transition,
    prompt_not_found,
    version_not_found,
    NOT_APPROVED,
)

RELEASE_NOT_FOUND_EC = ErrorCode(code=404014, message="发布记录不存在", http_status=404, description="发布记录未找到")
from app.modules.prompt_center.infrastructure.repositories import (
    prompt_audit_log_repo,
    prompt_def_repo,
    prompt_release_repo,
    prompt_version_repo,
)
from app.modules.prompt_center.schemas.release_schema import (
    ReleaseRequest,
    ReleaseResponse,
    RollbackRequest,
)

logger = logging.getLogger(__name__)


def gray_release(
    db: Session, prompt_id: int, version_id: int, data: ReleaseRequest,
) -> ReleaseResponse:
    return _release(db, prompt_id, version_id, data, PromptStatus.GRAY.value)


def production_release(
    db: Session, prompt_id: int, version_id: int, data: ReleaseRequest,
) -> ReleaseResponse:
    return _release(db, prompt_id, version_id, data, PromptStatus.PUBLISHED.value)


def _release(
    db: Session, prompt_id: int, version_id: int, data: ReleaseRequest, target_status: str,
) -> ReleaseResponse:
    prompt = prompt_def_repo.get_by_id(db, prompt_id)
    if prompt is None:
        raise prompt_not_found(prompt_id)

    version = prompt_version_repo.get_by_id(db, version_id)
    if version is None or version.prompt_id != prompt_id:
        raise version_not_found(version_id)

    if version.status not in (PromptStatus.APPROVED.value, PromptStatus.GRAY.value, PromptStatus.PUBLISHED.value):
        if version.status != target_status:
            if version.status not in (PromptStatus.APPROVED.value, PromptStatus.GRAY.value):
                raise NOT_APPROVED

    prompt_release_repo.deactivate_env(db, prompt_id, data.environment)

    release_record = prompt_release_repo.create(db, {
        "prompt_id": prompt_id,
        "version_id": version_id,
        "environment": data.environment,
        "release_type": data.release_type,
        "traffic_ratio": data.traffic_ratio,
        "status": "active",
        "approved_by": data.approved_by,
        "released_by": data.released_by,
        "release_note": data.release_note,
    })

    prompt_version_repo.update_status(db, version_id, target_status)
    prompt_def_repo.update(db, prompt_id, {
        "current_version_id": version_id,
        "status": target_status,
        "updated_by": data.released_by,
    })

    prompt_audit_log_repo.create(db, {
        "prompt_id": prompt_id,
        "version_id": version_id,
        "action": AuditAction.PUBLISH.value if target_status == PromptStatus.PUBLISHED.value else AuditAction.GRAY_RELEASE.value,
        "after_data": {
            "environment": data.environment,
            "release_type": data.release_type,
            "version": version.version,
        },
        "operator_id": data.released_by,
    })

    return ReleaseResponse.model_validate(release_record)


def rollback(
    db: Session, prompt_id: int, data: RollbackRequest,
) -> ReleaseResponse | None:
    prompt = prompt_def_repo.get_by_id(db, prompt_id)
    if prompt is None:
        raise prompt_not_found(prompt_id)

    current_release = prompt_release_repo.get_active(db, prompt_id, data.environment)
    if current_release is None:
        raise AppException.from_error_code(RELEASE_NOT_FOUND_EC)

    previous_releases = prompt_release_repo.list_by_prompt(db, prompt_id)
    prev_release = None
    for r in previous_releases:
        if r.id != current_release.id and r.environment == data.environment:
            prev_release = r
            break

    if prev_release is None:
        raise AppException.from_error_code(RELEASE_NOT_FOUND_EC)

    prompt_release_repo.deactivate_env(db, prompt_id, data.environment)

    rollback_record = prompt_release_repo.create(db, {
        "prompt_id": prompt_id,
        "version_id": prev_release.version_id,
        "environment": data.environment,
        "release_type": ReleaseType.ROLLBACK.value,
        "status": "active",
        "released_by": data.released_by,
        "rollback_version_id": current_release.version_id,
        "release_note": data.release_note,
    })

    prompt_version_repo.update_status(db, prev_release.version_id, PromptStatus.PUBLISHED.value)
    prompt_def_repo.update(db, prompt_id, {
        "current_version_id": prev_release.version_id,
        "status": PromptStatus.PUBLISHED.value,
    })

    prompt_audit_log_repo.create(db, {
        "prompt_id": prompt_id,
        "version_id": prev_release.version_id,
        "action": AuditAction.ROLLBACK.value,
        "after_data": {
            "environment": data.environment,
            "from_version": current_release.version_id,
            "to_version": prev_release.version_id,
        },
        "operator_id": data.released_by,
    })

    return ReleaseResponse.model_validate(rollback_record)


def get_releases(db: Session, prompt_id: int) -> list[ReleaseResponse]:
    items = prompt_release_repo.list_by_prompt(db, prompt_id)
    return [ReleaseResponse.model_validate(r) for r in items]
