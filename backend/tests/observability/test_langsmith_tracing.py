"""LangSmith Trace 配置与脱敏测试。"""

from app.config.settings import settings
from app.observability import langsmith_tracing


def test_sanitize_trace_payload_masks_credentials_and_personal_data() -> None:
    payload = {
        "api_key": "should-never-leave-process",
        "nested": {
            "message": "联系人手机号 13800138000，邮箱 user@example.com",
            "access_token": "another-secret",
            "copied_key": "误贴密钥 lsv2_test_example_12345678",
        },
    }

    sanitized = langsmith_tracing.sanitize_trace_payload(payload)

    assert sanitized["api_key"] == "[REDACTED:credential]"
    assert sanitized["nested"]["access_token"] == "[REDACTED:credential]"
    assert "13800138000" not in sanitized["nested"]["message"]
    assert "user@example.com" not in sanitized["nested"]["message"]
    assert "[REDACTED:mobile]" in sanitized["nested"]["message"]
    assert "[REDACTED:email]" in sanitized["nested"]["message"]
    assert "lsv2_test_example_12345678" not in sanitized["nested"]["copied_key"]
    assert "[REDACTED:api_key]" in sanitized["nested"]["copied_key"]


def test_disabled_tracing_returns_metadata_without_callbacks(monkeypatch) -> None:
    monkeypatch.setattr(settings, "langsmith_tracing", False)
    langsmith_tracing._get_client.cache_clear()

    config = langsmith_tracing.build_langsmith_config(
        trace_id="trace_001",
        graph_name="ioc_operation_analysis_graph",
        user_id="user_001",
        session_id="session_001",
        metadata={
            "company_ref": "company_001",
            "domain": "safety",
        },
    )

    assert "callbacks" not in config
    assert config["metadata"]["ioc_trace_id"] == "trace_001"
    assert config["metadata"]["domain"] == "safety"
    assert config["metadata"]["user_ref"] != "user_001"
    assert config["metadata"]["session_ref"] != "session_001"
    assert config["metadata"]["company_ref"] != "company_001"


def test_enabled_tracing_adds_langsmith_callback(monkeypatch) -> None:
    class _FakeClient:
        pass

    class _FakeTracer:
        def __init__(self, **kwargs) -> None:
            self.kwargs = kwargs

    monkeypatch.setattr(langsmith_tracing, "_get_client", lambda: _FakeClient())
    monkeypatch.setattr(langsmith_tracing, "LangChainTracer", _FakeTracer)

    config = langsmith_tracing.build_langsmith_config(
        trace_id="trace_002",
        graph_name="ioc_report_chat_graph",
        metadata={"report_id": "42"},
    )

    assert len(config["callbacks"]) == 1
    tracer = config["callbacks"][0]
    assert tracer.kwargs["project_name"] == settings.langsmith_project
    assert tracer.kwargs["metadata"]["ioc_trace_id"] == "trace_002"
    assert config["metadata"]["report_id"] == "42"
