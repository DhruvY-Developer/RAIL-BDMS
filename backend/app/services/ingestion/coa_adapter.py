"""
Rail-BDMS: COA Source Adapter (Control Office Application)
Ingests Corridor Block Availability, available possession windows, line road designations, and operational restrictions.
"""
from typing import List, Dict, Any, Tuple
from datetime import datetime, timedelta, timezone

from backend.app.schemas.schemas import SourceSystemEnum, LineOrRoadEnum
from backend.app.schemas.integration import COACorridorAvailability
from backend.app.services.ingestion.base_adapter import BaseSourceAdapter
from backend.app.services.ingestion.mock_data import SECTIONS

class COAAdapter(BaseSourceAdapter):
    def __init__(self):
        super().__init__(
            source_id="COA",
            source_name="Control Office Application (COA)",
            department="Operating / Traffic Control (COA)",
            description="Official Section Corridor Block Availability, Shadow Possession Windows & Operational Restrictions"
        )

    def fetch_raw(self) -> List[Dict[str, Any]]:
        raw_list: List[Dict[str, Any]] = []
        base_dt = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

        CANDIDATE_SLOTS = [
            {
                "slot_code": "NIGHT_MEGA",
                "start_m": 30, "end_m": 270,
                "label": "Night Mega Corridor (00:30 - 04:30)",
                "restrictions": ["SPEED_RESTRICTION_30KMH_ADJACENT", "OHE_ISOLATION_PERMITTED"],
                "possessions": []
            },
            {
                "slot_code": "MIDDAY_LULL",
                "start_m": 690, "end_m": 840,
                "label": "Mid-Day Traffic Lull (11:30 - 14:00)",
                "restrictions": ["NO_ADJACENT_LINE_OCCUPATION"],
                "possessions": ["FREIGHT_CROSSOVER_TKD"]
            },
            {
                "slot_code": "EVENING_WINDOW",
                "start_m": 1290, "end_m": 1410,
                "label": "Late Evening Window (21:30 - 23:30)",
                "restrictions": ["PASSENGER_CLEARANCE_STRICT"],
                "possessions": []
            }
        ]

        idx = 101
        for sec in SECTIONS:
            for line in [LineOrRoadEnum.UP, LineOrRoadEnum.DOWN]:
                for slot in CANDIDATE_SLOTS:
                    s_dt = base_dt + timedelta(minutes=slot["start_m"])
                    e_dt = base_dt + timedelta(minutes=slot["end_m"])
                    raw_list.append({
                        "coa_block_id": f"COA-BLK-2026-{sec['id']}-{line.value}-{slot['slot_code']}",
                        "section_id": sec["id"],
                        "station_from": sec["from"],
                        "station_to": sec["to"],
                        "line_or_road": line.value,
                        "direction": "UP" if line == LineOrRoadEnum.UP else "DOWN",
                        "start_time": s_dt.isoformat(),
                        "end_time": e_dt.isoformat(),
                        "start_minute": slot["start_m"],
                        "end_minute": slot["end_m"],
                        "duration_minutes": slot["end_m"] - slot["start_m"],
                        "availability_status": "CONFIRMED",
                        "operational_restrictions": slot["restrictions"],
                        "existing_possessions": slot["possessions"],
                        "timetable_reference": "WTT-NR-2026-V2",
                        "source_last_updated": (datetime.now(timezone.utc) - timedelta(hours=4)).isoformat()
                    })
                    idx += 1

        return raw_list

    def normalize(self, raw_data: List[Dict[str, Any]]) -> List[COACorridorAvailability]:
        normalized: List[COACorridorAvailability] = []
        now = datetime.now(timezone.utc)

        for r in raw_data:
            window = COACorridorAvailability(
                source_system=SourceSystemEnum.COA,
                coa_block_id=r["coa_block_id"],
                section_id=r["section_id"],
                line_or_road=LineOrRoadEnum(r["line_or_road"]),
                window_start=r["start_time"],
                window_end=r["end_time"],
                start_minute=r["start_minute"],
                end_minute=r["end_minute"],
                available_duration_min=r["duration_minutes"],
                allowed_block_type="MULTI_DEPARTMENT",
                timetable_version=r["timetable_reference"],
                direction=r["direction"],
                availability_status=r["availability_status"],
                affected_section=f"{r['section_id']} ({r['line_or_road']} Line, {r['station_from']} to {r['station_to']})",
                station_limits=f"{r['station_from']} - {r['station_to']}",
                existing_possessions=r["existing_possessions"],
                operational_restrictions=r["operational_restrictions"],
                last_sync=now.isoformat(),
                validation_status="VALID"
            )
            normalized.append(window)

        return normalized

    def validate(self, normalized_records: List[COACorridorAvailability]) -> Tuple[List[COACorridorAvailability], List[Dict[str, Any]]]:
        valid_records: List[COACorridorAvailability] = []
        issues: List[Dict[str, Any]] = []

        for win in normalized_records:
            win_issues = []
            if win.available_duration_min <= 0:
                win_issues.append("Invalid duration <= 0")
            if win.start_minute >= win.end_minute:
                win_issues.append("Start minute must be strictly before end minute")
            if not win.section_id:
                win_issues.append("Missing section identifier")

            if win_issues:
                issues.append({
                    "coa_block_id": win.coa_block_id,
                    "source": "COA",
                    "issues": win_issues
                })
            valid_records.append(win)

        return valid_records, issues
