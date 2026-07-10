"""ConversationService — 会话（Conversation）业务逻辑

会话是用户与系统一次独立对话的顶层容器，对应前端一个聊天窗口/标签页。
一个会话包含多条运行记录（Session），每次用户发送消息都会创建一个新的 Session。
Conversation 负责管理会话的生命周期（创建、关闭、信息更新）。
"""

from sqlalchemy.orm import Session

from app.runtime.repositories.conversation_repository import ConversationRepository
from app.runtime.schemas.conversation_schema import ConversationCreate, ConversationResponse, ConversationUpdate
from app.runtime.schemas.status import CONV_ACTIVE, CONV_CLOSED

_repo = ConversationRepository()


class ConversationService:
    def create(self, db: Session, payload: ConversationCreate) -> ConversationResponse:
        """创建新会话，返回包含会话 ID 的响应"""
        record = _repo.create(db, payload)
        return ConversationResponse.model_validate(record)

    def get_by_id(self, db: Session, conversation_id: str) -> ConversationResponse | None:
        """根据会话 ID 查询会话详情"""
        record = _repo.get_by_id(db, conversation_id)
        if record is None:
            return None
        return ConversationResponse.model_validate(record)

    def update(self, db: Session, conversation_id: str, payload: ConversationUpdate) -> ConversationResponse | None:
        """更新会话信息（如标题、状态等）"""
        record = _repo.update(db, conversation_id, payload)
        if record is None:
            return None
        return ConversationResponse.model_validate(record)

    def close(self, db: Session, conversation_id: str) -> ConversationResponse | None:
        """将会话状态标记为已关闭"""
        record = _repo.update_status(db, conversation_id, CONV_CLOSED)
        if record is None:
            return None
        return ConversationResponse.model_validate(record)


conversation_service = ConversationService()
