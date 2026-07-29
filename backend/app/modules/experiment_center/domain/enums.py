from enum import Enum


class ExperimentStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ExperimentVersion(str, Enum):
    SOURCE = "source"
    TARGET = "target"


class Winner(str, Enum):
    SOURCE = "source"
    TARGET = "target"
    DRAW = "draw"
    PENDING = "pending"
