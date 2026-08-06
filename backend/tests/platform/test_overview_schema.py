from app.platform.schemas.overview_schema import OverviewMetrics, PlatformOverviewResponse


def test_overview_response_accepts_zero_metrics_and_empty_sessions() -> None:
    result = PlatformOverviewResponse(
        metrics=OverviewMetrics(
            today_requests=0,
            running_tasks=0,
            pending_messages=0,
            failed_tasks=0,
            total_tokens=0,
            agent_success_rate=0,
            average_response_ms=0,
        ),
        recent_sessions=[],
    )

    assert result.metrics.total_tokens == 0
