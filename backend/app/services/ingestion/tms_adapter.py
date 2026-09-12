"""
Rail-BDMS: TMS Source Adapter (Track Management System)
Ingests Track Maintenance, ultrasonic rail flaws (IMR), tamping, and P-Way engineering demands.
"""
from typing import List, Dict, Any, Tuple
from datetime import datetime, timedelta, timezone
import random

from backend.app.schemas.schemas import (
    CanonicalAsset, SourceSystemEnum, DepartmentEnum,
    SafetyClassEnum, MachineTypeEnum, TaskStatusEnum, LineOrRoadEnum,
    RawAssetDemand
)
from backend.app.schemas.integration import UnifiedMaintenanceTask
from backend.app.services.ingestion.base_adapter import BaseSourceAdapter
from backend.app.services.identity.resolver import AssetIdentityResolver

class TMSAdapter(BaseSourceAdapter):
    def __init__(self, canonical_assets: List[CanonicalAsset], identity_resolver: Any = None):
        super().__init__(
            source_id="TMS",
            source_name="Track Management System (TMS)",
            department="Civil Engineering / Permanent Way (P-Way)",
            description="Official Civil Track Infrastructure, IMR Rail Flaws & Heavy Machine Demands"
        )
        self.canonical_assets = [a for a in canonical_assets if a.department == DepartmentEnum.ENGINEERING]
        self.all_assets = canonical_assets
        self.identity_resolver = identity_resolver if identity_resolver else AssetIdentityResolver(canonical_assets)

    def fetch_raw(self) -> List[Dict[str, Any]]:
        """
        Extracts raw maintenance work orders and defect logs from TMS feed.
        """
        raw_list: List[Dict[str, Any]] = []
        now = datetime.now(timezone.utc)
        
        TEMPLATES = [
            {
                "type": "IMR_RAIL_FRACTURE_REPAIR",
                "defect_code": "IMR-WELD-FLAW",
                "desc": "Urgent IMR ultrasonic rail weld flaw renewal & fishplate clamping",
                "severity": "SAFETY_CRITICAL",
                "dur": 120, "min_dur": 90, "max_dur": 150,
                "machine": "NONE",
                "power_isolation": False, "sig_disconnect": False
            },
            {
                "type": "PLAIN_TRACK_TAMPING_CSM",
                "defect_code": "TRACK-GEOMETRY-TWIST",
                "desc": "Continuous Action Tamping Machine (CSM) track lifting & lining",
                "severity": "OPERATIONAL_DEFECT",
                "dur": 180, "min_dur": 120, "max_dur": 240,
                "machine": "CSM",
                "power_isolation": False, "sig_disconnect": False
            },
            {
                "type": "DEEP_SCREENING_BCM",
                "defect_code": "CUSHION-DIRT-BALLAST",
                "desc": "Ballast Cleaning Machine (BCM) shoulder and trackbed deep screening",
                "severity": "ROUTINE",
                "dur": 240, "min_dur": 180, "max_dur": 300,
                "machine": "BCM",
                "power_isolation": True, "sig_disconnect": True
            },
            {
                "type": "TURNOUT_PACKING_UNIMAT",
                "defect_code": "TURNOUT-WEAR",
                "desc": "Points and crossing tamping & packing by UNIMAT-4S machine",
                "severity": "SAFETY_CRITICAL",
                "dur": 150, "min_dur": 120, "max_dur": 180,
                "machine": "UNIMAT",
                "power_isolation": False, "sig_disconnect": True
            }
        ]

        idx = 1001
        anchor_created = False
        for asset in self.canonical_assets:
            # Anchor showcase scenario for TKD-FDB DOWN Line
            if not anchor_created and asset.section_id == "TKD-FDB" and asset.line_or_road == LineOrRoadEnum.DOWN:
                anchor_created = True
                wo_num = "TMS-WO-1842"
                defect_id = "TMS-DEF-IMR-WELD-1842"
                task_type = "IMR_RAIL_FRACTURE_REPAIR"
                desc = "Urgent IMR ultrasonic rail weld flaw renewal & fishplate clamping at km 18.5"
                severity = "SAFETY_CRITICAL"
                dur, min_dur, max_dur = 120, 90, 150
                machine = "NONE"
                power_iso, sig_disc = False, False
                due_dt = now - timedelta(days=2) # Overdue by 2 days
                created_dt = now - timedelta(days=7)
            else:
                tmpl = random.choice(TEMPLATES)
                wo_num = f"TMS-WO-{idx}"
                defect_id = f"TMS-DEF-{tmpl['defect_code']}-{idx}"
                task_type = tmpl["type"]
                desc = tmpl["desc"]
                severity = tmpl["severity"]
                dur, min_dur, max_dur = tmpl["dur"], tmpl["min_dur"], tmpl["max_dur"]
                machine = tmpl["machine"]
                power_iso, sig_disc = tmpl["power_isolation"], tmpl["sig_disconnect"]
                due_days = random.choice([-5, -3, -1, 0, 1, 2, 4, 6, 8, 12, 16, 21, 27])
                due_dt = now + timedelta(days=due_days)
                created_dt = now - timedelta(days=random.randint(5, 30))

            raw_list.append({
                "source_system": "TMS",
                "work_order_number": wo_num,
                "defect_id": defect_id,
                "source_asset_id": asset.source_asset_id,
                "internal_asset_uuid": asset.asset_id,
                "section_id": asset.section_id,
                "line_or_road": asset.line_or_road.value,
                "chainage_from": asset.chainage_from,
                "chainage_to": asset.chainage_to,
                "task_type": task_type,
                "defect_description": desc,
                "severity": severity,
                "created_timestamp": created_dt.isoformat(),
                "due_date": due_dt.isoformat(),
                "latest_completion_date": (due_dt + timedelta(days=5)).isoformat(),
                "planned_duration_minutes": dur,
                "min_duration_minutes": min_dur,
                "max_duration_minutes": max_dur,
                "machine_type": machine,
                "traction_power_isolation": power_iso,
                "signal_disconnection": sig_disc,
                "crew_type": "P_WAY_GANG_04",
                "work_status": "PENDING",
                "source_last_updated": (now - timedelta(hours=random.randint(1, 48))).isoformat()
            })
            idx += 1

        # Unresolved candidate to demonstrate boundary exception handling (Section 9 & Checklist F)
        raw_list.append({
            "source_system": "TMS",
            "work_order_number": "TMS-WO-9991",
            "defect_id": "TMS-DEF-IMR-UNMAPPED-99",
            "source_asset_id": "UNMAPPED-PWAY-SEGMENT-99",
            "internal_asset_uuid": None,
            "section_id": "UNKNOWN_SECTION",
            "line_or_road": "DOWN",
            "chainage_from": 999.0,
            "chainage_to": 999.5,
            "task_type": "IMR_RAIL_FRACTURE_REPAIR",
            "defect_description": "Unmapped yard turnout weld defect [FLAGGED: Unresolved Identity]",
            "severity": "SAFETY_CRITICAL",
            "created_timestamp": (now - timedelta(days=10)).isoformat(),
            "due_date": (now - timedelta(days=1)).isoformat(),
            "latest_completion_date": (now + timedelta(days=2)).isoformat(),
            "planned_duration_minutes": 120,
            "min_duration_minutes": 90,
            "max_duration_minutes": 150,
            "machine_type": "NONE",
            "traction_power_isolation": False,
            "signal_disconnection": False,
            "crew_type": "P_WAY_GANG_04",
            "work_status": "UNRESOLVED_IDENTITY",
            "source_last_updated": (now - timedelta(hours=6)).isoformat(),
            "requires_verification": True
        })

        return raw_list

    def normalize(self, raw_data: List[Dict[str, Any]]) -> List[UnifiedMaintenanceTask]:
        """
        Normalizes raw TMS work orders into UnifiedMaintenanceTask models and executes
        deterministic 4-Tier Asset Identity Resolution.
        """
        normalized: List[UnifiedMaintenanceTask] = []
        now = datetime.now(timezone.utc)

        for r in raw_data:
            due_dt = datetime.fromisoformat(r["due_date"])
            overdue_days = max(0, (now - due_dt).days)

            machine = getattr(MachineTypeEnum, r.get("machine_type", "NONE"), MachineTypeEnum.NONE)
            safety = getattr(SafetyClassEnum, r.get("severity", "ROUTINE"), SafetyClassEnum.ROUTINE)
            line_enum = LineOrRoadEnum(r["line_or_road"]) if r["line_or_road"] in LineOrRoadEnum._value2member_map_ else LineOrRoadEnum.DOWN

            # Run 4-Tier Asset Identity Resolution
            raw_demand = RawAssetDemand(
                source_system=SourceSystemEnum.TMS,
                source_asset_id=r["source_asset_id"],
                raw_reference=r["source_asset_id"],
                department=DepartmentEnum.ENGINEERING,
                section_id=r.get("section_id", "NZM-OKA"),
                line_or_road=line_enum,
                chainage_from=r.get("chainage_from"),
                chainage_to=r.get("chainage_to")
            )
            resolution = self.identity_resolver.resolve_demand(raw_demand)

            resolved_asset_id = resolution.resolved_asset_id or r.get("internal_asset_uuid") or "UNRESOLVED"
            asset_type_val = resolution.canonical_asset.asset_type.value if resolution.canonical_asset else "TRACK_SEGMENT"
            location_str = f"{r['section_id']} ({line_enum.value} Line, km {r.get('chainage_from', 0)} - {r.get('chainage_to', 0)})"

            val_status = "VALID"
            val_flags: List[str] = []

            if resolution.requires_human_reconciliation or resolved_asset_id == "UNRESOLVED":
                val_status = "NEEDS_REVIEW"
                val_flags.append(f"Unresolved Asset Identity ({resolution.rationale})")
            if r.get("requires_verification"):
                val_status = "NEEDS_REVIEW"
                val_flags.append("Marked for field survey reconciliation")

            task = UnifiedMaintenanceTask(
                source_system=SourceSystemEnum.TMS,
                source_task_id=r["work_order_number"],
                asset_id=resolved_asset_id,
                department=DepartmentEnum.ENGINEERING,
                task_type=r["task_type"],
                description=f"{r['defect_description']} at {r['section_id']} ({r['line_or_road']} Line, km {r['chainage_from']})",
                created_at=r["created_timestamp"],
                due_at=r["due_date"],
                latest_completion_date=r["latest_completion_date"],
                estimated_duration_min=r["planned_duration_minutes"],
                min_duration_min=r["min_duration_minutes"],
                max_duration_min=r["max_duration_minutes"],
                requires_traffic_block=True,
                requires_ohe_isolation=r["traction_power_isolation"],
                requires_signal_disconnection=r["signal_disconnection"],
                requires_line_occupation=True,
                required_crew_type=r["crew_type"],
                required_machine_type=machine,
                safety_class=safety,
                status=TaskStatusEnum.UNRESOLVED_IDENTITY if resolved_asset_id == "UNRESOLVED" else TaskStatusEnum.PENDING,
                
                # Unified Maintenance Attributes
                unified_task_id=f"UMT-{r['work_order_number'].replace('TMS-WO-', 'TMS-')}",
                defect_id=r["defect_id"],
                defect_description=r["defect_description"],
                defect_severity=r["severity"],
                maintenance_type=r["task_type"],
                overdue_duration_days=overdue_days,
                section_id=r["section_id"],
                line_or_road=line_enum,
                chainage_from=r["chainage_from"],
                chainage_to=r["chainage_to"],
                location=location_str,
                asset_type=asset_type_val,
                original_asset_source_id=r["source_asset_id"],
                resolution_tier=resolution.matched_tier,
                resolution_confidence=resolution.confidence_score,
                source_updated_at=r["source_last_updated"],
                last_sync=now.isoformat(),
                validation_status=val_status,
                validation_flags=val_flags
            )
            normalized.append(task)

        return normalized

    def validate(self, normalized_records: List[UnifiedMaintenanceTask]) -> Tuple[List[UnifiedMaintenanceTask], List[Dict[str, Any]]]:
        """
        Validates completeness, positive durations, boundary constraints, and flags anomalies.
        """
        valid_records: List[UnifiedMaintenanceTask] = []
        issues: List[Dict[str, Any]] = []

        for task in normalized_records:
            task_issues = []
            if not task.asset_id or task.asset_id == "UNRESOLVED":
                task_issues.append("Unresolved Asset Identity reference")
            if task.estimated_duration_min <= 0:
                task_issues.append("Invalid estimated duration <= 0")
            if not task.due_at:
                task_issues.append("Missing due date")
            if not task.source_task_id:
                task_issues.append("Missing Source Task ID")
            if task.validation_status == "NEEDS_REVIEW":
                task_issues.extend(task.validation_flags)

            if task_issues:
                issues.append({
                    "task_id": task.source_task_id,
                    "source": "TMS",
                    "issues": list(set(task_issues))
                })
            valid_records.append(task)

        return valid_records, issues
