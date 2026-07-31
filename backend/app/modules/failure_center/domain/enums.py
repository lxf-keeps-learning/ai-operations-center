from enum import Enum


class FailureType(str, Enum):
    JSON_FORMAT = "json_format"
    SCHEMA_COMPLIANCE = "schema_compliance"
    FIELD_MISSING = "field_missing"
    HALLUCINATION = "hallucination"
    NOT_ANSWERED = "not_answered"
    NOT_GROUNDED = "not_grounded"
    NO_EVIDENCE = "no_evidence"
    VAGUE_ADVICE = "vague_advice"
    TIMEOUT = "timeout"
    LLM_ERROR = "llm_error"
    UNKNOWN = "unknown"


class FailureSeverity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class FailureStatus(str, Enum):
    PENDING = "pending"
    ANALYZED = "analyzed"
    CONVERTED = "converted"
    RESOLVED = "resolved"


FAILURE_TYPE_MAP: dict[str, FailureType] = {
    "json_format": FailureType.JSON_FORMAT,
    "schema_compliance": FailureType.SCHEMA_COMPLIANCE,
    "field_completeness": FailureType.FIELD_MISSING,
    "no_hallucination": FailureType.HALLUCINATION,
    "question_answered": FailureType.NOT_ANSWERED,
    "data_grounded": FailureType.NOT_GROUNDED,
    "evidence_provided": FailureType.NO_EVIDENCE,
    "actionable_advice": FailureType.VAGUE_ADVICE,
}
