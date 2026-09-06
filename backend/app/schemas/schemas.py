"""
Rail-BDMS: Canonical Schemas and Data Models
"""
from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
import uuid
from datetime import datetime

class DepartmentEnum(str, Enum):
    ENGINEERING = "ENGINEERING"   # Civil / P-Way (TMS)
    S_AND_T = "S_AND_T"           # Signalling & Telecom (SMMS)
    TRD = "TRD"                   # Traction Distribution / Electrical (TDMS)
    OPERATING = "OPERATING"       # Operating / Traffic (COA)

class SourceSystemEnum(str, Enum):
    TMS = "TMS"
    SMMS = "SMMS"
    TDMS = "TDMS"
    COA = "COA"

class AssetTypeEnum(str, Enum):
    TRACK_SEGMENT = "TRACK_SEGMENT"
    TURNOUT = "TURNOUT"
    CROSSOVER = "CROSSOVER"
    SIGNAL = "SIGNAL"
    AXLE_COUNTER = "AXLE_COUNTER"
    POINT_MACHINE = "POINT_MACHINE"
    OHE_MAST = "OHE_MAST"
    SECTION_INSULATOR = "SECTION_INSULATOR"
    POWER_SUBSTATION = "POWER_SUBSTATION"

class LineOrRoadEnum(str, Enum):
    UP = "UP"
    DOWN = "DOWN"
    SINGLE_LINE = "SL"
    ROAD_1 = "ROAD_1"
    ROAD_2 = "ROAD_2"
    ROAD_3 = "ROAD_3"
    ROAD_4 = "ROAD_4"
    YARD_LINE = "YARD_LINE"

class SafetyClassEnum(str, Enum):
    SAFETY_CRITICAL = "SAFETY_CRITICAL"   # E.g. IMR Rail fracture, Point lock failure
    OPERATIONAL_DEFECT = "OPERATIONAL_DEFECT" # E.g. REM defect, speed restriction
    ROUTINE = "ROUTINE"                   # E.g. Scheduled tamping, cantilever check

class MachineTypeEnum(str, Enum):
    NONE = "NONE"
    CSM = "CSM"                   # Continuous Action Tamping Machine
    BCM = "BCM"                   # Ballast Cleaning Machine
    UNIMAT = "UNIMAT"             # Points and Crossing Tamping Machine
    DGS = "DGS"                   # Dynamic Track Stabilizer
    TOWER_WAGON = "TOWER_WAGON"   # OHE Inspection Car
    UTV = "UTV"                   # Utility Track Vehicle
    CRANE = "CRANE"               # 140T Breakdown Crane

class TaskStatusEnum(str, Enum):
    PENDING = "PENDING"
    UNRESOLVED_IDENTITY = "UNRESOLVED_IDENTITY"
    VALIDATED = "VALIDATED"
    SCHEDULED = "SCHEDULED"
    APPROVED = "APPROVED"
    PROTECTION_APPLIED = "PROTECTION_APPLIED"
    IN_PROGRESS = "IN_PROGRESS"
    RESTORED = "RESTORED"
    COMPLETED = "COMPLETED"
    REJECTED = "REJECTED"

class TrainTypeEnum(str, Enum):
    PREMIUM_PASSENGER = "PREMIUM_PASSENGER"  # Vande Bharat, Rajdhani (Priority 1)
    EXPRESS = "EXPRESS"                      # Mail / Express / Superfast (Priority 2)
    SUBURBAN = "SUBURBAN"                    # MEMU / EMU / Passenger (Priority 3)
    CONTAINER_FREIGHT = "CONTAINER_FREIGHT"  # High-speed container (Priority 4)
    GOODS_FREIGHT = "GOODS_FREIGHT"          # Coal / Iron ore / BOXN (Priority 5)

# --- Asset Schemas ---
class CanonicalAsset(BaseModel):
    asset_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source_system: SourceSystemEnum
    source_asset_id: str
    asset_type: AssetTypeEnum
    department: DepartmentEnum
    division: str = "DELHI"
    section_id: str
    station_from: str
    station_to: str
    chainage_from: float  # e.g. 124.200 (km.m)
    chainage_to: float    # e.g. 124.800
    line_or_road: LineOrRoadEnum
    route_class: str = "HDN"  # High Density Network
    criticality_class: str = "CLASS_A" # CLASS_A, CLASS_B, CLASS_C
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    parent_asset_id: Optional[str] = None
    status: str = "OPERATIONAL"
    last_inspected: Optional[str] = None

# --- Inbound Raw Asset Demand for Identity Resolution ---
class RawAssetDemand(BaseModel):
    source_system: SourceSystemEnum
    source_asset_id: str
    raw_reference: str  # e.g., "km 124/2-8", "Point-102B", "Mast 124/14"
    department: DepartmentEnum
    section_id: str
    station_from: Optional[str] = None
    station_to: Optional[str] = None
    line_or_road: LineOrRoadEnum
    chainage_from: Optional[float] = None
    chainage_to: Optional[float] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None

class IdentityResolutionResult(BaseModel):
    resolved_asset_id: Optional[str] = None
    canonical_asset: Optional[CanonicalAsset] = None
    confidence_score: float  # 0.0 to 1.0
    matched_tier: str       # "TIER_1_EXACT", "TIER_2_HIERARCHY", "TIER_3_CHAINAGE", "TIER_4_SPATIAL", "UNRESOLVED"
    rationale: str
    requires_human_reconciliation: bool = False

# --- Maintenance Task Schemas ---
class MaintenanceTask(BaseModel):
    task_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source_system: SourceSystemEnum
    source_task_id: str
    asset_id: str
    department: DepartmentEnum
    task_type: str
    description: str
    created_at: str
    due_at: str
    latest_completion_date: str
    estimated_duration_min: int
    min_duration_min: int
    max_duration_min: int
    requires_traffic_block: bool = True
    requires_ohe_isolation: bool = False
    requires_signal_disconnection: bool = False
    requires_line_occupation: bool = True
    required_crew_type: Optional[str] = None
    required_machine_type: MachineTypeEnum = MachineTypeEnum.NONE
    predecessor_task_ids: List[str] = Field(default_factory=list)
    safety_class: SafetyClassEnum = SafetyClassEnum.SAFETY_CRITICAL
    status: TaskStatusEnum = TaskStatusEnum.PENDING
    
    # Priority and Risk Analytics
    priority_score: float = 0.0
    criticality_score: float = 0.0
    urgency_score: float = 0.0
    shadow_opportunity_score: float = 0.0
    priority_explanation: Optional[str] = None
    overrun_risk_score: float = 0.0
    predicted_p50_duration_min: int = 0
    predicted_p80_duration_min: int = 0
    predicted_p95_duration_min: int = 0

# --- Train Movements & Corridors ---
class TrainMovement(BaseModel):
    movement_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    train_number: str
    train_name: str
    service_date: str
    train_type: TrainTypeEnum
    origin: str
    destination: str
    section_id: str
    line_or_road: LineOrRoadEnum
    planned_entry: str  # ISO timestamp
    planned_exit: str   # ISO timestamp
    entry_minute: int   # Relative offset in horizon (0..T_max)
    exit_minute: int    # Relative offset in horizon
    min_clearance_before_min: int = 15
    min_clearance_after_min: int = 15
    priority_class: int = 1 # 1 (Highest, Vande Bharat) to 5 (Freight)
    speed_kmh: int = 110

class CorridorWindow(BaseModel):
    corridor_window_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    section_id: str
    line_or_road: LineOrRoadEnum
    window_start: str
    window_end: str
    start_minute: int
    end_minute: int
    available_duration_min: int
    allowed_block_type: str = "MULTI_DEPARTMENT"
    timetable_version: str = "WTT-NR-2026-V2"

# --- Shadow Block & Schedule Assignments ---
class ShadowBlockGroup(BaseModel):
    block_group_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    lead_department: DepartmentEnum
    section_id: str
    line_or_road: LineOrRoadEnum
    task_ids: List[str] = Field(default_factory=list)
    participating_departments: List[DepartmentEnum] = Field(default_factory=list)
    consolidated_start_minute: int = 0
    consolidated_end_minute: int = 0
    total_duration_min: int = 0
    corridor_time_saved_min: int = 0
    compatibility_score: float = 1.0
    compatibility_rationale: str = ""

class ScheduledBlockAssignment(BaseModel):
    assignment_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    plan_id: str
    task_id: str
    task_description: str
    department: DepartmentEnum
    section_id: str
    line_or_road: LineOrRoadEnum
    corridor_window_id: Optional[str] = None
    block_group_id: Optional[str] = None  # None if standalone, UUID if Shadow Block
    is_shadow_block: bool = False
    planned_start_min: int
    planned_end_min: int
    planned_start_time: str
    planned_end_time: str
    duration_min: int
    priority_score: float
    required_machine_type: MachineTypeEnum
    lead_department: DepartmentEnum
    approval_status: str = "SUGGESTED" # SUGGESTED, APPROVED, REJECTED
    actual_start_time: Optional[str] = None
    actual_end_time: Optional[str] = None
    actual_status: str = "SCHEDULED"
    overrun_risk_pct: float = 0.0

class TimetableProtectionCertificate(BaseModel):
    certificate_id: str
    plan_id: str
    issued_at: str
    hash_sha256: str
    timetable_version: str
    solver_status: str
    total_tasks_evaluated: int
    total_trains_protected: int
    verified_zero_clash: bool = True
    headway_buffer_verified: bool = True
    policy_hash: str
    explanation: str

class OptimizationPlan(BaseModel):
    plan_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    horizon_type: str = "WEEKLY"
    division: str = "DELHI"
    generated_at: str
    solver_status: str  # OPTIMAL, FEASIBLE, INFEASIBLE
    solve_time_ms: int
    assignments: List[ScheduledBlockAssignment] = Field(default_factory=list)
    shadow_groups: List[ShadowBlockGroup] = Field(default_factory=list)
    kpis: Dict[str, Any] = Field(default_factory=dict)
    certificate: Optional[TimetableProtectionCertificate] = None
    is_active: bool = True
    approved_by: Optional[str] = None
    approved_at: Optional[str] = None

class LoginRequest(BaseModel):
    username: str
    password: str

class UserProfile(BaseModel):
    username: str
    full_name: str
    role: str
    designation: str
    office: str
    division: str
    zone: str
    access_level: str

class LoginResponse(BaseModel):
    status: str
    token: str
    message: str
    user: UserProfile

class GisConfigResponse(BaseModel):
    api_key: str
    provider: str
    issued_to: str
    issued_at: str
    status: str
    corridor_bounds: Dict[str, Any]
    available_layers: List[Dict[str, str]]

class LiveTrainPosition(BaseModel):
    train_number: str
    train_name: str
    section_id: str
    line: str
    speed_kmh: float
    progress_pct: float
    priority_class: str
    lat: float
    lon: float
    heading: int
    origin_stn: str
    destination_stn: str
    safety_status: str


