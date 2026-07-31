from enum import Enum


class PromptStatus(str, Enum):
    DRAFT = "draft"
    TESTING = "testing"
    REVIEWING = "reviewing"
    APPROVED = "approved"
    REJECTED = "rejected"
    GRAY = "gray"
    PUBLISHED = "published"
    OFFLINE = "offline"
    ARCHIVED = "archived"


class ReleaseType(str, Enum):
    FULL = "full"
    GRAY = "gray"
    AB_TEST = "ab_test"
    ROLLBACK = "rollback"


class ReleaseStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    ROLLED_BACK = "rolled_back"


class Environment(str, Enum):
    DEVELOPMENT = "development"
    TESTING = "testing"
    STAGING = "staging"
    PRODUCTION = "production"


class VariableDataType(str, Enum):
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    OBJECT = "object"
    ARRAY = "array"


class VariableSourceType(str, Enum):
    GRAPH_STATE = "graph_state"
    DATA_SERVICE = "data_service"
    RAG = "rag"
    USER_INPUT = "user_input"
    SYSTEM = "system"


class TestCaseType(str, Enum):
    MANUAL = "manual"
    HISTORICAL = "historical"
    PRESET = "preset"
    DATASET = "dataset"
    FAILURE = "failure"


class EvaluatorType(str, Enum):
    DETERMINISTIC = "deterministic"
    LLM_JUDGE = "llm_judge"


class AuditAction(str, Enum):
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    SUBMIT_REVIEW = "submit_review"
    APPROVE = "approve"
    REJECT = "reject"
    PUBLISH = "publish"
    GRAY_RELEASE = "gray_release"
    ROLLBACK = "rollback"
    TEST = "test"
    OFFLINE = "offline"
    ARCHIVE = "archive"
