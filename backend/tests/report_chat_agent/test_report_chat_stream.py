"""Report Chat 真实回答流测试。"""

import json

import anyio
from langchain_core.messages import AIMessageChunk

from app.report_chat_agent.stream_context import get_answer_stream_callback
from app.report_chat_agent.stream_service import stream_chat_message
from app.runtime.llm.client import LlmClient


def _collect_events(monkeypatch, fake_send) -> list[dict]:
    monkeypatch.setattr(
        "app.report_chat_agent.stream_service.send_chat_message",
        fake_send,
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


def test_stream_chat_emits_real_deltas_and_completion(monkeypatch) -> None:
    def fake_send(**kwargs):
        callback = get_answer_stream_callback()
        assert callback is not None
        callback("第一段")
        callback("回答")
        return {
            "trace_id": kwargs["trace_id"],
            "message_id": "msg_stream_001",
            "question_scope": "report_internal",
            "final_answer": "第一段回答",
            "answer_type": "normal",
            "evidence_refs": ["EV_001"],
            "query_scope": {},
            "used_rag": False,
            "rag_source_refs": [],
            "rag_sources": [],
            "errors": [],
        }

    events = _collect_events(monkeypatch, fake_send)
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
    def fake_send(**_kwargs):
        callback = get_answer_stream_callback()
        assert callback is not None
        callback("未完成内容")
        return {
            "final_answer": "模型失败后的规则兜底回答",
            "question_scope": "report_internal",
            "answer_type": "normal",
            "errors": [{"node": "generate_answer", "message": "连接失败"}],
        }

    events = _collect_events(monkeypatch, fake_send)
    event_types = [event["event_type"] for event in events]

    assert "answer_reset" in event_types
    reset_index = event_types.index("answer_reset")
    assert events[reset_index + 1]["event_type"] == "answer_delta"
    assert events[reset_index + 1]["delta"] == "模型失败后的规则兜底回答"


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
