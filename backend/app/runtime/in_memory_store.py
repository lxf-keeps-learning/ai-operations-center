from dataclasses import dataclass, field
from datetime import UTC, datetime

from app.schemas.conversation import ConversationDetail, ConversationSummary, SessionSummary
from app.schemas.prompt import PromptDetail


@dataclass
class SessionRecord:
    session_id: str
    trace_id: str
    conversation_id: str
    agent_code: str
    scene_code: str
    message: str | None
    status: str = "running"
    create_time: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


@dataclass
class ConversationRecord:
    conversation_id: str
    title: str
    agent_code: str
    update_time: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    deleted: bool = False
    sessions: list[SessionRecord] = field(default_factory=list)


class InMemoryRuntimeStore:
    def __init__(self) -> None:
        self.conversations: dict[str, ConversationRecord] = {}
        self.sessions_by_trace: dict[str, SessionRecord] = {}
        self.feedback_ids: list[str] = []
        self.prompts = {
            "operation_daily_summary": PromptDetail(
                prompt_code="operation_daily_summary",
                version="v0.1.0",
                name="运营日报摘要",
                content="基于页面上下文、运营指标、告警和隐患数据，输出摘要、异常原因和关注建议。",
                status="active",
                agent_code="operation",
                scene_code="operation_daily_summary",
                description="初始化阶段内置 Prompt，用于联调接口和页面展示。",
            ),
            "hidden_risk_analysis": PromptDetail(
                prompt_code="hidden_risk_analysis",
                version="v0.1.0",
                name="隐患风险研判",
                content="基于隐患对象、整改状态和历史风险，输出风险评级、整改建议和跟踪要点。",
                status="active",
                agent_code="hidden_risk",
                scene_code="hidden_risk_analysis",
                description="初始化阶段内置 Prompt，用于后续隐患研判场景。",
            ),
        }

    def upsert_session(self, record: SessionRecord, title: str) -> None:
        conversation = self.conversations.get(record.conversation_id)

        if conversation is None:
            conversation = ConversationRecord(
                conversation_id=record.conversation_id,
                title=title,
                agent_code=record.agent_code,
            )
            self.conversations[record.conversation_id] = conversation

        conversation.update_time = datetime.now(UTC).isoformat()
        conversation.sessions.append(record)
        self.sessions_by_trace[record.trace_id] = record

    def set_session_status(self, trace_id: str, status: str) -> None:
        session = self.sessions_by_trace.get(trace_id)
        if session is not None:
            session.status = status

    def list_conversations(
        self,
        agent_code: str | None,
        page: int,
        page_size: int,
    ) -> tuple[list[ConversationSummary], int]:
        items = [
            conversation
            for conversation in self.conversations.values()
            if not conversation.deleted and (agent_code is None or conversation.agent_code == agent_code)
        ]
        items.sort(key=lambda item: item.update_time, reverse=True)

        total = len(items)
        start = (page - 1) * page_size
        end = start + page_size

        return [
            ConversationSummary(
                conversation_id=item.conversation_id,
                title=item.title,
                agent_code=item.agent_code,
                update_time=item.update_time,
            )
            for item in items[start:end]
        ], total

    def get_conversation(self, conversation_id: str) -> ConversationDetail | None:
        conversation = self.conversations.get(conversation_id)
        if conversation is None or conversation.deleted:
            return None

        return ConversationDetail(
            conversation_id=conversation.conversation_id,
            title=conversation.title,
            agent_code=conversation.agent_code,
            update_time=conversation.update_time,
            sessions=[
                SessionSummary(
                    session_id=session.session_id,
                    trace_id=session.trace_id,
                    scene_code=session.scene_code,
                    status=session.status,
                    message=session.message,
                    create_time=session.create_time,
                )
                for session in conversation.sessions
            ],
        )

    def delete_conversation(self, conversation_id: str) -> bool:
        conversation = self.conversations.get(conversation_id)
        if conversation is None:
            return False

        conversation.deleted = True
        conversation.update_time = datetime.now(UTC).isoformat()
        return True


runtime_store = InMemoryRuntimeStore()
