from __future__ import annotations

import sys

from app.db.session import get_session_local
from app.tool_registry.seed import seed_builtin_tools


def main() -> int:
    db = get_session_local()()
    try:
        seed_builtin_tools(db)
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"seed_tool_registry failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
