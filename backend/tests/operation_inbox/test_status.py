from app.operation_inbox.status import (
    OP_AWAITING_REVIEW,
    OP_CLAIMED,
    OP_FAILED,
    OP_REOPENED,
    OP_RESOLVED,
)
from app.runtime.schemas.status import SESS_QUEUED


def test_overview_status_contracts_are_stable() -> None:
    assert SESS_QUEUED == "queued"
    assert OP_AWAITING_REVIEW == "awaiting_review"
    assert OP_CLAIMED == "claimed"
    assert OP_RESOLVED == "resolved"
    assert OP_REOPENED == "reopened"
    assert OP_FAILED == "failed"
