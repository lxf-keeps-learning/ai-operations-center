from pydantic import BaseModel, Field


class OperatorActionRequest(BaseModel):
    """Explicit operator identity until request authentication is available."""

    operator_id: str = Field(min_length=1, max_length=64)


class ResolveMessageRequest(OperatorActionRequest):
    note: str = Field(default="", max_length=4000)
