import os
from dataclasses import dataclass

from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.config.env import find_env_files


class LLMSecretSettings(BaseSettings):
    qwen_api_key: str = ""
    deepseek_api_key: str = ""
    doubao_api_key: str = ""

    model_config = SettingsConfigDict(env_file=find_env_files(), env_file_encoding="utf-8", extra="ignore")


@dataclass
class LLMProviderConfig:
    provider: str
    display_name: str
    enabled: bool = True
    default: bool = False
    model: str = ""
    api_key: str = ""
    base_url: str = ""
    max_input_tokens: int = 8000
    max_output_tokens: int = 2000
    rpm_limit: int = 60

    def to_public(self) -> dict:
        return {
            "provider": self.provider,
            "displayName": self.display_name,
            "enabled": self.enabled,
            "default": self.default,
            "model": self.model,
            "maxInputTokens": self.max_input_tokens,
            "maxOutputTokens": self.max_output_tokens,
            "rpmLimit": self.rpm_limit,
        }


_secrets = LLMSecretSettings()
_QWEN_API_KEY = os.environ.get("QWEN_API_KEY", _secrets.qwen_api_key)
_DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", _secrets.deepseek_api_key)
_DOUBAO_API_KEY = os.environ.get("DOUBAO_API_KEY", _secrets.doubao_api_key)


class LLMSettings:
    def __init__(self) -> None:
        self._providers: dict[str, LLMProviderConfig] = {
            "qwen": LLMProviderConfig(
                provider="qwen",
                display_name="千问",
                enabled=True,
                default=False,
                model="qwen-plus",
                api_key=_QWEN_API_KEY,
                base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
                max_input_tokens=8000,
                max_output_tokens=2000,
                rpm_limit=60,
            ),
            "deepseek": LLMProviderConfig(
                provider="deepseek",
                display_name="DeepSeek",
                enabled=True,
                default=True,
                model="deepseek-chat",
                api_key=_DEEPSEEK_API_KEY,
                base_url="https://api.deepseek.com/v1",
                max_input_tokens=8000,
                max_output_tokens=2000,
                rpm_limit=60,
            ),
            "doubao": LLMProviderConfig(
                provider="doubao",
                display_name="豆包",
                enabled=True,
                default=False,
                model="doubao-pro",
                api_key=_DOUBAO_API_KEY,
                base_url="https://ark.cn-beijing.volces.com/api/v3",
                max_input_tokens=8000,
                max_output_tokens=2000,
                rpm_limit=60,
            ),
        }

    def get_provider(self, provider: str) -> LLMProviderConfig | None:
        return self._providers.get(provider)

    @property
    def default_provider(self) -> str:
        for name, cfg in self._providers.items():
            if cfg.default and cfg.enabled:
                return name
        return "qwen"

    @property
    def all_providers(self) -> list[LLMProviderConfig]:
        return list(self._providers.values())

    def list_public(self) -> list[dict]:
        return [p.to_public() for p in self._providers.values() if p.enabled]

    def get_api_key(self, provider: str) -> str:
        cfg = self._providers.get(provider)
        if cfg:
            return cfg.api_key
        return ""


llm_settings = LLMSettings()
