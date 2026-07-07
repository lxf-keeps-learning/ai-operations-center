from dataclasses import dataclass
from time import perf_counter

import httpx

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
                "当前后端默认接入的模型供应商是 DeepSeek，"
                f"模型名是 {provider.model}。"
            ),
            (
                "如果用户询问“你是谁/你是什么模型/你基于什么模型”，"
                "请准确说明当前接入 DeepSeek，"
            ),
            "不要自称 OpenAI、ChatGPT、GPT 架构或 GPT 系列模型。",
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
    def chat(
        self,
        prompt_content: str | None,
        user_message: str,
        history: list[dict[str, str]] | None = None,
        timeout_seconds: float | None = None,
    ) -> LlmResult:
        provider = llm_settings.get_provider("deepseek")
        if not provider:
            return LlmResult(
                content="",
                model="",
                prompt_tokens=0,
                completion_tokens=0,
                total_tokens=0,
                cost_ms=0,
                success=False,
                error_message="DeepSeek 模型配置不存在",
                system_prompt="",
            )

        system_content = prompt_content or _default_runtime_prompt(provider)
        if not provider.api_key:
            return LlmResult(
                content="",
                model=provider.model,
                prompt_tokens=0,
                completion_tokens=0,
                total_tokens=0,
                cost_ms=0,
                success=False,
                error_message=(
                    "DeepSeek API Key 未配置，"
                    "请在环境变量中设置 DEEPSEEK_API_KEY"
                ),
                system_prompt=system_content,
            )

        messages = [
            {"role": "system", "content": system_content},
            *_normalize_history(history),
            {"role": "user", "content": user_message},
        ]
        headers = {
            "Authorization": f"Bearer {provider.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": provider.model,
            "messages": messages,
            "max_tokens": provider.max_output_tokens,
            "temperature": 0.3,
        }

        start = perf_counter()
        try:
            with httpx.Client(timeout=timeout_seconds or 60) as http:
                resp = http.post(
                    f"{provider.base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                )
            cost_ms = max(1, int((perf_counter() - start) * 1000))

            if resp.status_code != 200:
                error_detail = resp.text[:500]
                return LlmResult(
                    content="",
                    model=provider.model,
                    prompt_tokens=0,
                    completion_tokens=0,
                    total_tokens=0,
                    cost_ms=cost_ms,
                    success=False,
                    error_message=f"DeepSeek API HTTP {resp.status_code}: {error_detail}",
                    system_prompt=system_content,
                )

            body = resp.json()
            choice = body.get("choices", [{}])[0]
            content = choice.get("message", {}).get("content", "")
            usage = body.get("usage", {})
            prompt_tokens = usage.get("prompt_tokens", 0)
            completion_tokens = usage.get("completion_tokens", 0)
            total_tokens = usage.get("total_tokens", 0)

            return LlmResult(
                content=content,
                model=body.get("model", provider.model),
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                cost_ms=cost_ms,
                success=True,
                system_prompt=system_content,
            )

        except httpx.TimeoutException:
            cost_ms = max(1, int((perf_counter() - start) * 1000))
            return LlmResult(
                content="",
                model=provider.model,
                prompt_tokens=0,
                completion_tokens=0,
                total_tokens=0,
                cost_ms=cost_ms,
                success=False,
                error_message="DeepSeek API 调用超时",
                system_prompt=system_content,
            )
        except Exception as e:
            cost_ms = max(1, int((perf_counter() - start) * 1000))
            return LlmResult(
                content="",
                model=provider.model,
                prompt_tokens=0,
                completion_tokens=0,
                total_tokens=0,
                cost_ms=cost_ms,
                success=False,
                error_message=f"DeepSeek API 调用异常: {e}",
                system_prompt=system_content,
            )


llm_client = LlmClient()
