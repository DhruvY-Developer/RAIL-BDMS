"""
Rail-BDMS: Multi-Source Operational & Maintenance Integration Layer Test Suite
Validates Requirement 1: TMS + SMMS + TDMS + COA + Timetable + Goods Forecast Integration.
Covers Sections A through P of the Acceptance Criteria.
"""
import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.schemas.schemas import (
    CanonicalAsset, SourceSystemEnum, DepartmentEnum, SafetyClassEnum,
    LineOrRoadEnum, TaskStatusEnum
)
from backend.app.schemas.integration import (
    UnifiedMaintenanceTask, COACorridorAvailability, IntegratedTimetablePath,
    GoodsTrainForecast, IntegrationSourceStatus, DataQualityReport, TaskLineageRecord,
    CrossSystemCorrelationScenario
)
from backend.app.services.ingestion.mock_data import generate_canonical_assets
from backend.app.services.ingestion.tms_adapter import TMSAdapter
from backend.app.services.ingestion.smms_adapter import SMMSAdapter
from backend.app.services.ingestion.tdms_adapter import TDMSAdapter
from backend.app.services.ingestion.coa_adapter import COAAdapter
from backend.app.services.ingestion.timetable_adapter import TimetableAdapter
from backend.app.services.ingestion.goods_forecast_adapter import GoodsForecastAdapter
from backend.app.services.ingestion.unified_service import UnifiedDataIntegrationService
from backend.app.services.optimizer.cpsat_scheduler import CPSATScheduler

@pytest.fixture
def client():
    return TestClient(app)

@pytest.fixture
def canonical_assets():
    return generate_canonical_assets()

@pytest.fixture
def integration_service(canonical_assets):
    return UnifiedDataIntegrationService(canonical_assets)

# ----------------- A. SOURCE INTEGRATION: TMS -----------------
def test_tms_adapter_ingestion(canonical_assets):
    adapter = TMSAdapter(canonical_assets)
    records = adapter.sync()
    assert len(records) > 0

    # Verify every record is a UnifiedMaintenanceTask
    for r in records:
        assert isinstance(r, UnifiedMaintenanceTask)
        assert r.source_system == SourceSystemEnum.TMS
        assert r.department == DepartmentEnum.ENGINEERING
        assert r.source_task_id.startswith("TMS-WO-")
        assert r.unified_task_id.startswith("UMT-TMS-")
        assert r.estimated_duration_min > 0
        assert r.due_at is not None
        assert r.last_sync is not None

    # Verify specific defect and overdue information ingestion
    imr_task = next((t for t in records if "IMR" in t.task_type), None)
    assert imr_task is not None
    assert imr_task.defect_id is not None
    assert imr_task.defect_description is not None
    assert imr_task.safety_class in (SafetyClassEnum.SAFETY_CRITICAL, SafetyClassEnum.OPERATIONAL_DEFECT)

    # Verify unmapped asset candidate is preserved and flagged (Checklist F & Section 9)
    unresolved_task = next((t for t in records if t.source_task_id == "TMS-WO-9991"), None)
    assert unresolved_task is not None
    assert unresolved_task.asset_id == "UNRESOLVED"
    assert unresolved_task.status == TaskStatusEnum.UNRESOLVED_IDENTITY
    assert unresolved_task.validation_status == "NEEDS_REVIEW"

# ----------------- A. SOURCE INTEGRATION: SMMS -----------------
def test_smms_adapter_ingestion(canonical_assets):
    adapter = SMMSAdapter(canonical_assets)
    records = adapter.sync()
    assert len(records) > 0

    for r in records:
        assert isinstance(r, UnifiedMaintenanceTask)
        assert r.source_system == SourceSystemEnum.SMMS
        assert r.department == DepartmentEnum.S_AND_T
        assert r.source_task_id.startswith("SMMS-WO-")
        assert r.unified_task_id.startswith("UMT-SMMS-")
        assert r.requires_signal_disconnection is True  # S&T disconnect mandatory
        assert r.defect_id is not None
        assert r.due_at is not None

    # Check Point Machine Overhaul anchor
    pt_task = next((t for t in records if "POINT_MACHINE" in t.task_type), None)
    assert pt_task is not None
    assert pt_task.estimated_duration_min >= 60

# ----------------- A. SOURCE INTEGRATION: TDMS -----------------
def test_tdms_adapter_ingestion(canonical_assets):
    adapter = TDMSAdapter(canonical_assets)
    records = adapter.sync()
    assert len(records) > 0

    for r in records:
        assert isinstance(r, UnifiedMaintenanceTask)
        assert r.source_system == SourceSystemEnum.TDMS
        assert r.department == DepartmentEnum.TRD
        assert r.source_task_id.startswith("TDMS-WO-")
        assert r.unified_task_id.startswith("UMT-TDMS-")
        assert r.requires_ohe_isolation is True  # TRD 25kV power isolation mandatory
        assert r.defect_id is not None

    # Check Cantilever adjustment task
    ohe_task = next((t for t in records if "CANTILEVER" in t.task_type), None)
    assert ohe_task is not None
    assert ohe_task.estimated_duration_min > 0

# ----------------- B. COA / CORRIDOR AVAILABILITY -----------------
def test_coa_adapter_corridor_availability():
    adapter = COAAdapter()
    windows = adapter.sync()
    assert len(windows) > 0

    for w in windows:
        assert isinstance(w, COACorridorAvailability)
        assert w.source_system == SourceSystemEnum.COA
        assert w.coa_block_id.startswith("COA-BLK-")
        assert w.start_minute < w.end_minute
        assert w.available_duration_min == (w.end_minute - w.start_minute)
        assert w.line_or_road in (LineOrRoadEnum.UP, LineOrRoadEnum.DOWN)
        assert w.availability_status == "CONFIRMED"
        assert w.last_sync is not None

    # Verify night mega possession on TKD-FDB DOWN Line
    night_mega = next((w for w in windows if w.section_id == "TKD-FDB" and w.line_or_road == LineOrRoadEnum.DOWN and w.start_minute == 30), None)
    assert night_mega is not None
    assert night_mega.available_duration_min == 240  # 4 hours
    assert "OHE_ISOLATION_PERMITTED" in night_mega.operational_restrictions

# ----------------- C. TRAIN TIMETABLE INTEGRATION -----------------
def test_timetable_adapter_train_paths():
    adapter = TimetableAdapter()
    train_paths = adapter.sync()
    assert len(train_paths) > 0

    for tr in train_paths:
        assert isinstance(tr, IntegratedTimetablePath)
        assert tr.source_system == "TIMETABLE_WTT"
        assert tr.train_number is not None
        assert tr.section_id is not None
        assert tr.entry_minute < tr.exit_minute
        assert tr.headway_buffer_min == 15
        assert tr.min_clearance_before_min >= 15
        assert tr.min_clearance_after_min >= 15
        assert tr.priority_class in (1, 2, 3, 4)

# ----------------- D. GOODS-TRAIN FORECAST INTEGRATION -----------------
def test_goods_forecast_adapter():
    adapter = GoodsForecastAdapter()
    forecasts = adapter.sync()
    assert len(forecasts) > 0

    for fc in forecasts:
        assert isinstance(fc, GoodsTrainForecast)
        assert fc.forecast_id.startswith("FOIS-FCST-")
        assert fc.time_window is not None
        assert fc.expected_goods_train_count >= 0
        assert 0.0 <= fc.confidence_pct <= 100.0
        assert fc.is_simulated is True  # Honest prototype labeling (Checklist D & M)
        assert fc.source == "Control Office / Goods Freight Forecast (FOIS)"
        assert len(fc.expected_train_paths) >= 0

# ----------------- E & F. UNIFIED DATA SERVICE & ASSET RESOLUTION -----------------
def test_unified_service_orchestration(integration_service):
    # Check that all 6 feeds are populated
    assert len(integration_service.tasks) > 0
    assert len(integration_service.windows) > 0
    assert len(integration_service.trains) > 0
    assert len(integration_service.goods_forecasts) > 0

    # Verify task distribution across 3 maintenance departments
    tms_count = len([t for t in integration_service.tasks if t.source_system == SourceSystemEnum.TMS])
    smms_count = len([t for t in integration_service.tasks if t.source_system == SourceSystemEnum.SMMS])
    tdms_count = len([t for t in integration_service.tasks if t.source_system == SourceSystemEnum.TDMS])
    assert tms_count > 0
    assert smms_count > 0
    assert tdms_count > 0

    # Source status report
    statuses = integration_service.get_sources_status()
    for src in ["TMS", "SMMS", "TDMS", "COA", "TIMETABLE", "GOODS_FORECAST"]:
        assert src in statuses
        assert statuses[src].total_records > 0
        assert "Simulated" in statuses[src].connection_mode.value or "Demo" in statuses[src].connection_mode.value

# ----------------- G. DATA QUALITY AND VALIDATION -----------------
def test_data_quality_report(integration_service):
    report = integration_service.get_data_quality_report()
    assert isinstance(report, DataQualityReport)
    assert report.total_ingested > 0
    assert report.total_valid > 0
    assert report.overall_health_pct > 80.0
    assert len(report.validation_rules_enforced) >= 7

    # Ensure unmapped tasks are caught in recent validation notices
    flagged_unresolved = [n for n in report.recent_validation_notices if "TMS-WO-9991" in str(n.get("task_id", ""))]
    assert len(flagged_unresolved) > 0

# ----------------- H. DATA LINEAGE TRACEABILITY -----------------
def test_task_lineage_extraction(integration_service):
    lineage = integration_service.get_task_lineage("TMS-WO-1842")
    assert lineage is not None
    assert isinstance(lineage, TaskLineageRecord)
    assert lineage.source_system == "TMS"
    assert lineage.source_task_id == "TMS-WO-1842"
    assert lineage.unified_task_id.startswith("UMT-")
    assert lineage.section_id == "TKD-FDB"
    assert lineage.line_or_road == "DOWN"
    assert lineage.coa_corridor_window is not None
    assert lineage.goods_forecast_context is not None
    assert lineage.timetable_safety_status == "HEADWAY_PROTECTED_0_CLASH"

# ----------------- K. CROSS-SYSTEM CORRELATION SCENARIO -----------------
def test_cross_system_correlation_scenario(integration_service):
    scenario = integration_service.get_correlation_scenario()
    assert isinstance(scenario, CrossSystemCorrelationScenario)
    assert scenario.section_id == "TKD-FDB"
    assert scenario.line_or_road == "DOWN"
    assert scenario.tms_task.source_system.value == "TMS"
    assert scenario.smms_task.source_system.value == "SMMS"
    assert scenario.tdms_task.source_system.value == "TDMS"
    assert scenario.coa_window.source_system.value == "COA"
    assert len(scenario.timetable_trains) > 0
    assert scenario.goods_forecast.corridor_id in ("NZM-PWL", "TKD-FDB")

# ----------------- J & 13. PLANNER INGESTION (NO REGRESSION) -----------------
def test_existing_planner_consumes_unified_data(integration_service, canonical_assets):
    scheduler = CPSATScheduler(canonical_assets)
    # CP-SAT solve directly on unified dataset
    plan = scheduler.solve(
        tasks=integration_service.tasks,
        trains=integration_service.trains,
        windows=integration_service.windows,
        horizon_minutes=1440,
        enforce_shadow_packing=True,
        timeout_seconds=15
    )
    assert plan is not None
    assert plan.solver_status in ("OPTIMAL", "FEASIBLE")
    assert len(plan.assignments) > 0
    assert plan.kpis["timetable_conflicts"] == 0

# ----------------- API ENDPOINTS VERIFICATION -----------------
def test_api_integration_endpoints(client):
    # 1. GET /api/v1/integration/status
    res_status = client.get("/api/v1/integration/status")
    assert res_status.status_code == 200
    status_data = res_status.json()
    assert "TMS" in status_data
    assert "SMMS" in status_data
    assert "TDMS" in status_data
    assert "COA" in status_data
    assert "TIMETABLE" in status_data
    assert "GOODS_FORECAST" in status_data

    # 2. GET /api/v1/integration/quality
    res_qual = client.get("/api/v1/integration/quality")
    assert res_qual.status_code == 200
    qual_data = res_qual.json()
    assert qual_data["overall_health_pct"] > 80.0
    assert len(qual_data["validation_rules_enforced"]) >= 7

    # 3. GET /api/v1/integration/goods-forecast
    res_fcst = client.get("/api/v1/integration/goods-forecast")
    assert res_fcst.status_code == 200
    fcsts = res_fcst.json()
    assert len(fcsts) > 0
    assert fcsts[0]["expected_goods_train_count"] >= 0

    # 4. GET /api/v1/integration/lineage/{task_id}
    res_lin = client.get("/api/v1/integration/lineage/TMS-WO-1842")
    assert res_lin.status_code == 200
    lin_data = res_lin.json()
    assert lin_data["source_system"] == "TMS"
    assert lin_data["source_task_id"] == "TMS-WO-1842"
    assert "coa_corridor_window" in lin_data

    # 5. GET /api/v1/integration/correlation-scenario
    res_corr = client.get("/api/v1/integration/correlation-scenario")
    assert res_corr.status_code == 200
    corr_data = res_corr.json()
    assert corr_data["section_id"] == "TKD-FDB"
    assert "tms_task" in corr_data
    assert "smms_task" in corr_data
    assert "tdms_task" in corr_data

    # 6. POST /api/v1/integration/sync
    res_sync = client.post("/api/v1/integration/sync")
    assert res_sync.status_code == 200
    assert res_sync.json()["status"] == "SUCCESS"
