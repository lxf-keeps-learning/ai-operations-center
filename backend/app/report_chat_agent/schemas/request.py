from pydantic import BaseModel, Field


class CreateSessionRequest(BaseModel):
    user_id: str = Field(default="anonymous", description="用户 ID")


class SendMessageRequest(BaseModel):
    report_id: int = Field(description="报告 ID")
    question: str = Field(description="用户问题")
