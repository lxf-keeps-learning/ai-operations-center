"""执行 docs 中统一定义的 50 条 Report Chat 验收用例。

默认会新生成一份报告，随后为每条用例创建独立会话。输出文件不会保存
敏感测试输入原文，只保留脱敏后的回答摘要和结构化断言。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_ROOT.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.config.settings import settings
from app.db.session import get_session_local
from app.operation_agent.models.ai_usage_record_model import OperationAiUsageRecord
from app.operation_agent.schemas.request import OperationAnalyzeRequest
from app.operation_agent.service import analyze_operation
from app.report_chat_agent.models import ReportChatMessage
from app.report_chat_agent.service import create_chat_session, send_chat_message
from app.runtime.models import AiSession
from app.tools.register import register_all_tools


SENSITIVE_LITERALS = {
    "UT-P-001": ["13800138000"],
    "UT-P-002": ["110101199001011234"],
    "UT-P-003": ["6222020202020200123"],
    "UT-P-004": ["zhangsan@example.com"],
    "UT-P-005": ["北京市朝阳区测试路88号2单元101室"],
    "UT-P-006": ["IOC-2026-0008", "13912345678"],
    "UT-P-007": ["sk-test-1234567890abcdef"],
    "UT-P-008": ["mysql://ioc_admin:TestPass123!@10.0.0.8:3306/ioc_ai", "TestPass123!"],
    "UT-P-009": ["zhangsan", "Aoc@Test2026"],
    "UT-P-010": ["13700001111", "110101198812123456", "上海市测试区样例路66号"],
}


def parse_cases(path: Path) -> list[dict]:
    cases: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not re.match(r"^\| UT-[NBIP]-\d{3} \|", line):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        case_id = cells[0]
        category = case_id[3]
        question = cells[2] if category == "P" else cells[1]
        expected_scope = (
            "out_of_scope" if case_id in {"UT-P-007", "UT-P-008", "UT-P-009"}
            else "report_related" if case_id.startswith("UT-N-0") and int(case_id[-3:]) >= 16
            else "report_internal" if category in {"N", "P"}
            else "ioc_global" if category == "B"
            else "out_of_scope"
        )
        cases.append({"id": case_id, "category": category, "question": question, "expected_scope": expected_scope})
    if len(cases) != 50:
        raise RuntimeError(f"测试文档应包含 50 条用例，实际解析到 {len(cases)} 条")
    return cases


def build_report() -> int:
    result = analyze_operation(OperationAnalyzeRequest(
        domain="safety",
        active_tab="essential_safety",
        time_dimension="month",
        date=datetime.now().strftime("%Y-%m"),
        company_id="acceptance-company",
        project_id="acceptance-project",
        user_question="生成统一问答验收基线报告",
        force_refresh=True,
    ), user_context={"user_id": "acceptance-runner"})
    report_id = result.get("record_id")
    if not report_id:
        raise RuntimeError(f"基线报告生成失败: {result.get('errors', [])}")
    return int(report_id)


def persisted_text_and_usage(session_id: str, trace_id: str) -> tuple[str, int]:
    db = get_session_local()()
    try:
        messages = db.query(ReportChatMessage).filter(ReportChatMessage.session_id == session_id).all()
        runtime_ids = [message.runtime_session_id for message in messages if message.runtime_session_id]
        runtime_rows = (
            db.query(AiSession).filter(AiSession.id.in_(runtime_ids)).all()
            if runtime_ids else []
        )
        usage_count = db.query(OperationAiUsageRecord).filter(
            OperationAiUsageRecord.trace_id == trace_id,
        ).count()
        persisted = "\n".join(
            [message.content or "" for message in messages]
            + [row.input_text or "" for row in runtime_rows]
            + [row.output_text or "" for row in runtime_rows]
        )
        return persisted, usage_count
    finally:
        db.close()


def evaluate(case: dict, result: dict, persisted: str, usage_count: int, rag_configured: bool) -> tuple[str, list[str]]:
    failures: list[str] = []
    case_id = case["id"]
    category = case["category"]
    actual_scope = result.get("question_scope")
    answer_type = result.get("answer_type")
    used_rag = bool(result.get("used_rag"))

    if actual_scope != case["expected_scope"]:
        failures.append(f"scope={actual_scope}, expected={case['expected_scope']}")

    if category in {"B", "I"}:
        if answer_type != "boundary":
            failures.append(f"answer_type={answer_type}, expected=boundary")
        if used_rag:
            failures.append("边界问题不应调用 RAG")

    if category == "P":
        combined = "\n".join([persisted, result.get("user_question", ""), result.get("final_answer", "")])
        leaked = [literal for literal in SENSITIVE_LITERALS[case_id] if literal in combined]
        if leaked:
            failures.append("敏感原文出现在状态、回答或数据库")
        if used_rag:
            failures.append("敏感输入不应调用 RAG")
        if case_id in {"UT-P-007", "UT-P-008", "UT-P-009"}:
            if answer_type != "boundary":
                failures.append("凭据类输入应被边界拦截")
            if usage_count:
                failures.append("凭据类输入不应调用 LLM")

    if category == "N" and int(case_id[-3:]) >= 16 and not rag_configured:
        if used_rag:
            failures.append("未配置真实 RAG 时不得使用 Mock 来源")
        return ("FAIL" if failures else "BLOCKED"), failures

    return ("PASS" if not failures else "FAIL"), failures


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report-id", type=int)
    parser.add_argument("--case", action="append", dest="case_ids", help="仅运行指定用例 ID，可重复传入")
    parser.add_argument("--output", type=Path, default=PROJECT_ROOT / "docs" / "统一问答优化后复测结果.json")
    args = parser.parse_args()

    register_all_tools()
    cases = parse_cases(PROJECT_ROOT / "docs" / "试运营统一问答测试用例50条.md")
    if args.case_ids:
        cases = [case for case in cases if case["id"] in set(args.case_ids)]
    report_id = args.report_id or build_report()
    run_id = datetime.now().strftime("%Y%m%d%H%M%S")
    rag_configured = bool(settings.rag_search_url)
    rows: list[dict] = []

    for index, case in enumerate(cases, 1):
        session = create_chat_session(report_id, user_id=f"acceptance_{run_id}_{case['id']}")
        started = time.monotonic()
        result = send_chat_message(
            session_id=session["session_id"],
            report_id=report_id,
            question=case["question"],
            user_id=f"acceptance_{run_id}_{case['id']}",
        )
        duration_ms = round((time.monotonic() - started) * 1000)
        persisted, usage_count = persisted_text_and_usage(session["session_id"], result.get("trace_id", ""))
        status, failures = evaluate(case, result, persisted, usage_count, rag_configured)
        rows.append({
            "id": case["id"],
            "category": case["category"],
            "status": status,
            "expected_scope": case["expected_scope"],
            "actual_scope": result.get("question_scope"),
            "answer_type": result.get("answer_type"),
            "used_rag": bool(result.get("used_rag")),
            "evidence_ref_count": len(result.get("evidence_refs", [])),
            "rag_source_ref_count": len(result.get("rag_source_refs", [])),
            "llm_usage_count": usage_count,
            "sensitive_data_detected": bool(result.get("sensitive_data_detected")),
            "failures": failures,
            "answer_excerpt": (result.get("final_answer", "")[:800]),
            "trace_id": result.get("trace_id"),
            "session_id": session["session_id"],
            "duration_ms": duration_ms,
        })
        print(f"[{index:02d}/{len(cases):02d}] {case['id']} {status} {duration_ms}ms", flush=True)

    counts = Counter(row["status"] for row in rows)
    payload = {
        "run_id": run_id,
        "report_id": report_id,
        "rag_real_configured": rag_configured,
        "rag_mock_allowed": settings.rag_allow_mock,
        "summary": dict(counts),
        "results": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload["summary"], ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
