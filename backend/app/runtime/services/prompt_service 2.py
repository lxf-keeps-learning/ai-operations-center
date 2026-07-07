from sqlalchemy.orm import Session

from app.runtime.repositories.prompt_repository import PromptRepository
from app.runtime.schemas.prompt_schema import PromptCreate, PromptResponse
from app.runtime.schemas.status import PR_ACTIVE

_repo = PromptRepository()


class PromptService:
    def create(self, db: Session, payload: PromptCreate) -> PromptResponse:
        record = _repo.create(db, payload)
        return PromptResponse.model_validate(record)

    def get_active_by_code(self, db: Session, code: str) -> PromptResponse | None:
        record = _repo.get_active_by_code(db, code)
        if record is None:
            return None
        return PromptResponse.model_validate(record)

    def get_versions_by_code(self, db: Session, code: str) -> list[PromptResponse]:
        records = _repo.get_versions_by_code(db, code)
        return [PromptResponse.model_validate(r) for r in records]


prompt_service = PromptService()
