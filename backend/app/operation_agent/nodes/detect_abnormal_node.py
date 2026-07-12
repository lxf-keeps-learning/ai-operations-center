"""
异常检测节点 — DetectAbnormalNode。

职责：
  1. 遍历 metrics 列表，对每个指标按 metric_code 做阈值规则检查。
  2. 分析告警、隐患、工单列表，识别未闭环的高等级记录。
  3. 汇总异常项并排序（按严重等级），写入 state["abnormal_items"]。
  4. 将异常项转为风险条目写入 state["risk_items"]。

本节点完全基于规则，不调用 LLM 或外部 Tool。
"""

from app.operation_agent.state import OperationState

_SEVERITY_RANK = {"critical": 0, "high": 1, "warning": 2, "medium": 2, "low": 3}


def detect_abnormal_node(state: OperationState) -> OperationState:
    metrics = state.get("metrics", [])
    raw_data = state.get("raw_data", {})
    abnormal: list[dict] = []

    for metric in metrics:
        abnormal.extend(_detect_metric_abnormal(metric, metrics))

    abnormal.extend(_detect_alarm_abnormal(raw_data.get("alarm_items", [])))
    abnormal.extend(_detect_risk_abnormal(raw_data.get("risk_items", [])))
    abnormal.extend(_detect_work_order_abnormal(raw_data.get("work_order_items", [])))

    abnormal = sorted(abnormal, key=lambda item: _SEVERITY_RANK.get(item.get("severity", ""), 9))
    state["abnormal_items"] = abnormal
    state["risk_items"] = _build_risk_items(abnormal)
    return state


def _detect_metric_abnormal(metric: dict, metrics: list[dict]) -> list[dict]:
    code = metric.get("metric_code", "")
    name = metric.get("metric_name", "")
    value = metric.get("value")
    unit = metric.get("unit", "")
    status = metric.get("status", "")
    domain = metric.get("domain", "safety")

    if value is None or value == "--":
        return [
            {
                "domain": domain,
                "metric_code": code,
                "metric_name": name,
                "type": "data_missing",
                "severity": "high",
                "message": f"指标 {name} 数据缺失，值为空",
                "evidence": [_rule_evidence(f"{name} 值为空")],
            }
        ]

    numeric = _to_number(value)
    if numeric is None:
        return []

    abnormal = []

    if code == "energy_consumption" and status in {"warning", "critical"}:
        abnormal.append(
            _threshold_item(
                metric,
                severity="high" if status == "critical" else "warning",
                message=f"{name} ({numeric}{unit}) 状态为 {status}",
                value=numeric,
            )
        )

    if code == "alarm_handling_rate" and numeric < 95 and _has_total_alarms(metrics):
        abnormal.append(
            _threshold_item(
                metric,
                severity="warning",
                message=f"告警处理率 {numeric}{unit}，低于阈值 95%",
                value=numeric,
                threshold=95,
            )
        )

    if code == "work_order_completion_rate" and numeric < 80:
        abnormal.append(
            _threshold_item(
                metric,
                severity="warning",
                message=f"工单完成率 {numeric}{unit}，低于 80%",
                value=numeric,
                threshold=80,
            )
        )

    if code == "equipment_availability" and numeric < 90:
        abnormal.append(
            _threshold_item(
                metric,
                severity="high",
                message=f"设备可用率 {numeric}{unit}，低于 90%",
                value=numeric,
                threshold=90,
            )
        )

    if code == "operation_improvement_rate" and numeric < 90:
        abnormal.append(
            _threshold_item(
                metric,
                severity="warning",
                message=f"经营改善完成率 {numeric}{unit}，低于目标 90%",
                value=numeric,
                threshold=90,
            )
        )

    if code == "contract_fulfillment_rate" and numeric < 96:
        abnormal.append(
            _threshold_item(
                metric,
                severity="warning",
                message=f"合同履约率 {numeric}{unit}，低于目标 96%",
                value=numeric,
                threshold=96,
            )
        )

    if code == "low_score_customer_count" and numeric > 0:
        abnormal.append(
            _threshold_item(
                metric,
                severity="warning",
                message=f"存在 {int(numeric)} 户低评分客户，需要跟进服务体验",
                value=numeric,
                threshold=0,
            )
        )

    if code == "personnel_certificate_rate" and numeric < 100:
        severity = "high" if numeric < 80 else "warning"
        abnormal.append(
            _threshold_item(
                metric,
                severity=severity,
                message=f"人员持证上岗率 {numeric}{unit}，未达到 100% 要求",
                value=numeric,
                threshold=100,
            )
        )

    if code == "employee_efficiency" and numeric < 20:
        abnormal.append(
            _threshold_item(
                metric,
                severity="warning",
                message=f"人均处理工单 {numeric}{unit}，低于目标 20 单/人",
                value=numeric,
                threshold=20,
            )
        )

    if code == "iot_online_rate" and numeric < 98:
        abnormal.append(
            _threshold_item(
                metric,
                severity="warning",
                message=f"设备在线率 {numeric}{unit}，低于目标 98%",
                value=numeric,
                threshold=98,
            )
        )

    if code == "uncertified_company_count" and numeric > 0:
        abnormal.append(
            _threshold_item(
                metric,
                severity="high",
                message=f"存在 {int(numeric)} 家企业持证未达标，需要专项跟进",
                value=numeric,
                threshold=0,
            )
        )

    if code == "high_alarm_count" and numeric > 0:
        abnormal.append(
            _threshold_item(
                metric,
                severity="high",
                message=f"存在 {int(numeric)} 条高等级未闭环告警",
                value=numeric,
                threshold=0,
            )
        )

    if code in {"pending_risk_count", "pending_work_order_count"} and numeric > 0:
        abnormal.append(
            _threshold_item(
                metric,
                severity="warning",
                message=f"{name} 为 {int(numeric)}{unit}，需要推进闭环",
                value=numeric,
                threshold=0,
            )
        )

    return abnormal


def _detect_alarm_abnormal(alarms: list[dict]) -> list[dict]:
    abnormal = []
    for alarm in alarms:
        level = alarm.get("alarm_level", "")
        status = alarm.get("status", "")
        if status == "closed" or level not in {"critical", "high"}:
            continue
        title = alarm.get("title", "未命名告警")
        severity = "critical" if level == "critical" else "high"
        abnormal.append(
            {
                "domain": "safety",
                "metric_code": "alarm",
                "metric_name": title,
                "type": "high_level_alarm",
                "severity": severity,
                "message": f"{title} 处于 {status} 状态，告警等级为 {level}",
                "record_id": alarm.get("alarm_id"),
                "evidence": [
                    _record_evidence(
                        source_type="alarm_api",
                        record_id=alarm.get("alarm_id"),
                        description=(
                            f"告警 {alarm.get('alarm_id')}: {title}, "
                            f"等级={level}, 状态={status}, 部门={alarm.get('department', '')}"
                        ),
                    )
                ],
            }
        )
    return abnormal


def _detect_risk_abnormal(risks: list[dict]) -> list[dict]:
    abnormal = []
    for risk in risks:
        level = risk.get("risk_level", "")
        status = risk.get("status", "")
        if status != "pending" or level not in {"high", "medium"}:
            continue
        title = risk.get("title", "未命名隐患")
        abnormal.append(
            {
                "domain": "safety",
                "metric_code": "risk",
                "metric_name": title,
                "type": "pending_risk",
                "severity": "high" if level == "high" else "warning",
                "message": f"{title} 待整改，隐患等级为 {level}",
                "record_id": risk.get("risk_id"),
                "evidence": [
                    _record_evidence(
                        source_type="risk_api",
                        record_id=risk.get("risk_id"),
                        description=(
                            f"隐患 {risk.get('risk_id')}: {title}, "
                            f"等级={level}, 责任人={risk.get('owner', '')}"
                        ),
                    )
                ],
            }
        )
    return abnormal


def _detect_work_order_abnormal(work_orders: list[dict]) -> list[dict]:
    abnormal = []
    for order in work_orders:
        if order.get("status") != "pending":
            continue
        title = order.get("title", "未命名工单")
        abnormal.append(
            {
                "domain": "safety",
                "metric_code": "work_order",
                "metric_name": title,
                "type": "pending_work_order",
                "severity": "warning",
                "message": f"{title} 尚未处理，负责人为 {order.get('owner') or '未指定'}",
                "record_id": order.get("work_order_id"),
                "evidence": [
                    _record_evidence(
                        source_type="work_order_api",
                        record_id=order.get("work_order_id"),
                        description=(
                            f"工单 {order.get('work_order_id')}: {title}, "
                            f"状态={order.get('status')}, 负责人={order.get('owner', '')}"
                        ),
                    )
                ],
            }
        )
    return abnormal


def _threshold_item(
    metric: dict,
    *,
    severity: str,
    message: str,
    value: float,
    threshold: float | None = None,
) -> dict:
    name = metric.get("metric_name", "")
    unit = metric.get("unit", "")
    evidence_text = f"{name} = {value}{unit}"
    if threshold is not None:
        evidence_text = f"{evidence_text}, 阈值={threshold}"
    return {
        "domain": metric.get("domain", "safety"),
        "metric_code": metric.get("metric_code", ""),
        "metric_name": name,
        "type": "threshold_exceeded",
        "severity": severity,
        "message": message,
        "value": value,
        "threshold": threshold,
        "evidence": [_rule_evidence(evidence_text)],
    }


def _build_risk_items(abnormal: list[dict]) -> list[dict]:
    risk_items = []
    for index, item in enumerate(abnormal, start=1):
        severity = item.get("severity", "warning")
        risk_items.append(
            {
                "risk_id": item.get("record_id") or f"operation_risk_{index:03d}",
                "title": item.get("metric_name") or item.get("message", ""),
                "severity": severity,
                "priority": _priority_for_severity(severity),
                "source_type": item.get("type", "rule"),
                "description": item.get("message", ""),
                "evidence": item.get("evidence", []),
            }
        )
    return risk_items


def _priority_for_severity(severity: str) -> str:
    if severity in {"critical", "high"}:
        return "P1"
    return "P2"


def _rule_evidence(description: str) -> dict:
    return {"source": "rule_based_detection", "source_type": "rule", "description": description}


def _record_evidence(source_type: str, record_id: str | None, description: str) -> dict:
    return {
        "source": "mock_ioc_api",
        "source_type": source_type,
        "record_id": record_id,
        "description": description,
    }


def _to_number(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _has_total_alarms(metrics: list[dict]) -> bool:
    for metric in metrics:
        if metric.get("metric_code") == "alarm_handling_rate":
            value = metric.get("value")
            if value is not None and value != "--":
                try:
                    return float(value) >= 0
                except (TypeError, ValueError):
                    return False
    return False
