"""
LLM 客户端 — 基于 LangChain ChatOpenAI，支持多 Provider 切换

接入方式：
  每个 Provider（deepseek / qwen / doubao）独立配置 base_url + api_key + model，
  通过 ChatOpenAI 统一适配（所有 Provider 均兼容 OpenAI 接口格式）。

使用方式：
  pip install langchain-openai
  配置环境变量 DEEPSEEK_API_KEY / QWEN_API_KEY / DOUBAO_API_KEY 即可使用。
"""

from collections.abc import Callable
from dataclasses import dataclass
from time import perf_counter

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app.core.config.llm_settings import LLMProviderConfig, llm_settings
from app.utils.timezone import now_local


@dataclass
class LlmResult:
    content: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost_ms: int
    success: bool
    error_message: str = ""
    system_prompt: str = ""


def _default_runtime_prompt(provider: LLMProviderConfig) -> str:
    today = now_local().date().isoformat()
    return "\n".join(
        [
            "你是智能运营中心 AI 助手，运行在本项目的 AI Agent Runtime 中。",
            (
                "当前 AI Agent Runtime 已接入 LangGraph，使用 StateGraph 编排对话流程："
                "START → init_session → load_prompt → call_llm → finalize → END。"
            ),
            (
                "当用户询问是否接入 LangGraph 时，应明确回答已经接入，"
                "不得回答尚未接入，也不要建议用户在 Runtime 上层重复接入。"
            ),
            (
                "当前后端默认接入的模型供应商是 DeepSeek，"
                f"模型名是 {provider.model}。"
            ),
            (
                '如果用户询问「你是谁/你是什么模型/你基于什么模型」，'
                '请准确说明当前接入 DeepSeek，'
            ),
            '不要自称 OpenAI、ChatGPT、GPT 架构或 GPT 系列模型。',
            (
                "你的主要职责是面向智能运营中心场景，"
                "帮助用户做运营分析、告警解读、隐患研判、"
            ),
            "日报建议和通用问答。",
            (
                "如果用户询问实时天气、行情、新闻或企业实时业务数据，"
                "而当前消息没有提供工具结果，"
            ),
            (
                "你必须明确说明尚未接入对应实时 Tool，不能编造实时数据；"
                "同时给出可执行的查询建议。"
            ),
            (
                "回答要求：使用中文，先直接回答结论，再补充必要说明；"
                "不要输出与问题无关的套话。"
            ),
            f"当前日期：{today}。",
        ]
    )


def _normalize_history(history: list[dict[str, str]] | None) -> list[dict[str, str]]:
    normalized: list[dict[str, str]] = []
    for item in history or []:
        role = item.get("role")
        content = item.get("content", "").strip()
        if role in {"user", "assistant"} and content:
            normalized.append({"role": role, "content": content})
    return normalized[-12:]


class LlmClient:
    def __init__(self) -> None:
        self._models: dict[str, ChatOpenAI] = {}
        self._default_provider = "deepseek"
        self._init_models()

    def _init_models(self) -> None:
        for provider in llm_settings.all_providers:
            if provider.enabled and provider.api_key:
                self._models[provider.provider] = ChatOpenAI(
                    model=provider.model,
                    api_key=provider.api_key,
                    base_url=provider.base_url,
                    max_tokens=provider.max_output_tokens,
                    temperature=0.3,
                    timeout=60,
                )

    def chat(
        self,
        prompt_content: str | None,
        user_message: str,
        history: list[dict[str, str]] | None = None,
        timeout_seconds: float | None = None,
        provider_name: str | None = None,
    ) -> LlmResult:
        provider_name = provider_name or self._default_provider
        provider = llm_settings.get_provider(provider_name)

        if not provider:
            return LlmResult(
                content="",
                model="",
                prompt_tokens=0,
                completion_tokens=0,
                total_tokens=0,
                cost_ms=0,
                success=False,
                error_message=f"模型配置不存在: {provider_name}",
                system_prompt="",
            )

        model = self._models.get(provider_name)
        if not model:
            return LlmResult(
                content="",
                model=provider.model,
                prompt_tokens=0,
                completion_tokens=0,
                total_tokens=0,
                cost_ms=0,
                success=False,
                error_message=(
                    f"{provider.display_name} API Key 未配置，"
                    f"请在环境变量中设置 {provider.provider.upper()}_API_KEY"
                ),
                system_prompt="",
            )

        system_content = prompt_content or _default_runtime_prompt(provider)

        messages: list = []
        if system_content:
            messages.append(SystemMessage(content=system_content))
        for h in _normalize_history(history):
            if h["role"] == "user":
                messages.append(HumanMessage(content=h["content"]))
            elif h["role"] == "assistant":
                messages.append(AIMessage(content=h["content"]))
        messages.append(HumanMessage(content=user_message))

        start = perf_counter()
        try:
            response: AIMessage = model.invoke(messages, timeout=timeout_seconds or 60)
            cost_ms = max(1, int((perf_counter() - start) * 1000))

            usage = response.usage_metadata or {}
            return LlmResult(
                content=response.content or "",
                model=response.response_metadata.get("model_name", provider.model),
                prompt_tokens=usage.get("input_tokens", 0),
                completion_tokens=usage.get("output_tokens", 0),
                total_tokens=usage.get("total_tokens", 0),
                cost_ms=cost_ms,
                success=True,
                system_prompt=system_content,
            )
        except Exception as e:
            cost_ms = max(1, int((perf_counter() - start) * 1000))
            error_msg = str(e)
            if "timeout" in error_msg.lower():
                error_msg = f"{provider.display_name} API 调用超时"
            return LlmResult(
                content="",
                model=provider.model,
                prompt_tokens=0,
                completion_tokens=0,
                total_tokens=0,
                cost_ms=cost_ms,
                success=False,
                error_message=f"{provider.display_name} API 调用异常: {error_msg}",
                system_prompt=system_content,
            )

    def stream_chat(
        self,
        prompt_content: str | None,
        user_message: str,
        on_chunk: Callable[[str], None],
        history: list[dict[str, str]] | None = None,
        timeout_seconds: float | None = None,
        provider_name: str | None = None,
    ) -> LlmResult:
        """真实消费模型流并逐段回调，同时汇总为兼容原接口的 LlmResult。"""
        provider_name = provider_name or self._default_provider
        provider = llm_settings.get_provider(provider_name)

        if not provider:
            return LlmResult(
                content="",
                model="",
                prompt_tokens=0,
                completion_tokens=0,
                total_tokens=0,
                cost_ms=0,
                success=False,
                error_message=f"模型配置不存在: {provider_name}",
                system_prompt="",
            )

        model = self._models.get(provider_name)
        if not model:
            return LlmResult(
                content="",
                model=provider.model,
                prompt_tokens=0,
                completion_tokens=0,
                total_tokens=0,
                cost_ms=0,
                success=False,
                error_message=(
                    f"{provider.display_name} API Key 未配置，"
                    f"请在环境变量中设置 {provider.provider.upper()}_API_KEY"
                ),
                system_prompt="",
            )

        system_content = prompt_content or _default_runtime_prompt(provider)
        messages = _build_messages(system_content, user_message, history)
        content_parts: list[str] = []
        usage: dict = {}
        model_name = provider.model
        start = perf_counter()

        try:
            for chunk in model.stream(
                messages,
                timeout=timeout_seconds or 60,
                stream_usage=True,
            ):
                text = _message_content_text(chunk.content)
                if text:
                    content_parts.append(text)
                    on_chunk(text)
                if chunk.usage_metadata:
                    usage = dict(chunk.usage_metadata)
                if chunk.response_metadata.get("model_name"):
                    model_name = str(chunk.response_metadata["model_name"])

            cost_ms = max(1, int((perf_counter() - start) * 1000))
            return LlmResult(
                content="".join(content_parts),
                model=model_name,
                prompt_tokens=usage.get("input_tokens", 0),
                completion_tokens=usage.get("output_tokens", 0),
                total_tokens=usage.get("total_tokens", 0),
                cost_ms=cost_ms,
                success=True,
                system_prompt=system_content,
            )
        except Exception as e:
            cost_ms = max(1, int((perf_counter() - start) * 1000))
            error_msg = str(e)
            if "timeout" in error_msg.lower():
                error_msg = f"{provider.display_name} API 调用超时"
            return LlmResult(
                content="".join(content_parts),
                model=model_name,
                prompt_tokens=usage.get("input_tokens", 0),
                completion_tokens=usage.get("output_tokens", 0),
                total_tokens=usage.get("total_tokens", 0),
                cost_ms=cost_ms,
                success=False,
                error_message=f"{provider.display_name} API 调用异常: {error_msg}",
                system_prompt=system_content,
            )


def _build_messages(
    system_content: str,
    user_message: str,
    history: list[dict[str, str]] | None = None,
) -> list:
    messages: list = []
    if system_content:
        messages.append(SystemMessage(content=system_content))
    for item in _normalize_history(history):
        if item["role"] == "user":
            messages.append(HumanMessage(content=item["content"]))
        else:
            messages.append(AIMessage(content=item["content"]))
    messages.append(HumanMessage(content=user_message))
    return messages


def _message_content_text(content: object) -> str:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""

    parts: list[str] = []
    for block in content:
        if isinstance(block, str):
            parts.append(block)
        elif isinstance(block, dict):
            text = block.get("text") or block.get("content")
            if isinstance(text, str):
                parts.append(text)
    return "".join(parts)


llm_client = LlmClient()
