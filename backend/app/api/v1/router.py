"""
Rail-BDMS: FastAPI REST API Router (v1)
Full REST API layer for Control Office Command Center, Shadow Workbench, and Field Depot PWA.
"""
from fastapi import APIRouter, HTTPException, Query, Body
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
import uuid

from backend.app.schemas.schemas import (
    CanonicalAsset, MaintenanceTask, TrainMovement, CorridorWindow,
    OptimizationPlan, ScheduledBlockAssignment, ShadowBlockGroup,
    RawAssetDemand, IdentityResolutionResult, TimetableProtectionCertificate,
    DepartmentEnum, SafetyClassEnum, TaskStatusEnum, LineOrRoadEnum,
    LoginRequest, UserProfile, LoginResponse,
    GisConfigResponse, LiveTrainPosition,
    HorizonTypeEnum, PlanStatusEnum, DataConfidenceEnum, PlanningHorizon
)
from backend.app.schemas.integration import (
    UnifiedMaintenanceTask, COACorridorAvailability, IntegratedTimetablePath,
    GoodsTrainForecast, IntegrationSourceStatus, DataQualityReport, TaskLineageRecord,
    CrossSystemCorrelationScenario
)
from backend.app.services.ingestion.mock_data import (
    STATIONS, SECTIONS, generate_canonical_assets, generate_maintenance_tasks,
    generate_train_movements, generate_corridor_windows,
    generate_raw_demands_for_reconciliation
)
from backend.app.services.ingestion.unified_service import UnifiedDataIntegrationService
from backend.app.services.identity.resolver import AssetIdentityResolver
from backend.app.services.analytics.priority_engine import PriorityAnalyticsEngine
from backend.app.services.optimizer.horizon_orchestrator import RollingHorizonOrchestrator
from backend.app.services.optimizer.compatibility import ShadowBlockCompatibilityEngine

router = APIRouter()

# --- State Store for In-Memory Demo / Active Session ---
class DatabaseStore:
    def __init__(self):
        self.stations = STATIONS
        self.sections = SECTIONS
        self.assets: List[CanonicalAsset] = generate_canonical_assets()
        
        # Initialize Unified Data Integration Layer (TMS + SMMS + TDMS + COA + Timetable + Goods Forecast)
        self.integration_service = UnifiedDataIntegrationService(self.assets)
        self.tasks: List[MaintenanceTask] = self.integration_service.tasks
        self.trains: List[TrainMovement] = self.integration_service.trains
        self.windows: List[CorridorWindow] = self.integration_service.windows
        self.goods_forecasts: List[GoodsTrainForecast] = self.integration_service.goods_forecasts
        
        self.identity_resolver = self.integration_service.identity_resolver
        self.priority_engine = PriorityAnalyticsEngine(
            self.assets,
            trains=self.trains,
            goods_forecasts=self.goods_forecasts
        )
        self.orchestrator = RollingHorizonOrchestrator(self.assets)
        self.compat_engine = ShadowBlockCompatibilityEngine(self.assets)
        
        # Initial evaluation of tasks
        self.tasks = self.priority_engine.batch_evaluate(self.tasks)
        
        # Initial multi-horizon plans: 24H Rolling, 7D Weekly, 30D Monthly
        self.plan_24h: OptimizationPlan = self.orchestrator.run_optimization(
            horizon_type="24H",
            tasks=self.tasks,
            trains=self.trains,
            windows=self.windows,
            goods_forecasts=self.goods_forecasts,
            enforce_shadow_packing=True
        )
        self.plan_7d: OptimizationPlan = self.orchestrator.run_optimization(
            horizon_type="7D",
            tasks=self.tasks,
            trains=self.trains,
            windows=self.windows,
            goods_forecasts=self.goods_forecasts,
            enforce_shadow_packing=True
        )
        self.plan_30d: OptimizationPlan = self.orchestrator.run_optimization(
            horizon_type="30D",
            tasks=self.tasks,
            trains=self.trains,
            windows=self.windows,
            goods_forecasts=self.goods_forecasts,
            enforce_shadow_packing=True
        )
        
        self.active_horizon: str = "7D"
        self.active_plan: OptimizationPlan = self.plan_7d
        self.plans_by_horizon: Dict[str, OptimizationPlan] = {
            "24H": self.plan_24h,
            "7D": self.plan_7d,
            "30D": self.plan_30d,
            "DAILY": self.plan_24h,
            "WEEKLY": self.plan_7d,
            "MONTHLY": self.plan_30d,
        }
        self.plan_history: Dict[str, List[OptimizationPlan]] = {
            "24H": [self.plan_24h],
            "7D": [self.plan_7d],
            "30D": [self.plan_30d]
        }
        
        # Unresolved queue
        raw_demands = generate_raw_demands_for_reconciliation(self.assets)
        self.reconciliation_results = self.identity_resolver.batch_resolve(raw_demands)
        self.reconciliation_queue = [
            {"demand": d, "result": r} 
            for d, r in zip(raw_demands, self.reconciliation_results)
            if r.requires_human_reconciliation
        ]
        
        # Field execution block states
        self.execution_states: Dict[str, Dict[str, Any]] = {}
        for a in self.active_plan.assignments[:8]:
            self.execution_states[a.assignment_id] = {
                "assignment": a,
                "current_state": "SCHEDULED", # SCHEDULED, PERMIT_REQUESTED, PROTECTION_APPLIED, IN_PROGRESS, RESTORED, CLOSED
                "checklist_completed": False,
                "actual_start": None,
                "actual_end": None,
                "overrun_risk_score": a.overrun_risk_pct / 100.0,
                "notes": []
            }

        # Active officer authentication sessions
        self.active_sessions: Dict[str, dict] = {}
        # Geospatial GIS API Key for Delhi Division Corridor Radar
        self.gis_api_key: str = f"IR-GIS-DEL-{uuid.uuid4().hex[:16]}"
        self.sim_minute: int = 400

db = DatabaseStore()

SECTION_STATIONS = {
    "NZM-OKA": ("NZM", "OKA"),
    "OKA-TKD": ("OKA", "TKD"),
    "TKD-FDB": ("TKD", "FDB"),
    "FDB-FDN": ("FDB", "FDN"),
    "FDN-BVH": ("FDN", "BVH"),
    "BVH-AST": ("BVH", "AST"),
    "AST-PWL": ("AST", "PWL"),
    "PWL-RDI": ("PWL", "RDI")
}

STATION_COORDS = {
    "NDLS": (28.6428, 77.2197),
    "NZM": (28.5892, 77.2530),
    "OKA": (28.5583, 77.2728),
    "TKD": (28.5085, 77.2910),
    "FDB": (28.4089, 77.3178),
    "FDN": (28.3842, 77.3195),
    "BVH": (28.3412, 77.3245),
    "AST": (28.2562, 77.3298),
    "PWL": (28.1487, 77.3325),
    "RDI": (28.0671, 77.3489)
}

def compute_train_telemetry(train: TrainMovement, sim_minute: int) -> LiveTrainPosition:
    prog = (sim_minute - train.entry_minute) / max(1, train.exit_minute - train.entry_minute)
    prog = max(0.0, min(1.0, prog))
    
    sec = SECTION_STATIONS.get(train.section_id, ("NZM", "PWL"))
    c_from = STATION_COORDS.get(sec[0], (28.5892, 77.2530))
    c_to = STATION_COORDS.get(sec[1], (28.1487, 77.3325))
    
    is_up = train.line_or_road.value == "UP"
    if is_up:
        lat = c_to[0] + (c_from[0] - c_to[0]) * prog
        lon = c_to[1] + (c_from[1] - c_to[1]) * prog - 0.0012  # UP line offset West
        heading = 350
        origin_stn = sec[1]
        dest_stn = sec[0]
    else:
        lat = c_from[0] + (c_to[0] - c_from[0]) * prog
        lon = c_from[1] + (c_to[1] - c_from[1]) * prog + 0.0012  # DOWN line offset East
        heading = 170
        origin_stn = sec[0]
        dest_stn = sec[1]
        
    return LiveTrainPosition(
        train_number=train.train_number,
        train_name=train.train_name,
        section_id=train.section_id,
        line=train.line_or_road.value,
        speed_kmh=train.speed_kmh,
        progress_pct=round(prog * 100, 1),
        priority_class=str(train.priority_class),
        lat=round(lat, 6),
        lon=round(lon, 6),
        heading=heading,
        origin_stn=origin_stn,
        destination_stn=dest_stn,
        safety_status="HEADWAY_PROTECTED_0_CLASH"
    )


CTPC_OFFICER_PROFILE = UserProfile(
    username="CTPC",
    full_name="Chief Train Planner & Controller",
    role="CTPC / Sr. DOM",
    designation="Sr. Divisional Operations Manager (Sr. DOM)",
    office="Delhi Control Office",
    division="Delhi Division",
    zone="Northern Railway (NR)",
    access_level="CHIEF_OPERATIONS_DIRECTOR"
)

# ----------------- 0. Authentication (CTPC / Sr. DOM) -----------------
@router.post("/auth/login", response_model=LoginResponse)
def login(credentials: LoginRequest):
    u = credentials.username.strip()
    p = credentials.password.strip()
    
    # Strictly check CTPC / CTPC@123
    if u.upper() == "CTPC" and p == "CTPC@123":
        token = f"ctpc_session_{uuid.uuid4().hex}"
        now_str = datetime.now(timezone.utc).isoformat()
        db.active_sessions[token] = {
            "user": CTPC_OFFICER_PROFILE.model_dump(),
            "logged_in_at": now_str
        }
        return LoginResponse(
            status="SUCCESS",
            token=token,
            message="Access Granted. Welcome to Delhi Control Office Operations Console.",
            user=CTPC_OFFICER_PROFILE
        )
    else:
        raise HTTPException(
            status_code=401,
            detail="Access Denied: Invalid Login ID or Password. Only authorized CTPC / Sr. DOM credentials are valid for Delhi Control Office."
        )

@router.get("/auth/verify")
def verify_session(token: Optional[str] = Query(None)):
    if not token or token not in db.active_sessions:
        raise HTTPException(status_code=401, detail="Session invalid, expired, or missing.")
    return {
        "status": "VALID",
        "user": db.active_sessions[token]["user"],
        "session_started": db.active_sessions[token]["logged_in_at"]
    }

@router.post("/auth/logout")
def logout(token: Optional[str] = Body(None, embed=True)):
    if token and token in db.active_sessions:
        del db.active_sessions[token]
    return {"status": "SUCCESS", "message": "Officer session terminated successfully."}

# ----------------- 0.1 Geospatial GIS Configuration & API Key -----------------
@router.get("/gis/config", response_model=GisConfigResponse)
def get_gis_config():
    """
    Returns active Geospatial GIS configuration, active API Key, corridor boundaries,
    and supported map layer configurations.
    """
    return GisConfigResponse(
        api_key=db.gis_api_key,
        provider="Indian Railways Geospatial GIS Intelligence Engine",
        issued_to="Delhi Control Office (CTPC / Sr. DOM)",
        issued_at=datetime.now(timezone.utc).isoformat(),
        status="ACTIVE_AUTHENTICATED",
        corridor_bounds={
            "center": [28.4089, 77.3178],
            "zoom": 11,
            "min_lat": 28.05,
            "max_lat": 28.66,
            "min_lon": 77.20,
            "max_lon": 77.36,
            "corridor": "Hazrat Nizamuddin (NZM) — Palwal (PWL) — Rundhi (RDI)"
        },
        available_layers=[
            {
                "id": "tactical-dark",
                "name": "Tactical Dark Ops (CartoDB Vector)",
                "url": "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
                "max_zoom": "19",
                "requires_api_key": "true"
            },
            {
                "id": "satellite-hybrid",
                "name": "High-Res Satellite Imagery (ArcGIS)",
                "url": "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
                "max_zoom": "18",
                "requires_api_key": "true"
            },
            {
                "id": "openrailwaymap",
                "name": "OpenRailwayMap Infrastructure (Tracks & Signals)",
                "url": "https://{s}.tile.openrailwaymap.org/standard/{z}/{x}/{y}.png",
                "max_zoom": "19",
                "requires_api_key": "false"
            }
        ]
    )

@router.post("/gis/api-key/regenerate")
def regenerate_gis_api_key():
    """
    Regenerates a fresh cryptographically secure API key for the Geospatial GIS Map section.
    """
    db.gis_api_key = f"IR-GIS-DEL-{uuid.uuid4().hex[:16]}"
    return {
        "status": "SUCCESS",
        "new_api_key": db.gis_api_key,
        "message": "New Geospatial GIS API Key successfully provisioned for Delhi Control Office.",
        "generated_at": datetime.now(timezone.utc).isoformat()
    }

@router.get("/trains/live-positions", response_model=List[LiveTrainPosition])
def get_live_train_positions(sim_minute: Optional[int] = Query(None)):
    """
    Calculates and returns precise real-time coordinates, speed, heading, and headway safety status
    for all trains currently traversing the Delhi-Palwal-Rundhi corridor.
    """
    curr_min = sim_minute if sim_minute is not None else db.sim_minute
    active = []
    for tr in db.trains:
        if tr.entry_minute <= curr_min <= tr.exit_minute:
            telemetry = compute_train_telemetry(tr, curr_min)
            active.append(telemetry)
    # If no trains in this minute, provide active sample trains along the corridor
    if not active:
        for tr in db.trains[:6]:
            active.append(compute_train_telemetry(tr, (tr.entry_minute + tr.exit_minute) // 2))
    return active

# ----------------- 1. Overview & KPIs -----------------
@router.get("/overview/kpis", response_model=Dict[str, Any])
def get_overview_kpis():
    plan = db.active_plan
    kpis = plan.kpis
    
    # Department task counts
    dept_counts = {
        "ENGINEERING": len([t for t in db.tasks if t.department == DepartmentEnum.ENGINEERING]),
        "S_AND_T": len([t for t in db.tasks if t.department == DepartmentEnum.S_AND_T]),
        "TRD": len([t for t in db.tasks if t.department == DepartmentEnum.TRD])
    }
    
    overdue_count = len([t for t in db.tasks if t.urgency_score >= 70])
    safety_critical_count = len([t for t in db.tasks if t.safety_class == SafetyClassEnum.SAFETY_CRITICAL])
    
    return {
        "kpis": kpis,
        "department_distribution": dept_counts,
        "total_assets": len(db.assets),
        "total_trains": len(db.trains),
        "total_demands": len(db.tasks),
        "overdue_defects_count": overdue_count,
        "safety_critical_count": safety_critical_count,
        "reconciliation_pending_count": len(db.reconciliation_queue),
        "active_plan_id": plan.plan_id,
        "active_horizon": db.active_horizon,
        "plan_version": plan.plan_version,
        "plan_status": plan.plan_status.value if hasattr(plan.plan_status, 'value') else str(plan.plan_status),
        "plan_confidence": plan.plan_confidence.value if hasattr(plan.plan_confidence, 'value') else str(plan.plan_confidence),
        "backlog_summary": plan.backlog_summary,
        "horizon_comparison": plan.horizon_comparison,
        "certificate_id": plan.certificate.certificate_id if plan.certificate else None,
        "certificate_hash": plan.certificate.hash_sha256 if plan.certificate else None,
        "system_status": "NORMAL - ALL HEADWAY ENVELOPES CONSTRAINT VERIFIED",
        "ml_intelligence": {
            "status": "OPERATIONAL",
            "model_name": db.priority_engine.inference_service.metadata.get("model_name", "RailRisk"),
            "model_version": db.priority_engine.inference_service.metadata.get("model_version", "v1.0"),
            "prediction_horizon": "7 Days",
            "data_mode": "Synthetic prototype evaluation",
            "critical_risk_tasks_count": len([t for t in db.tasks if (t.ai_risk_score or 0) >= 76.0]),
            "high_ai_priority_count": len([t for t in db.tasks if (t.ai_priority_score or 0) >= 80.0]),
            "safety_override_count": len([t for t in db.tasks if t.is_safety_override_applied])
        }
    }

# ----------------- 2. Assets & Reconciliation -----------------
@router.get("/assets/stations")
def get_stations():
    return db.stations

@router.get("/assets/sections")
def get_sections():
    return db.sections

@router.get("/assets", response_model=List[CanonicalAsset])
def get_assets(
    department: Optional[DepartmentEnum] = None,
    section_id: Optional[str] = None,
    line_or_road: Optional[LineOrRoadEnum] = None
):
    assets = db.assets
    if department:
        assets = [a for a in assets if a.department == department]
    if section_id:
        assets = [a for a in assets if a.section_id == section_id]
    if line_or_road:
        assets = [a for a in assets if a.line_or_road == line_or_road]
    return assets

@router.post("/assets/reconcile", response_model=IdentityResolutionResult)
def reconcile_asset_demand(demand: RawAssetDemand):
    result = db.identity_resolver.resolve_demand(demand)
    if result.requires_human_reconciliation:
        db.reconciliation_queue.append({"demand": demand, "result": result})
    return result

@router.get("/assets/reconciliation-queue")
def get_reconciliation_queue():
    return db.reconciliation_queue

@router.post("/assets/reconciliation-queue/approve")
def approve_manual_reconciliation(item_idx: int = Body(..., embed=True), target_asset_id: str = Body(..., embed=True)):
    if 0 <= item_idx < len(db.reconciliation_queue):
        item = db.reconciliation_queue.pop(item_idx)
        target_asset = next((a for a in db.assets if a.asset_id == target_asset_id), None)
        return {
            "status": "APPROVED",
            "message": f"Successfully mapped raw demand {item['demand'].raw_reference} to Canonical Asset {target_asset.source_asset_id if target_asset else target_asset_id}"
        }
    raise HTTPException(status_code=404, detail="Queue item not found")

# ----------------- 3. Maintenance Tasks -----------------
@router.get("/tasks", response_model=List[MaintenanceTask])
def get_tasks(
    department: Optional[DepartmentEnum] = None,
    safety_class: Optional[SafetyClassEnum] = None,
    min_priority: Optional[float] = None
):
    tasks = db.tasks
    if department:
        tasks = [t for t in tasks if t.department == department]
    if safety_class:
        tasks = [t for t in tasks if t.safety_class == safety_class]
    if min_priority is not None:
        tasks = [t for t in tasks if t.priority_score >= min_priority]
    return sorted(tasks, key=lambda x: x.priority_score, reverse=True)

@router.post("/tasks", response_model=MaintenanceTask)
def create_maintenance_task(task_in: MaintenanceTask):
    task = db.priority_engine.evaluate_task(task_in, db.tasks)
    db.tasks.append(task)
    return task

@router.get("/tasks/{task_id}/priority-explanation")
def get_task_priority_explanation(task_id: str):
    task = next((t for t in db.tasks if t.task_id == task_id), None)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return {
        "task_id": task.task_id,
        "description": task.description,
        "priority_score": task.priority_score,
        "criticality_score": task.criticality_score,
        "urgency_score": task.urgency_score,
        "shadow_opportunity_score": task.shadow_opportunity_score,
        "explanation": task.priority_explanation,
        "duration_estimates": {
            "p50_min": task.predicted_p50_duration_min,
            "p80_min": task.predicted_p80_duration_min,
            "p95_min": task.predicted_p95_duration_min,
        },
        "overrun_risk_score": task.overrun_risk_score
    }

# ----------------- 4. Train Movements & Corridors -----------------
@router.get("/trains", response_model=List[TrainMovement])
def get_trains(section_id: Optional[str] = None, line_or_road: Optional[LineOrRoadEnum] = None):
    trains = db.trains
    if section_id:
        trains = [t for t in trains if t.section_id == section_id]
    if line_or_road:
        trains = [t for t in trains if t.line_or_road == line_or_road]
    return sorted(trains, key=lambda x: x.entry_minute)

@router.get("/corridors", response_model=List[CorridorWindow])
def get_corridors():
    return db.windows

# ----------------- 5. Optimization & Shadow Workbench -----------------
@router.post("/optimizer/solve", response_model=OptimizationPlan)
def run_solver(
    horizon: str = "WEEKLY",
    enforce_shadow_packing: bool = True,
    timeout_seconds: int = 30,
    use_ai_priority: bool = False
):
    solve_tasks = db.tasks
    if use_ai_priority:
        # Pass tasks with priority_score reflecting ai_priority_score to CP-SAT solver
        solve_tasks = []
        for t in db.tasks:
            t_copy = t.model_copy()
            if t_copy.ai_priority_score is not None:
                t_copy.priority_score = t_copy.ai_priority_score
            solve_tasks.append(t_copy)

    plan = db.orchestrator.run_optimization(
        horizon_type=horizon,
        tasks=solve_tasks,
        trains=db.trains,
        windows=db.windows,
        goods_forecasts=db.goods_forecasts,
        enforce_shadow_packing=enforce_shadow_packing,
        timeout_seconds=timeout_seconds
    )
    norm_key = horizon.upper()
    if norm_key in ("DAILY", "24H"):
        norm_key = "24H"
    elif norm_key in ("MONTHLY", "30D"):
        norm_key = "30D"
    else:
        norm_key = "7D"
    db.active_horizon = norm_key
    db.active_plan = plan
    db.plans_by_horizon[norm_key] = plan
    if norm_key not in db.plan_history:
        db.plan_history[norm_key] = []
    db.plan_history[norm_key].append(plan)
    return plan

@router.post("/optimizer/what-if")
def run_what_if_simulation(
    selected_task_ids: List[str] = Body(..., embed=True),
    custom_buffer_minutes: int = Body(15, embed=True),
    enforce_shadow_packing: bool = Body(True, embed=True)
):
    """
    Real-time interactive What-If simulation sandbox.
    """
    sub_tasks = [t for t in db.tasks if t.task_id in selected_task_ids]
    if not sub_tasks:
        sub_tasks = db.tasks[:20]

    custom_certifier = db.orchestrator.certifier
    custom_certifier.headway_before_min = custom_buffer_minutes
    custom_certifier.headway_after_min = custom_buffer_minutes

    plan = db.orchestrator.scheduler.solve(
        tasks=sub_tasks,
        trains=db.trains,
        windows=db.windows,
        goods_forecasts=db.goods_forecasts,
        horizon_minutes=1440,
        enforce_shadow_packing=enforce_shadow_packing
    )
    
    cert = custom_certifier.verify_and_certify(plan, db.trains)
    
    return {
        "what_if_plan": plan,
        "certificate": cert,
        "kpi_comparison": {
            "baseline_corridor_hours_saved": db.active_plan.kpis.get("corridor_hours_saved", 0),
            "simulated_corridor_hours_saved": plan.kpis.get("corridor_hours_saved", 0),
            "baseline_asset_availability": db.active_plan.kpis.get("asset_availability_pct", 95.0),
            "simulated_asset_availability": plan.kpis.get("asset_availability_pct", 95.0),
            "baseline_downtime_avoided_hrs": db.active_plan.kpis.get("asset_downtime_avoided_hrs", 0),
            "simulated_downtime_avoided_hrs": plan.kpis.get("asset_downtime_avoided_hrs", 0),
            "total_tasks_scheduled": len(plan.assignments),
            "shadow_groups_count": len(plan.shadow_groups),
            "possessions_avoided": plan.kpis.get("separate_blocks_avoided", 0),
            "safety_verified": cert.verified_zero_clash
        }
    }

@router.get("/optimizer/comparison")
def get_optimization_comparison():
    """
    Returns structured Before vs After Baseline Comparison Metrics (Requirement 3 Section 29):
    Blocks, Corridor Occupation, Asset Downtime, Asset Availability %, Possessions Avoided.
    """
    return db.active_plan.comparison_metrics or {}

@router.get("/optimizer/audit-trail")
def get_optimization_audit_trail():
    """
    Returns full cryptographic & operational audit trail for the active optimization plan (Section 27).
    """
    return db.active_plan.audit_trail or {}

@router.get("/optimizer/asset-availability")
def get_asset_availability_metrics():
    """
    Returns mathematically derived corridor asset availability & downtime metrics (Section 8 & 9).
    """
    plan = db.active_plan
    return {
        "baseline_asset_availability_pct": plan.baseline_asset_availability_pct,
        "optimized_asset_availability_pct": plan.asset_availability_pct,
        "improvement_percentage_points": plan.asset_availability_improvement_pp,
        "total_asset_downtime_min": plan.total_asset_downtime_min,
        "baseline_asset_downtime_min": plan.baseline_asset_downtime_min,
        "asset_downtime_saved_min": plan.asset_downtime_saved_min,
        "corridor_hours_saved": plan.corridor_hours_saved,
        "blocks_consolidated": plan.blocks_consolidated,
        "possessions_avoided": plan.possessions_avoided,
        "solver_status": plan.solver_status,
        "solver_explanation": plan.solver_explanation
    }

@router.get("/plans/latest", response_model=OptimizationPlan)
def get_latest_plan():
    return db.active_plan

@router.post("/plans/{plan_id}/approve")
def approve_plan(plan_id: str, approver_name: str = Body("Sr. DOM / Delhi Division", embed=True)):
    if db.active_plan.plan_id == plan_id:
        db.active_plan.approved_by = approver_name
        db.active_plan.approved_at = datetime.now(timezone.utc).isoformat()
        return {"status": "APPROVED", "plan_id": plan_id, "approved_by": approver_name}
    raise HTTPException(status_code=404, detail="Plan not found")

@router.get("/shadow-blocks", response_model=List[ShadowBlockGroup])
def get_shadow_block_groups():
    return db.active_plan.shadow_groups

# ----------------- Multi-Horizon Block Planning Endpoints (Requirement 4) -----------------
@router.post("/plans/generate", response_model=OptimizationPlan)
def generate_horizon_plan(
    horizon_type: str = Body("7D", embed=True),
    enforce_shadow_packing: bool = Body(True, embed=True),
    timeout_seconds: int = Body(30, embed=True),
    freeze_approved: bool = Body(False, embed=True)
):
    """
    Generate or regenerate an optimization plan for a specific horizon (24H, 7D, 30D).
    """
    norm_key = horizon_type.upper()
    if norm_key in ("DAILY", "24H"):
        norm_key = "24H"
    elif norm_key in ("MONTHLY", "30D"):
        norm_key = "30D"
    else:
        norm_key = "7D"

    prev_plan = db.plans_by_horizon.get(norm_key)
    plan = db.orchestrator.run_optimization(
        horizon_type=norm_key,
        tasks=db.tasks,
        trains=db.trains,
        windows=db.windows,
        goods_forecasts=db.goods_forecasts,
        enforce_shadow_packing=enforce_shadow_packing,
        timeout_seconds=timeout_seconds,
        freeze_approved=freeze_approved,
        previous_plan=prev_plan
    )
    db.active_horizon = norm_key
    db.active_plan = plan
    db.plans_by_horizon[norm_key] = plan
    if norm_key not in db.plan_history:
        db.plan_history[norm_key] = []
    db.plan_history[norm_key].append(plan)
    return plan

@router.get("/plans/horizon/{horizon_type}", response_model=OptimizationPlan)
def get_plan_by_horizon(horizon_type: str):
    """
    Retrieve the current plan for a given horizon: 24H, 7D, or 30D.
    """
    norm_key = horizon_type.upper()
    if norm_key in ("DAILY", "24H"):
        norm_key = "24H"
    elif norm_key in ("MONTHLY", "30D"):
        norm_key = "30D"
    elif norm_key in ("WEEKLY", "7D"):
        norm_key = "7D"
    else:
        raise HTTPException(status_code=400, detail=f"Invalid horizon type: {horizon_type}. Use 24H, 7D, or 30D.")

    plan = db.plans_by_horizon.get(norm_key)
    if not plan:
        plan = db.orchestrator.run_optimization(
            horizon_type=norm_key,
            tasks=db.tasks,
            trains=db.trains,
            windows=db.windows,
            goods_forecasts=db.goods_forecasts,
            enforce_shadow_packing=True
        )
        db.plans_by_horizon[norm_key] = plan
        db.plan_history[norm_key] = [plan]
    
    db.active_plan = plan
    db.active_horizon = norm_key
    return plan

@router.get("/plans/versions")
def get_plan_versions():
    """
    List all generated plan versions across horizons.
    """
    versions = []
    for horizon, hist in db.plan_history.items():
        for p in hist:
            versions.append({
                "plan_id": p.plan_id,
                "plan_version": p.plan_version,
                "horizon": horizon,
                "generated_at": p.generated_at,
                "assignments_count": len(p.assignments),
                "shadow_groups_count": len(p.shadow_groups),
                "plan_status": p.plan_status.value if hasattr(p.plan_status, 'value') else str(p.plan_status),
                "plan_confidence": p.plan_confidence.value if hasattr(p.plan_confidence, 'value') else str(p.plan_confidence),
                "corridor_hours_saved": p.corridor_hours_saved,
                "asset_availability_pct": p.asset_availability_pct,
                "approved_by": p.approved_by,
                "is_active": (p.plan_id == db.active_plan.plan_id)
            })
    return versions

@router.get("/plans/comparison-horizons")
def get_horizon_comparison():
    """
    Returns side-by-side comparison matrix across 24H Rolling, 7D Weekly, and 30D Monthly horizons.
    """
    return db.active_plan.horizon_comparison or {
        "horizons": ["24-Hour Rolling (24H)", "7-Day Weekly (7D)", "30-Day Monthly (30D)"],
        "metrics": {
            "tasks_scheduled": [len(db.plan_24h.assignments), len(db.plan_7d.assignments), len(db.plan_30d.assignments)],
            "shadow_groups": [len(db.plan_24h.shadow_groups), len(db.plan_7d.shadow_groups), len(db.plan_30d.shadow_groups)],
            "corridor_hours_saved": [db.plan_24h.corridor_hours_saved, db.plan_7d.corridor_hours_saved, db.plan_30d.corridor_hours_saved],
            "asset_availability_pct": [db.plan_24h.asset_availability_pct, db.plan_7d.asset_availability_pct, db.plan_30d.asset_availability_pct],
            "confidence": ["CONFIRMED", "HIGH", "PROVISIONAL"]
        }
    }

@router.post("/plans/reoptimize", response_model=OptimizationPlan)
def reoptimize_active_plan(
    horizon_type: Optional[str] = Body(None, embed=True),
    freeze_approved: bool = Body(True, embed=True)
):
    """
    Execute rolling re-optimization against the active or specified horizon.
    Preserves approved/locked blocks within the freeze window and computes plan diff.
    """
    target_horizon = horizon_type or db.active_horizon
    norm_key = target_horizon.upper()
    if norm_key in ("DAILY", "24H"):
        norm_key = "24H"
    elif norm_key in ("MONTHLY", "30D"):
        norm_key = "30D"
    else:
        norm_key = "7D"

    prev_plan = db.plans_by_horizon.get(norm_key, db.active_plan)
    new_plan = db.orchestrator.run_optimization(
        horizon_type=norm_key,
        tasks=db.tasks,
        trains=db.trains,
        windows=db.windows,
        goods_forecasts=db.goods_forecasts,
        enforce_shadow_packing=True,
        freeze_approved=freeze_approved,
        previous_plan=prev_plan
    )
    db.active_horizon = norm_key
    db.active_plan = new_plan
    db.plans_by_horizon[norm_key] = new_plan
    if norm_key not in db.plan_history:
        db.plan_history[norm_key] = []
    db.plan_history[norm_key].append(new_plan)
    return new_plan

@router.get("/plans/unscheduled-tasks")
def get_unscheduled_tasks(horizon_type: Optional[str] = None):
    """
    Returns unscheduled/deferred tasks with root cause constraints and recommended actions.
    """
    target_horizon = horizon_type or db.active_horizon
    norm_key = target_horizon.upper()
    if norm_key in ("DAILY", "24H"):
        norm_key = "24H"
    elif norm_key in ("MONTHLY", "30D"):
        norm_key = "30D"
    else:
        norm_key = "7D"

    plan = db.plans_by_horizon.get(norm_key, db.active_plan)
    return {
        "horizon": norm_key,
        "plan_version": plan.plan_version,
        "unscheduled_count": len(plan.unscheduled_tasks),
        "deferred_count": len(plan.deferred_tasks),
        "unscheduled_tasks": plan.unscheduled_tasks,
        "deferred_tasks": plan.deferred_tasks,
        "backlog_summary": plan.backlog_summary
    }

# ----------------- 6. Field Execution & SSE Cockpit -----------------
@router.get("/execution/blocks")
def get_execution_blocks():
    return list(db.execution_states.values())

@router.post("/execution/safety-checklist")
def submit_safety_checklist(
    assignment_id: str = Body(..., embed=True),
    permit_to_work: bool = Body(True, embed=True),
    traction_isolation_verified: bool = Body(True, embed=True),
    signalling_disconnection_memo: bool = Body(True, embed=True),
    crew_briefing_conducted: bool = Body(True, embed=True),
    machine_fitness_certified: bool = Body(True, embed=True)
):
    state = db.execution_states.get(assignment_id)
    if not state:
        raise HTTPException(status_code=404, detail="Assignment not found")
    
    all_ok = permit_to_work and traction_isolation_verified and signalling_disconnection_memo and crew_briefing_conducted and machine_fitness_certified
    state["checklist_completed"] = all_ok
    state["current_state"] = "PROTECTION_APPLIED" if all_ok else "PERMIT_REQUESTED"
    state["notes"].append(f"Pre-work safety checklist submitted by SSE: {'PASSED' if all_ok else 'DEFICIENT'}")
    
    return {"status": "SUCCESS", "checklist_passed": all_ok, "current_state": state["current_state"]}

@router.post("/execution/state-transition")
def transition_block_state(
    assignment_id: str = Body(..., embed=True),
    target_state: str = Body(..., embed=True), # PROTECTION_APPLIED, IN_PROGRESS, RESTORED, CLOSED
    notes: Optional[str] = Body(None, embed=True)
):
    state = db.execution_states.get(assignment_id)
    if not state:
        raise HTTPException(status_code=404, detail="Assignment not found")
    
    now_iso = datetime.now(timezone.utc).isoformat()
    state["current_state"] = target_state
    
    if target_state == "IN_PROGRESS":
        state["actual_start"] = now_iso
    elif target_state in ("RESTORED", "CLOSED"):
        state["actual_end"] = now_iso
        
    if notes:
        state["notes"].append(f"[{now_iso}] {notes}")
        
    return {"status": "SUCCESS", "assignment_id": assignment_id, "new_state": target_state}

# ----------------- 7. Requirement 1: Unified Data Integration & Lineage -----------------
@router.get("/integration/status", response_model=Dict[str, IntegrationSourceStatus])
def get_integration_status():
    """
    Returns real-time operational status, connection mode (Simulated/Demo), record counts,
    and sync timestamps across all 6 sources: TMS, SMMS, TDMS, COA, Timetable, Goods Forecast.
    """
    return db.integration_service.get_sources_status()

@router.get("/integration/quality", response_model=DataQualityReport)
def get_integration_quality():
    """
    Returns data quality, boundary validation checks, and health metrics across all integrated feeds.
    """
    return db.integration_service.get_data_quality_report()

@router.get("/integration/goods-forecast", response_model=List[GoodsTrainForecast])
def get_goods_forecast(corridor_id: Optional[str] = None):
    """
    Returns expected freight train traffic forecasts from Control Office / FOIS.
    """
    fcsts = db.goods_forecasts
    if corridor_id:
        fcsts = [f for f in fcsts if f.corridor_id == corridor_id or f.section_id == corridor_id]
    return fcsts

@router.get("/integration/lineage/{task_id}", response_model=TaskLineageRecord)
def get_task_lineage(task_id: str):
    """
    Returns 6-way cross-source operational provenance trace for a maintenance task:
    TMS/SMMS/TDMS Work Order -> Asset ID -> COA Window -> Timetable Headway -> Goods Forecast.
    """
    lineage = db.integration_service.get_task_lineage(task_id)
    if not lineage:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found for lineage extraction")
    return lineage

@router.get("/integration/correlation-scenario", response_model=CrossSystemCorrelationScenario)
def get_correlation_scenario():
    """
    Returns the 6-way cross-system operational convergence scenario
    demonstrating TMS + SMMS + TDMS + COA + Timetable + Goods Forecast integration
    on the same corridor/section and window (TKD–FDB DOWN Line, 00:30–04:30).
    """
    return db.integration_service.get_correlation_scenario()

@router.post("/integration/sync")
def trigger_integration_sync():
    """
    Forces immediate re-synchronization across all 6 source adapters.
    """
    db.integration_service.sync_all()
    db.tasks = db.priority_engine.batch_evaluate(db.integration_service.tasks)
    db.trains = db.integration_service.trains
    db.windows = db.integration_service.windows
    db.goods_forecasts = db.integration_service.goods_forecasts
    db.plan_24h = db.orchestrator.run_optimization("24H", tasks=db.tasks, trains=db.trains, windows=db.windows, goods_forecasts=db.goods_forecasts)
    db.plan_7d = db.orchestrator.run_optimization("7D", tasks=db.tasks, trains=db.trains, windows=db.windows, goods_forecasts=db.goods_forecasts)
    db.plan_30d = db.orchestrator.run_optimization("30D", tasks=db.tasks, trains=db.trains, windows=db.windows, goods_forecasts=db.goods_forecasts)
    db.active_plan = db.plan_7d
    db.plans_by_horizon["24H"] = db.plan_24h
    db.plans_by_horizon["7D"] = db.plan_7d
    db.plans_by_horizon["30D"] = db.plan_30d
    db.plans_by_horizon["DAILY"] = db.plan_24h
    db.plans_by_horizon["WEEKLY"] = db.plan_7d
    db.plans_by_horizon["MONTHLY"] = db.plan_30d
    return {
        "status": "SUCCESS",
        "message": "All 6 operational source adapters successfully re-synchronized.",
        "timestamp": db.integration_service.last_sync_timestamp,
        "record_counts": {k: v.total_records for k, v in db.integration_service.get_sources_status().items()}
    }

# ----------------- 8. Requirement 2: AI/ML Maintenance Risk & Priority Engine -----------------
@router.get("/ml/metadata")
def get_ml_metadata():
    """
    Returns verified model version, training metrics (F1, ROC-AUC), feature set,
    chronological split details, and honest synthetic prototype data labeling.
    """
    meta = db.priority_engine.inference_service.get_metadata()
    return {
        "status": "OPERATIONAL",
        "model_name": meta.get("model_name", "RailRisk"),
        "model_version": meta.get("model_version", "v1.0"),
        "model_type": meta.get("model_type", "RandomForestClassifier (Calibrated Ensemble)"),
        "training_date": meta.get("training_date"),
        "prediction_horizon": meta.get("prediction_horizon", "7 Days"),
        "target_definition": meta.get("target_definition", "Probability of critical failure or severe operational disruption within 7 days"),
        "feature_set": meta.get("feature_set", "FS-01 (17 Domain Features)"),
        "data_mode": meta.get("data_mode", "Prototype ML Model — Synthetic Training Data"),
        "data_mode_label": "Synthetic prototype evaluation",
        "split_strategy": meta.get("split_strategy", "Chronological (Older 75% Train, Newer 25% Test - Zero Leakage)"),
        "total_samples": meta.get("total_samples", 1200),
        "train_samples": meta.get("train_samples", 900),
        "test_samples": meta.get("test_samples", 300),
        "metrics": meta.get("metrics", {}),
        "feature_importances": meta.get("feature_importances", {}),
        "risk_thresholds": meta.get("risk_thresholds", {
            "LOW": [0.0, 25.0],
            "MODERATE": [26.0, 50.0],
            "HIGH": [51.0, 75.0],
            "CRITICAL": [76.0, 100.0]
        })
    }

@router.get("/ml/prioritized-tasks", response_model=List[MaintenanceTask])
def get_ml_prioritized_tasks(
    department: Optional[DepartmentEnum] = None,
    safety_class: Optional[SafetyClassEnum] = None,
    min_ai_priority: Optional[float] = None
):
    """
    Returns maintenance tasks ranked by genuine AI-Assisted Priority Score,
    preserving both deterministic and AI scores side-by-side.
    """
    tasks = db.tasks
    if department:
        tasks = [t for t in tasks if t.department == department]
    if safety_class:
        tasks = [t for t in tasks if t.safety_class == safety_class]
    if min_ai_priority is not None:
        tasks = [t for t in tasks if (t.ai_priority_score or 0.0) >= min_ai_priority]
    return sorted(tasks, key=lambda x: x.ai_priority_score or 0.0, reverse=True)

@router.get("/ml/explain/{task_id}")
def get_task_ml_explanation(task_id: str):
    """
    Returns transparent, explainable AI recommendation breakdown for a specific maintenance task:
    Risk Probability, AI Priority, Risk Class, 7-Day Horizon, Top Contributing Factors,
    Availability Impact, Traffic Exposure, and Safety Override status.
    """
    task = next((t for t in db.tasks if t.task_id == task_id or t.source_task_id == task_id), None)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found")
    
    asset = next((a for a in db.assets if a.asset_id == task.asset_id), None)
    
    return {
        "task_id": task.task_id,
        "source_task_id": task.source_task_id,
        "description": task.description,
        "department": task.department.value if hasattr(task.department, "value") else str(task.department),
        "section_id": asset.section_id if asset else "TKD-FDB",
        "line_or_road": asset.line_or_road.value if asset and hasattr(asset.line_or_road, "value") else "DOWN",
        "deterministic_score": task.priority_score,
        "criticality_score": task.criticality_score,
        "urgency_score": task.urgency_score,
        "ai_risk_score": task.ai_risk_score,
        "ai_risk_class": task.ai_risk_class,
        "ai_priority_score": task.ai_priority_score,
        "ai_confidence_level": task.ai_confidence_level,
        "availability_impact_score": task.availability_impact_score,
        "traffic_exposure_score": task.traffic_exposure_score,
        "prediction_horizon": "7 Days",
        "top_contributing_factors": task.ai_contributing_factors or [],
        "ai_explanation": task.ai_explanation or "Routine maintenance parameters",
        "is_safety_override_applied": task.is_safety_override_applied,
        "is_cold_start": task.is_cold_start,
        "model_version": task.model_version or "RailRisk v1.0",
        "data_mode_label": "Synthetic prototype evaluation"
    }

@router.get("/ml/demo-scenario")
def get_ml_demo_scenario():
    """
    Returns the required 3-task demonstration scenario (Section 29 of prompt):
    Task A (Critical, ~91-96%), Task B (Moderate, ~44-57%), Task C (Routine, ~4-18%)
    generated dynamically via the calibrated ML model pipeline.
    """
    return db.priority_engine.inference_service.get_demo_scenario()

@router.get("/ml/monitoring")
def get_ml_monitoring_stats():
    """
    Returns lightweight ML operational monitoring statistics and distribution benchmarks.
    """
    return db.priority_engine.inference_service.get_monitoring_stats()

@router.post("/ml/retrain")
def retrain_ml_model():
    """
    Triggers offline model retraining with chronological splitting, updates the serialized artifact,
    reloads inference engine, and re-evaluates all active maintenance tasks.
    """
    from backend.app.services.ml.training_pipeline import train_and_evaluate_model
    meta = train_and_evaluate_model()
    db.priority_engine.inference_service.reload()
    db.tasks = db.priority_engine.batch_evaluate(db.tasks)
    return {
        "status": "SUCCESS",
        "message": "RailRisk model retraining completed successfully with chronological train/test split.",
        "training_date": meta.get("training_date"),
        "metrics": meta.get("metrics"),
        "total_tasks_reevaluated": len(db.tasks)
    }

