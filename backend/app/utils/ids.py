from datetime import UTC, datetime
from uuid import uuid4


def _new_id(prefix: str) -> str:
    date = datetime.now(UTC).strftime("%Y%m%d")
    return f"{prefix}_{date}_{uuid4().hex[:12]}"


def new_trace_id() -> str:
    return _new_id("trace")


def new_session_id() -> str:
    return _new_id("sess")


def new_conversation_id() -> str:
    return _new_id("conv")


def new_feedback_id() -> str:
    return _new_id("fb")
