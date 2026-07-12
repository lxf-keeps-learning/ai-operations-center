"""LangGraphEventAdapter 单元测试。"""

from app.analysis_stream.event_emitter import SseEventEmitter
from app.analysis_stream.langgraph_event_adapter import (
    LangGraphEventAdapter,
    _calc_progress,
    _detect_source_label,
)
from app.operation_agent.graph import NODE_METADATA


NODE_ORDER = list(NODE_METADATA.keys())
RUN_ID = "test_adapter_001"


def _make_emitter() -> SseEventEmitter:
    return SseEventEmitter(run_id=RUN_ID)


def test_adapter_node_started_from_custom():
    """custom.kind=node_started 应转换为 node_started 事件。"""
    emitter = _make_emitter()
    adapter = LangGraphEventAdapter(emitter, NODE_METADATA, NODE_ORDER)

    events = adapter.process("custom", {
        "kind": "node_started",
        "node_key": "init_context",
        "node_name": "初始化环境",
    })

    assert len(events) == 1
    assert events[0]["event_type"] == "node_started"
    assert events[0]["node_key"] == "init_context"
    assert events[0]["status"] == "running"


def test_adapter_node_completed_from_updates():
    """updates 中节点更新应转换为 node_completed 事件。"""
    emitter = _make_emitter()
    adapter = LangGraphEventAdapter(emitter, NODE_METADATA, NODE_ORDER)

    # Simulate node_started first to record start time
    adapter.process("custom", {
        "kind": "node_started",
        "node_key": "init_context",
    })

    events = adapter.process("updates", {
        "init_context": {"trace_id": RUN_ID, "llm_usages": []},
    })

    assert len(events) == 1
    assert events[0]["event_type"] == "node_completed"
    assert events[0]["node_key"] == "init_context"
    assert events[0]["status"] == "completed"
    assert isinstance(events[0].get("duration_ms"), int)


def test_adapter_values_stores_final_state():
    """values 事件应被记录为最终 State。"""
    emitter = _make_emitter()
    adapter = LangGraphEventAdapter(emitter, NODE_METADATA, NODE_ORDER)

    adapter.process("values", {"trace_id": RUN_ID, "final_answer": "test"})
    final = adapter.get_final_state()
    assert final is not None
    assert final["final_answer"] == "test"


def test_adapter_unknown_custom_event_safe():
    """未知 Custom Event 应安全忽略。"""
    emitter = _make_emitter()
    adapter = LangGraphEventAdapter(emitter, NODE_METADATA, NODE_ORDER)

    events = adapter.process("custom", {"kind": "unknown_event", "data": "xyz"})
    assert events == []


def test_adapter_report_delta_from_custom():
    """summary 的 Markdown 增量应转换为 report_delta。"""
    emitter = _make_emitter()
    adapter = LangGraphEventAdapter(emitter, NODE_METADATA, NODE_ORDER)

    events = adapter.process("custom", {
        "kind": "report_delta",
        "delta": "## 运营分析报告\n\n",
    })

    assert len(events) == 1
    assert events[0]["event_type"] == "report_delta"
    assert events[0]["node_key"] == "summary"
    assert events[0]["payload"]["delta"] == "## 运营分析报告\n\n"


def test_adapter_empty_report_delta_safe():
    emitter = _make_emitter()
    adapter = LangGraphEventAdapter(emitter, NODE_METADATA, NODE_ORDER)
    assert adapter.process("custom", {"kind": "report_delta", "delta": ""}) == []


def test_adapter_non_dict_custom_safe():
    """非 dict Custom Event 应安全忽略。"""
    emitter = _make_emitter()
    adapter = LangGraphEventAdapter(emitter, NODE_METADATA, NODE_ORDER)

    events = adapter.process("custom", "just a string")
    assert events == []


def test_adapter_non_dict_updates_safe():
    """非 dict updates 数据应安全忽略。"""
    emitter = _make_emitter()
    adapter = LangGraphEventAdapter(emitter, NODE_METADATA, NODE_ORDER)

    events = adapter.process("updates", "not a dict")
    assert events == []


def test_adapter_event_sequence_preserved():
    """模拟完整事件流，验证顺序正确。"""
    emitter = _make_emitter()
    adapter = LangGraphEventAdapter(emitter, NODE_METADATA, NODE_ORDER)

    all_events = []

    # Simulate full streaming sequence
    stream = [
        ("values", {"trace_id": RUN_ID}),
        ("custom", {"kind": "node_started", "node_key": "init_context"}),
        ("updates", {"init_context": {"trace_id": RUN_ID}}),
        ("values", {"trace_id": RUN_ID, "final_answer": ""}),
        ("custom", {"kind": "node_started", "node_key": "summary"}),
        ("updates", {"summary": {"final_answer": "report"}}),
        ("values", {"trace_id": RUN_ID, "final_answer": "report"}),
    ]

    for mode, data in stream:
        all_events.extend(adapter.process(mode, data))

    event_types = [e["event_type"] for e in all_events]
    assert event_types == [
        "node_started",
        "node_completed",
        "node_started",
        "node_completed",
    ]

    node_keys = [e["node_key"] for e in all_events]
    assert node_keys == ["init_context", "init_context", "summary", "summary"]

    final = adapter.get_final_state()
    assert final is not None
    assert final["final_answer"] == "report"


def test_adapter_flush_no_pending():
    """flush 在无待发事件时应返回空列表。"""
    emitter = _make_emitter()
    adapter = LangGraphEventAdapter(emitter, NODE_METADATA, NODE_ORDER)
    assert adapter.flush() == []


def test_calc_progress_started():
    """_calc_progress 在 started 状态应正确计算进度。"""
    assert _calc_progress("init_context", "started", NODE_ORDER) == 0
    assert _calc_progress("analyze_reason", "started", NODE_ORDER) == int(3 * 100 / 6)
    assert _calc_progress("summary", "started", NODE_ORDER) == int(5 * 100 / 6)


def test_calc_progress_completed():
    """_calc_progress 在 completed 状态应正确计算进度。"""
    assert _calc_progress("init_context", "completed", NODE_ORDER) == int(1 * 100 / 6)
    assert _calc_progress("summary", "completed", NODE_ORDER) == 100


def test_calc_progress_unknown_key():
    """未知 node_key 应返回 None。"""
    assert _calc_progress("non_existent", "started", NODE_ORDER) is None


def test_detect_source_label_init_context():
    """init_context 应固定返回本地初始化来源。"""
    label = _detect_source_label({}, "init_context", 42)
    assert "本地初始化" in label
    assert "42ms" in label


def test_detect_source_label_with_ioc():
    """包含 ioc_summary 的 raw_data 应返回 Tool Center。"""
    state = {"raw_data": {"ioc_summary": {"total": 5}}}
    label = _detect_source_label(state, "query_operation_data", 100)
    assert "Tool Center" in label


def test_detect_source_label_with_snapshot():
    """包含 domain_snapshot 的 raw_data 应返回 Mock IOC。"""
    state = {"raw_data": {"domain_snapshot": {"items": [{"domain": "safety"}]}}}
    label = _detect_source_label(state, "query_operation_data", 100)
    assert "Mock IOC" in label


def test_detect_source_label_no_raw_data():
    """无 raw_data 时默认返回 Mock IOC。"""
    state = {}
    label = _detect_source_label(state, "query_operation_data", 100)
    assert "Mock IOC" in label


def test_detect_source_label_llm():
    """LLM 节点应返回模型名称。"""
    state = {
        "llm_usages": [
            {"model_name": "deepseek-chat", "success": True},
        ],
    }
    label = _detect_source_label(state, "analyze_reason", 500)
    assert "DeepSeek" in label


def test_detect_source_label_llm_no_usage():
    """无 LLM usage 记录时默认 deepseek。"""
    state = {}
    label = _detect_source_label(state, "analyze_reason", 500)
    assert "DeepSeek" in label


def test_detect_source_label_summary():
    """summary 固定返回 Markdown 渲染。"""
    label = _detect_source_label({}, "summary", 200)
    assert "Markdown 渲染" in label


def test_detect_source_label_unknown_node():
    """未知节点应返回通用 Node 标签。"""
    label = _detect_source_label({}, "unknown_node", 300)
    assert "Node" in label


def test_adapter_multiple_nodes_no_duplicate():
    """多个节点依次执行时，同一节点不应重复 emitting completed。"""
    emitter = _make_emitter()
    adapter = LangGraphEventAdapter(emitter, NODE_METADATA, NODE_ORDER)

    all_events = []
    stream = [
        ("custom", {"kind": "node_started", "node_key": "init_context"}),
        ("updates", {"init_context": {"trace_id": RUN_ID}}),
        ("custom", {"kind": "node_started", "node_key": "query_operation_data"}),
        ("updates", {"query_operation_data": {"raw_data": {}}}),
    ]
    for mode, data in stream:
        all_events.extend(adapter.process(mode, data))

    completed = [e for e in all_events if e["event_type"] == "node_completed"]
    node_keys = [e["node_key"] for e in completed]
    assert node_keys == ["init_context", "query_operation_data"]
    assert len(completed) == len(set(node_keys))


def test_adapter_duplicate_runtime_events_are_idempotent():
    """重放相同 Runtime 事件时，不应让前端节点状态重复或回退。"""
    emitter = _make_emitter()
    adapter = LangGraphEventAdapter(emitter, NODE_METADATA, NODE_ORDER)

    started = {"kind": "node_started", "node_key": "init_context"}
    update = {"init_context": {"trace_id": RUN_ID}}

    assert len(adapter.process("custom", started)) == 1
    assert adapter.process("custom", started) == []
    assert len(adapter.process("updates", update)) == 1
    assert adapter.process("updates", update) == []


def test_adapter_hides_unknown_runtime_nodes():
    """interrupt 等内部 Runtime update 不得泄漏为产品节点事件。"""
    emitter = _make_emitter()
    adapter = LangGraphEventAdapter(emitter, NODE_METADATA, NODE_ORDER)

    assert adapter.process("custom", {
        "kind": "node_started",
        "node_key": "__interrupt__",
    }) == []
    assert adapter.process("updates", {
        "__interrupt__": {"prompt": "internal"},
    }) == []
