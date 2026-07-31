from langgraph.checkpoint.memory import InMemorySaver
from langgraph.runtime import Runtime
from langgraph.store.memory import InMemoryStore

from app.report_chat_agent.graph import build_report_chat_graph
from app.report_chat_agent.memory import load_chat_memory_node, save_chat_memory_node


def test_report_chat_graph_accepts_official_checkpointer_and_store():
    graph = build_report_chat_graph(
        checkpointer=InMemorySaver(),
        store=InMemoryStore(),
    )

    assert graph.checkpointer is not None
    assert graph.store is not None


def test_report_chat_memory_uses_store_namespace_and_checkpointer_state():
    store = InMemoryStore()
    runtime = Runtime(store=store, context={"user_id": "user-1"})
    state = {
        "user_id": "user-1",
        "session_id": "session-1",
        "runtime_session_id": "turn-1",
        "report_id": "42",
        "user_question": "请记住以后优先关注高风险项",
        "final_answer": "好的，我会优先关注高风险项。",
        "chat_history": [],
    }

    saved = save_chat_memory_node(state, runtime)
    loaded = load_chat_memory_node({**state, **saved}, Runtime(store=store, context={"user_id": "user-1"}))

    assert saved["memory_saved"] is True
    assert loaded["chat_history"][-1]["role"] == "assistant"
    assert loaded["memory_context"][0]["value"]["content"] == "以后优先关注高风险项"


def test_report_memory_is_isolated_from_user_memory_and_has_audit_fields():
    store = InMemoryStore()
    runtime = Runtime(store=store, context={"user_id": "user-1"})

    save_chat_memory_node(
        {
            "user_id": "user-1",
            "session_id": "session-1",
            "runtime_session_id": "turn-1",
            "report_id": "42",
            "trace_id": "trace-1",
            "user_question": "请记住本报告的整改负责人是张三",
            "final_answer": "已记录本报告整改负责人。",
        },
        runtime,
    )
    save_chat_memory_node(
        {
            "user_id": "user-1",
            "session_id": "session-1",
            "runtime_session_id": "turn-2",
            "report_id": "42",
            "trace_id": "trace-2",
            "user_question": "我的偏好是优先展示高风险项",
            "final_answer": "已记录你的展示偏好。",
        },
        runtime,
    )

    report_items = store.search(("user-1", "report_memory", "42"), query="", limit=10)
    user_items = store.search(("user-1", "user_memory"), query="", limit=10)

    assert len(report_items) == 1
    assert len(user_items) == 1
    value = report_items[0].value
    assert value["memory_type"] == "report_fact"
    assert value["source"]["trace_id"] == "trace-1"
    assert value["status"] == "active"
    assert value["confidence"] == 1.0


def test_report_memory_does_not_cross_report_namespace():
    store = InMemoryStore()
    runtime = Runtime(store=store, context={"user_id": "user-1"})
    save_chat_memory_node(
        {
            "user_id": "user-1",
            "session_id": "session-1",
            "runtime_session_id": "turn-1",
            "report_id": "42",
            "user_question": "请记住本报告的整改负责人是张三",
            "final_answer": "已记录。",
        },
        runtime,
    )

    loaded = load_chat_memory_node(
        {"user_id": "user-1", "report_id": "43", "user_question": "整改负责人"},
        Runtime(store=store, context={"user_id": "user-1"}),
    )

    assert loaded["memory_context"] == []


class FailingStore:
    def search(self, *_args, **_kwargs):
        raise RuntimeError("memory search unavailable")

    def put(self, *_args, **_kwargs):
        raise RuntimeError("memory store unavailable")


def test_memory_read_failure_does_not_block_report_answer():
    loaded = load_chat_memory_node(
        {"user_id": "user-1", "report_id": "42", "user_question": "风险原因是什么"},
        Runtime(store=FailingStore(), context={"user_id": "user-1"}),
    )

    assert loaded["memory_context"] == []
    assert loaded["errors"][0]["node"] == "load_chat_memory"


def test_memory_write_failure_keeps_chat_history_and_report_answer():
    saved = save_chat_memory_node(
        {
            "user_id": "user-1",
            "session_id": "session-1",
            "runtime_session_id": "turn-1",
            "report_id": "42",
            "user_question": "请记住本报告的整改负责人是张三",
            "final_answer": "已记录本报告整改负责人。",
            "chat_history": [],
        },
        Runtime(store=FailingStore(), context={"user_id": "user-1"}),
    )

    assert saved["memory_saved"] is False
    assert saved["chat_history"][-1]["content"] == "已记录本报告整改负责人。"
    assert saved["errors"][0]["node"] == "save_chat_memory"
