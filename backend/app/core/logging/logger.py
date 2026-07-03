import logging
import sys

from app.core.trace.trace_context import get_trace_id

_LOG_FORMAT = "%(asctime)s  %(levelname)-8s  %(name)s  %(trace_id)-36s  %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


class TraceIdFilter(logging.Filter):
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
    fmt = logging.Formatter(fmt=_LOG_FORMAT, datefmt=_DATE_FORMAT)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(fmt)
    handler.addFilter(TraceIdFilter())

    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    root.handlers.clear()
    root.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    _inject_trace_filter(logger)
    return logger


def _patch_existing_loggers() -> None:
    for name in list(logging.root.manager.loggerDict):
        if name.startswith(_PACKAGE_PREFIX):
            logger = logging.getLogger(name)
            _inject_trace_filter(logger)
