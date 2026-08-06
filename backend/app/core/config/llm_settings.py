"""
大模型配置模块 — 多 Provider 管理与配置

支持 DeepSeek / Doubao / Zhipu 三种大模型 Provider，并保留 Qwen 兼容配置。
通过适配器模式统一管理 API Key、模型名、Base URL、Token 限制、RPM 限流等配置。
敏感信息（API Key）通过环境变量注入，不硬编码。
提供 list_public() 方法向前端暴露非敏感字段。
"""

import os
from dataclasses import dataclass

from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.config.env import find_env_files


class LLMSecretSettings(BaseSettings):
    qwen_api_key: str = ""
    deepseek_api_key: str = ""
    doubao_api_key: str = ""
    zhipu_api_key: str = ""

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
    model_versions: list[str] | None = None

    def to_public(self) -> dict:
        """返回非敏感配置（不含 api_key），供前端展示"""
        return {
            "provider": self.provider,
            "displayName": self.display_name,
            "enabled": self.enabled,
            "default": self.default,
            "model": self.model,
            "maxInputTokens": self.max_input_tokens,
            "maxOutputTokens": self.max_output_tokens,
            "rpmLimit": self.rpm_limit,
            "modelVersions": self.model_versions or [self.model],
        }


_secrets = LLMSecretSettings()
_QWEN_API_KEY = os.environ.get("QWEN_API_KEY", _secrets.qwen_api_key)
_DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", _secrets.deepseek_api_key)
_DOUBAO_API_KEY = os.environ.get("DOUBAO_API_KEY", _secrets.doubao_api_key)
_ZHIPU_API_KEY = os.environ.get("ZHIPU_API_KEY", _secrets.zhipu_api_key)


class LLMSettings:
    """大模型配置管理器 — 管理所有 Provider 的配置并统一暴露访问接口"""

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
                model_versions=["qwen-plus", "qwen-max", "qwen-turbo"],
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
                model_versions=["deepseek-chat", "deepseek-reasoner"],
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
                model_versions=["doubao-seed-1-6-250615", "doubao-1-5-pro-32k-250115", "doubao-1-5-lite-32k-250115"],
            ),
            "zhipu": LLMProviderConfig(
                provider="zhipu",
                display_name="智谱",
                enabled=True,
                default=False,
                model="glm-4.5",
                api_key=_ZHIPU_API_KEY,
                base_url="https://open.bigmodel.cn/api/paas/v4",
                max_input_tokens=128000,
                max_output_tokens=8192,
                rpm_limit=60,
                model_versions=["glm-4.5", "glm-4.5-air", "glm-4-flash"],
            ),
        }

    def get_provider(self, provider: str) -> LLMProviderConfig | None:
        """根据 provider 名称获取配置"""
        return self._providers.get(provider)

    @property
    def default_provider(self) -> str:
        """获取默认启用的 provider 名称"""
        for name, cfg in self._providers.items():
            if cfg.default and cfg.enabled:
                return name
        return "qwen"

    def select(self, provider_name: str, model: str) -> LLMProviderConfig:
        """切换当前进程的默认供应商和模型版本，不持久化 API Key。"""
        provider = self._providers.get(provider_name)
        if provider is None or not provider.enabled:
            raise ValueError(f"模型供应商不存在或未启用: {provider_name}")
        if model not in (provider.model_versions or [provider.model]):
            raise ValueError(f"模型版本不属于供应商 {provider_name}: {model}")
        for item in self._providers.values():
            item.default = item.provider == provider_name
        provider.model = model
        return provider

    @property
    def all_providers(self) -> list[LLMProviderConfig]:
        """获取所有 provider 配置列表"""
        return list(self._providers.values())

    def list_public(self) -> list[dict]:
        """返回所有已启用 provider 的非敏感配置，供 API 返回给前端"""
        return [p.to_public() for p in self._providers.values() if p.enabled]

    def get_api_key(self, provider: str) -> str:
        """根据 provider 名称获取对应的 API Key（敏感信息，仅后端使用）"""
        cfg = self._providers.get(provider)
        if cfg:
            return cfg.api_key
        return ""


llm_settings = LLMSettings()
