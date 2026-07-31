from enum import Enum


class EvaluatorType(str, Enum):
    DETERMINISTIC = "deterministic"
    LLM_JUDGE = "llm_judge"


class EvaluatorKey(str, Enum):
    JSON_FORMAT = "json_format"
    SCHEMA_COMPLIANCE = "schema_compliance"
    FIELD_COMPLETENESS = "field_completeness"
    TYPE_CHECK = "type_check"
    ENUM_CHECK = "enum_check"
    NO_EMPTY_ARRAY = "no_empty_array"
    RESPONSE_LENGTH = "response_length"
    QUESTION_ANSWERED = "question_answered"
    DATA_GROUNDED = "data_grounded"
    NO_HALLUCINATION = "no_hallucination"
    EVIDENCE_PROVIDED = "evidence_provided"
    ACTIONABLE_ADVICE = "actionable_advice"
    RULE_COMPLIANCE = "rule_compliance"


class MetricName(str, Enum):
    COMPLIANCE_RATE = "compliance_rate"
    FORMAT_COMPLIANCE = "format_compliance"
    AVG_SCORE = "avg_score"
    HALLUCINATION_RATE = "hallucination_rate"
    EVIDENCE_COMPLETE_RATE = "evidence_complete_rate"
    TOTAL_EVALUATIONS = "total_evaluations"
    PASS_RATE = "pass_rate"
