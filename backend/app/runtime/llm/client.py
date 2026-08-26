"""
LLM 客户端 — 基于 LangChain ChatOpenAI，支持多 Provider 切换

接入方式：
  每个 Provider（deepseek / qwen / doubao）独立配置 base_url + api_key + model，
  通过 ChatOpenAI 统一适配（所有 Provider 均兼容 OpenAI 接口格式）。

使用方式：
  pip install langchain-openai
  配置环境变量 DEEPSEEK_API_KEY / QWEN_API_KEY / DOUBAO_API_KEY 即可使用。

超时语义：
  - achat / astream_chat 是异步入口，受 asyncio.timeout 硬约束：
    预算 = min(显式 timeout_seconds 或 settings.llm_timeout_seconds, Deadline 剩余预算)。
  - 超时返回 LlmResult(success=False, error_code="LLM_TIMEOUT")（业务层映射 504101）。
  - asyncio.CancelledError 始终原样向上传播，不包装成普通错误。
  - 不使用 `timeout_seconds or 60` 兜底：显式合法值（含 0 之外的任意正数）原样生效，
    只有 None 才回落到配置默认。
"""

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from time import perf_counter

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app.config.settings import settings
from app.core.config.llm_settings import LLMProviderConfig, llm_settings
from app.core.timeout import child_timeout, current_deadline
from app.runtime.execution_control import RuntimeCancelledError
from app.utils.timezone import now_local

# ── LLM 错误分类（向后兼容：error_code 默认空串，不改变既有调用方契约） ──
# 分类函数 classify_llm_error(exc, error_message) 定义在模块底部；
# 以下常量供 Operation 重试层稳定引用。
LLM_CODE_TIMEOUT = "LLM_TIMEOUT"
LLM_CODE_NETWORK = "LLM_NETWORK_ERROR"
LLM_CODE_RATE_LIMITED = "LLM_RATE_LIMITED"
LLM_CODE_PROVIDER = "LLM_PROVIDER_ERROR"
LLM_CODE_AUTH = "LLM_AUTH_ERROR"
LLM_CODE_INVALID_REQUEST = "LLM_INVALID_REQUEST"
LLM_CODE_CONTENT_POLICY = "LLM_CONTENT_POLICY"
LLM_CODE_UNKNOWN = "LLM_UNKNOWN_ERROR"

# 允许重试的错误码：超时 / 网络异常 / 限流 / Provider 5xx（归类为 LLM_PROVIDER_ERROR）。
RETRYABLE_LLM_ERROR_CODES = {
    LLM_CODE_TIMEOUT,
    LLM_CODE_NETWORK,
    LLM_CODE_RATE_LIMITED,
    LLM_CODE_PROVIDER,
}


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
    cancelled: bool = False
    error_code: str = ""


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
        self._init_models()

    def _build_model(self, provider: LLMProviderConfig) -> ChatOpenAI:
        return ChatOpenAI(
            model=provider.model,
            api_key=provider.api_key,
            base_url=provider.base_url,
            max_tokens=provider.max_output_tokens,
            temperature=0.3,
            timeout=60,
        )

    def _init_models(self) -> None:
        for provider in llm_settings.all_providers:
            if provider.enabled and provider.api_key:
                self._models[provider.provider] = self._build_model(provider)

    def _get_model(self, provider: LLMProviderConfig) -> ChatOpenAI | None:
        model = self._models.get(provider.provider)
        if model is not None:
            configured_model = getattr(model, "model_name", None)
            if configured_model is None or configured_model == provider.model:
                return model
        if not provider.api_key:
            return None
        model = self._build_model(provider)
        self._models[provider.provider] = model
        return model

    @staticmethod
    def _resolve_timeout(timeout_seconds: float | None) -> float:
        """显式值原样生效（None 才回落配置默认），并按 Deadline 预算收口。"""
        explicit = settings.llm_timeout_seconds if timeout_seconds is None else timeout_seconds
        return child_timeout(explicit)

    def chat(
        self,
        prompt_content: str | None,
        user_message: str,
        history: list[dict[str, str]] | None = None,
        timeout_seconds: float | None = None,
        provider_name: str | None = None,
    ) -> LlmResult:
        provider_name = provider_name or llm_settings.default_provider
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

        model = self._get_model(provider)
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
            response: AIMessage = model.invoke(
                messages,
                timeout=timeout_seconds if timeout_seconds is not None else settings.llm_timeout_seconds,
            )
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
        except RuntimeCancelledError:
            cost_ms = max(1, int((perf_counter() - start) * 1000))
            return LlmResult(
                content="",
                model=provider.model,
                prompt_tokens=0,
                completion_tokens=0,
                total_tokens=0,
                cost_ms=cost_ms,
                success=False,
                error_message="Session 已取消",
                system_prompt=system_content,
                cancelled=True,
                error_code="CANCELLED_BY_USER",
            )
        except Exception as e:
            cost_ms = max(1, int((perf_counter() - start) * 1000))
            error_code = classify_llm_error(e, str(e))
            error_msg = (
                f"{provider.display_name} API 调用超时"
                if error_code == LLM_CODE_TIMEOUT
                else f"{provider.display_name} API 调用异常: {e}"
            )
            return LlmResult(
                content="",
                model=provider.model,
                prompt_tokens=0,
                completion_tokens=0,
                total_tokens=0,
                cost_ms=cost_ms,
                success=False,
                error_message=error_msg,
                system_prompt=system_content,
                error_code=error_code,
            )

    async def achat(
        self,
        prompt_content: str | None,
        user_message: str,
        history: list[dict[str, str]] | None = None,
        timeout_seconds: float | None = None,
        provider_name: str | None = None,
    ) -> LlmResult:
        """异步非流式 LLM 调用，受 asyncio.timeout 硬约束（可被 Deadline 取消）。"""
        provider_name = provider_name or llm_settings.default_provider
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

        model = self._get_model(provider)
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
        budget = self._resolve_timeout(timeout_seconds)
        start = perf_counter()
        try:
            async with asyncio.timeout(budget):
                response: AIMessage = await model.ainvoke(messages, timeout=budget)
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
        except TimeoutError:
            cost_ms = max(1, int((perf_counter() - start) * 1000))
            return LlmResult(
                content="",
                model=provider.model,
                prompt_tokens=0,
                completion_tokens=0,
                total_tokens=0,
                cost_ms=cost_ms,
                success=False,
                error_message=f"{provider.display_name} API 调用超时",
                system_prompt=system_content,
                error_code="LLM_TIMEOUT",
            )
        except asyncio.CancelledError:
            # 用户主动取消原样传播；外层 Deadline 到期导致的取消按 LLM_TIMEOUT 返回。
            if _deadline_expired():
                cost_ms = max(1, int((perf_counter() - start) * 1000))
                return LlmResult(
                    content="",
                    model=provider.model,
                    prompt_tokens=0,
                    completion_tokens=0,
                    total_tokens=0,
                    cost_ms=cost_ms,
                    success=False,
                    error_message=f"{provider.display_name} API 调用超时",
                    system_prompt=system_content,
                    error_code="LLM_TIMEOUT",
                )
            raise
        except Exception as e:
            cost_ms = max(1, int((perf_counter() - start) * 1000))
            error_code = classify_llm_error(e, str(e))
            error_msg = (
                f"{provider.display_name} API 调用超时"
                if error_code == LLM_CODE_TIMEOUT
                else f"{provider.display_name} API 调用异常: {e}"
            )
            return LlmResult(
                content="",
                model=provider.model,
                prompt_tokens=0,
                completion_tokens=0,
                total_tokens=0,
                cost_ms=cost_ms,
                success=False,
                error_message=error_msg,
                system_prompt=system_content,
                error_code=error_code,
            )

    async def astream_chat(
        self,
        prompt_content: str | None,
        user_message: str,
        on_chunk: Callable[[str], None],
        history: list[dict[str, str]] | None = None,
        timeout_seconds: float | None = None,
        provider_name: str | None = None,
    ) -> LlmResult:
        """异步流式 LLM 调用；超时后停止 token 消费并关闭流。

        与同步 stream_chat 的区别：
          - 迭代发生在事件循环内，asyncio.timeout 到期会取消当前迭代，
            底层 httpx 流随取消清理关闭。
          - 不吞 CancelledError。
        """
        provider_name = provider_name or llm_settings.default_provider
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

        model = self._get_model(provider)
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
        budget = self._resolve_timeout(timeout_seconds)
        start = perf_counter()

        try:
            async with asyncio.timeout(budget):
                async for chunk in model.astream(
                    messages,
                    timeout=budget,
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
        except TimeoutError:
            cost_ms = max(1, int((perf_counter() - start) * 1000))
            return LlmResult(
                content="".join(content_parts),
                model=model_name,
                prompt_tokens=usage.get("input_tokens", 0),
                completion_tokens=usage.get("output_tokens", 0),
                total_tokens=usage.get("total_tokens", 0),
                cost_ms=cost_ms,
                success=False,
                error_message=f"{provider.display_name} API 调用超时",
                system_prompt=system_content,
                error_code="LLM_TIMEOUT",
            )
        except asyncio.CancelledError:
            # 用户主动取消原样传播；外层 Deadline 到期导致的取消按 LLM_TIMEOUT 返回。
            if _deadline_expired():
                cost_ms = max(1, int((perf_counter() - start) * 1000))
                return LlmResult(
                    content="".join(content_parts),
                    model=model_name,
                    prompt_tokens=usage.get("input_tokens", 0),
                    completion_tokens=usage.get("output_tokens", 0),
                    total_tokens=usage.get("total_tokens", 0),
                    cost_ms=cost_ms,
                    success=False,
                    error_message=f"{provider.display_name} API 调用超时",
                    system_prompt=system_content,
                    error_code="LLM_TIMEOUT",
                )
            raise
        except Exception as e:
            cost_ms = max(1, int((perf_counter() - start) * 1000))
            error_code = classify_llm_error(e, str(e))
            error_msg = (
                f"{provider.display_name} API 调用超时"
                if error_code == LLM_CODE_TIMEOUT
                else f"{provider.display_name} API 调用异常: {e}"
            )
            return LlmResult(
                content="".join(content_parts),
                model=model_name,
                prompt_tokens=usage.get("input_tokens", 0),
                completion_tokens=usage.get("output_tokens", 0),
                total_tokens=usage.get("total_tokens", 0),
                cost_ms=cost_ms,
                success=False,
                error_message=error_msg,
                system_prompt=system_content,
                error_code=error_code,
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
        provider_name = provider_name or llm_settings.default_provider
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

        model = self._get_model(provider)
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
                timeout=timeout_seconds if timeout_seconds is not None else settings.llm_timeout_seconds,
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
            error_code = classify_llm_error(e, str(e))
            error_msg = (
                f"{provider.display_name} API 调用超时"
                if error_code == LLM_CODE_TIMEOUT
                else f"{provider.display_name} API 调用异常: {e}"
            )
            return LlmResult(
                content="".join(content_parts),
                model=model_name,
                prompt_tokens=usage.get("input_tokens", 0),
                completion_tokens=usage.get("output_tokens", 0),
                total_tokens=usage.get("total_tokens", 0),
                cost_ms=cost_ms,
                success=False,
                error_message=error_msg,
                system_prompt=system_content,
                error_code=error_code,
            )


def _deadline_expired() -> bool:
    """当前上下文的 Deadline 是否已过期（区分 Deadline 取消与用户主动取消）。"""
    current = current_deadline()
    return current is not None and current.expired


def classify_llm_error(exc: Exception, error_message: str) -> str:
    """对 Provider 异常做稳定、向后兼容的错误码分类。

    新增分类不改变正常调用方契约；LlmResult.success / content / tokens 等字段保持不变，
    仅让失败路径拥有更精确的 error_code，供 Operation Agent 重试与自修复决策使用。
    """
    status_code = getattr(exc, "status_code", None)
    if isinstance(status_code, int):
        if status_code == 401 or status_code == 403:
            return "LLM_AUTH_ERROR"
        if status_code == 429:
            return "LLM_RATE_LIMITED"
        if status_code == 408:
            return "LLM_TIMEOUT"
        if 400 <= status_code < 500:
            return "LLM_INVALID_REQUEST"
        if status_code >= 500:
            return "LLM_PROVIDER_ERROR"

    lowered = (error_message or "").lower()
    if _contains_any(
        lowered,
        ("connecterror", "connectionerror", "connection error", "network error",
         "connection refused", "timed out", "timeout", "dns", "unreachable",
         "eof", "remote disconnected", "server disconnected", "read error"),
    ):
        if _contains_any(lowered, ("timed out", "timeout")):
            return "LLM_TIMEOUT"
        return "LLM_NETWORK_ERROR"
    if _contains_any(lowered, ("api key", "apikey", "authentication", "unauthorized", "invalid_api_key", "permission denied")):
        return "LLM_AUTH_ERROR"
    if _contains_any(lowered, ("rate limit", "429", "too many requests")):
        return "LLM_RATE_LIMITED"
    if _contains_any(
        lowered,
        ("content filter", "content_filter", "safety system", "policy violation",
         "moderation", "content policy", "refused to answer", "sensitive content"),
    ):
        return "LLM_CONTENT_POLICY"
    return LLM_CODE_UNKNOWN


def _contains_any(text: str, markers: tuple[str, ...]) -> bool:
    return any(marker in text for marker in markers)


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
