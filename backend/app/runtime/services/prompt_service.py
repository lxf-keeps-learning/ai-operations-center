"""PromptService — Prompt 模板业务逻辑

管理 Prompt 模板的 CRUD 和版本控制。每个 Prompt 通过 code 唯一标识，
支持多版本管理（通过 version 字段），同一 code 下只有一个版本处于激活状态。
RuntimeService 在调用 LLM 前会通过 get_active_by_code 获取当前激活的 System Prompt。
"""

from sqlalchemy.orm import Session

from app.runtime.repositories.prompt_repository import PromptRepository
from app.runtime.schemas.prompt_schema import PromptCreate, PromptResponse
from app.runtime.schemas.status import PR_ACTIVE

_repo = PromptRepository()


class PromptService:
    def create(self, db: Session, payload: PromptCreate) -> PromptResponse:
        """创建新 Prompt 模板（含 code、version、content 等）"""
        record = _repo.create(db, payload)
        return PromptResponse.model_validate(record)

    def get_active_by_code(self, db: Session, code: str) -> PromptResponse | None:
        """根据 code 获取当前激活版本的 Prompt（供 LLM 调用使用）"""
        record = _repo.get_active_by_code(db, code)
        if record is None:
            return None
        return PromptResponse.model_validate(record)

    def get_versions_by_code(self, db: Session, code: str) -> list[PromptResponse]:
        """获取指定 code 的所有历史版本"""
        records = _repo.get_versions_by_code(db, code)
        return [PromptResponse.model_validate(r) for r in records]

    def update_status(self, db: Session, prompt_id: str, status: str) -> PromptResponse | None:
        """更新 Prompt 状态（如 draft → active）"""
        record = _repo.update_status(db, prompt_id, status)
        if record is None:
            return None
        return PromptResponse.model_validate(record)


prompt_service = PromptService()
