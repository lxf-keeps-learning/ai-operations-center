import json
from collections.abc import Mapping


def to_sse(event: str, data: Mapping[str, object | None]) -> str:
    payload = json.dumps(
        {key: value for key, value in data.items() if value is not None},
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return f"event: {event}\ndata: {payload}\n\n"
