from enum import Enum, IntEnum


class ModerationSeverity(IntEnum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3

    def __str__(self) -> str:
        return self.name.lower()


class ModerationAction(str, Enum):
    PASS = "pass"
    MASK = "mask"
    BLOCK = "block"
    ESCALATE = "escalate"
