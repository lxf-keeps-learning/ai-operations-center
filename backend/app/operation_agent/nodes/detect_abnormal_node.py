"""
DetectAbnormalNode — 基于规则检测运营异常。

职责：
1. 遍历 metrics 列表，使用确定性规则判断异常。
2. 不调用 LLM，不查询数据库。
3. 输出 abnormal_items 列表，每条异常携带 evidence。

当前支持的规则：
- 数据缺失：值为 None 或 "--" → data_missing / high
- 能耗异常：status=warning / critical → threshold_exceeded
- 告警处理率 < 95% → threshold_exceeded / warning
- 工单完成率 < 80% → threshold_exceeded / warning
- 设备可用率 < 90% → threshold_exceeded / high

规则可扩展：后续增加 alarm/risk 数据的异常检测时在此添加规则即可。
"""
from app.operation_agent.state import OperationState


def detect_abnormal_node(state: OperationState) -> OperationState:
    """检测异常并写入 state.abnormal_items。"""
    metrics = state.get("metrics", [])
    abnormal: list[dict] = []

    for m in metrics:
        code = m.get("metric_code", "")
        name = m.get("metric_name", "")
        value = m.get("value")
        unit = m.get("unit", "")
        status = m.get("status", "")

        # ── 规则 1：数据缺失检测 ────────────────────
        if value is None or value == "--":
            abnormal.append({
                "metric_code": code,
                "metric_name": name,
                "type": "data_missing",
                "severity": "high",
                "message": f"指标 {name} 数据缺失，值为空",
                "evidence": [{"source": "rule_based_detection", "description": f"{name} 值为空"}],
            })
            continue

        numeric = _to_number(value)
        if numeric is None:
            continue

        # ── 规则 2：能耗异常（warning / critical） ──
        if code == "energy_consumption" and status in ("warning", "critical"):
            abnormal.append({
                "metric_code": code,
                "metric_name": name,
                "type": "threshold_exceeded",
                "severity": "high" if status == "critical" else "warning",
                "message": f"{name} ({numeric}{unit}) 状态为 {status}",
                "value": numeric,
                "threshold": None,
                "evidence": [{"source": "rule_based_detection", "description": f"{name} = {numeric}{unit}, 状态={status}"}],
            })

        # ── 规则 3：告警处理率 < 95% ────────────────
        if code == "alarm_handling_rate":
            if numeric < 95 and _has_total_alarms(metrics):
                abnormal.append({
                    "metric_code": code,
                    "metric_name": name,
                    "type": "threshold_exceeded",
                    "severity": "warning",
                    "message": f"告警处理率 {numeric}{unit}，低于阈值 95%",
                    "value": numeric,
                    "threshold": 95,
                    "evidence": [{"source": "rule_based_detection", "description": f"告警处理率 = {numeric}{unit} < 95%"}],
                })

        # ── 规则 4：工单完成率 < 80% ────────────────
        if code == "work_order_completion_rate":
            if numeric < 80:
                abnormal.append({
                    "metric_code": code,
                    "metric_name": name,
                    "type": "threshold_exceeded",
                    "severity": "warning",
                    "message": f"工单完成率 {numeric}{unit}，低于 80%",
                    "value": numeric,
                    "threshold": 80,
                    "evidence": [{"source": "rule_based_detection", "description": f"工单完成率 = {numeric}{unit} < 80%"}],
                })

        # ── 规则 5：设备可用率 < 90% ────────────────
        if code == "equipment_availability" and numeric < 90:
            abnormal.append({
                "metric_code": code,
                "metric_name": name,
                "type": "threshold_exceeded",
                "severity": "high",
                "message": f"设备可用率 {numeric}{unit}，低于 90%",
                "value": numeric,
                "threshold": 90,
                "evidence": [{"source": "rule_based_detection", "description": f"设备可用率 = {numeric}{unit} < 90%"}],
            })

    state["abnormal_items"] = abnormal
    return state


def _to_number(value) -> float | None:
    """尝试将值转换为浮点数，失败返回 None。"""
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _has_total_alarms(metrics: list[dict]) -> bool:
    """检查是否存在告警相关的指标记录（用于判断是否应该做告警处理率检测）。"""
    for m in metrics:
        if m.get("metric_code") == "alarm_handling_rate":
            v = m.get("value")
            if v is not None and v != "--":
                try:
                    return float(v) >= 0
                except (TypeError, ValueError):
                    return False
    return False
