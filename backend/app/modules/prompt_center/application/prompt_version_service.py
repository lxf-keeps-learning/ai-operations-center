import logging
from typing import Any

from sqlalchemy.orm import Session

from app.modules.prompt_center.domain.enums import AuditAction, PromptStatus
from app.modules.prompt_center.domain.exceptions import (
    invalid_status_transition,
    prompt_not_found,
    version_not_found,
    VERSION_LOCKED,
    NOT_APPROVED,
)
from app.modules.prompt_center.infrastructure.repositories import (
    prompt_audit_log_repo,
    prompt_def_repo,
    prompt_version_repo,
)
from app.modules.prompt_center.schemas.prompt_schema import PromptVersionSummary
from app.modules.prompt_center.schemas.version_schema import (
    DiffItem,
    VersionCompareResponse,
    VersionCreate,
    VersionResponse,
    VersionUpdate,
)

logger = logging.getLogger(__name__)

_ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    PromptStatus.DRAFT.value: {PromptStatus.TESTING.value, PromptStatus.REVIEWING.value},
    PromptStatus.TESTING.value: {PromptStatus.REVIEWING.value, PromptStatus.DRAFT.value},
    PromptStatus.REVIEWING.value: {PromptStatus.APPROVED.value, PromptStatus.REJECTED.value},
    PromptStatus.REJECTED.value: {PromptStatus.DRAFT.value},
    PromptStatus.APPROVED.value: {PromptStatus.GRAY.value, PromptStatus.PUBLISHED.value},
    PromptStatus.GRAY.value: {PromptStatus.PUBLISHED.value, PromptStatus.DRAFT.value},
    PromptStatus.PUBLISHED.value: set(),
    PromptStatus.OFFLINE.value: set(),
    PromptStatus.ARCHIVED.value: set(),
}


def _check_transition(current: str, target: str) -> None:
    allowed = _ALLOWED_TRANSITIONS.get(current, set())
    if target not in allowed:
        raise invalid_status_transition(current, target)


def create_version(
    db: Session, prompt_id: int, data: VersionCreate, operator_id: str | None = None,
) -> VersionResponse:
    prompt = prompt_def_repo.get_by_id(db, prompt_id)
    if prompt is None:
        raise prompt_not_found(prompt_id)

    payload = data.model_dump(exclude_none=True, by_alias=True)
    base_version = None
    if prompt.current_version_id:
        base_version = prompt_version_repo.get_by_id(db, prompt.current_version_id)
    if base_version is None:
        existing_versions = prompt_version_repo.get_by_prompt(db, prompt_id)
        base_version = existing_versions[0] if existing_versions else None
    if base_version is not None:
        for field in (
            "system_content",
            "business_role_content",
            "business_goal_content",
            "business_rules",
            "output_requirement",
            "positive_examples",
            "negative_examples",
            "model_config",
            "output_schema",
        ):
            if field not in payload:
                payload[field] = getattr(base_version, field)
    payload["prompt_id"] = prompt_id
    payload["status"] = PromptStatus.DRAFT.value
    payload["created_by"] = operator_id

    record = prompt_version_repo.create_draft_version(db, payload)
    if data.business_rules is not None:
        record.business_rules = [r.model_dump() for r in data.business_rules]
    if data.positive_examples is not None:
        record.positive_examples = [e.model_dump() for e in data.positive_examples]
    if data.negative_examples is not None:
        record.negative_examples = [e.model_dump() for e in data.negative_examples]
    db.commit()
    db.refresh(record)

    prompt_audit_log_repo.create(db, {
        "prompt_id": prompt_id,
        "version_id": record.id,
        "action": AuditAction.CREATE.value,
        "after_data": {"version": record.version, "change_reason": data.change_reason},
        "operator_id": operator_id,
    })

    return VersionResponse.model_validate(record)


def update_version(
    db: Session, version_id: int, data: VersionUpdate, operator_id: str | None = None,
) -> VersionResponse:
    record = prompt_version_repo.get_by_id(db, version_id)
    if record is None:
        raise version_not_found(version_id)
    if record.status not in (PromptStatus.DRAFT.value, PromptStatus.REJECTED.value):
        raise VERSION_LOCKED

    payload = data.model_dump(exclude_none=True, by_alias=True)
    if "business_rules" in payload and isinstance(data.business_rules, list):
        payload["business_rules"] = [r.model_dump() for r in data.business_rules]
    if "positive_examples" in payload and isinstance(data.positive_examples, list):
        payload["positive_examples"] = [e.model_dump() for e in data.positive_examples]
    if "negative_examples" in payload and isinstance(data.negative_examples, list):
        payload["negative_examples"] = [e.model_dump() for e in data.negative_examples]

    record = prompt_version_repo.update(db, version_id, payload)
    if record is None:
        raise version_not_found(version_id)

    prompt_audit_log_repo.create(db, {
        "prompt_id": record.prompt_id,
        "version_id": version_id,
        "action": AuditAction.UPDATE.value,
        "before_data": {"version": record.version},
        "after_data": {"change_reason": data.change_reason},
        "operator_id": operator_id,
    })
    return VersionResponse.model_validate(record)


def submit_version(
    db: Session, version_id: int, operator_id: str | None = None,
) -> VersionResponse:
    record = prompt_version_repo.get_by_id(db, version_id)
    if record is None:
        raise version_not_found(version_id)
    _check_transition(record.status, PromptStatus.REVIEWING.value)
    record = prompt_version_repo.update_status(db, version_id, PromptStatus.REVIEWING.value)
    prompt_audit_log_repo.create(db, {
        "prompt_id": record.prompt_id,
        "version_id": version_id,
        "action": AuditAction.SUBMIT_REVIEW.value,
        "operator_id": operator_id,
    })
    return VersionResponse.model_validate(record)


def approve_version(
    db: Session, version_id: int, operator_id: str | None = None,
) -> VersionResponse:
    record = prompt_version_repo.get_by_id(db, version_id)
    if record is None:
        raise version_not_found(version_id)
    _check_transition(record.status, PromptStatus.APPROVED.value)
    record = prompt_version_repo.update_status(db, version_id, PromptStatus.APPROVED.value)
    prompt_def_repo.update(db, record.prompt_id, {"current_version_id": version_id})
    prompt_audit_log_repo.create(db, {
        "prompt_id": record.prompt_id,
        "version_id": version_id,
        "action": AuditAction.APPROVE.value,
        "operator_id": operator_id,
    })
    return VersionResponse.model_validate(record)


def reject_version(
    db: Session, version_id: int, operator_id: str | None = None,
) -> VersionResponse:
    record = prompt_version_repo.get_by_id(db, version_id)
    if record is None:
        raise version_not_found(version_id)
    _check_transition(record.status, PromptStatus.REJECTED.value)
    record = prompt_version_repo.update_status(db, version_id, PromptStatus.REJECTED.value)
    prompt_audit_log_repo.create(db, {
        "prompt_id": record.prompt_id,
        "version_id": version_id,
        "action": AuditAction.REJECT.value,
        "operator_id": operator_id,
    })
    return VersionResponse.model_validate(record)


def get_version(db: Session, version_id: int) -> VersionResponse:
    record = prompt_version_repo.get_by_id(db, version_id)
    if record is None:
        raise version_not_found(version_id)
    return VersionResponse.model_validate(record)


def get_versions_by_prompt(db: Session, prompt_id: int) -> list[PromptVersionSummary]:
    records = prompt_version_repo.get_by_prompt(db, prompt_id)
    return [PromptVersionSummary.model_validate(r) for r in records]


def compare_versions(
    db: Session,
    source_version_id: int,
    target_version_id: int,
    prompt_id: int | None = None,
) -> VersionCompareResponse:
    source = prompt_version_repo.get_by_id(db, source_version_id)
    target = prompt_version_repo.get_by_id(db, target_version_id)
    if source is None:
        raise version_not_found(source_version_id)
    if target is None:
        raise version_not_found(target_version_id)
    if (
        source.prompt_id != target.prompt_id
        or (prompt_id is not None and source.prompt_id != prompt_id)
    ):
        raise version_not_found(target_version_id)

    diffs = _compute_diffs(source, target)
    return VersionCompareResponse(
        source_version=VersionResponse.model_validate(source),
        target_version=VersionResponse.model_validate(target),
        diffs=diffs,
    )


def _compute_diffs(source: Any, target: Any) -> list[DiffItem]:
    fields = [
        ("system_content", "系统提示"),
        ("business_role_content", "角色定义"),
        ("business_goal_content", "业务目标"),
        ("output_requirement", "输出要求"),
        ("business_rules", "业务规则"),
        ("positive_examples", "正例"),
        ("negative_examples", "反例"),
        ("model_config", "模型配置"),
        ("output_schema", "输出 Schema"),
    ]
    diffs: list[DiffItem] = []
    for field, label in fields:
        s_val = _val_to_str(getattr(source, field, None))
        t_val = _val_to_str(getattr(target, field, None))
        if s_val == t_val:
            continue
        change_type = "added" if not s_val else "removed" if not t_val else "modified"
        diffs.append(DiffItem(
            field=field, field_label=label,
            source_value=s_val, target_value=t_val,
            change_type=change_type,
        ))
    return diffs


def _val_to_str(val: Any) -> str | None:
    if val is None:
        return None
    if isinstance(val, (list, dict)):
        import json
        return json.dumps(val, ensure_ascii=False, indent=2)
    return str(val)
