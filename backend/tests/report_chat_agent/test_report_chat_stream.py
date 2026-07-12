"""Report Chat 真实回答流测试。"""

import json
from types import SimpleNamespace

import anyio
from langchain_core.messages import AIMessageChunk

from app.report_chat_agent.report_chat_event_adapter import ReportChatEventAdapter
from app.report_chat_agent.stream_service import stream_chat_message
from app.runtime.llm.client import LlmClient


def _mock_session_and_turn(monkeypatch) -> None:
    """Mock report_chat_repo 以跳过数据库操作。"""
    fake_session = SimpleNamespace(
        id="session_stream_test",
        conversation_id="conv_stream_test",
        report_id=1,
        user_id="tester",
    )
    fake_runtime_session = SimpleNamespace(id="rt_session_test")

    def fake_get_session(_db, session_id):
        return fake_session

    def fake_begin_turn(_db, **kw):
        return fake_runtime_session

    monkeypatch.setattr(
        "app.report_chat_agent.stream_service.report_chat_repo.get_session",
        fake_get_session,
    )
    monkeypatch.setattr(
        "app.report_chat_agent.stream_service.report_chat_repo.begin_turn",
        fake_begin_turn,
    )


def _collect_astsream_events(monkeypatch, mock_stream_events: list) -> list[dict]:
    """模拟 graph.astream 产出指定事件，收集 SSE 输出。"""
    _mock_session_and_turn(monkeypatch)
    monkeypatch.setattr(
        "app.report_chat_agent.stream_service.report_chat_graph",
        _MockGraph(mock_stream_events),
    )

    raw_events: list[str] = []

    async def run() -> None:
        async for raw in stream_chat_message(
            session_id="session_stream_test",
            report_id=1,
            question="为什么是高风险？",
            user_id="tester",
            trace_id="trace_stream_test",
        ):
            raw_events.append(raw)

    anyio.run(run)

    events: list[dict] = []
    for raw in raw_events:
        data_line = next(
            (line for line in raw.splitlines() if line.startswith("data: ")),
            "",
        )
        if data_line:
            events.append(json.loads(data_line[6:]))
    return events


class _MockGraph:
    """模拟 CompiledStateGraph.astream() 返回指定事件序列。"""

    def __init__(self, events: list) -> None:
        self._events = events

    async def astream(self, *args, **kwargs):
        for event in self._events:
            yield event


def test_stream_chat_emits_real_deltas_and_completion(monkeypatch) -> None:
    """模拟 LLM token 流 + 正常完成。"""
    mock_events = [
        ("custom", {"kind": "llm_token", "token": "第一段"}),
        ("custom", {"kind": "llm_token", "token": "回答"}),
        ("values", {
            "trace_id": "trace_stream_test",
            "message_id": "msg_stream_001",
            "conversation_id": "conv_stream_test",
            "session_id": "session_stream_test",
            "runtime_session_id": "rt_session_test",
            "question_scope": "report_internal",
            "final_answer": "第一段回答",
            "answer_type": "normal",
            "evidence_refs": ["EV_001"],
            "query_scope": {},
            "used_rag": False,
            "rag_source_refs": [],
            "rag_sources": [],
            "errors": [],
            "llm_usages": [],
        }),
    ]

    events = _collect_astsream_events(monkeypatch, mock_events)
    event_types = [event["event_type"] for event in events]
    deltas = [event["delta"] for event in events if event["event_type"] == "answer_delta"]

    assert event_types == [
        "message_started",
        "answer_delta",
        "answer_delta",
        "message_completed",
        "stream_closed",
    ]
    assert deltas == ["第一段", "回答"]
    assert events[-2]["answer"] == "第一段回答"
    assert events[-2]["message_id"] == "msg_stream_001"


def test_stream_chat_resets_partial_content_when_graph_falls_back(monkeypatch) -> None:
    """模拟流式 token 与 Graph 最终答案不一致时触发 answer_reset。"""
    mock_events = [
        ("custom", {"kind": "llm_token", "token": "未完成内容"}),
        ("values", {
            "final_answer": "模型失败后的规则兜底回答",
            "question_scope": "report_internal",
            "answer_type": "normal",
            "conversation_id": "conv_stream_test",
            "runtime_session_id": "rt_session_test",
            "errors": [{"node": "generate_answer", "message": "连接失败"}],
            "evidence_refs": [],
            "query_scope": {},
            "used_rag": False,
            "rag_source_refs": [],
            "rag_sources": [],
            "llm_usages": [],
        }),
    ]

    events = _collect_astsream_events(monkeypatch, mock_events)
    event_types = [event["event_type"] for event in events]

    assert "answer_reset" in event_types
    reset_index = event_types.index("answer_reset")
    assert events[reset_index + 1]["event_type"] == "answer_delta"
    assert events[reset_index + 1]["delta"] == "模型失败后的规则兜底回答"


def test_blocked_input_still_completes_stream(monkeypatch) -> None:
    """安全拦截也必须返回权威答案和 message_completed。"""
    _mock_session_and_turn(monkeypatch)
    monkeypatch.setattr(
        "app.report_chat_agent.stream_service.content_moderator.moderate",
        lambda _text: SimpleNamespace(
            action="block",
            message="输入已被安全策略拦截",
        ),
    )
    monkeypatch.setattr(
        "app.report_chat_agent.stream_service.report_chat_repo.complete_turn",
        lambda *_args, **_kwargs: SimpleNamespace(id="blocked_msg_001"),
    )

    raw_events: list[str] = []

    async def run() -> None:
        async for raw in stream_chat_message(
            session_id="session_stream_test",
            report_id=1,
            question="blocked",
            user_id="tester",
            trace_id="trace_blocked_test",
        ):
            raw_events.append(raw)

    anyio.run(run)
    events = [
        json.loads(next(line for line in raw.splitlines() if line.startswith("data: "))[6:])
        for raw in raw_events
    ]
    event_types = [event["event_type"] for event in events]

    assert event_types == [
        "message_started",
        "answer_delta",
        "message_completed",
        "stream_closed",
    ]
    assert events[-2]["answer"] == "输入已被安全策略拦截"
    assert events[-2]["answer_type"] == "boundary"


def test_llm_client_stream_chat_forwards_model_chunks() -> None:
    class FakeStreamingModel:
        def stream(self, messages, **kwargs):
            assert messages[-1].content == "用户问题"
            assert kwargs["stream_usage"] is True
            yield AIMessageChunk(content="流式")
            yield AIMessageChunk(
                content="回答",
                usage_metadata={
                    "input_tokens": 8,
                    "output_tokens": 2,
                    "total_tokens": 10,
                },
                response_metadata={"model_name": "deepseek-chat"},
            )

    client = LlmClient.__new__(LlmClient)
    client._default_provider = "deepseek"
    client._models = {"deepseek": FakeStreamingModel()}
    chunks: list[str] = []

    result = client.stream_chat(
        prompt_content="系统提示",
        user_message="用户问题",
        on_chunk=chunks.append,
    )

    assert result.success is True
    assert result.content == "流式回答"
    assert result.total_tokens == 10
    assert chunks == ["流式", "回答"]
