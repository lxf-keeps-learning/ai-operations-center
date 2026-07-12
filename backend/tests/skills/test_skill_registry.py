import pytest

from app.skills.contracts import SkillDefinition
from app.skills.definitions import build_skill_registry
from app.skills.registry import DuplicateSkillError, SkillNotFoundError, SkillRegistry


def test_builtin_registry_contains_first_read_only_skills() -> None:
    registry = build_skill_registry()

    assert [skill.id for skill in registry.list()] == [
        "operation_analysis",
        "report_deep_answer",
    ]
    assert all(skill.risk_level == "read_only" for skill in registry.list())
    assert all(skill.side_effects.business_write is False for skill in registry.list())


def test_operation_skill_declares_current_tool_allowlist() -> None:
    skill = build_skill_registry().get("operation_analysis")

    assert set(skill.allowed_tools) == {
        "kpi_query",
        "alarm_query",
        "risk_query",
        "work_order_query",
        "ioc_summary_analysis",
    }


def test_registry_rejects_duplicate_skill() -> None:
    registry = SkillRegistry()
    definition = SkillDefinition(
        id="demo_skill",
        name="Demo",
        description="Demo skill",
        executor_id="demo_graph",
    )
    registry.register(definition)

    with pytest.raises(DuplicateSkillError, match="Skill already registered"):
        registry.register(definition)


def test_registry_raises_exact_missing_skill_error() -> None:
    with pytest.raises(SkillNotFoundError, match="Skill not found: missing_skill"):
        build_skill_registry().get("missing_skill")
