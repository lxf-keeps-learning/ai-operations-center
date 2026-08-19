from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
import hashlib

from app.tool_center.contracts import ToolContext
from app.tool_registry.contracts import ToolDefinitionRecord, ToolPolicyRecord, ToolVersionRecord
from app.tool_registry.policy import resolve_policy


@dataclass(frozen=True)
class VersionSelection:
    version_id: int
    version: str
    implementation_ref: str
    gray_bucket: int | None
    selected_stable: bool


def gray_bucket(tool_key: str, tenant_id: str) -> int:
    digest = hashlib.sha256(f"tool-registry-v1:{tool_key}:{tenant_id}".encode()).digest()
    return int.from_bytes(digest[:8], "big") % 100


def choose_version(
    tool: ToolDefinitionRecord,
    versions: Sequence[ToolVersionRecord],
    policies: Sequence[ToolPolicyRecord],
    context: ToolContext,
    stable_only: bool = False,
) -> VersionSelection:
    stable = _stable_version(versions)
    if stable_only or not context.tenant_id:
        return _selection(stable, gray_bucket_value=None, selected_stable=True)

    gray_candidates = sorted(
        (version for version in versions if not version.is_stable),
        key=lambda version: version.id,
        reverse=True,
    )
    if not gray_candidates:
        return _selection(stable, gray_bucket_value=None, selected_stable=True)

    bucket = gray_bucket(tool.tool_key, context.tenant_id)
    for candidate in gray_candidates:
        try:
            candidate_policy = resolve_policy(
                list(policies),
                version_id=candidate.id,
                context=context,
            )
        except ValueError:
            # 候选没有自己的可继承权限时只跳过候选；稳定版稍后独立授权。
            continue
        if candidate_policy.decision.value == "deny":
            continue
        if bucket < candidate.gray_percentage:
            return _selection(candidate, gray_bucket_value=bucket, selected_stable=False)

    return _selection(stable, gray_bucket_value=bucket, selected_stable=True)


def _stable_version(versions: Sequence[ToolVersionRecord]) -> ToolVersionRecord:
    stable_versions = sorted(
        (version for version in versions if version.is_stable),
        key=lambda version: version.id,
        reverse=True,
    )
    if not stable_versions:
        raise ValueError("no stable version available")
    return stable_versions[0]


def _selection(
    version: ToolVersionRecord,
    *,
    gray_bucket_value: int | None,
    selected_stable: bool,
) -> VersionSelection:
    return VersionSelection(
        version_id=version.id,
        version=version.version,
        implementation_ref=version.implementation_ref,
        gray_bucket=gray_bucket_value,
        selected_stable=selected_stable,
    )
