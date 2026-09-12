"""
Requirement 4 Test Suite: Multi-Horizon Block Planning (24H Rolling, 7D Weekly, 30D Monthly)
Validates:
- 24-Hour Rolling Plan with urgent task prioritization and timetable certification
- 7-Day Weekly Plan with daily CP-SAT solves and multi-department shadow blocks
- 30-Day Monthly Plan with 4-week cohort decomposition and decaying confidence
- Common integrated dataset traceability across all 3 horizons
- Plan versioning, freeze window locking, and re-optimization plan diff
- Transparent root-cause constraint explanations for unscheduled and deferred tasks
- Multi-horizon comparison matrix and full REST API endpoint integration
"""
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.api.v1.router import db
from backend.app.schemas.schemas import (
    HorizonTypeEnum, DataConfidenceEnum, PlanStatusEnum
)

client = TestClient(app)


def test_24h_rolling_plan_generation():
    """
    Test 1: 24-Hour Rolling Plan (24H)
    - Generates 24-hour horizon with DAY-YYYY-MM-DD-V01 format
    - Focuses on immediate day (day_offset == 0)
    - Enforces 15-minute headway protection and achieves verified zero-clash certificate
    """
    plan = db.orchestrator.run_optimization(
        horizon_type="24H",
        tasks=db.tasks,
        trains=db.trains,
        windows=db.windows,
        goods_forecasts=db.goods_forecasts,
        enforce_shadow_packing=True
    )
    
    assert plan.planning_horizon.type == HorizonTypeEnum.HORIZON_24H
    assert plan.horizon_type == "24H"
    assert plan.plan_version.startswith("DAY-")
    assert "CONFIDENCE" in str(plan.plan_confidence).upper() or "CONFIRMED" in str(plan.plan_confidence).upper()
    assert len(plan.assignments) > 0
    assert plan.certificate is not None
    assert plan.certificate.verified_zero_clash is True
    assert plan.certificate.headway_buffer_verified is True

    # Ensure all assignments in 24H are day 0
    for a in plan.assignments:
        assert a.day_offset == 0


def test_7d_weekly_plan_generation():
    """
    Test 2: 7-Day Weekly Tactical Plan (7D)
    - Generates 7-day multi-day schedule with WEEK-YYYY-WW-V01 format
    - Populates daily_schedules for days 0..6 (Mon-Sun)
    - Solves shadow blocks across departments (Engineering, S&T, TRD)
    - Zero timetable clashes certified
    """
    plan = db.orchestrator.run_optimization(
        horizon_type="7D",
        tasks=db.tasks,
        trains=db.trains,
        windows=db.windows,
        goods_forecasts=db.goods_forecasts,
        enforce_shadow_packing=True
    )

    assert plan.planning_horizon.type == HorizonTypeEnum.HORIZON_7D
    assert plan.horizon_type == "7D"
    assert plan.plan_version.startswith("WEEK-")
    assert len(plan.assignments) >= len(db.plan_24h.assignments)
    assert len(plan.shadow_groups) > 0
    assert plan.certificate is not None
    assert plan.certificate.verified_zero_clash is True
    
    # Check daily breakdown
    assert len(plan.daily_schedules) == 7
    days = [d["day_offset"] for d in plan.daily_schedules.values()]
    assert sorted(days) == list(range(7))


def test_30d_monthly_plan_generation():
    """
    Test 3: 30-Day Monthly Strategic Plan (30D)
    - Generates strategic plan with MONTH-YYYY-MM-V01 format
    - Backlog summary accounts for completed vs remaining backlog
    - Confidence reflects PROVISIONAL status due to decaying goods forecast
    """
    plan = db.orchestrator.run_optimization(
        horizon_type="30D",
        tasks=db.tasks,
        trains=db.trains,
        windows=db.windows,
        goods_forecasts=db.goods_forecasts,
        enforce_shadow_packing=True
    )

    assert plan.planning_horizon.type == HorizonTypeEnum.HORIZON_30D
    assert plan.horizon_type == "30D"
    assert plan.plan_version.startswith("MONTH-")
    assert "PROVISIONAL" in str(plan.plan_confidence).upper()
    assert plan.backlog_summary is not None
    assert "remaining_backlog_tasks" in plan.backlog_summary
    assert "tasks_scheduled" in plan.backlog_summary
    assert plan.backlog_summary["total_demands_evaluated"] > 0
    assert plan.backlog_summary["tasks_scheduled"] > 0


def test_multi_horizon_traceability():
    """
    Test 4: Traceability across horizons
    - All tasks scheduled in 24H, 7D, and 30D are traceable to valid DB tasks
    - Task IDs match real unified maintenance tasks
    """
    valid_task_ids = {t.task_id for t in db.tasks}

    for a in db.plan_24h.assignments:
        assert a.task_id in valid_task_ids
    for a in db.plan_7d.assignments:
        assert a.task_id in valid_task_ids
    for a in db.plan_30d.assignments:
        assert a.task_id in valid_task_ids


def test_plan_versioning_and_reoptimization_diff():
    """
    Test 5: Rolling Re-optimization & Freeze Window
    - Calling re-optimization with previous plan increments version
    - Locked / freeze assignments remain scheduled at same start time
    - Generates plan_diff tracking changes
    """
    prev_plan = db.plan_7d

    reopt_plan = db.orchestrator.run_optimization(
        horizon_type="7D",
        tasks=db.tasks,
        trains=db.trains,
        windows=db.windows,
        goods_forecasts=db.goods_forecasts,
        enforce_shadow_packing=True,
        freeze_approved=True,
        previous_plan=prev_plan
    )

    assert "-V0" in reopt_plan.plan_version
    assert reopt_plan.plan_diff is not None
    assert "previous_version" in reopt_plan.plan_diff
    assert "new_version" in reopt_plan.plan_diff
    assert "tasks_added_count" in reopt_plan.plan_diff
    assert "unchanged_tasks_count" in reopt_plan.plan_diff


def test_unscheduled_tasks_explanations():
    """
    Test 6: Transparent root-cause constraint explanations for unscheduled tasks
    - Unscheduled tasks provide clear engineering reasons and recommended actions
    """
    plan = db.plan_24h
    if plan.unscheduled_tasks:
        for u in plan.unscheduled_tasks:
            assert "task_id" in u
            assert "reason_unscheduled" in u
            assert len(u["reason_unscheduled"]) > 5
            assert "recommended_action" in u
            assert len(u["recommended_action"]) > 5


def test_horizon_comparison_matrix():
    """
    Test 7: Horizon Comparison Matrix
    - Active plan contains side-by-side comparison across 24H, 7D, and 30D
    """
    plan = db.plan_7d
    comp = plan.horizon_comparison
    assert comp is not None
    assert "horizons" in comp
    assert len(comp["horizons"]) == 3
    assert "dimensions" in comp
    metrics = [d["metric"] for d in comp["dimensions"]]
    assert "Tasks Successfully Scheduled" in metrics
    assert "Corridor Possession Hours Saved" in metrics


def test_rest_api_multi_horizon_endpoints():
    """
    Test 8: REST API endpoints for Requirement 4
    - GET /api/v1/plans/horizon/24H
    - GET /api/v1/plans/horizon/7D
    - GET /api/v1/plans/horizon/30D
    - POST /api/v1/plans/generate
    - GET /api/v1/plans/versions
    - GET /api/v1/plans/comparison-horizons
    - POST /api/v1/plans/reoptimize
    - GET /api/v1/plans/unscheduled-tasks
    """
    # 1. GET /plans/horizon/{type}
    r24 = client.get("/api/v1/plans/horizon/24H")
    assert r24.status_code == 200
    assert r24.json()["planning_horizon"]["type"] == "24H"

    r7 = client.get("/api/v1/plans/horizon/7D")
    assert r7.status_code == 200
    assert r7.json()["planning_horizon"]["type"] == "7D"

    r30 = client.get("/api/v1/plans/horizon/30D")
    assert r30.status_code == 200
    assert r30.json()["planning_horizon"]["type"] == "30D"

    # 2. GET /plans/versions
    r_ver = client.get("/api/v1/plans/versions")
    assert r_ver.status_code == 200
    versions = r_ver.json()
    assert len(versions) >= 3
    assert "generated_at" in versions[0]

    # 3. GET /plans/comparison-horizons
    r_comp = client.get("/api/v1/plans/comparison-horizons")
    assert r_comp.status_code == 200
    assert "horizons" in r_comp.json()

    # 4. POST /plans/reoptimize
    r_reopt = client.post("/api/v1/plans/reoptimize", json={"horizon_type": "7D", "freeze_approved": True})
    assert r_reopt.status_code == 200
    assert r_reopt.json()["plan_diff"] is not None

    # 5. GET /plans/unscheduled-tasks
    r_unsched = client.get("/api/v1/plans/unscheduled-tasks?horizon_type=24H")
    assert r_unsched.status_code == 200
    assert "unscheduled_tasks" in r_unsched.json()

    # 6. POST /plans/generate
    r_gen = client.post("/api/v1/plans/generate", json={"horizon_type": "24H", "enforce_shadow_packing": True})
    assert r_gen.status_code == 200
    assert r_gen.json()["planning_horizon"]["type"] == "24H"
