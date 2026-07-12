"""Runtime Skill 能力目录。

Skill 负责描述业务目标、输入输出、允许使用的 Tool 和风险边界；
真正的流程执行继续复用现有 LangGraph/Service。
"""

from app.skills.definitions import skill_registry

__all__ = ["skill_registry"]
