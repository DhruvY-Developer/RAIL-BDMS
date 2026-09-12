"""
Rail-BDMS: Canonical Integration Schemas & Data Contracts
Fulfills Requirement 1: Multi-Source Operational & Maintenance Data Integration Layer
Sources: TMS, SMMS, TDMS, COA, Train Timetable (WTT), Goods Train Forecast (Control Office / FOIS)
"""
from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
import uuid
from datetime import datetime, timezone

from backend.app.schemas.schemas import (
    MaintenanceTask, TrainMovement, CorridorWindow,
    SourceSystemEnum, DepartmentEnum, LineOrRoadEnum,
    SafetyClassEnum, MachineTypeEnum, TaskStatusEnum, TrainTypeEnum
)

class IntegrationSourceEnum(str, Enum):
    TMS = "TMS"
    SMMS = "SMMS"
    TDMS = "TDMS"
    COA = "COA"
    TIMETABLE = "TIMETABLE"
    GOODS_FORECAST = "GOODS_FORECAST"

class ConnectionModeEnum(str, Enum):
    SIMULATED_PROTOTYPE = "Simulated / Prototype Data Source"
    DEMO_ADAPTER = "Configured Demo Adapter"
    LIVE_REST_API = "Live Official API (Not Connected)"

class UnifiedMaintenanceTask(MaintenanceTask):
    """
    Normalized maintenance task schema unifying TMS, SMMS, and TDMS.
    Inherits all core fields from MaintenanceTask to ensure 100% backward
    compatibility with the CP-SAT scheduler, priority analytics, and shadow packing.
    """
    unified_task_id: str = Field(default_factory=lambda: f"UMT-{uuid.uuid4().hex[:8].upper()}")
    defect_id: Optional[str] = None
    defect_description: Optional[str] = None
    defect_severity: Optional[str] = None  # CRITICAL_IMR, MAJOR, ROUTINE
    maintenance_type: Optional[str] = None
    overdue_duration_days: int = 0
    section_id: Optional[str] = None
    line_or_road: Optional[LineOrRoadEnum] = None
    chainage_from: Optional[float] = None
    chainage_to: Optional[float] = None
    location: Optional[str] = None
    asset_type: Optional[str] = None
    original_asset_source_id: Optional[str] = None
    resolution_tier: Optional[str] = "TIER_1_EXACT"  # TIER_1_EXACT, TIER_2_HIERARCHY, TIER_3_CHAINAGE, TIER_4_SPATIAL, UNRESOLVED
    resolution_confidence: Optional[float] = 1.0
    source_updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_sync: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    validation_status: str = "VALID"  # VALID, NEEDS_REVIEW, WARNING
    validation_flags: List[str] = Field(default_factory=list)

class COACorridorAvailability(CorridorWindow):
    """
    Normalized COA corridor block availability window.
    Integrates block slots with official COA identifiers and operational restrictions.
    """
    source_system: SourceSystemEnum = SourceSystemEnum.COA
    coa_block_id: str = Field(default_factory=lambda: f"COA-BLK-{uuid.uuid4().hex[:8].upper()}")
    direction: str = "BOTH"  # UP, DOWN, BOTH
    availability_status: str = "CONFIRMED"  # CONFIRMED, TENTATIVE, CANCELLED
    affected_section: str = ""
    station_limits: Optional[str] = None
    existing_possessions: List[str] = Field(default_factory=list)
    operational_restrictions: List[str] = Field(default_factory=list)
    last_sync: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    validation_status: str = "VALID"

class IntegratedTimetablePath(TrainMovement):
    """
    Normalized Train Working Timetable (WTT) movement path with headway protection envelopes.
    """
    source_system: str = "TIMETABLE_WTT"
    train_category: str = "PASSENGER"
    headway_buffer_min: int = 15
    last_sync: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    validation_status: str = "VALID"

class GoodsTrainForecast(BaseModel):
    """
    Goods Train Traffic Forecast model from Control Office / FOIS.
    Represents expected freight movement windows, train counts, and prediction confidence.
    """
    forecast_id: str = Field(default_factory=lambda: f"GTF-{uuid.uuid4().hex[:8].upper()}")
    forecast_date: str
    time_window: str  # e.g., "00:00-04:00", "04:00-08:00", "11:30-14:00"
    start_minute: int
    end_minute: int
    corridor_id: str  # e.g. "NZM-PWL"
    section_id: str   # e.g. "TKD-FDB"
    direction: str = "BOTH"  # UP, DOWN, BOTH
    expected_goods_train_count: int
    expected_train_paths: List[str] = Field(default_factory=list)  # e.g. ["COAL-44", "CONRAJ-91"]
    confidence_pct: float = 85.0
    forecast_generated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    source: str = "Control Office / Goods Freight Forecast (FOIS)"
    train_category: str = "CONTAINER / COAL / BULK RAKE"
    is_simulated: bool = True
    operational_impact: str = "LOW"  # LOW, MODERATE, HIGH
    notes: Optional[str] = None
    last_sync: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    validation_status: str = "VALID"

class IntegrationSourceStatus(BaseModel):
    """
    Health and synchronization metadata for an integrated data source.
    """
    source_id: str
    source_name: str
    department: str
    connection_mode: ConnectionModeEnum = ConnectionModeEnum.SIMULATED_PROTOTYPE
    status: str = "OPERATIONAL"  # OPERATIONAL, SYNCING, DEGRADED
    total_records: int = 0
    valid_records: int = 0
    needs_review_records: int = 0
    last_sync: str
    data_freshness_seconds: int = 0
    description: str

class DataQualityReport(BaseModel):
    """
    Data quality and validation audit report across all integrated sources.
    """
    generated_at: str
    total_ingested: int
    total_valid: int
    total_flagged: int
    overall_health_pct: float
    sources: Dict[str, IntegrationSourceStatus]
    validation_rules_enforced: List[str]
    recent_validation_notices: List[Dict[str, Any]] = Field(default_factory=list)

class TaskLineageRecord(BaseModel):
    """
    Complete end-to-end data lineage showing provenance across all operational sources.
    """
    unified_task_id: str
    task_id: str
    source_system: str
    source_task_id: str
    asset_id: str
    asset_source_id: str
    asset_name: str
    department: str
    section_id: str
    line_or_road: str
    task_type: str
    defect_description: str
    safety_class: str
    due_at: str
    overdue_duration_days: int
    planned_duration_min: int
    requires_ohe_isolation: bool
    requires_signal_disconnection: bool
    
    asset_type: Optional[str] = None
    location: Optional[str] = None
    resolution_tier: Optional[str] = "TIER_1_EXACT"
    resolution_confidence: Optional[float] = 1.0
    
    # Associated COA corridor window
    coa_corridor_window: Optional[Dict[str, Any]] = None
    
    # Associated timetable trains in this window / section
    protected_trains: List[Dict[str, Any]] = Field(default_factory=list)
    timetable_safety_status: str = "HEADWAY_PROTECTED_0_CLASH"
    
    # Associated goods traffic forecast
    goods_forecast_context: Optional[Dict[str, Any]] = None
    
    last_sync: str
    validation_status: str

class CrossSystemCorrelationScenario(BaseModel):
    """
    Demonstration scenario proving multi-source operational convergence:
    TMS + SMMS + TDMS maintenance tasks on the same corridor/section and window,
    correlated with COA corridor availability, Timetable movement paths, and Goods Forecast.
    """
    scenario_id: str
    scenario_name: str
    corridor_id: str
    section_id: str
    line_or_road: str
    time_window_str: str
    start_minute: int
    end_minute: int
    tms_task: UnifiedMaintenanceTask
    smms_task: UnifiedMaintenanceTask
    tdms_task: UnifiedMaintenanceTask
    coa_window: COACorridorAvailability
    timetable_trains: List[IntegratedTimetablePath]
    goods_forecast: GoodsTrainForecast
    description: str
