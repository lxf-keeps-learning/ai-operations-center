"""SummaryNode - render the final operation analysis markdown."""

from app.operation_agent.state import OperationState


def summary_node(state: OperationState) -> OperationState:
    metrics = state.get("metrics", [])
    abnormal = state.get("abnormal_items", [])
    risk_items = state.get("risk_items", [])
    reason = state.get("reason_analysis", "")
    advice = state.get("advice_items", [])
    evidence = state.get("evidence", [])
    errors = state.get("errors", [])

    domain = state.get("page_context", {}).get("domain") or state.get("domain", "safety")
    domain_label = _domain_label(domain)

    lines = ["## 运营分析结论", ""]

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
        lines.append(f"本次对 **{domain_label}** 领域进行分析，共识别 **{len(abnormal)}** 项异常。")
    else:
        lines.append(f"本次对 **{domain_label}** 领域进行分析，所有指标均在正常范围内。")
    lines.append("")

    lines.append("### 2. 关键发现")
    if metrics:
        lines.append("| 指标 | 值 | 状态 |")
        lines.append("|------|-----|------|")
        for metric in metrics:
            name = metric.get("metric_name", "")
            value = metric.get("value", "-")
            unit = metric.get("unit", "")
            status = metric.get("status", "normal")
            lines.append(f"| {name} | {value}{unit} | {status} |")
    else:
        lines.append("无指标数据。")
    lines.append("")

    lines.append("### 3. 异常与风险")
    if reason:
        lines.append("**原因分析**")
        lines.extend(f"> {line}" for line in reason.splitlines() if line.strip())
        lines.append("")
    if abnormal:
        for item in abnormal:
            severity = item.get("severity", "warning")
            lines.append(f"- **[{_severity_label(severity)}]** {item.get('message', '')}")
    else:
        lines.append("未识别到异常。")
    if risk_items:
        lines.append("")
        lines.append("**风险排序**")
        for risk in risk_items[:5]:
            lines.append(
                f"- **[{risk.get('priority', 'P2')}] {risk.get('title', '')}**："
                f"{risk.get('description', '')}"
            )
    lines.append("")

    lines.append("### 4. 建议动作")
    if advice:
        for item in advice:
            priority = item.get("priority", "P2")
            title = item.get("title", "")
            action = item.get("action", "")
            owner = item.get("owner_role", "")
            lines.append(f"- **[{priority}] {title}**")
            lines.append(f"  - 操作：{action}")
            lines.append(f"  - 负责人：{owner}")
    else:
        lines.append("当前无待处理建议。")
    lines.append("")

    lines.append("### 5. 数据依据")
    if evidence:
        for item in evidence:
            source = item.get("source", "")
            description = item.get("description", "")
            lines.append(f"- 来源：{source} | {description}")
    else:
        lines.append("本次分析无外部数据引用。")
    if errors:
        lines.append("")
        lines.append("#### 处理过程中的错误")
        for error in errors:
            lines.append(f"- {error.get('node', '')}: {error.get('message', '')}")

    state["final_answer"] = "\n".join(lines)
    return state


def _domain_label(domain: str) -> str:
    return {
        "safety": "本质安全",
        "maintenance": "设备运维",
        "business": "经营分析",
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
