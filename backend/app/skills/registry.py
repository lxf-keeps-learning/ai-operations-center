"""Runtime Skill 注册表。"""

from app.skills.contracts import SkillDefinition


class SkillNotFoundError(LookupError):
    def __init__(self, skill_id: str):
        self.skill_id = skill_id
        super().__init__(f"Skill not found: {skill_id}")


class DuplicateSkillError(ValueError):
    def __init__(self, skill_id: str):
        self.skill_id = skill_id
        super().__init__(f"Skill already registered: {skill_id}")


class SkillRegistry:
    """Skill 定义的单一发现入口。"""

    def __init__(self) -> None:
        self._skills: dict[str, SkillDefinition] = {}

    def register(self, definition: SkillDefinition) -> None:
        if definition.id in self._skills:
            raise DuplicateSkillError(definition.id)
        self._skills[definition.id] = definition

    def get(self, skill_id: str) -> SkillDefinition:
        try:
            return self._skills[skill_id]
        except KeyError as exc:
            raise SkillNotFoundError(skill_id) from exc

    def list(self) -> list[SkillDefinition]:
        return [self._skills[skill_id] for skill_id in sorted(self._skills)]
