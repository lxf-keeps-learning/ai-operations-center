from typing import Any

from pydantic import BaseModel, Field


class IocApiResponse(BaseModel):
    success: bool
    data: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    source: str = "mock_ioc_api"
    metadata: dict[str, Any] = Field(default_factory=dict)


class KpiRecord(BaseModel):
    metric_code: str
    metric_name: str
    value: float
    unit: str
    status: str
    time_range: str
    department: str | None = None


class AlarmRecord(BaseModel):
    alarm_id: str
    alarm_level: str
    alarm_type: str
    title: str
    status: str
    occurred_at: str
    department: str | None = None


class RiskRecord(BaseModel):
    risk_id: str
    risk_level: str
    title: str
    status: str
    owner: str | None = None
    discovered_at: str
    department: str | None = None


class WorkOrderRecord(BaseModel):
    work_order_id: str
    title: str
    status: str
    owner: str | None = None
    created_at: str
    department: str | None = None
    related_alarm_id: str | None = None
    related_risk_id: str | None = None
