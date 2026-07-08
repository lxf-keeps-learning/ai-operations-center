"""
Report Chat Graph 本地演示脚本。

用法：
    cd backend
    python scripts/demo_report_chat.py

前提：已安装依赖，.env 中 DEEPSEEK_API_KEY 已配置，MySQL 已启动且有分析记录。
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.report_chat_agent.graph import report_chat_graph
from app.report_chat_agent.state import ReportChatState
from app.utils.ids import new_trace_id


def demo_internal_question():
    """测试报告内问题"""
    initial: ReportChatState = {
        "trace_id": new_trace_id(),
        "report_id": "1",
        "session_id": "demo_session_001",
        "user_id": "demo",
        "user_question": "为什么这个风险排第一？",
        "scene": "essential_safety",
        "report_context": {},
        "report_sections": [],
        "abnormal_items": [],
        "risk_items": [],
        "advice_items": [],
        "evidence": [],
        "chat_history": [],
        "question_scope": "report_internal",
        "scope_reason": "",
        "retrieved_context": [],
        "evidence_refs": [],
        "need_tool_query": False,
        "query_scope": {},
        "tool_results": [],
        "final_answer": "",
        "answer_type": "normal",
        "errors": [],
    }

    print("=" * 60)
    print("测试 1：报告内追问")
    print(f"问题: {initial['user_question']}")
    print("-" * 60)

    result = report_chat_graph.invoke(initial)

    print(f"question_scope: {result.get('question_scope')}")
    print(f"scope_reason: {result.get('scope_reason')}")
    print(f"answer_type: {result.get('answer_type')}")
    print(f"evidence_refs: {result.get('evidence_refs')}")
    print(f"errors: {result.get('errors')}")
    print()
    print("--- final_answer ---")
    print(result.get("final_answer", ""))
    print()


def demo_out_of_scope():
    """测试无关问题"""
    initial: ReportChatState = {
        "trace_id": new_trace_id(),
        "report_id": "1",
        "session_id": "demo_session_002",
        "user_id": "demo",
        "user_question": "帮我写首诗",
        "scene": "essential_safety",
        "report_context": {},
        "report_sections": [],
        "abnormal_items": [],
        "risk_items": [],
        "advice_items": [],
        "evidence": [],
        "chat_history": [],
        "question_scope": "report_internal",
        "scope_reason": "",
        "retrieved_context": [],
        "evidence_refs": [],
        "need_tool_query": False,
        "query_scope": {},
        "tool_results": [],
        "final_answer": "",
        "answer_type": "normal",
        "errors": [],
    }

    print("=" * 60)
    print("测试 2：无关问题")
    print(f"问题: {initial['user_question']}")
    print("-" * 60)

    result = report_chat_graph.invoke(initial)

    print(f"question_scope: {result.get('question_scope')}")
    print(f"answer_type: {result.get('answer_type')}")
    print()
    print("--- final_answer ---")
    print(result.get("final_answer", ""))
    print()


def demo_ioc_global():
    """测试 IOC 全局问题"""
    initial: ReportChatState = {
        "trace_id": new_trace_id(),
        "report_id": "1",
        "session_id": "demo_session_003",
        "user_id": "demo",
        "user_question": "全公司本月风险趋势如何？",
        "scene": "essential_safety",
        "report_context": {},
        "report_sections": [],
        "abnormal_items": [],
        "risk_items": [],
        "advice_items": [],
        "evidence": [],
        "chat_history": [],
        "question_scope": "report_internal",
        "scope_reason": "",
        "retrieved_context": [],
        "evidence_refs": [],
        "need_tool_query": False,
        "query_scope": {},
        "tool_results": [],
        "final_answer": "",
        "answer_type": "normal",
        "errors": [],
    }

    print("=" * 60)
    print("测试 3：IOC 全局问题")
    print(f"问题: {initial['user_question']}")
    print("-" * 60)

    result = report_chat_graph.invoke(initial)

    print(f"question_scope: {result.get('question_scope')}")
    print(f"answer_type: {result.get('answer_type')}")
    print()
    print("--- final_answer ---")
    print(result.get("final_answer", ""))
    print()


def demo_missing_report():
    """测试不存在的 report_id"""
    initial: ReportChatState = {
        "trace_id": new_trace_id(),
        "report_id": "999999",
        "session_id": "demo_session_004",
        "user_id": "demo",
        "user_question": "为什么判断为高风险？",
        "scene": "essential_safety",
        "report_context": {},
        "report_sections": [],
        "abnormal_items": [],
        "risk_items": [],
        "advice_items": [],
        "evidence": [],
        "chat_history": [],
        "question_scope": "report_internal",
        "scope_reason": "",
        "retrieved_context": [],
        "evidence_refs": [],
        "need_tool_query": False,
        "query_scope": {},
        "tool_results": [],
        "final_answer": "",
        "answer_type": "normal",
        "errors": [],
    }

    print("=" * 60)
    print("测试 4：不存在的报告")
    print(f"report_id: {initial['report_id']}")
    print("-" * 60)

    result = report_chat_graph.invoke(initial)

    print(f"errors: {result.get('errors')}")
    print(f"answer_type: {result.get('answer_type')}")
    print()
    print("--- final_answer ---")
    print(result.get("final_answer", ""))
    print()


if __name__ == "__main__":
    demo_internal_question()
    demo_out_of_scope()
    demo_ioc_global()
    demo_missing_report()
