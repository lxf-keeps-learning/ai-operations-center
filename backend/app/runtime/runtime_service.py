from time import perf_counter

from sqlalchemy.orm import Session

from app.core.config.llm_settings import llm_settings
from app.core.exception.base_exception import AppException
from app.core.exception.error_code import PROMPT_NOT_FOUND
from app.runtime.llm.client import llm_client
from app.runtime.schemas.conversation_schema import ConversationCreate
from app.runtime.schemas.feedback_schema import FeedbackCreate
from app.runtime.schemas.session_schema import SessionCreate, SessionUpdate
from app.runtime.schemas.status import SESS_FAILED, SESS_RUNNING, SESS_SUCCESS
from app.runtime.schemas.trace_schema import TraceCreate
from app.runtime.services.conversation_service import conversation_service
from app.runtime.services.feedback_service import feedback_service
from app.runtime.services.prompt_service import prompt_service
from app.runtime.services.session_service import session_service
from app.runtime.services.trace_service import trace_service
from app.utils.ids import new_span_id, new_trace_id

RUNTIME_GRAPH_NAME = "ioc_runtime_chat_graph"
PROMPT_NODE_NAME = "load_active_prompt"
CONTEXT_TOOL_NAME = "mysql_conversation_history"


def _elapsed_ms(start: float) -> int:
    return max(1, int((perf_counter() - start) * 1000))


class RuntimeService:
    def _record_span(
        self,
        db: Session,
        *,
        trace_id: str,
        session_id: str,
        conversation_id: str,
        span_type: str,
        span_id: str | None = None,
        parent_span_id: str | None = None,
        graph_name: str | None = None,
        node_name: str | None = None,
        tool_name: str | None = None,
        model_name: str | None = None,
        prompt_id: str | None = None,
        prompt_code: str | None = None,
        prompt_version: int | None = None,
        prompt_snapshot: str | None = None,
        input_data: dict | None = None,
        output_data: dict | None = None,
        cost_ms: int | None = None,
        prompt_tokens: int | None = None,
        completion_tokens: int | None = None,
        total_tokens: int | None = None,
        status: str = "success",
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> str:
        current_span_id = span_id or new_span_id()
        trace_service.create(
            db,
            TraceCreate(
                trace_id=trace_id,
                span_id=current_span_id,
                parent_span_id=parent_span_id,
                conversation_id=conversation_id,
                session_id=session_id,
                span_type=span_type,
                graph_name=graph_name,
                node_name=node_name,
                tool_name=tool_name,
                model_name=model_name,
                prompt_id=prompt_id,
                prompt_code=prompt_code,
                prompt_version=prompt_version,
                prompt_snapshot=prompt_snapshot,
                input_data=input_data,
                output_data=output_data,
                cost_ms=cost_ms,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                status=status,
                error_code=error_code,
                error_message=error_message,
            ),
        )
        return current_span_id

    def chat(
        self,
        db: Session,
        user_id: str,
        message: str,
        conversation_id: str | None = None,
        biz_type: str | None = None,
        prompt_code: str | None = None,
    ) -> dict:
        # 1. 创建或获取 Conversation
        conv = None
        if conversation_id:
            conv = conversation_service.get_by_id(db, conversation_id)
        if conv is None:
            conv = conversation_service.create(
                db, ConversationCreate(user_id=user_id, title=message[:100], biz_type=biz_type)
            )
            conversation_id = conv.id

        history_messages = session_service.list_recent_messages(db, conversation_id)

        # 2. 创建 Session（running）
        sess = session_service.create(
            db,
            SessionCreate(
                conversation_id=conversation_id,
                user_id=user_id,
                input_text=message,
                task_type="chat",
                context={
                    "biz_type": biz_type,
                    "prompt_code": prompt_code,
                    "history_messages": len(history_messages),
                },
                status=SESS_RUNNING,
            ),
        )

        trace_id = new_trace_id()
        root_span_id = self._record_span(
            db,
            trace_id=trace_id,
            session_id=sess.id,
            conversation_id=conversation_id,
            span_type="runtime",
            input_data={"event": "session_created", "user_id": user_id},
            output_data={"conversation_id": conversation_id, "session_id": sess.id},
            status="success",
        )
        graph_span_id = self._record_span(
            db,
            trace_id=trace_id,
            session_id=sess.id,
            conversation_id=conversation_id,
            span_type="graph",
            parent_span_id=root_span_id,
            graph_name=RUNTIME_GRAPH_NAME,
            input_data={"message": message, "biz_type": biz_type},
            output_data={"nodes": [PROMPT_NODE_NAME, CONTEXT_TOOL_NAME, "deepseek_llm"]},
            status="success",
        )

        # 3. 获取 active Prompt，并在 Trace 中记录实际版本
        prompt = None
        prompt_start = perf_counter()
        if prompt_code:
            prompt = prompt_service.get_active_by_code(db, prompt_code)
            if prompt is None:
                error_message = f"未找到 active Prompt: {prompt_code}"
                self._record_span(
                    db,
                    trace_id=trace_id,
                    session_id=sess.id,
                    conversation_id=conversation_id,
                    span_type="node",
                    parent_span_id=graph_span_id,
                    node_name=PROMPT_NODE_NAME,
                    input_data={"prompt_code": prompt_code},
                    cost_ms=_elapsed_ms(prompt_start),
                    status="failed",
                    error_code=str(PROMPT_NOT_FOUND.code),
                    error_message=error_message,
                )
                session_service.update(
                    db,
                    sess.id,
                    SessionUpdate(status=SESS_FAILED, error_message=error_message),
                )
                raise AppException.from_error_code(
                    PROMPT_NOT_FOUND,
                    message=error_message,
                    data={"runtime_trace_id": trace_id, "session_id": sess.id},
                )

        self._record_span(
            db,
            trace_id=trace_id,
            session_id=sess.id,
            conversation_id=conversation_id,
            span_type="node",
            parent_span_id=graph_span_id,
            node_name=PROMPT_NODE_NAME,
            input_data={"prompt_code": prompt_code},
            output_data={
                "prompt_found": prompt is not None,
                "prompt_id": prompt.id if prompt else None,
                "prompt_code": prompt.code if prompt else None,
                "prompt_version": prompt.version if prompt else None,
            },
            cost_ms=_elapsed_ms(prompt_start),
            status="success",
        )

        # 4. 执行上下文 Tool / LLM
        tool_start = perf_counter()
        self._record_span(
            db,
            trace_id=trace_id,
            session_id=sess.id,
            conversation_id=conversation_id,
            span_type="tool",
            parent_span_id=graph_span_id,
            tool_name=CONTEXT_TOOL_NAME,
            input_data={"conversation_id": conversation_id, "session_id": sess.id},
            output_data={
                "context_source": "mysql_session_json",
                "history_messages": len(history_messages),
                "runtime_db_stores_ioc_master_data": False,
            },
            cost_ms=_elapsed_ms(tool_start),
            status="success",
        )

        llm_start = perf_counter()
        llm_result = llm_client.chat(
            prompt.content if prompt else None,
            message,
            history=history_messages,
        )

        if llm_result.success:
            answer = llm_result.content
        else:
            answer = f"（AI 回复失败：{llm_result.error_message or '未知错误'}）"

        self._record_span(
            db,
            trace_id=trace_id,
            session_id=sess.id,
            conversation_id=conversation_id,
            span_type="llm",
            parent_span_id=graph_span_id,
            model_name=llm_result.model or llm_settings.default_provider,
            prompt_id=prompt.id if prompt else None,
            prompt_code=prompt.code if prompt else None,
            prompt_version=prompt.version if prompt else None,
            prompt_snapshot=llm_result.system_prompt or (prompt.content if prompt else None),
            input_data={
                "input": message,
                "history_messages": len(history_messages),
            },
            output_data={
                "output": answer,
                "provider": "deepseek",
                "model": llm_result.model,
            },
            cost_ms=llm_result.cost_ms,
            prompt_tokens=llm_result.prompt_tokens,
            completion_tokens=llm_result.completion_tokens,
            total_tokens=llm_result.total_tokens,
            status="success" if llm_result.success else "failed",
            error_code=None if llm_result.success else "LLM_PROVIDER_ERROR",
            error_message=None if llm_result.success else llm_result.error_message,
        )

        if llm_result.success:
            # 5a. 成功：更新 Session 输出
            session_service.update_output(db, sess.id, answer, status=SESS_SUCCESS)
            self._record_span(
                db,
                trace_id=trace_id,
                session_id=sess.id,
                conversation_id=conversation_id,
                span_type="runtime",
                parent_span_id=root_span_id,
                input_data={"event": "session_finished"},
                output_data={"status": SESS_SUCCESS},
                status="success",
            )
        else:
            # 5b. 失败：更新 Session 为 failed
            session_service.update(
                db,
                sess.id,
                SessionUpdate(status=SESS_FAILED, error_message=llm_result.error_message),
            )
            self._record_span(
                db,
                trace_id=trace_id,
                session_id=sess.id,
                conversation_id=conversation_id,
                span_type="runtime",
                parent_span_id=root_span_id,
                input_data={"event": "session_finished"},
                output_data={"status": SESS_FAILED, "error": llm_result.error_message},
                status="failed",
            )

        # 6. 返回结果
        return {
            "conversation_id": conversation_id,
            "session_id": sess.id,
            "trace_id": trace_id,
            "answer": answer,
            "reply": answer,
        }

    def submit_feedback(self, db: Session, payload: FeedbackCreate) -> dict:
        fb = feedback_service.create(db, payload)
        return {"feedback_id": fb.id, "message": "反馈提交成功"}


runtime_service = RuntimeService()
