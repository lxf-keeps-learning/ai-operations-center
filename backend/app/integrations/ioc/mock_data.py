from app.integrations.ioc.schema import AlarmRecord, KpiRecord, RiskRecord, WorkOrderRecord

# ── KPI 数据 ──────────────────────────────────────────
KPI_DATA: list[KpiRecord] = [
    KpiRecord(metric_code="energy_consumption", metric_name="综合能耗", value=1280.5, unit="tce", status="warning", time_range="today", department="能源运营部"),
    KpiRecord(metric_code="energy_consumption", metric_name="综合能耗", value=1250.3, unit="tce", status="normal", time_range="yesterday", department="能源运营部"),
    KpiRecord(metric_code="carbon_emission", metric_name="碳排放", value=320.8, unit="tCO2", status="normal", time_range="today", department="能源运营部"),
    KpiRecord(metric_code="carbon_emission", metric_name="碳排放", value=315.2, unit="tCO2", status="normal", time_range="yesterday", department="能源运营部"),
    KpiRecord(metric_code="equipment_availability", metric_name="设备可用率", value=97.5, unit="%", status="normal", time_range="today", department="生产运维部"),
    KpiRecord(metric_code="equipment_availability", metric_name="设备可用率", value=98.1, unit="%", status="normal", time_range="yesterday", department="生产运维部"),
    KpiRecord(metric_code="alarm_handling_rate", metric_name="告警处理率", value=82.3, unit="%", status="warning", time_range="today", department="安全环保部"),
    KpiRecord(metric_code="alarm_handling_rate", metric_name="告警处理率", value=88.7, unit="%", status="normal", time_range="yesterday", department="安全环保部"),
    KpiRecord(metric_code="work_order_completion_rate", metric_name="工单完成率", value=76.4, unit="%", status="warning", time_range="today", department="生产运维部"),
    KpiRecord(metric_code="work_order_completion_rate", metric_name="工单完成率", value=80.0, unit="%", status="normal", time_range="yesterday", department="生产运维部"),
    KpiRecord(metric_code="energy_consumption", metric_name="综合能耗", value=1350.2, unit="tce", status="critical", time_range="today", department="华北能源站A"),
    KpiRecord(metric_code="energy_consumption", metric_name="综合能耗", value=1100.0, unit="tce", status="normal", time_range="today", department="华南能源站B"),
]

# ── 告警数据 ──────────────────────────────────────────
ALARM_DATA: list[AlarmRecord] = [
    AlarmRecord(alarm_id="alarm_001", alarm_level="high", alarm_type="energy", title="冷站出水温度异常", status="open", occurred_at="2026-07-06T08:20:00", department="能源运营部"),
    AlarmRecord(alarm_id="alarm_002", alarm_level="critical", alarm_type="equipment", title="2号机组振动超标", status="open", occurred_at="2026-07-06T07:45:00", department="生产运维部"),
    AlarmRecord(alarm_id="alarm_003", alarm_level="medium", alarm_type="safety", title="安全通道堵塞预警", status="processing", occurred_at="2026-07-06T06:30:00", department="安全环保部"),
    AlarmRecord(alarm_id="alarm_004", alarm_level="high", alarm_type="energy", title="配电室温度异常升高", status="open", occurred_at="2026-07-06T08:00:00", department="能源运营部"),
    AlarmRecord(alarm_id="alarm_005", alarm_level="low", alarm_type="equipment", title="冷却塔风扇转速偏低", status="closed", occurred_at="2026-07-05T14:00:00", department="生产运维部"),
    AlarmRecord(alarm_id="alarm_006", alarm_level="high", alarm_type="safety", title="有毒气体探测器报警", status="open", occurred_at="2026-07-06T09:10:00", department="安全环保部"),
    AlarmRecord(alarm_id="alarm_007", alarm_level="medium", alarm_type="energy", title="蒸汽管道压力波动", status="processing", occurred_at="2026-07-06T05:20:00", department="能源运营部"),
    AlarmRecord(alarm_id="alarm_008", alarm_level="critical", alarm_type="equipment", title="主变压器油温过高", status="open", occurred_at="2026-07-06T08:50:00", department="华北能源站A"),
]

# ── 隐患数据 ──────────────────────────────────────────
RISK_DATA: list[RiskRecord] = [
    RiskRecord(risk_id="risk_001", risk_level="high", title="2号泵运行振动偏高，存在设备劣化风险", status="pending", owner="张工", discovered_at="2026-07-04T09:00:00", department="生产运维部"),
    RiskRecord(risk_id="risk_002", risk_level="medium", title="电缆沟积水未及时清理", status="pending", owner="李工", discovered_at="2026-07-05T10:30:00", department="安全环保部"),
    RiskRecord(risk_id="risk_003", risk_level="high", title="锅炉排烟温度持续上升趋势", status="pending", owner="王工", discovered_at="2026-07-03T14:00:00", department="能源运营部"),
    RiskRecord(risk_id="risk_004", risk_level="low", title="部分仪表检定即将到期", status="mitigated", owner="赵工", discovered_at="2026-07-02T08:00:00", department="生产运维部"),
    RiskRecord(risk_id="risk_005", risk_level="medium", title="应急预案演练未按期完成", status="pending", owner="刘工", discovered_at="2026-07-06T07:00:00", department="安全环保部"),
    RiskRecord(risk_id="risk_006", risk_level="high", title="化学品存储区通风系统故障", status="closed", owner="陈工", discovered_at="2026-07-01T11:00:00", department="安全环保部"),
    RiskRecord(risk_id="risk_007", risk_level="medium", title="冷却水循环泵效率下降", status="pending", owner="张工", discovered_at="2026-07-05T16:00:00", department="华北能源站A"),
]

# ── 工单数据 ──────────────────────────────────────────
WORK_ORDER_DATA: list[WorkOrderRecord] = [
    WorkOrderRecord(
        work_order_id="wo_001",
        title="处理冷站出水温度异常",
        status="in_progress",
        owner="张工",
        created_at="2026-07-06T09:00:00",
        department="能源运营部",
        related_alarm_id="alarm_001",
    ),
    WorkOrderRecord(
        work_order_id="wo_002",
        title="2号机组振动检测与维修",
        status="pending",
        owner="李工",
        created_at="2026-07-06T08:30:00",
        department="生产运维部",
        related_alarm_id="alarm_002",
    ),
    WorkOrderRecord(
        work_order_id="wo_003",
        title="安全通道堵塞清理",
        status="completed",
        owner="王工",
        created_at="2026-07-06T07:00:00",
        department="安全环保部",
        related_alarm_id="alarm_003",
    ),
    WorkOrderRecord(
        work_order_id="wo_004",
        title="配电室温度异常排查",
        status="pending",
        owner="赵工",
        created_at="2026-07-06T08:10:00",
        department="能源运营部",
        related_alarm_id="alarm_004",
    ),
    WorkOrderRecord(
        work_order_id="wo_005",
        title="2号泵振动监测与维修方案",
        status="in_progress",
        owner="张工",
        created_at="2026-07-05T10:00:00",
        department="生产运维部",
        related_risk_id="risk_001",
    ),
    WorkOrderRecord(
        work_order_id="wo_006",
        title="电缆沟积水清理",
        status="completed",
        owner="李工",
        created_at="2026-07-05T11:30:00",
        department="安全环保部",
        related_risk_id="risk_002",
    ),
    WorkOrderRecord(
        work_order_id="wo_007",
        title="锅炉排烟温度专项检查",
        status="pending",
        owner="王工",
        created_at="2026-07-04T15:00:00",
        department="能源运营部",
        related_risk_id="risk_003",
    ),
    WorkOrderRecord(
        work_order_id="wo_008",
        title="冷却水循环泵效率评估",
        status="pending",
        owner="张工",
        created_at="2026-07-06T10:00:00",
        department="华北能源站A",
        related_risk_id="risk_007",
    ),
]
