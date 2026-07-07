from app.operation_agent.state import OperationState


def detect_abnormal_node(state: OperationState) -> OperationState:
    metrics = state.get("metrics", [])
    abnormal: list[dict] = []

    for m in metrics:
        code = m.get("metric_code", "")
        name = m.get("metric_name", "")
        value = m.get("value")
        unit = m.get("unit", "")
        status = m.get("status", "")

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
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _has_total_alarms(metrics: list[dict]) -> bool:
    for m in metrics:
        if m.get("metric_code") == "alarm_handling_rate":
            v = m.get("value")
            if v is not None and v != "--":
                try:
                    return float(v) >= 0
                except (TypeError, ValueError):
                    return False
    return False
