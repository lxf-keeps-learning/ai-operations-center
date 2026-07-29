import logging
from typing import Any

from sqlalchemy.orm import Session

from app.modules.prompt_center.domain.enums import AuditAction, PromptStatus
from app.modules.prompt_center.domain.exceptions import (
    prompt_not_found,
    PROMPT_KEY_EXISTS,
)
from app.modules.prompt_center.infrastructure.repositories import (
    prompt_audit_log_repo,
    prompt_def_repo,
    prompt_variable_repo,
)
from app.modules.prompt_center.schemas.prompt_schema import (
    PromptCreate,
    PromptDetailResponse,
    PromptResponse,
    PromptUpdate,
    VariableSchema,
)

logger = logging.getLogger(__name__)


def create_prompt(db: Session, data: PromptCreate, operator_id: str | None = None) -> PromptResponse:
    existing = prompt_def_repo.get_by_key(db, data.prompt_key)
    if existing:
        raise PROMPT_KEY_EXISTS
    record = prompt_def_repo.create(db, {
        "prompt_key": data.prompt_key,
        "prompt_name": data.prompt_name,
        "business_scene": data.business_scene,
        "graph_name": data.graph_name,
        "node_name": data.node_name,
        "description": data.description,
        "owner_id": data.owner_id,
        "status": PromptStatus.DRAFT.value,
        "created_by": operator_id or data.owner_id,
    })
    prompt_audit_log_repo.create(db, {
        "prompt_id": record.id,
        "action": AuditAction.CREATE.value,
        "after_data": {"prompt_key": data.prompt_key, "prompt_name": data.prompt_name},
        "operator_id": operator_id,
    })
    return PromptResponse.model_validate(record)


def update_prompt(db: Session, prompt_id: int, data: PromptUpdate, operator_id: str | None = None) -> PromptResponse:
    record = prompt_def_repo.get_by_id(db, prompt_id)
    if record is None:
        raise prompt_not_found(prompt_id)
    before = {"prompt_name": record.prompt_name, "description": record.description}
    record = prompt_def_repo.update(db, prompt_id, {
        "prompt_name": data.prompt_name,
        "business_scene": data.business_scene,
        "graph_name": data.graph_name,
        "node_name": data.node_name,
        "description": data.description,
        "owner_id": data.owner_id,
        "updated_by": operator_id,
    })
    if record is None:
        raise prompt_not_found(prompt_id)
    prompt_audit_log_repo.create(db, {
        "prompt_id": prompt_id,
        "action": AuditAction.UPDATE.value,
        "before_data": before,
        "after_data": {"prompt_name": record.prompt_name, "description": record.description},
        "operator_id": operator_id,
    })
    return PromptResponse.model_validate(record)


def delete_prompt(db: Session, prompt_id: int, operator_id: str | None = None) -> None:
    record = prompt_def_repo.get_by_id(db, prompt_id)
    if record is None:
        raise prompt_not_found(prompt_id)
    prompt_def_repo.soft_delete(db, prompt_id)
    prompt_audit_log_repo.create(db, {
        "prompt_id": prompt_id,
        "action": AuditAction.DELETE.value,
        "before_data": {"prompt_key": record.prompt_key, "prompt_name": record.prompt_name},
        "operator_id": operator_id,
    })


def get_prompt(db: Session, prompt_id: int) -> PromptDetailResponse:
    record = prompt_def_repo.get_by_id(db, prompt_id)
    if record is None or record.deleted:
        raise prompt_not_found(prompt_id)

    variables = prompt_variable_repo.get_by_prompt(db, prompt_id)
    from app.modules.prompt_center.application.prompt_version_service import get_versions_by_prompt
    versions = get_versions_by_prompt(db, prompt_id)

    return PromptDetailResponse(
        id=record.id,
        prompt_key=record.prompt_key,
        prompt_name=record.prompt_name,
        business_scene=record.business_scene,
        graph_name=record.graph_name,
        node_name=record.node_name,
        description=record.description,
        owner_id=record.owner_id,
        current_version_id=record.current_version_id,
        status=record.status,
        created_by=record.created_by,
        created_at=record.created_at,
        updated_by=record.updated_by,
        updated_at=record.updated_at,
        variables=[VariableSchema.model_validate(v) for v in variables],
        versions=versions,
    )


def list_prompts(
    db: Session,
    search: str | None = None,
    business_scene: str | None = None,
    graph_name: str | None = None,
    node_name: str | None = None,
    status: str | None = None,
    owner_id: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[PromptResponse], int]:
    offset = (page - 1) * page_size
    items, total = prompt_def_repo.list(
        db, search=search, business_scene=business_scene,
        graph_name=graph_name, node_name=node_name,
        status=status, owner_id=owner_id,
        offset=offset, limit=page_size,
    )
    return [PromptResponse.model_validate(r) for r in items], total


def get_prompt_by_key(db: Session, prompt_key: str) -> PromptResponse | None:
    record = prompt_def_repo.get_by_key(db, prompt_key)
    if record is None:
        return None
    return PromptResponse.model_validate(record)
