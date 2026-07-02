from app.schemas.common import IocBaseModel


class PromptDetail(IocBaseModel):
    prompt_code: str
    version: str
    name: str
    content: str
    status: str
    agent_code: str
    scene_code: str
    description: str | None = None
