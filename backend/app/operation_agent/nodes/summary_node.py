from app.operation_agent.state import OperationState


def summary_node(state: OperationState) -> OperationState:
    metrics = state.get("metrics", [])
    abnormal = state.get("abnormal_items", [])
    reason = state.get("reason_analysis", "")
    advice = state.get("advice_items", [])
    evidence = state.get("evidence", [])
    errors = state.get("errors", [])

    domain = state.get("page_context", {}).get("domain") or state.get("domain", "safety")

    lines = ["## 运营分析结论", ""]

    # 1. 总体判断
    lines.append("### 1. 总体判断")
    if errors:
        lines.append("> 本次分析部分数据获取异常，以下结论基于已获取数据生成。")
        lines.append("")
    if abnormal:
        lines.append(f"本次对 **{domain}** 领域进行分析，共识别 **{len(abnormal)}** 项异常。")
    else:
        lines.append(f"本次对 **{domain}** 领域进行分析，所有指标均在正常范围内。")
    lines.append("")

    # 2. 关键发现
    lines.append("### 2. 关键发现")
    if metrics:
        lines.append("| 指标 | 值 | 状态 |")
        lines.append("|------|-----|------|")
        for m in metrics:
            name = m.get("metric_name", "")
            val = m.get("value", "-")
            unit = m.get("unit", "")
            status = m.get("status", "normal")
            lines.append(f"| {name} | {val}{unit} | {status} |")
    else:
        lines.append("无指标数据。")
    lines.append("")

    # 3. 异常与风险
    lines.append("### 3. 异常与风险")
    if abnormal:
        for a in abnormal:
            sev = a.get("severity", "warning")
            sev_label = "🔴 高风险" if sev == "high" else "🟡 中风险"
            lines.append(f"- **[{sev_label}]** {a.get('message', '')}")
    else:
        lines.append("未识别到异常。")
    lines.append("")

    # 4. 建议动作
    lines.append("### 4. 建议动作")
    if advice:
        for a in advice:
            pri = a.get("priority", "P2")
            title = a.get("title", "")
            action = a.get("action", "")
            owner = a.get("owner_role", "")
            lines.append(f"- **[{pri}] {title}**")
            lines.append(f"  - 操作：{action}")
            lines.append(f"  - 负责人：{owner}")
    else:
        lines.append("当前无待处理建议。")
    lines.append("")

    # 5. 数据依据
    lines.append("### 5. 数据依据")
    if evidence:
        for ev in evidence:
            src = ev.get("source", "")
            desc = ev.get("description", "")
            lines.append(f"- 来源：{src} | {desc}")
    else:
        lines.append("本次分析无外部数据引用。")
    if errors:
        lines.append("")
        lines.append("#### 处理过程中的错误")
        for err in errors:
            lines.append(f"- {err.get('node', '')}: {err.get('message', '')}")

    state["final_answer"] = "\n".join(lines)
    return state
