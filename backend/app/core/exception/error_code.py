"""
错误码定义模块 — 统一管理所有业务错误码

设计原则：
  - HTTP 状态码表示协议层状态（200/400/500）
  - 业务错误码表示业务层具体错误（400001/500101/504101）
  - 二者分层，不混用

错误码分段规则：
  0       成功
  400xxx  客户端参数错误
  401xxx  认证错误
  403xxx  权限错误
  404xxx  资源不存在
  422xxx  校验错误
  429xxx  限流
  500xxx  系统内部错误
  50xxxx  AI 模型相关错误
  503xxx  依赖服务不可用
"""

from dataclasses import dataclass
from typing import Self


@dataclass(frozen=True)
class ErrorCode:
    code: int
    message: str
    http_status: int
    description: str


# ── 成功 ──────────────────────────────────────────────
SUCCESS = ErrorCode(code=0, message="success", http_status=200, description="业务处理成功")

# ── 4xx 参数与客户端错误 ──────────────────────────────
PARAM_ERROR = ErrorCode(code=400001, message="参数错误", http_status=400, description="请求参数不符合接口要求")
UNAUTHORIZED = ErrorCode(code=401001, message="未登录", http_status=401, description="用户未认证或登录已过期")
FORBIDDEN = ErrorCode(code=403001, message="无权限", http_status=403, description="用户无操作权限")
NOT_FOUND = ErrorCode(code=404001, message="资源不存在", http_status=404, description="请求的资源不存在")
VALIDATION_ERROR = ErrorCode(code=422001, message="参数校验失败", http_status=422, description="Pydantic 请求体验证失败")
RATE_LIMIT = ErrorCode(code=429001, message="请求过于频繁", http_status=429, description="触发限流限制")

# ── 5xx 服务端错误 ────────────────────────────────────
INTERNAL_ERROR = ErrorCode(code=500001, message="系统内部错误", http_status=500, description="未预期的系统异常")
LLM_PROVIDER_ERROR = ErrorCode(code=500101, message="大模型调用失败", http_status=502, description="LLM Provider 返回错误或调用异常")
LLM_TIMEOUT = ErrorCode(code=504101, message="大模型调用超时", http_status=504, description="LLM Provider 调用超时")

# ── 扩展业务码（文档中定义，按需使用） ─────────────────
MESSAGE_EMPTY = ErrorCode(code=400003, message="问题内容不能为空", http_status=400, description="AI 问答 message 为空")
SESSION_NOT_FOUND = ErrorCode(code=404002, message="会话不存在", http_status=404, description="conversation_id 无效")
TRACE_NOT_FOUND = ErrorCode(code=404003, message="Trace 不存在", http_status=404, description="traceId 无效")
PROMPT_NOT_FOUND = ErrorCode(code=404004, message="Prompt 不存在", http_status=404, description="prompt_code 无效")
ITEM_NOT_FOUND = ErrorCode(code=404005, message="Item 不存在", http_status=404, description="item_id 无效")
SSE_STREAM_NOT_FOUND = ErrorCode(code=404006, message="SSE 流不存在", http_status=404, description="traceId 找不到对应流")
CONVERSATION_NOT_FOUND = ErrorCode(code=404007, message="会话不存在", http_status=404, description="conversation_id 无效")
CONVERSATION_CLOSED = ErrorCode(code=400004, message="会话已关闭，无法继续对话", http_status=400, description="conversation 状态不允许新的对话")
DATA_WRITE_ERROR = ErrorCode(code=500002, message="数据写入失败", http_status=500, description="写入业务数据或日志失败")
DATA_QUERY_ERROR = ErrorCode(code=500003, message="数据查询失败", http_status=500, description="查询数据库失败")
LLM_CONFIG_MISSING = ErrorCode(code=500004, message="LLM 配置缺失", http_status=500, description="LLM Key、Base URL、模型名缺失")
LLM_RESPONSE_FORMAT_ERROR = ErrorCode(code=500102, message="大模型返回格式异常", http_status=502, description="LLM 响应无法解析")
DB_CONNECTION_ERROR = ErrorCode(code=503001, message="数据库连接失败", http_status=503, description="MySQL 不可用")
REDIS_CONNECTION_ERROR = ErrorCode(code=503002, message="Redis 连接失败", http_status=503, description="Redis 不可用")

# ── 所有错误码列表（用于注册和文档展示） ────────────────
ALL_CODES: list[ErrorCode] = [
    SUCCESS,
    PARAM_ERROR,
    UNAUTHORIZED,
    FORBIDDEN,
    NOT_FOUND,
    VALIDATION_ERROR,
    RATE_LIMIT,
    INTERNAL_ERROR,
    LLM_PROVIDER_ERROR,
    LLM_TIMEOUT,
    MESSAGE_EMPTY,
    SESSION_NOT_FOUND,
    TRACE_NOT_FOUND,
    PROMPT_NOT_FOUND,
    ITEM_NOT_FOUND,
    SSE_STREAM_NOT_FOUND,
    CONVERSATION_NOT_FOUND,
    CONVERSATION_CLOSED,
    DATA_WRITE_ERROR,
    DATA_QUERY_ERROR,
    LLM_CONFIG_MISSING,
    LLM_RESPONSE_FORMAT_ERROR,
    DB_CONNECTION_ERROR,
    REDIS_CONNECTION_ERROR,
]

_CODE_MAP: dict[int, ErrorCode] = {ec.code: ec for ec in ALL_CODES}


def get_by_code(code: int) -> ErrorCode | None:
    """根据业务错误码数字查找对应的 ErrorCode 对象"""
    return _CODE_MAP.get(code)


def get_http_status(code: int) -> int:
    """根据业务错误码获取对应的 HTTP 状态码，未匹配时默认返回 500"""
    ec = _CODE_MAP.get(code)
    if ec is not None:
        return ec.http_status
    return 500
