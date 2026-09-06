"""
Rail-BDMS: Comprehensive Unit & Integration Test Suite
Validates Ingestion, Identity Resolution, Priority Analytics, Shadow Packing, CP-SAT Solver & Certifier.
"""
import pytest
from datetime import datetime, timezone

from backend.app.schemas.schemas import (
    CanonicalAsset, MaintenanceTask, TrainMovement, CorridorWindow,
    RawAssetDemand, DepartmentEnum, SourceSystemEnum, AssetTypeEnum,
    LineOrRoadEnum, SafetyClassEnum, MachineTypeEnum, TrainTypeEnum
)
from backend.app.services.ingestion.mock_data import (
    generate_canonical_assets, generate_maintenance_tasks,
    generate_train_movements, generate_corridor_windows,
    generate_raw_demands_for_reconciliation
)
from backend.app.services.identity.resolver import AssetIdentityResolver
from backend.app.services.analytics.priority_engine import PriorityAnalyticsEngine
from backend.app.services.optimizer.compatibility import ShadowBlockCompatibilityEngine
from backend.app.services.optimizer.cpsat_scheduler import CPSATScheduler
from backend.app.services.optimizer.certifier import (
    TimetableProtectionCertifier, TimetableViolationException
)
from backend.app.services.optimizer.horizon_orchestrator import RollingHorizonOrchestrator

@pytest.fixture
def assets():
    return generate_canonical_assets()

@pytest.fixture
def tasks(assets):
    return generate_maintenance_tasks(assets)

@pytest.fixture
def trains():
    return generate_train_movements()

@pytest.fixture
def windows():
    return generate_corridor_windows()

# --- 1. Test Asset Identity Resolution Engine ---
def test_identity_resolution_tiers(assets):
    resolver = AssetIdentityResolver(assets)
    
    # Tier 1: Exact Match
    exact_demand = RawAssetDemand(
        source_system=SourceSystemEnum.TMS,
        source_asset_id=assets[0].source_asset_id,
        raw_reference=assets[0].source_asset_id,
        department=assets[0].department,
        section_id=assets[0].section_id,
        line_or_road=assets[0].line_or_road
    )
    res1 = resolver.resolve_demand(exact_demand)
    assert res1.confidence_score == 1.0
    assert res1.matched_tier == "TIER_1_EXACT"
    assert not res1.requires_human_reconciliation

    # Tier 3: Chainage Overlap >= 90%
    target = assets[1]
    chainage_demand = RawAssetDemand(
        source_system=SourceSystemEnum.TMS,
        source_asset_id="CUSTOM_PWAY_DEMAND",
        raw_reference="km 8.0/9.0",
        department=DepartmentEnum.ENGINEERING,
        section_id=target.section_id,
        line_or_road=target.line_or_road,
        chainage_from=target.chainage_from + 0.005,
        chainage_to=target.chainage_to - 0.005
    )
    res3 = resolver.resolve_demand(chainage_demand)
    assert res3.confidence_score >= 0.90
    assert res3.matched_tier == "TIER_3_CHAINAGE"

    # Ambiguous Demands -> Routed to Human Queue
    ambiguous_demand = RawAssetDemand(
        source_system=SourceSystemEnum.SMMS,
        source_asset_id="UNKNOWN_YARD_POINT",
        raw_reference="Unknown point near yard switch",
        department=DepartmentEnum.S_AND_T,
        section_id="NON_EXISTENT_SECTION",
        line_or_road=LineOrRoadEnum.YARD_LINE
    )
    res_amb = resolver.resolve_demand(ambiguous_demand)
    assert res_amb.confidence_score < 0.85
    assert res_amb.requires_human_reconciliation is True
    assert res_amb.matched_tier == "UNRESOLVED"

# --- 2. Test Explainable Priority Analytics Engine ---
def test_priority_scoring_and_explanation(assets, tasks):
    engine = PriorityAnalyticsEngine(assets)
    evaluated_tasks = engine.batch_evaluate(tasks)
    
    # Check that all tasks have valid scores between 0 and 100
    for t in evaluated_tasks:
        assert 0.0 <= t.priority_score <= 100.0
        assert 0.0 <= t.criticality_score <= 100.0
        assert 0.0 <= t.urgency_score <= 100.0
        assert t.priority_explanation is not None
        assert "Priority" in t.priority_explanation
        assert t.predicted_p95_duration_min >= t.predicted_p80_duration_min >= t.predicted_p50_duration_min

    # Safety critical IMR task must score higher than a routine inspection
    imr_tasks = [t for t in evaluated_tasks if "IMR" in t.task_type]
    routine_tasks = [t for t in evaluated_tasks if t.safety_class == SafetyClassEnum.ROUTINE]
    
    if imr_tasks and routine_tasks:
        assert imr_tasks[0].priority_score > routine_tasks[0].priority_score

# --- 3. Test Shadow Block Compatibility Graph ---
def test_shadow_block_compatibility(assets, tasks):
    compat_engine = ShadowBlockCompatibilityEngine(assets)
    groups = compat_engine.extract_shadow_block_groups(tasks)
    
    # Verify multi-department clustering
    for g in groups:
        assert len(g.task_ids) >= 2
        assert len(g.participating_departments) >= 2
        assert g.corridor_time_saved_min > 0
        assert g.lead_department in [DepartmentEnum.ENGINEERING, DepartmentEnum.TRD, DepartmentEnum.S_AND_T]

# --- 4. Test Google OR-Tools CP-SAT Solver & Certifier ---
def test_cpsat_solver_and_certification(assets, tasks, trains, windows):
    engine = PriorityAnalyticsEngine(assets)
    eval_tasks = engine.batch_evaluate(tasks)
    
    orchestrator = RollingHorizonOrchestrator(assets)
    plan = orchestrator.run_optimization(
        horizon_type="WEEKLY",
        tasks=eval_tasks,
        trains=trains,
        windows=windows,
        enforce_shadow_packing=True,
        timeout_seconds=15
    )
    
    assert plan.solver_status in ("OPTIMAL", "FEASIBLE")
    assert len(plan.assignments) > 0
    assert plan.certificate is not None
    assert plan.certificate.verified_zero_clash is True
    assert len(plan.certificate.hash_sha256) == 64

# --- 5. Test Intentional Timetable Clash Detection in Certifier ---
def test_certifier_detects_clash_and_raises_exception(assets, tasks, trains):
    certifier = TimetableProtectionCertifier(headway_before_min=15, headway_after_min=15)
    
    # Create an artificial overlapping plan
    target_train = trains[0]
    bad_task = tasks[0]
    
    from backend.app.schemas.schemas import OptimizationPlan, ScheduledBlockAssignment
    clashing_assignment = ScheduledBlockAssignment(
        plan_id="BAD_TEST_PLAN",
        task_id=bad_task.task_id,
        task_description="Clashing task",
        department=bad_task.department,
        section_id=target_train.section_id,
        line_or_road=target_train.line_or_road,
        planned_start_min=target_train.entry_minute, # EXACT CLASH!
        planned_end_min=target_train.exit_minute + 30,
        planned_start_time=target_train.planned_entry,
        planned_end_time=target_train.planned_exit,
        duration_min=60,
        priority_score=90.0,
        required_machine_type=MachineTypeEnum.NONE,
        lead_department=bad_task.department
    )
    
    bad_plan = OptimizationPlan(
        plan_id="BAD_TEST_PLAN",
        horizon_type="WEEKLY",
        generated_at=datetime.now(timezone.utc).isoformat(),
        solver_status="FEASIBLE",
        solve_time_ms=10,
        assignments=[clashing_assignment]
    )
    
    with pytest.raises(TimetableViolationException):
        certifier.verify_and_certify(bad_plan, trains)
