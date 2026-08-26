"""LLM 错误分类测试：稳定 error_code，支撑 Operation 重试决策。"""

from app.runtime.llm.client import (
    LLM_CODE_AUTH,
    LLM_CODE_CONTENT_POLICY,
    LLM_CODE_INVALID_REQUEST,
    LLM_CODE_NETWORK,
    LLM_CODE_PROVIDER,
    LLM_CODE_RATE_LIMITED,
    LLM_CODE_TIMEOUT,
    LLM_CODE_UNKNOWN,
    RETRYABLE_LLM_ERROR_CODES,
    classify_llm_error,
)


def _exc(message: str) -> Exception:
    return Exception(message)


def test_timeout_maps_to_llm_timeout():
    assert classify_llm_error(_exc("Request timed out after 30s"), "Request timed out") == LLM_CODE_TIMEOUT


def test_http_429_maps_to_rate_limited():
    exc = Exception("Rate limit reached")
    exc.status_code = 429
    assert classify_llm_error(exc, "Rate limit") == LLM_CODE_RATE_LIMITED


def test_http_5xx_maps_to_provider_error():
    exc = Exception("Bad gateway")
    exc.status_code = 502
    assert classify_llm_error(exc, "Bad gateway") == LLM_CODE_PROVIDER


def test_http_4xx_maps_to_invalid_request():
    exc = Exception("Invalid request")
    exc.status_code = 400
    assert classify_llm_error(exc, "Invalid request") == LLM_CODE_INVALID_REQUEST


def test_auth_error_maps_to_auth():
    exc = Exception("Incorrect API key")
    exc.status_code = 401
    assert classify_llm_error(exc, "Incorrect API key") == LLM_CODE_AUTH


def test_network_error_maps_to_network():
    assert classify_llm_error(
        _exc("Connection error. Connection refused"), "Connection error"
    ) == LLM_CODE_NETWORK


def test_content_policy_maps_to_content_policy():
    assert classify_llm_error(
        _exc("Content filter triggered"), "Content filter"
    ) == LLM_CODE_CONTENT_POLICY


def test_unknown_error_is_not_misclassified_as_retryable_provider_5xx():
    assert classify_llm_error(_exc("Some unexpected error"), "Some unexpected") == LLM_CODE_UNKNOWN


def test_retryable_codes_contain_transient_only():
    assert LLM_CODE_TIMEOUT in RETRYABLE_LLM_ERROR_CODES
    assert LLM_CODE_NETWORK in RETRYABLE_LLM_ERROR_CODES
    assert LLM_CODE_RATE_LIMITED in RETRYABLE_LLM_ERROR_CODES
    assert LLM_CODE_PROVIDER in RETRYABLE_LLM_ERROR_CODES
    assert LLM_CODE_AUTH not in RETRYABLE_LLM_ERROR_CODES
    assert LLM_CODE_INVALID_REQUEST not in RETRYABLE_LLM_ERROR_CODES
    assert LLM_CODE_CONTENT_POLICY not in RETRYABLE_LLM_ERROR_CODES
    assert LLM_CODE_UNKNOWN not in RETRYABLE_LLM_ERROR_CODES
