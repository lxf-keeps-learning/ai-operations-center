"""
日志模块 — 统一日志输出格式，自动注入 traceId

提供：
  - setup_logging(level)：在应用启动时初始化全局日志配置
  - get_logger(name)：获取带 TraceIdFilter 的 Logger 实例
  - TraceIdFilter：自动将当前请求的 traceId 注入日志记录

日志格式：[时间] [级别] [Logger名] [traceId] [消息]
"""

import logging
import sys

from app.core.trace.trace_context import get_trace_id

# 日志格式：时间  级别     Logger名称   traceId                 消息
_LOG_FORMAT = "%(asctime)s  %(levelname)-8s  %(name)s  %(trace_id)-36s  %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


class TraceIdFilter(logging.Filter):
    """日志过滤器 — 自动将当前请求的 traceId 注入日志记录"""

    def filter(self, record: logging.LogRecord) -> bool:
        trace_id = get_trace_id()
        record.trace_id = trace_id if trace_id else "-"
        return True


_PACKAGE_PREFIX = "app."


def _inject_trace_filter(logger: logging.Logger) -> None:
    has_filter = any(isinstance(f, TraceIdFilter) for f in logger.filters)
    if not has_filter:
        logger.addFilter(TraceIdFilter())


def setup_logging(level: str = "INFO") -> None:
    """初始化全局日志配置（应用启动时调用一次）"""
    fmt = logging.Formatter(fmt=_LOG_FORMAT, datefmt=_DATE_FORMAT)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(fmt)
    handler.addFilter(TraceIdFilter())

    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    root.handlers.clear()
    root.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    """获取带 TraceIdFilter 的 Logger，确保日志行包含当前 traceId"""
    logger = logging.getLogger(name)
    _inject_trace_filter(logger)
    return logger


def _patch_existing_loggers() -> None:
    for name in list(logging.root.manager.loggerDict):
        if name.startswith(_PACKAGE_PREFIX):
            logger = logging.getLogger(name)
            _inject_trace_filter(logger)
