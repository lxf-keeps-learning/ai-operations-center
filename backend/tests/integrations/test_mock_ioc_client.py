from app.integrations.ioc.client import IocApiClient
from app.integrations.ioc.mock_client import MockIocApiClient


class TestMockIocClient:
    def setup_method(self):
        self.client = MockIocApiClient()

    def test_client_is_instance_of_abstract(self):
        assert isinstance(self.client, IocApiClient)

    # ── KPI ──

    def test_get_kpis_returns_data(self):
        resp = self.client.get_kpis()
        assert resp.success is True
        assert len(resp.data["items"]) > 0
        assert resp.data["total"] > 0

    def test_get_kpis_items_have_expected_fields(self):
        resp = self.client.get_kpis()
        item = resp.data["items"][0]
        assert "metric_code" in item
        assert "metric_name" in item
        assert "value" in item
        assert "unit" in item

    def test_get_kpis_filter_by_department(self):
        resp = self.client.get_kpis(filters={"department": "能源运营部"})
        assert resp.success is True
        for item in resp.data["items"]:
            assert item["department"] == "能源运营部"

    def test_get_kpis_filter_by_metric_code(self):
        resp = self.client.get_kpis(filters={"metric_code": "carbon_emission"})
        assert resp.success is True
        for item in resp.data["items"]:
            assert item["metric_code"] == "carbon_emission"

    def test_get_kpis_filter_by_status(self):
        resp = self.client.get_kpis(filters={"status": "critical"})
        assert resp.success is True
        for item in resp.data["items"]:
            assert item["status"] == "critical"

    def test_get_kpis_filter_no_match_returns_empty(self):
        resp = self.client.get_kpis(filters={"department": "不存在部门"})
        assert resp.success is True
        assert resp.data["total"] == 0
        assert resp.data["items"] == []

    # ── Alarm ──

    def test_get_alarms_returns_data(self):
        resp = self.client.get_alarms()
        assert resp.success is True
        assert len(resp.data["items"]) > 0

    def test_get_alarms_items_have_expected_fields(self):
        resp = self.client.get_alarms()
        item = resp.data["items"][0]
        assert "alarm_id" in item
        assert "alarm_level" in item
        assert "title" in item
        assert "status" in item

    def test_get_alarms_filter_by_level(self):
        resp = self.client.get_alarms(filters={"alarm_level": "high"})
        assert resp.success is True
        for item in resp.data["items"]:
            assert item["alarm_level"] == "high"

    def test_get_alarms_filter_by_status(self):
        resp = self.client.get_alarms(filters={"status": "open"})
        assert resp.success is True
        for item in resp.data["items"]:
            assert item["status"] == "open"

    def test_get_alarms_filter_by_department(self):
        resp = self.client.get_alarms(filters={"department": "安全环保部"})
        assert resp.success is True
        for item in resp.data["items"]:
            assert item["department"] == "安全环保部"

    def test_get_alarms_filter_no_match_returns_empty(self):
        resp = self.client.get_alarms(filters={"alarm_level": "nonexistent"})
        assert resp.success is True
        assert resp.data["total"] == 0

    # ── Risk ──

    def test_get_risks_returns_data(self):
        resp = self.client.get_risks()
        assert resp.success is True
        assert len(resp.data["items"]) > 0

    def test_get_risks_items_have_expected_fields(self):
        resp = self.client.get_risks()
        item = resp.data["items"][0]
        assert "risk_id" in item
        assert "risk_level" in item
        assert "title" in item
        assert "status" in item

    def test_get_risks_filter_by_level(self):
        resp = self.client.get_risks(filters={"risk_level": "high"})
        assert resp.success is True
        for item in resp.data["items"]:
            assert item["risk_level"] == "high"

    def test_get_risks_filter_by_status(self):
        resp = self.client.get_risks(filters={"status": "pending"})
        assert resp.success is True
        for item in resp.data["items"]:
            assert item["status"] == "pending"

    def test_get_risks_filter_by_department(self):
        resp = self.client.get_risks(filters={"department": "安全环保部"})
        assert resp.success is True
        for item in resp.data["items"]:
            assert item["department"] == "安全环保部"

    # ── WorkOrder ──

    def test_get_work_orders_returns_data(self):
        resp = self.client.get_work_orders()
        assert resp.success is True
        assert len(resp.data["items"]) > 0

    def test_get_work_orders_items_have_expected_fields(self):
        resp = self.client.get_work_orders()
        item = resp.data["items"][0]
        assert "work_order_id" in item
        assert "title" in item
        assert "status" in item
        assert "owner" in item
        assert "department" in item

    def test_get_work_orders_filter_by_status(self):
        resp = self.client.get_work_orders(filters={"status": "pending"})
        assert resp.success is True
        for item in resp.data["items"]:
            assert item["status"] == "pending"

    def test_get_work_orders_filter_by_owner(self):
        resp = self.client.get_work_orders(filters={"owner": "张工"})
        assert resp.success is True
        for item in resp.data["items"]:
            assert item["owner"] == "张工"

    def test_get_work_orders_filter_by_related_alarm(self):
        resp = self.client.get_work_orders(filters={"related_alarm_id": "alarm_001"})
        assert resp.success is True
        for item in resp.data["items"]:
            assert item["related_alarm_id"] == "alarm_001"

    def test_get_work_orders_filter_by_department(self):
        resp = self.client.get_work_orders(filters={"department": "能源运营部"})
        assert resp.success is True
        assert resp.data["total"] > 0
        for item in resp.data["items"]:
            assert item["department"] == "能源运营部"

    # ── General ──

    def test_source_is_mock_ioc_api(self):
        for method in [self.client.get_kpis, self.client.get_alarms, self.client.get_risks, self.client.get_work_orders]:
            resp = method()
            assert resp.source == "mock_ioc_api"

    def test_data_has_items_and_total(self):
        for method in [self.client.get_kpis, self.client.get_alarms, self.client.get_risks, self.client.get_work_orders]:
            resp = method()
            assert "items" in resp.data
            assert "total" in resp.data

    def test_success_response_has_metadata(self):
        resp = self.client.get_kpis(filters={"department": "能源运营部"})
        assert resp.metadata["empty"] is False
        assert resp.metadata["filters"] == {"department": "能源运营部"}
        assert "department" in resp.metadata["supported_filters"]

    def test_no_filters_returns_all(self):
        all_kpi = self.client.get_kpis()
        filtered = self.client.get_kpis(filters={})
        assert all_kpi.data["total"] == filtered.data["total"]

    def test_unsupported_filter_returns_failure(self):
        resp = self.client.get_kpis(filters={"unknown": "value"})
        assert resp.success is False
        assert "Unsupported filters: unknown" in resp.error
