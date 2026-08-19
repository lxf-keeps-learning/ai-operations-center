from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.context.user_context import UserContext
from app.core.exception.base_exception import AppException
from app.core.exception.error_code import TOOL_REGISTRY_CONFIG_ERROR, TOOL_REGISTRY_NOT_FOUND
from app.core.schema.response_schema import ApiResponse
from app.db.session import get_db
from app.tool_center.exceptions import RegistryConfigurationError, ToolNotFoundError
from app.tool_registry.dependencies import require_tool_registry_admin
from app.tool_registry.repository import AuditFilters
from app.tool_registry.schemas import (
    AuditPageResponse,
    PolicyReplaceRequest,
    PolicyResponse,
    PublishRequest,
    ToolCreateRequest,
    ToolResponse,
    ToolUpdateRequest,
    VersionCreateRequest,
    VersionResponse,
)
from app.tool_registry.service import ToolRegistryService

router = APIRouter(prefix="/tool-registry", tags=["Tool Registry"])


def _guard(fn):
    try:
        return fn()
    except ToolNotFoundError as exc:
        raise AppException.from_error_code(TOOL_REGISTRY_NOT_FOUND, message=exc.message) from exc
    except RegistryConfigurationError as exc:
        raise AppException.from_error_code(TOOL_REGISTRY_CONFIG_ERROR, message=exc.message) from exc


@router.get("/tools", response_model=ApiResponse[list[ToolResponse]])
def list_tools(
    db: Session = Depends(get_db),
    _admin: UserContext = Depends(require_tool_registry_admin),
) -> ApiResponse[list[ToolResponse]]:
    return ApiResponse(data=ToolRegistryService(db).list_tools())


@router.post("/tools", response_model=ApiResponse[ToolResponse])
def create_tool(
    payload: ToolCreateRequest,
    db: Session = Depends(get_db),
    admin: UserContext = Depends(require_tool_registry_admin),
) -> ApiResponse[ToolResponse]:
    return _guard(
        lambda: ApiResponse(
            data=ToolRegistryService(db).create_tool(payload, operator_id=admin.user_id)
        )
    )


@router.patch("/tools/{tool_key}", response_model=ApiResponse[ToolResponse])
def update_tool(
    tool_key: str,
    payload: ToolUpdateRequest,
    db: Session = Depends(get_db),
    admin: UserContext = Depends(require_tool_registry_admin),
) -> ApiResponse[ToolResponse]:
    return _guard(
        lambda: ApiResponse(
            data=ToolRegistryService(db).update_tool(tool_key, payload, operator_id=admin.user_id)
        )
    )


@router.get("/tools/{tool_key}/versions", response_model=ApiResponse[list[VersionResponse]])
def list_versions(
    tool_key: str,
    db: Session = Depends(get_db),
    _admin: UserContext = Depends(require_tool_registry_admin),
) -> ApiResponse[list[VersionResponse]]:
    return _guard(lambda: ApiResponse(data=ToolRegistryService(db).list_versions(tool_key)))


@router.post("/tools/{tool_key}/versions", response_model=ApiResponse[VersionResponse])
def create_version(
    tool_key: str,
    payload: VersionCreateRequest,
    db: Session = Depends(get_db),
    admin: UserContext = Depends(require_tool_registry_admin),
) -> ApiResponse[VersionResponse]:
    return _guard(
        lambda: ApiResponse(
            data=ToolRegistryService(db).create_version(tool_key, payload, operator_id=admin.user_id)
        )
    )


@router.post(
    "/tools/{tool_key}/versions/{version}/publish",
    response_model=ApiResponse[VersionResponse],
)
def publish_version(
    tool_key: str,
    version: str,
    payload: PublishRequest,
    db: Session = Depends(get_db),
    admin: UserContext = Depends(require_tool_registry_admin),
) -> ApiResponse[VersionResponse]:
    return _guard(
        lambda: ApiResponse(
            data=ToolRegistryService(db).publish_version(
                tool_key,
                version,
                release_type=payload.release_type,
                gray_percentage=payload.gray_percentage,
                operator_id=admin.user_id,
            )
        )
    )


@router.post(
    "/tools/{tool_key}/versions/{version}/retire",
    response_model=ApiResponse[VersionResponse],
)
def retire_version(
    tool_key: str,
    version: str,
    db: Session = Depends(get_db),
    admin: UserContext = Depends(require_tool_registry_admin),
) -> ApiResponse[VersionResponse]:
    return _guard(
        lambda: ApiResponse(
            data=ToolRegistryService(db).retire_version(tool_key, version, operator_id=admin.user_id)
        )
    )


@router.put("/tools/{tool_key}/policies", response_model=ApiResponse[list[PolicyResponse]])
def replace_policies(
    tool_key: str,
    payload: PolicyReplaceRequest,
    db: Session = Depends(get_db),
    admin: UserContext = Depends(require_tool_registry_admin),
) -> ApiResponse[list[PolicyResponse]]:
    return _guard(
        lambda: ApiResponse(
            data=ToolRegistryService(db).replace_policies(
                tool_key,
                payload.policies,
                operator_id=admin.user_id,
            )
        )
    )


@router.get("/audits", response_model=ApiResponse[AuditPageResponse])
def list_audits(
    trace_id: str | None = Query(default=None),
    tool_id: int | None = Query(default=None),
    version_id: int | None = Query(default=None),
    policy_id: int | None = Query(default=None),
    implementation_ref: str | None = Query(default=None),
    tenant_id: str | None = Query(default=None),
    user_id: str | None = Query(default=None),
    role: str | None = Query(default=None),
    decision: str | None = Query(default=None),
    status: str | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    _admin: UserContext = Depends(require_tool_registry_admin),
) -> ApiResponse[AuditPageResponse]:
    rows, total = ToolRegistryService(db).list_audits(
        AuditFilters(
            trace_id=trace_id,
            tool_id=tool_id,
            version_id=version_id,
            policy_id=policy_id,
            implementation_ref=implementation_ref,
            tenant_id=tenant_id,
            user_id=user_id,
            role=role,
            decision=decision,
            status=status,
        ),
        offset,
        limit,
    )
    return ApiResponse(
        data=AuditPageResponse(items=rows, total=total, offset=offset, limit=limit)
    )
