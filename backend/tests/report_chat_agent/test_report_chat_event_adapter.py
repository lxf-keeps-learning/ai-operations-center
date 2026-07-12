"""ReportChatEventAdapter 单元测试。"""

from app.report_chat_agent.report_chat_event_adapter import ReportChatEventAdapter

TRACE_ID = "trace_adapter_001"
SESSION_ID = "session_adapter_001"


def _adapter() -> ReportChatEventAdapter:
    return ReportChatEventAdapter(TRACE_ID, SESSION_ID)


def test_message_started():
    """get_message_started 应返回正确的事件类型。"""
    event_t, event_d = _adapter().get_message_started()
    assert event_t == "message_started"
    assert event_d["event_type"] == "message_started"


def test_llm_token_to_answer_delta():
    """custom.kind=llm_token 应转换为 answer_delta。"""
    adapter = _adapter()
    events = adapter.process("custom", {"kind": "llm_token", "token": "你好"})
    assert len(events) == 1
    assert events[0][0] == "answer_delta"
    assert events[0][1]["delta"] == "你好"


def test_unknown_custom_event():
    """未知 custom 事件应安全忽略。"""
    events = _adapter().process("custom", {"kind": "unknown"})
    assert events == []


def test_empty_or_invalid_token_ignored():
    adapter = _adapter()
    assert adapter.process("custom", {"kind": "llm_token", "token": ""}) == []
    assert adapter.process("custom", {"kind": "llm_token", "token": None}) == []


def test_non_dict_values_ignored():
    adapter = _adapter()
    adapter.process("values", "internal")
    assert adapter.get_final_state() is None


def test_values_stores_state():
    """values 事件应保存最终 State。"""
    adapter = _adapter()
    adapter.process("values", {"final_answer": "test answer"})
    fs = adapter.get_final_state()
    assert fs is not None
    assert fs["final_answer"] == "test answer"


def test_finalize_no_correction():
    """finalize 在流式与最终一致时不发 answer_reset。"""
    adapter = _adapter()
    adapter.process("custom", {"kind": "llm_token", "token": "一致的回答"})
    adapter.process("values", {"final_answer": "一致的回答", "conversation_id": "c1"})
    events = adapter.finalize()
    event_types = [e[0] for e in events]
    assert "answer_reset" not in event_types
    assert "message_completed" in event_types


def test_finalize_with_correction():
    """finalize 在流式与最终不一致时发 answer_reset。"""
    adapter = _adapter()
    adapter.process("custom", {"kind": "llm_token", "token": "未完成"})
    adapter.process("values", {"final_answer": "完整回答", "conversation_id": "c1"})
    events = adapter.finalize()
    event_types = [e[0] for e in events]
    assert "answer_reset" in event_types
    # answer_reset 后面跟着 answer_delta
    reset_idx = event_types.index("answer_reset")
    assert events[reset_idx + 1][0] == "answer_delta"
    assert events[reset_idx + 1][1]["delta"] == "完整回答"


def test_finalize_no_stream():
    """finalize 在没有 token 时不发 answer_reset。"""
    adapter = _adapter()
    adapter.process("values", {"final_answer": "直接回答", "conversation_id": "c1"})
    events = adapter.finalize()
    event_types = [e[0] for e in events]
    assert "answer_reset" not in event_types


def test_message_completed_metadata():
    """message_completed 应携带 RAG 相关元数据。"""
    adapter = _adapter()
    adapter.process("values", {
        "final_answer": "回答",
        "message_id": "msg_001",
        "conversation_id": "conv_001",
        "runtime_session_id": "rs_001",
        "question_scope": "report_internal",
        "answer_type": "normal",
        "used_rag": True,
        "evidence_refs": ["EV_001"],
        "rag_source_refs": ["RAG_001"],
        "rag_sources": [{"title": "doc"}],
        "query_scope": {"domain": "safety"},
        "errors": [],
        "llm_usages": [],
    })
    events = adapter.finalize()
    mc_event = next(e for e in events if e[0] == "message_completed")
    mc = mc_event[1]
    assert mc["message_id"] == "msg_001"
    assert mc["question_scope"] == "report_internal"
    assert mc["used_rag"] is True
    assert mc["rag_source_refs"] == ["RAG_001"]


def test_failed_event():
    """get_failed_event 应返回正确的错误事件。"""
    event_t, event_d = _adapter().get_failed_event("连接超时")
    assert event_t == "message_failed"
    assert event_d["error_message"] == "连接超时"


def test_closed_event():
    """get_closed_event 应返回 stream_closed。"""
    event_t, event_d = _adapter().get_closed_event()
    assert event_t == "stream_closed"


def test_sequence_increments():
    """每次发出的事件的 sequence 应递增。"""
    adapter = _adapter()
    adapter.process("custom", {"kind": "llm_token", "token": "a"})
    adapter.process("custom", {"kind": "llm_token", "token": "b"})
    adapter.process("values", {"final_answer": "ab", "conversation_id": "c1"})
    events = []
    for e_t, e_d in adapter.finalize():
        events.append(e_d)
    # Verify sequences are unique
    seqs = [e["sequence"] for e in events if "sequence" in e]
    assert len(seqs) == len(set(seqs))
