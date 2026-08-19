from types import SimpleNamespace

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.core.exception.base_exception import AppException
from app.main import create_app
from app.modules.experiment_center.application import experiment_service as experiment_module
from app.modules.evaluation_center.application import evaluation_service as evaluation_module
from app.modules.evaluation_center.schemas.evaluation_schema import EvaluateRequest
from app.modules.prompt_center.application import (
    langgraph_integration,
    prompt_evaluation_service,
    prompt_release_service,
    prompt_service,
    prompt_version_service,
)
from app.modules.prompt_center.application.prompt_render_service import render_prompt
from app.modules.prompt_center.schemas.prompt_schema import PromptCreate
from app.modules.prompt_center.schemas.release_schema import ReleaseRequest, RollbackRequest
from app.modules.prompt_center.schemas.version_schema import VersionCreate
from app.modules.prompt_center.domain.entities import PromptRenderResult
from app.modules.prompt_center.infrastructure.models import PromptVariable
from app.operation_agent.nodes import analyze_reason_node as analyze_reason_module
from app.operation_agent import service as operation_service
from app.operation_agent.schemas.request import OperationAnalyzeRequest
from app.runtime.llm.client import LlmResult


class _ScalarResult:
    def all(self) -> list:
        return []


class _ReadOnlySession:
    def scalars(self, _statement) -> _ScalarResult:
        return _ScalarResult()


def _override_db():
    yield _ReadOnlySession()


def test_v2_migrations_form_one_resolvable_head() -> None:
    config = Config("alembic.ini")
    script = ScriptDirectory.from_config(config)

    assert script.get_heads() == ["20260819_0004"]
    assert script.get_revision("20260728_0001").down_revision == "20260711_0006"


def test_static_routes_are_not_shadowed_by_integer_detail_routes() -> None:
    app = create_app()
    app.dependency_overrides[get_db] = _override_db

    with TestClient(app) as client:
        by_trace = client.get("/api/v1/evaluation/results/by-trace/trace-v2-001")
        failure_stats = client.get("/api/v1/failures/stats/ioc.safety.analysis")

    assert by_trace.status_code == 200
    assert failure_stats.status_code == 200


def test_preview_route_accepts_version_id_payload() -> None:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    db = Session(engine)
    prompt = prompt_service.create_prompt(
        db,
        PromptCreate(
            prompt_key="ioc.preview.acceptance",
            prompt_name="预览验收",
        ),
    )
    version = prompt_version_service.create_version(
        db,
        prompt.id,
        VersionCreate(
            system_content="system",
            business_goal_content="goal",
        ),
    )
    db.add(
        PromptVariable(
            prompt_id=prompt.id,
            variable_key="device_name",
            variable_name="设备名称",
            required=True,
        )
    )
    db.commit()

    app = create_app()

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app) as client:
            response = client.post(
                f"/api/v1/prompt-center/prompts/{prompt.id}/preview",
                json={
                    "prompt_id": prompt.id,
                    "version_id": version.id,
                    "variables": {},
                },
            )
        assert response.status_code == 200
        assert response.json()["data"]["version"] == version.version
        assert "<未提供：设备名称>" in response.json()["data"]["messages"][-1]["content"]
    finally:
        db.close()


def test_experiment_renders_the_selected_prompt_version(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    version = SimpleNamespace(id=21, version="2.1.0")
    prompt = SimpleNamespace(id=3, prompt_key="ioc.safety.analysis")
    test_case = SimpleNamespace(
        id=8,
        input_data={"user_question": "请分析当前风险"},
    )
    unselected_case = SimpleNamespace(
        id=9,
        input_data={"user_question": "不应执行"},
    )
    rendered_versions: list[str | None] = []

    monkeypatch.setattr(
        experiment_module.prompt_test_case_repo,
        "list_by_prompt",
        lambda _db, _prompt_id: [test_case, unselected_case],
    )
    monkeypatch.setattr(
        experiment_module.experiment_repo,
        "get_by_id",
        lambda _db, _experiment_id: SimpleNamespace(test_case_ids=[8]),
    )

    def fake_render_prompt(**kwargs):
        rendered_versions.append(kwargs.get("version"))
        return SimpleNamespace(
            messages=[
                {"role": "system", "content": "system"},
                {"role": "user", "content": "user"},
            ]
        )

    monkeypatch.setattr(experiment_module, "render_prompt", fake_render_prompt)
    monkeypatch.setattr(
        experiment_module.llm_client,
        "chat",
        lambda **_kwargs: LlmResult(
            content='{"title":"ok","priority":"P1"}',
            model="test-model",
            prompt_tokens=2,
            completion_tokens=3,
            total_tokens=5,
            cost_ms=1,
            success=True,
        ),
    )
    monkeypatch.setattr(
        experiment_module.experiment_result_repo,
        "create",
        lambda _db, data: SimpleNamespace(id=1, **data),
    )
    monkeypatch.setattr(
        experiment_module.experiment_result_repo,
        "update",
        lambda _db, _result_id, _data: None,
    )

    experiment_module.experiment_service._call_llm_for_version(
        None,
        experiment_id=5,
        version_label="target",
        version_record=version,
        prompt_def=prompt,
    )

    assert rendered_versions == ["2.1.0"]


def test_experiment_comparison_reports_executed_sample_counts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    experiment = SimpleNamespace(
        id=5,
        name="版本对比",
        status="completed",
        winner_version="target",
        source_version_id=11,
        target_version_id=12,
    )
    versions = {
        11: SimpleNamespace(version="1.0.0"),
        12: SimpleNamespace(version="1.1.0"),
    }
    results = {
        "source": [
            SimpleNamespace(token_usage={"total_tokens": 10}, latency_ms=100),
            SimpleNamespace(token_usage={"total_tokens": 12}, latency_ms=120),
        ],
        "target": [
            SimpleNamespace(token_usage={"total_tokens": 9}, latency_ms=90),
            SimpleNamespace(token_usage={"total_tokens": 11}, latency_ms=110),
        ],
    }
    monkeypatch.setattr(
        experiment_module.experiment_repo,
        "get_by_id",
        lambda _db, _experiment_id: experiment,
    )
    monkeypatch.setattr(
        experiment_module.prompt_version_repo,
        "get_by_id",
        lambda _db, version_id: versions[version_id],
    )
    monkeypatch.setattr(
        experiment_module.experiment_result_repo,
        "get_aggregate_metrics",
        lambda _db, _experiment_id, version: [
            {"evaluator_key": "json_format", "avg_score": 1.0, "sample_count": 2}
        ],
    )
    monkeypatch.setattr(
        experiment_module.experiment_result_repo,
        "get_by_experiment_and_version",
        lambda _db, _experiment_id, version: results[version],
    )

    comparison = experiment_module.experiment_service.compare_versions(None, 5)

    assert comparison.source_version.sample_count == 2
    assert comparison.target_version.sample_count == 2


def test_prompt_lifecycle_publishes_and_rolls_back_an_immutable_version() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as db:
        prompt = prompt_service.create_prompt(
            db,
            PromptCreate(
                prompt_key="ioc.safety.analysis",
                prompt_name="设备安全分析",
            ),
            operator_id="creator",
        )
        v1 = prompt_version_service.create_version(
            db,
            prompt.id,
            VersionCreate(
                system_content="system-v1",
                business_goal_content="goal-v1",
                model_config={"temperature": 0.1},
                change_reason="初始版本",
            ),
            operator_id="creator",
        )
        assert v1.version == "1.0.0"
        assert v1.llm_config == {"temperature": 0.1}
        prompt_version_service.submit_version(db, v1.id, operator_id="creator")
        prompt_version_service.approve_version(db, v1.id, operator_id="reviewer")
        prompt_release_service.production_release(
            db,
            prompt.id,
            v1.id,
            ReleaseRequest(
                environment="production",
                released_by="publisher",
                approved_by="reviewer",
            ),
        )

        v2 = prompt_version_service.create_version(
            db,
            prompt.id,
            VersionCreate(
                business_goal_content="goal-v2",
                change_reason="调整业务目标",
            ),
            operator_id="creator",
        )
        assert v2.version == "1.1.0"
        assert v2.system_content == "system-v1"
        assert v2.llm_config == {"temperature": 0.1}
        prompt_version_service.submit_version(db, v2.id, operator_id="creator")
        prompt_version_service.approve_version(db, v2.id, operator_id="reviewer")
        prompt_release_service.production_release(
            db,
            prompt.id,
            v2.id,
            ReleaseRequest(
                environment="production",
                released_by="publisher",
                approved_by="reviewer",
            ),
        )

        current = render_prompt(
            db,
            prompt_key=prompt.prompt_key,
            environment="production",
            user_question="当前风险如何？",
        )
        assert current.version == "1.1.0"
        assert "goal-v2" in current.messages[-1]["content"]

        prompt_release_service.rollback(
            db,
            prompt.id,
            RollbackRequest(
                environment="production",
                released_by="publisher",
                release_note="验收回滚",
            ),
        )
        rolled_back = render_prompt(
            db,
            prompt_key=prompt.prompt_key,
            environment="production",
            user_question="当前风险如何？",
        )
        assert rolled_back.version == "1.0.0"
        assert "goal-v1" in rolled_back.messages[-1]["content"]


def test_release_rejects_a_version_owned_by_another_prompt() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as db:
        prompt_a = prompt_service.create_prompt(
            db,
            PromptCreate(prompt_key="ioc.prompt.a", prompt_name="Prompt A"),
        )
        prompt_b = prompt_service.create_prompt(
            db,
            PromptCreate(prompt_key="ioc.prompt.b", prompt_name="Prompt B"),
        )
        version_a = prompt_version_service.create_version(
            db,
            prompt_a.id,
            VersionCreate(system_content="system-a"),
        )
        prompt_version_service.submit_version(db, version_a.id)
        prompt_version_service.approve_version(db, version_a.id)

        with pytest.raises(AppException):
            prompt_release_service.production_release(
                db,
                prompt_b.id,
                version_a.id,
                ReleaseRequest(environment="production"),
            )


def test_operation_reason_node_uses_managed_prompt_and_records_version(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    managed = PromptRenderResult(
        prompt_id=7,
        prompt_key="ioc.safety.analysis",
        prompt_name="设备安全分析",
        version="1.2.0",
        environment="production",
        messages=[
            {"role": "system", "content": "managed-system"},
            {"role": "user", "content": "managed-user"},
        ],
        variables={},
        langsmith_commit_hash="commit-120",
    )
    monkeypatch.setattr(
        analyze_reason_module,
        "get_rendered_prompt",
        lambda **_kwargs: managed,
        raising=False,
    )

    captured: dict[str, str | None] = {}

    def fake_chat(**kwargs) -> LlmResult:
        captured["system"] = kwargs.get("prompt_content")
        captured["user"] = kwargs.get("user_message")
        return LlmResult(
            content="托管 Prompt 已生效",
            model="test-model",
            prompt_tokens=2,
            completion_tokens=3,
            total_tokens=5,
            cost_ms=1,
            success=True,
        )

    monkeypatch.setattr(analyze_reason_module.llm_client, "chat", fake_chat)
    state = {
        "metrics": [{"metric_name": "高等级告警", "value": 2}],
        "abnormal_items": [{"type": "high_level_alarm", "severity": "high"}],
        "page_context": {"domain": "safety", "active_tab": "本质安全"},
        "raw_data": {"alarm": [{"level": "high"}]},
        "evidence": [{"source": "alarm_api"}],
        "errors": [],
        "llm_usages": [],
    }

    result = analyze_reason_module.analyze_reason_node(state)

    assert captured == {"system": "managed-system", "user": "managed-user"}
    assert result["prompt_facts"]["analyze_reason"] == {
        "prompt_key": "ioc.safety.analysis",
        "prompt_version": "1.2.0",
        "prompt_commit_hash": "commit-120",
        "prompt_environment": "production",
    }


def test_operation_graph_trace_receives_prompt_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prompt_metadata = {
        "prompt_key": "ioc.safety.analysis",
        "prompt_version": "1.2.0",
        "prompt_commit_hash": "commit-120",
        "prompt_environment": "production",
    }
    captured_metadata: dict = {}

    monkeypatch.setattr(
        operation_service,
        "get_prompt_metadata",
        lambda *_args, **_kwargs: prompt_metadata,
        raising=False,
    )

    def fake_config(**kwargs):
        captured_metadata.update(kwargs["metadata"])
        return {}

    monkeypatch.setattr(operation_service, "build_langsmith_config", fake_config)
    monkeypatch.setattr(
        operation_service.operation_graph,
        "invoke",
        lambda state, config: {
            **state,
            "final_answer": "ok",
            "errors": [],
        },
    )
    monkeypatch.setattr(
        operation_service,
        "save_analysis_result",
        lambda *_args, **_kwargs: SimpleNamespace(id=1),
    )

    operation_service.analyze_operation(
        OperationAnalyzeRequest(force_refresh=True),
        user_context={"user_id": "acceptance-user"},
        trace_id="trace-v2-metadata",
    )

    assert {
        key: captured_metadata[key]
        for key in prompt_metadata
    } == prompt_metadata


def test_langgraph_prompt_integration_opens_a_real_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_session = SimpleNamespace(closed=False)
    fake_session.close = lambda: setattr(fake_session, "closed", True)
    managed = PromptRenderResult(
        prompt_id=7,
        prompt_key="ioc.safety.analysis",
        prompt_name="设备安全分析",
        version="1.0.0",
        environment="production",
        messages=[{"role": "user", "content": "managed"}],
        variables={},
    )

    monkeypatch.setattr(
        langgraph_integration,
        "get_session_local",
        lambda: lambda: fake_session,
    )
    monkeypatch.setattr(
        langgraph_integration,
        "render_prompt",
        lambda **kwargs: managed if kwargs["db"] is fake_session else None,
    )

    result = langgraph_integration.get_rendered_prompt(
        prompt_key="ioc.safety.analysis",
    )

    assert result.version == "1.0.0"
    assert fake_session.closed is True


def test_prompt_test_evaluations_keep_the_real_test_run_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run = SimpleNamespace(
        raw_output='{"title":"风险","priority":"P1"}',
        structured_output={"title": "风险", "priority": "P1"},
        input_data={},
    )
    captured: list[dict] = []
    monkeypatch.setattr(
        prompt_evaluation_service.prompt_test_run_repo,
        "get_by_id",
        lambda _db, _run_id: run,
    )
    monkeypatch.setattr(
        prompt_evaluation_service.prompt_evaluation_repo,
        "batch_create",
        lambda _db, items: captured.extend(items) or [],
    )

    prompt_evaluation_service.run_deterministic_evaluations(None, test_run_id=42)

    assert captured
    assert {item["test_run_id"] for item in captured} == {42}


def test_evaluation_center_persists_violations_as_json_arrays(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    monkeypatch.setattr(
        evaluation_module,
        "run_all_llm_judges",
        lambda **_kwargs: [],
    )

    with Session(engine) as db:
        results = evaluation_module.evaluation_service.evaluate(
            db,
            EvaluateRequest(
                trace_id="trace-eval-001",
                prompt_key="ioc.safety.analysis",
                prompt_version="1.0.0",
                input="请输出风险",
                output='{"title":"风险","priority":"P1"}',
            ),
        )

    assert len(results) == 5
    assert all(isinstance(item.violations, list) for item in results)
