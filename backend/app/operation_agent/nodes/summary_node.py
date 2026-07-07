"""SummaryNode - render the final operation analysis markdown."""

import re

from app.operation_agent.state import OperationState


def summary_node(state: OperationState) -> OperationState:
    metrics = state.get("metrics", [])
    abnormal = state.get("abnormal_items", [])
    risk_items = state.get("risk_items", [])
    reason = state.get("reason_analysis", "")
    advice = state.get("advice_items", [])
    evidence = state.get("evidence", [])
    errors = state.get("errors", [])

    page_context = state.get("page_context", {})
    domain = page_context.get("domain") or state.get("domain", "safety")
    domain_label = _domain_label(domain)
    active_tab = page_context.get("active_tab") or domain_label
    time_dimension = _time_dimension_label(page_context.get("time_dimension", ""))
    analysis_date = page_context.get("date") or "-"

    lines = ["## 运营分析报告", ""]
    lines.append("| 分析对象 | 时间维度 | 分析日期 | 异常数量 |")
    lines.append("|------|------|------|------|")
    lines.append(
        f"| {_cell(active_tab)} | {_cell(time_dimension)} | "
        f"{_cell(analysis_date)} | {len(abnormal)} 项 |"
    )
    lines.append("")

    lines.append("### 1. 总体判断")
    query_errors = [err for err in errors if err.get("node") == "query_operation_data"]
    llm_errors = [
        err
        for err in errors
        if err.get("node") in {"analyze_reason", "generate_advice"}
    ]
    if query_errors:
        lines.append("> 本次分析部分数据获取异常，以下结论基于已获取数据生成。")
        lines.append("")
    elif llm_errors:
        lines.append("> 本次 DeepSeek 分析调用触发降级，以下结论基于规则和 Tool Center 数据生成。")
        lines.append(f"> 降级原因：{llm_errors[0].get('message', '未知原因')}")
        lines.append("")
    if abnormal:
        critical_count = sum(
            1 for item in abnormal if item.get("severity") in {"critical", "high"}
        )
        lines.append(
            f"- **整体状态：异常。** 本次对 **{domain_label}** 领域进行分析，"
            f"共识别 **{len(abnormal)}** 项异常。"
        )
        if critical_count:
            lines.append(f"- **优先级提示：** 其中 **{critical_count}** 项为高等级风险，应优先闭环。")
    else:
        lines.append(f"- **整体状态：正常。** 本次对 **{domain_label}** 领域进行分析，所有指标均在正常范围内。")
    lines.append("")

    lines.append("### 2. 关键发现")
    if metrics:
        lines.append("| 指标 | 当前值 | 状态 |")
        lines.append("|------|-----|------|")
        for metric in metrics:
            name = metric.get("metric_name", "")
            value = metric.get("value", "-")
            unit = metric.get("unit", "")
            status = metric.get("status", "normal")
            lines.append(
                f"| {_cell(name)} | {_cell(f'{value}{unit}')} | "
                f"{_cell(_status_label(status))} |"
            )
    else:
        lines.append("无指标数据。")
    lines.append("")

    lines.append("### 3. 异常与风险")
    if reason:
        lines.append("#### 原因分析")
        lines.extend(_normalize_reason_lines(reason))
        lines.append("")
    if abnormal:
        lines.append("#### 异常清单")
        lines.append("| 等级 | 异常说明 |")
        lines.append("|------|------|")
        for item in abnormal:
            severity = item.get("severity", "warning")
            lines.append(
                f"| {_cell(_severity_label(severity))} | "
                f"{_cell(item.get('message', ''))} |"
            )
    else:
        lines.append("未识别到异常。")
    if risk_items:
        lines.append("")
        lines.append("#### 风险排序")
        lines.append("| 优先级 | 风险项 | 风险描述 |")
        lines.append("|------|------|------|")
        for risk in risk_items[:5]:
            lines.append(
                f"| {_cell(risk.get('priority', 'P2'))} | {_cell(risk.get('title', ''))} | "
                f"{_cell(risk.get('description', ''))} |"
            )
    lines.append("")

    lines.append("### 4. 建议动作")
    if advice:
        lines.append("| 优先级 | 建议事项 | 责任角色 | 执行动作 |")
        lines.append("|------|------|------|------|")
        for item in advice:
            priority = item.get("priority", "P2")
            title = item.get("title", "")
            action = item.get("action", "")
            owner = item.get("owner_role", "")
            lines.append(
                f"| {_cell(priority)} | {_cell(title)} | {_cell(owner)} | {_cell(action)} |"
            )
    else:
        lines.append("当前无待处理建议。")
    lines.append("")

    lines.append("### 5. 数据依据")
    if evidence:
        lines.append("| 数据来源 | 说明 |")
        lines.append("|------|------|")
        for item in evidence:
            source = item.get("source", "")
            description = item.get("description", "")
            lines.append(f"| {_cell(source)} | {_cell(description)} |")
    else:
        lines.append("本次分析无外部数据引用。")
    if errors:
        lines.append("")
        lines.append("### 6. 处理过程提示")
        lines.append("| 节点 | 信息 |")
        lines.append("|------|------|")
        for error in errors:
            lines.append(f"| {_cell(error.get('node', ''))} | {_cell(error.get('message', ''))} |")

    state["final_answer"] = "\n".join(lines)
    return state


def _domain_label(domain: str) -> str:
    return {
        "safety": "本质安全",
        "maintenance": "设备运维",
        "business": "经营改善",
        "capability": "能力提升",
        "all": "综合运营",
    }.get(domain, domain)


def _severity_label(severity: str) -> str:
    return {
        "critical": "严重风险",
        "high": "高风险",
        "warning": "中风险",
        "medium": "中风险",
        "low": "低风险",
    }.get(severity, "中风险")


def _status_label(status: str) -> str:
    return {
        "normal": "正常",
        "warning": "关注",
        "medium": "关注",
        "critical": "严重",
        "high": "高风险",
        "low": "低风险",
    }.get(status, status or "-")


def _time_dimension_label(value: str) -> str:
    return {
        "day": "日维度",
        "week": "周维度",
        "month": "月维度",
        "quarter": "季维度",
        "year": "年维度",
    }.get(value, value or "-")


def _cell(value: object) -> str:
    text = str(value or "-").replace("\n", " ").replace("|", " / ")
    return text.strip() or "-"


def _normalize_reason_lines(text: str) -> list[str]:
    lines: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            if lines and lines[-1]:
                lines.append("")
            continue
        if _is_boilerplate_line(line):
            continue
        heading = re.sub(r"^#{1,6}\s*", "", line).strip()
        if heading != line:
            if _is_report_title(heading):
                continue
            lines.append(f"**{heading}**")
            continue
        lines.append(line)

    while lines and not lines[-1]:
        lines.pop()
    return lines or ["当前暂无可展示的原因分析。"]


def _is_boilerplate_line(line: str) -> bool:
    normalized = line.strip("：:，,。. ")
    return (
        normalized.startswith("好的")
        or normalized.startswith("当然")
        or normalized.startswith("以下是")
        or normalized.startswith("下面是")
        or normalized.startswith("作为企业级智能运营中心")
        or normalized.startswith("作为运营分析专家")
        or normalized.startswith("报告时间")
        or normalized.startswith("分析维度")
        or normalized.startswith("分析对象")
    )


def _is_report_title(line: str) -> bool:
    compact = re.sub(r"\s+", "", line)
    return compact in {
        "运营分析报告",
        "运营状态分析报告",
        "运营分析结论",
        "原因分析",
        "异常与风险",
    }
