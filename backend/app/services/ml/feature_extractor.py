"""
Rail-BDMS AI/ML Feature Engineering & Preprocessing Engine (Requirement 2)
Extracts 17 structured domain features from maintenance tasks, assets,
WTT passenger timetables, and FOIS goods train forecasts.
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
import numpy as np

from backend.app.schemas.schemas import (
    MaintenanceTask, CanonicalAsset, SafetyClassEnum, DepartmentEnum,
    MachineTypeEnum, TrainMovement
)
from backend.app.schemas.integration import GoodsTrainForecast

FEATURE_NAMES = [
    "asset_type_enc",
    "department_enc",
    "route_class_enc",
    "criticality_class_enc",
    "defect_severity_score",
    "days_overdue",
    "days_until_due",
    "estimated_duration_min",
    "passenger_train_density",
    "goods_train_density",
    "total_traffic_exposure",
    "asset_availability_impact",
    "historical_maintenance_count",
    "historical_failure_count",
    "requires_ohe_isolation",
    "requires_signal_disconnection",
    "shadow_block_potential"
]

ASSET_TYPE_MAP = {
    "TRACK_SEGMENT": 0.0,
    "TURNOUT": 1.0,
    "CROSSOVER": 2.0,
    "POINT_MACHINE": 3.0,
    "SIGNAL": 4.0,
    "TRACK_CIRCUIT": 5.0,
    "AXLE_COUNTER": 6.0,
    "OHE_CANTILEVER": 7.0,
    "OHE_MAST": 8.0,
    "SECTION_INSULATOR": 9.0
}

DEPT_MAP = {
    DepartmentEnum.ENGINEERING: 0.0,
    DepartmentEnum.S_AND_T: 1.0,
    DepartmentEnum.TRD: 2.0,
    DepartmentEnum.OPERATING: 3.0
}

class FeatureExtractor:
    """
    Reproducible feature extraction pipeline for training and inference.
    """
    def __init__(self, canonical_assets: Optional[List[CanonicalAsset]] = None):
        self.asset_lookup: Dict[str, CanonicalAsset] = (
            {a.asset_id: a for a in canonical_assets} if canonical_assets else {}
        )

    def extract_features_dict(
        self,
        task: MaintenanceTask,
        asset: Optional[CanonicalAsset] = None,
        trains: Optional[List[TrainMovement]] = None,
        goods_forecasts: Optional[List[GoodsTrainForecast]] = None,
        all_tasks: Optional[List[MaintenanceTask]] = None,
        simulated_now: Optional[datetime] = None
    ) -> Dict[str, float]:
        """
        Extracts 17 numerical/encoded features as a dictionary.
        Handles missing assets, unknown categories, and cold-start safely.
        """
        now = simulated_now or datetime.now(timezone.utc)
        target_asset = asset or self.asset_lookup.get(task.asset_id)

        # 1. Asset Type Encoding
        asset_type_str = ""
        if target_asset:
            asset_type_str = str(target_asset.asset_type.value if hasattr(target_asset.asset_type, "value") else target_asset.asset_type)
        elif hasattr(task, "asset_type") and getattr(task, "asset_type"):
            asset_type_str = str(getattr(task, "asset_type"))
        else:
            # Infer from task type or department
            if "POINT_MACHINE" in task.task_type:
                asset_type_str = "POINT_MACHINE"
            elif "CANTILEVER" in task.task_type or "MAST" in task.task_type:
                asset_type_str = "OHE_CANTILEVER"
            else:
                asset_type_str = "TRACK_SEGMENT"

        asset_type_enc = ASSET_TYPE_MAP.get(asset_type_str, 10.0)

        # 2. Department Encoding
        dept_val = task.department.value if hasattr(task.department, "value") else str(task.department)
        dept_enc = DEPT_MAP.get(task.department, 0.0)

        # 3. Route Class Encoding (HDN=2, HUN=1, Branch/Other=0)
        route_class = target_asset.route_class if target_asset else "HDN"
        if route_class == "HDN":
            route_class_enc = 2.0
        elif route_class == "HUN":
            route_class_enc = 1.0
        else:
            route_class_enc = 0.0

        # 4. Criticality Class Encoding (CLASS_A=3, CLASS_B=2, CLASS_C=1)
        crit_class = target_asset.criticality_class if target_asset else "CLASS_A"
        if crit_class == "CLASS_A":
            crit_class_enc = 3.0
        elif crit_class == "CLASS_B":
            crit_class_enc = 2.0
        else:
            crit_class_enc = 1.0

        # 5. Defect Severity Score (0.0 to 1.0)
        defect_sev = getattr(task, "defect_severity", None)
        task_desc = (task.description or "").upper()
        task_type = (task.task_type or "").upper()
        
        if defect_sev == "CRITICAL_IMR" or "IMR" in task_type or "IMR" in task_desc or "FRACTURE" in task_desc:
            defect_severity_score = 1.0
        elif defect_sev == "MAJOR" or task.safety_class == SafetyClassEnum.SAFETY_CRITICAL:
            defect_severity_score = 0.70
        elif "OBS" in task_type or "POINT_MACHINE" in task_type:
            defect_severity_score = 0.55
        else:
            defect_severity_score = 0.25

        # 6 & 7. Days Overdue & Days Until Due
        days_overdue = 0.0
        days_until_due = 7.0
        try:
            if hasattr(task, "overdue_duration_days") and getattr(task, "overdue_duration_days", 0) > 0:
                days_overdue = float(getattr(task, "overdue_duration_days"))
                days_until_due = 0.0
            elif task.due_at:
                # Parse ISO timestamp
                due_clean = task.due_at.replace("Z", "+00:00")
                due_dt = datetime.fromisoformat(due_clean)
                if due_dt.tzinfo is None:
                    due_dt = due_dt.replace(tzinfo=timezone.utc)
                diff_days = (now - due_dt).total_seconds() / 86400.0
                if diff_days > 0:
                    days_overdue = round(diff_days, 1)
                    days_until_due = 0.0
                else:
                    days_until_due = round(abs(diff_days), 1)
                    days_overdue = 0.0
        except Exception:
            days_overdue = 0.0
            days_until_due = 3.0

        # 8. Estimated Duration Minutes
        estimated_duration_min = float(task.estimated_duration_min or 120)

        # 9. Passenger Train Density (from integrated Timetable WTT)
        task_section = (
            getattr(task, "section_id", None)
            or (target_asset.section_id if target_asset else "TKD-FDB")
        )
        task_line = (
            str(getattr(task, "line_or_road", "") or (target_asset.line_or_road if target_asset else "DOWN"))
        )

        passenger_density = 0.0
        if trains:
            # Count trains scheduled on this section and line
            sec_trains = [
                tr for tr in trains
                if tr.section_id == task_section
                and (not task_line or task_line == "BOTH" or str(tr.line_or_road) == task_line)
            ]
            passenger_density = float(len(sec_trains))
        else:
            # Default density benchmark for Delhi HDN corridor
            passenger_density = 28.0

        # 10. Goods Train Density (from integrated FOIS forecast)
        goods_density = 0.0
        if goods_forecasts:
            sec_goods = [
                gf for gf in goods_forecasts
                if gf.section_id == task_section
            ]
            goods_density = float(sum(gf.expected_goods_train_count for gf in sec_goods))
        else:
            goods_density = 4.0

        # 11. Total Traffic Exposure
        total_traffic_exposure = round(passenger_density * 1.0 + goods_density * 1.5, 1)

        # 12. Asset Availability Impact (0 to 100)
        # Higher if route is HDN, line is main/DOWN/UP, duration is long, and defect is severe
        avail_impact = 35.0
        if route_class_enc == 2.0:
            avail_impact += 25.0
        elif route_class_enc == 1.0:
            avail_impact += 15.0
            
        if crit_class_enc == 3.0:
            avail_impact += 15.0
            
        if estimated_duration_min >= 180:
            avail_impact += 15.0
        elif estimated_duration_min >= 120:
            avail_impact += 10.0
            
        if defect_severity_score >= 0.8:
            avail_impact += 10.0

        asset_availability_impact = min(100.0, max(10.0, avail_impact))

        # 13 & 14. Historical Maintenance & Failure Count
        # Based on realistic railway asset degradation baselines
        hist_maint_count = 4.0
        hist_fail_count = 0.0
        if asset_type_str in ["TRACK_SEGMENT", "TURNOUT"]:
            hist_maint_count = 8.0
            hist_fail_count = 1.0 if defect_severity_score > 0.5 else 0.0
        elif asset_type_str == "POINT_MACHINE":
            hist_maint_count = 6.0
            hist_fail_count = 1.0
        elif asset_type_str in ["OHE_CANTILEVER", "SECTION_INSULATOR"]:
            hist_maint_count = 5.0
            hist_fail_count = 0.0

        if days_overdue > 7:
            hist_fail_count += 1.0

        # 15 & 16. Power Isolation & Signalling Disconnection
        requires_ohe = 1.0 if task.requires_ohe_isolation else 0.0
        requires_sig = 1.0 if task.requires_signal_disconnection else 0.0

        # 17. Shadow Block Potential (0 to 100)
        shadow_pot = 30.0
        if all_tasks:
            same_loc = [
                t for t in all_tasks
                if t.task_id != task.task_id
                and getattr(t, "section_id", None) == task_section
            ]
            other_depts = set(t.department for t in same_loc if t.department != task.department)
            if len(other_depts) >= 2:
                shadow_pot = 95.0
            elif len(other_depts) == 1:
                shadow_pot = 75.0
            elif len(same_loc) > 0:
                shadow_pot = 50.0

        return {
            "asset_type_enc": asset_type_enc,
            "department_enc": dept_enc,
            "route_class_enc": route_class_enc,
            "criticality_class_enc": crit_class_enc,
            "defect_severity_score": defect_severity_score,
            "days_overdue": days_overdue,
            "days_until_due": days_until_due,
            "estimated_duration_min": estimated_duration_min,
            "passenger_train_density": passenger_density,
            "goods_train_density": goods_density,
            "total_traffic_exposure": total_traffic_exposure,
            "asset_availability_impact": asset_availability_impact,
            "historical_maintenance_count": hist_maint_count,
            "historical_failure_count": hist_fail_count,
            "requires_ohe_isolation": requires_ohe,
            "requires_signal_disconnection": requires_sig,
            "shadow_block_potential": shadow_pot
        }

    def extract_features_vector(
        self,
        task: MaintenanceTask,
        asset: Optional[CanonicalAsset] = None,
        trains: Optional[List[TrainMovement]] = None,
        goods_forecasts: Optional[List[GoodsTrainForecast]] = None,
        all_tasks: Optional[List[MaintenanceTask]] = None,
        simulated_now: Optional[datetime] = None
    ) -> np.ndarray:
        """
        Extracts features as a 1D numpy vector ordered by FEATURE_NAMES.
        """
        f_dict = self.extract_features_dict(
            task, asset, trains, goods_forecasts, all_tasks, simulated_now
        )
        return np.array([f_dict[k] for k in FEATURE_NAMES], dtype=np.float32)
