"""报告整体超时与取消传播专项测试。

验证：
  1. Graph Task 超时后，正在执行的 async Node 收到 CancelledError（取消穿透 LangGraph）。
  2. analyze_operation 超时 → ReportTimeoutError，best-effort 写失败状态，不保存成功报告。
  3. 总时长受 report_graph_timeout_seconds 约束（可配置短超时）。
"""

import asyncio
from types import SimpleNamespace

import pytest

from app.config.settings import settings
from app.operation_agent.multi_agent.graph import build_supervisor_graph
from app.operation_agent.nodes import query_operation_data_node
from app.operation_agent.state import OperationState
from app.core.timeout import ReportTimeoutError


def _safety_state() -> OperationState:
    return {
        "trace_id": "trace_timeout_1",
        "trigger_type": "tab_analysis",
        "user_question": "测试",
        "user_context": {"user_id": "u1"},
        "page_context": {"domain": "safety"},
        "llm_usages": [],
        "errors": [],
    }


class TestGraphCancellation:
    @pytest.mark.anyio
    async def test_graph_timeout_cancels_inflight_async_node(self) -> None:
        """Graph Task 被取消时，正在 await 的 Node 协程必须收到 CancelledError。"""
        node_cancelled = False

        async def _slow_run_tool(tool_name, filters, context, errors):
            nonlocal node_cancelled
            try:
                await asyncio.sleep(60)
            except asyncio.CancelledError:
                node_cancelled = True
                raise
            return None

        monkeypatch = pytest.MonkeyPatch()
        monkeypatch.setattr(query_operation_data_node, "_run_tool", _slow_run_tool)
        try:
            graph = build_supervisor_graph()
            with pytest.raises(TimeoutError):
                await asyncio.wait_for(graph.ainvoke(_safety_state()), timeout=0.3)
            assert node_cancelled is True, "取消必须穿透到 Node 协程"
        finally:
            monkeypatch.undo()


class TestReportServiceTimeout:
    @pytest.mark.anyio
    async def test_analyze_operation_raises_report_timeout(self, monkeypatch) -> None:
        """Graph 超时 → ReportTimeoutError（内部 504 语义），且不保存成功报告。"""
        saved_calls: list[dict] = []

        async def _slow_run_tool(tool_name, filters, context, errors):
            await asyncio.sleep(60)
            return None

        monkeypatch.setattr(query_operation_data_node, "_run_tool", _slow_run_tool)
        monkeypatch.setattr(settings, "report_graph_timeout_seconds", 0.2)
        monkeypatch.setattr(settings, "report_generation_timeout_seconds", 0.5)

        import app.operation_agent.service as op_service

        save_calls: list = []

        def _fake_save(db, **kwargs):
            save_calls.append(kwargs)
            return SimpleNamespace(id=1)

        monkeypatch.setattr(op_service, "save_analysis_result", _fake_save)

        class _FakeSession:
            def close(self) -> None:
                pass

        monkeypatch.setattr(op_service, "get_session_local", lambda: _FakeSession)

        request = SimpleNamespace(
            user_question="测试",
            domain="safety",
            active_tab=None,
            time_dimension=None,
            date=None,
            company_id=None,
            project_id=None,
            trigger_type="tab_analysis",
            force_refresh=False,
        )
        start = asyncio.get_event_loop().time()
        with pytest.raises(ReportTimeoutError):
            await op_service.analyze_operation(request, user_context={"user_id": "u1"})
        elapsed = asyncio.get_event_loop().time() - start
        assert elapsed < 2.0, "超时必须快速返回，不能无限等待"
        # 不得保存成功报告
        assert not any(kwargs.get("status") == "success" for kwargs in save_calls)

    @pytest.mark.anyio
    async def test_report_timeout_error_carries_code(self) -> None:
        err = ReportTimeoutError("报告生成超时")
        assert err.code == 504102
        assert err.http_status == 504
        assert err.retryable is False
