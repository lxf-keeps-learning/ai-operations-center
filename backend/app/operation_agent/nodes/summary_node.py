"""
SummaryNode — 生成最终的 Markdown 运营分析报告。

职责：
1. 从 State 中收集 metrics、abnormal_items、advice_items、evidence。
2. 按固定 Markdown 模板组装结论。
3. 包含 5 个章节：总体判断、关键发现、异常与风险、建议动作、数据依据。
4. 如果存在 error，在报告开头注明"部分数据异常"。
5. 输出的 final_answer 可直接在前端展示。

该节点不调用 LLM，纯粹按规则组装文本。
"""
from app.operation_agent.state import OperationState


def summary_node(state: OperationState) -> OperationState:
    """
    组装 Markdown 格式的运营分析结论。

    Markdown 结构：
        ## 运营分析结论
        ### 1. 总体判断
        ### 2. 关键发现
        ### 3. 异常与风险
        ### 4. 建议动作
        ### 5. 数据依据
    """
    metrics = state.get("metrics", [])
    abnormal = state.get("abnormal_items", [])
    reason = state.get("reason_analysis", "")
    advice = state.get("advice_items", [])
    evidence = state.get("evidence", [])
    errors = state.get("errors", [])

    domain = state.get("page_context", {}).get("domain") or state.get("domain", "safety")

    lines = ["## 运营分析结论", ""]

    # ── 1. 总体判断 ──────────────────────────────
    lines.append("### 1. 总体判断")
    if errors:
        lines.append("> 本次分析部分数据获取异常，以下结论基于已获取数据生成。")
        lines.append("")
    if abnormal:
        lines.append(f"本次对 **{domain}** 领域进行分析，共识别 **{len(abnormal)}** 项异常。")
    else:
        lines.append(f"本次对 **{domain}** 领域进行分析，所有指标均在正常范围内。")
    lines.append("")

    # ── 2. 关键发现（指标列表） ──────────────────
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

    # ── 3. 异常与风险 ────────────────────────────
    lines.append("### 3. 异常与风险")
    if abnormal:
        for a in abnormal:
            sev = a.get("severity", "warning")
            sev_label = "🔴 高风险" if sev == "high" else "🟡 中风险"
            lines.append(f"- **[{sev_label}]** {a.get('message', '')}")
    else:
        lines.append("未识别到异常。")
    lines.append("")

    # ── 4. 建议动作 ──────────────────────────────
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

    # ── 5. 数据依据 ──────────────────────────────
    lines.append("### 5. 数据依据")
    if evidence:
        for ev in evidence:
            src = ev.get("source", "")
            desc = ev.get("description", "")
            lines.append(f"- 来源：{src} | {desc}")
    else:
        lines.append("本次分析无外部数据引用。")

    # 如果有错误，在末尾追加详细错误信息
    if errors:
        lines.append("")
        lines.append("#### 处理过程中的错误")
        for err in errors:
            lines.append(f"- {err.get('node', '')}: {err.get('message', '')}")

    state["final_answer"] = "\n".join(lines)
    return state
