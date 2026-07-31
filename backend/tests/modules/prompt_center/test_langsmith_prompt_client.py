from types import SimpleNamespace

import pytest

from app.config.settings import settings
from app.modules.prompt_center.infrastructure.langsmith_client import (
    LangSmithPromptClient,
    LangSmithPromptClientError,
)


class FakeLangSmithSdkClient:
    def __init__(self, returned_url: str = "https://smith.langchain.com/prompts/ioc.safety.analysis/abc12345"):
        self.returned_url = returned_url
        self.calls: list[dict] = []

    def push_prompt(self, prompt_identifier: str, **kwargs) -> str:
        self.calls.append({"prompt_identifier": prompt_identifier, **kwargs})
        return self.returned_url


def _prompt_and_version():
    prompt = SimpleNamespace(
        prompt_key="ioc.safety.analysis",
        description="运营安全分析 Prompt",
    )
    version = SimpleNamespace(
        version="1.2.0",
        system_content='只返回 JSON，例如 {"ok": true}',
        business_role_content="你是安全运营分析师。",
        business_goal_content="分析 {{device_name}} 的状态。",
        business_rules=[{"enabled": True, "content": "不得编造"}],
        output_requirement="输出结论。",
        positive_examples=[{"content": "风险可控"}],
        negative_examples=[{"content": "信息不足仍下结论"}],
        change_reason="补充安全规则",
    )
    return prompt, version


def test_push_prompt_uses_current_sdk_contract_and_preserves_only_runtime_variables(monkeypatch):
    monkeypatch.setattr(settings, "langsmith_api_key", "test-key")
    sdk_client = FakeLangSmithSdkClient()
    factory_calls: list[dict] = []

    def client_factory(**kwargs):
        factory_calls.append(kwargs)
        return sdk_client

    prompt, version = _prompt_and_version()
    result = LangSmithPromptClient(client_factory=client_factory).push_prompt(prompt, version)

    assert factory_calls == [{
        "api_url": settings.langsmith_endpoint,
        "api_key": "test-key",
    }]
    assert result.commit_hash == "abc12345"
    assert result.tag == "1.2.0"
    assert result.url.endswith("/abc12345")

    call = sdk_client.calls[0]
    assert call["prompt_identifier"] == "ioc.safety.analysis"
    assert call["is_public"] is False
    assert call["description"] == "运营安全分析 Prompt"
    assert call["tags"] == ["ioc", "managed-prompt"]
    assert call["commit_tags"] == ["1.2.0", "managed-by-ioc"]
    assert call["commit_description"] == "补充安全规则"

    template = call["object"]
    assert set(template.input_variables) == {"runtime_context", "user_question"}
    rendered = template.invoke({
        "runtime_context": "设备：A-01",
        "user_question": "是否需要停机？",
    }).messages
    assert '{"ok": true}' in rendered[0].content
    assert "{{device_name}}" in rendered[1].content
    assert "设备：A-01" in rendered[1].content
    assert "是否需要停机？" in rendered[1].content


@pytest.mark.parametrize(
    "url",
    [
        "https://smith.langchain.com/prompts/ioc.safety.analysis/",
        "https://smith.langchain.com/not-a-prompt/deadbeef",
    ],
)
def test_push_prompt_rejects_url_without_commit_hash(monkeypatch, url):
    monkeypatch.setattr(settings, "langsmith_api_key", "test-key")
    prompt, version = _prompt_and_version()

    with pytest.raises(LangSmithPromptClientError, match="Commit Hash"):
        LangSmithPromptClient(
            client_factory=lambda **_: FakeLangSmithSdkClient(url),
        ).push_prompt(prompt, version)


@pytest.mark.parametrize(
    "url, expected_hash",
    [
        ("https://smith.langchain.com/prompts/ioc.safety.analysis/deadbeef?organizationId=1", "deadbeef"),
        ("https://smith.langchain.com/hub/acme/ioc.safety.analysis:cafebabe", "cafebabe"),
    ],
)
def test_push_prompt_parses_supported_commit_urls(monkeypatch, url, expected_hash):
    monkeypatch.setattr(settings, "langsmith_api_key", "test-key")
    prompt, version = _prompt_and_version()

    result = LangSmithPromptClient(
        client_factory=lambda **_: FakeLangSmithSdkClient(url),
    ).push_prompt(prompt, version)

    assert result.commit_hash == expected_hash


def test_push_prompt_rejects_missing_api_key(monkeypatch):
    monkeypatch.setattr(settings, "langsmith_api_key", "")
    prompt, version = _prompt_and_version()

    with pytest.raises(LangSmithPromptClientError, match="API Key"):
        LangSmithPromptClient(client_factory=lambda **_: FakeLangSmithSdkClient()).push_prompt(
            prompt,
            version,
        )


def test_push_prompt_wraps_sdk_error_without_exposing_remote_details(monkeypatch):
    monkeypatch.setattr(settings, "langsmith_api_key", "test-key")
    prompt, version = _prompt_and_version()

    class FailingClient:
        def push_prompt(self, *args, **kwargs):
            raise RuntimeError("remote body contains sensitive prompt")

    with pytest.raises(LangSmithPromptClientError, match="LangSmith API 请求失败") as exc:
        LangSmithPromptClient(client_factory=lambda **_: FailingClient()).push_prompt(
            prompt,
            version,
        )

    assert "sensitive prompt" not in str(exc.value)
