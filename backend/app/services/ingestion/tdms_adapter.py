"""
Rail-BDMS: TDMS Source Adapter (Traction Distribution Management System)
Ingests Electrical Traction (TRD) maintenance, OHE cantilevers, section insulators, and 25kV power block isolations.
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

class TDMSAdapter(BaseSourceAdapter):
    def __init__(self, canonical_assets: List[CanonicalAsset], identity_resolver: Any = None):
        super().__init__(
            source_id="TDMS",
            source_name="Traction Distribution Management System (TDMS)",
            department="Traction Distribution / Electrical (TRD)",
            description="25kV Overhead Equipment (OHE), Cantilevers, Section Insulators & Tower Wagon Demands"
        )
        self.canonical_assets = [a for a in canonical_assets if a.department == DepartmentEnum.TRD]
        self.all_assets = canonical_assets
        self.identity_resolver = identity_resolver if identity_resolver else AssetIdentityResolver(canonical_assets)

    def fetch_raw(self) -> List[Dict[str, Any]]:
        raw_list: List[Dict[str, Any]] = []
        now = datetime.now(timezone.utc)

        TEMPLATES = [
            {
                "type": "OHE_CANTILEVER_ADJUSTMENT",
                "defect_code": "OHE-STAGGER-DEFECT",
                "desc": "OHE cantilever stagger, contact wire height & dropper adjustment by Tower Wagon",
                "severity": "OPERATIONAL_DEFECT",
                "dur": 150, "min_dur": 120, "max_dur": 180,
                "machine": "TOWER_WAGON",
                "power_isolation": True, "sig_disconnect": False
            },
            {
                "type": "SECTION_INSULATOR_OVERHAUL",
                "defect_code": "SEC-INS-ARC-TRAP",
                "desc": "OHE section insulator runners replacement & arc-trap clearance check",
                "severity": "SAFETY_CRITICAL",
                "dur": 120, "min_dur": 90, "max_dur": 150,
                "machine": "NONE",
                "power_isolation": True, "sig_disconnect": False
            },
            {
                "type": "ANNUAL_OHE_POWER_BLOCK",
                "defect_code": "ANNUAL-25KV-ISOLATION",
                "desc": "Annual 25kV traction power isolation, jumper tightening & neutral section check",
                "severity": "ROUTINE",
                "dur": 180, "min_dur": 120, "max_dur": 240,
                "machine": "TOWER_WAGON",
                "power_isolation": True, "sig_disconnect": False
            }
        ]

        idx = 3001
        anchor_created = False
        for asset in self.canonical_assets:
            # Anchor showcase scenario for Mast MAST-TKD-FDB-DOWN-10
            if not anchor_created and asset.section_id == "TKD-FDB" and asset.line_or_road == LineOrRoadEnum.DOWN:
                anchor_created = True
                wo_num = "TDMS-WO-1842"
                defect_id = "TDMS-DEF-OHE-STAGGER-1842"
                task_type = "OHE_CANTILEVER_ADJUSTMENT"
                desc = "OHE cantilever stagger, contact wire height & dropper adjustment at Mast TKD-FDB-DOWN-10"
                severity = "SAFETY_CRITICAL"
                dur, min_dur, max_dur = 150, 120, 180
                machine = "TOWER_WAGON"
                power_iso = True
                due_dt = now + timedelta(days=1)
                created_dt = now - timedelta(days=4)
            else:
                tmpl = random.choice(TEMPLATES)
                wo_num = f"TDMS-WO-{idx}"
                defect_id = f"TDMS-DEF-{tmpl['defect_code']}-{idx}"
                task_type = tmpl["type"]
                desc = tmpl["desc"]
                severity = tmpl["severity"]
                dur, min_dur, max_dur = tmpl["dur"], tmpl["min_dur"], tmpl["max_dur"]
                machine = tmpl["machine"]
                power_iso = tmpl["power_isolation"]
                due_days = random.choice([-3, -1, 0, 2, 4, 6, 8, 11, 14, 18, 23, 29])
                due_dt = now + timedelta(days=due_days)
                created_dt = now - timedelta(days=random.randint(3, 25))

            raw_list.append({
                "source_system": "TDMS",
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
                "latest_completion_date": (due_dt + timedelta(days=7)).isoformat(),
                "planned_duration_minutes": dur,
                "min_duration_minutes": min_dur,
                "max_duration_minutes": max_dur,
                "machine_type": machine,
                "traction_power_isolation": power_iso,
                "signal_disconnection": False,
                "crew_type": "TRD_POWER_CREW_01",
                "work_status": "PENDING",
                "source_last_updated": (now - timedelta(hours=random.randint(2, 40))).isoformat()
            })
            idx += 1

        return raw_list

    def normalize(self, raw_data: List[Dict[str, Any]]) -> List[UnifiedMaintenanceTask]:
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
                source_system=SourceSystemEnum.TDMS,
                source_asset_id=r["source_asset_id"],
                raw_reference=r["source_asset_id"],
                department=DepartmentEnum.TRD,
                section_id=r.get("section_id", "NZM-OKA"),
                line_or_road=line_enum,
                chainage_from=r.get("chainage_from"),
                chainage_to=r.get("chainage_to")
            )
            resolution = self.identity_resolver.resolve_demand(raw_demand)

            resolved_asset_id = resolution.resolved_asset_id or r.get("internal_asset_uuid") or "UNRESOLVED"
            asset_type_val = resolution.canonical_asset.asset_type.value if resolution.canonical_asset else "OHE_MAST"
            location_str = f"{r['section_id']} (Mast {r['source_asset_id']})"

            val_status = "VALID"
            val_flags: List[str] = []
            if resolution.requires_human_reconciliation or resolved_asset_id == "UNRESOLVED":
                val_status = "NEEDS_REVIEW"
                val_flags.append(f"Unresolved Asset Identity ({resolution.rationale})")

            task = UnifiedMaintenanceTask(
                source_system=SourceSystemEnum.TDMS,
                source_task_id=r["work_order_number"],
                asset_id=resolved_asset_id,
                department=DepartmentEnum.TRD,
                task_type=r["task_type"],
                description=f"{r['defect_description']} at {r['section_id']} (Mast {r['source_asset_id']})",
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
                unified_task_id=f"UMT-{r['work_order_number'].replace('TDMS-WO-', 'TDMS-')}",
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
        valid_records: List[UnifiedMaintenanceTask] = []
        issues: List[Dict[str, Any]] = []

        for task in normalized_records:
            task_issues = []
            if not task.asset_id or task.asset_id == "UNRESOLVED":
                task_issues.append("Unresolved Asset Identity")
            if not task.requires_ohe_isolation:
                task_issues.append("TRD task unflagged for 25kV power isolation")
            if task.estimated_duration_min <= 0:
                task_issues.append("Invalid duration <= 0")
            if not task.source_task_id:
                task_issues.append("Missing Source Task ID")
            if task.validation_status == "NEEDS_REVIEW":
                task_issues.extend(task.validation_flags)

            if task_issues:
                issues.append({
                    "task_id": task.source_task_id,
                    "source": "TDMS",
                    "issues": list(set(task_issues))
                })
            valid_records.append(task)

        return valid_records, issues
