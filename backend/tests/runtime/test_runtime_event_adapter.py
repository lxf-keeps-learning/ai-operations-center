"""RuntimeEventAdapter 单元测试。"""

from app.runtime.runtime_event_adapter import RuntimeEventAdapter


def test_message_started():
    adapter = RuntimeEventAdapter()
    event_t, event_d = adapter.get_message_started()
    assert event_t == "message_started"


def test_llm_token_to_token_event():
    adapter = RuntimeEventAdapter()
    events = adapter.process("custom", {"kind": "llm_token", "token": "你好"})
    assert len(events) == 1
    assert events[0][0] == "token"
    assert events[0][1]["delta"] == "你好"


def test_multi_token_events():
    adapter = RuntimeEventAdapter()
    adapter.process("custom", {"kind": "llm_token", "token": "Hello"})
    adapter.process("custom", {"kind": "llm_token", "token": " "})
    adapter.process("custom", {"kind": "llm_token", "token": "World"})
    adapter.process("values", {"answer": "Hello World"})

    completed = adapter.get_completed_event()
    assert completed is not None
    assert completed[1]["answer"] == "Hello World"


def test_unknown_custom_event_ignored():
    events = RuntimeEventAdapter().process("custom", {"kind": "unknown"})
    assert events == []


def test_empty_or_invalid_token_ignored():
    adapter = RuntimeEventAdapter()
    assert adapter.process("custom", {"kind": "llm_token", "token": ""}) == []
    assert adapter.process("custom", {"kind": "llm_token", "token": None}) == []


def test_non_dict_values_ignored():
    adapter = RuntimeEventAdapter()
    adapter.process("values", "internal")
    assert adapter.get_final_state() is None


def test_non_dict_custom_ignored():
    events = RuntimeEventAdapter().process("custom", "string")
    assert events == []


def test_completed_event_without_state():
    adapter = RuntimeEventAdapter()
    assert adapter.get_completed_event() is None


def test_completed_event_metadata():
    class FakeConv:
        id = "conv_001"
    adapter = RuntimeEventAdapter()
    adapter.process("values", {
        "conversation": FakeConv(),
        "session_id": "sess_001",
        "trace_id": "trace_001",
        "answer": "测试回答",
    })
    completed = adapter.get_completed_event()
    assert completed is not None
    assert completed[0] == "message_completed"
    assert completed[1]["conversation_id"] == "conv_001"
    assert completed[1]["answer"] == "测试回答"


def test_failed_event():
    event_t, event_d = RuntimeEventAdapter().get_failed_event("API 超时")
    assert event_t == "message_failed"
    assert event_d["error_message"] == "API 超时"


def test_closed_event():
    event_t, event_d = RuntimeEventAdapter().get_closed_event()
    assert event_t == "stream_closed"
