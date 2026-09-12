"""
Rail-BDMS: Train Working Timetable (WTT) Source Adapter
Ingests Train Schedules, arrival/departure timestamps, corridor path segments, and headway safety envelopes.
"""
from typing import List, Dict, Any, Tuple
from datetime import datetime, timedelta, timezone

from backend.app.schemas.schemas import LineOrRoadEnum, TrainTypeEnum
from backend.app.schemas.integration import IntegratedTimetablePath
from backend.app.services.ingestion.base_adapter import BaseSourceAdapter
from backend.app.services.ingestion.mock_data import SECTIONS

class TimetableAdapter(BaseSourceAdapter):
    def __init__(self):
        super().__init__(
            source_id="TIMETABLE",
            source_name="Train Working Time Table (WTT / Timetable)",
            department="Operating / Scheduling & Timetable Control",
            description="Official Published Working Time Table (WTT), Passenger Train Paths & Operational Headway Buffers"
        )

    def fetch_raw(self) -> List[Dict[str, Any]]:
        raw_list: List[Dict[str, Any]] = []
        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        TRAIN_TEMPLATES = [
            # Premium Passenger (Vande Bharat, Rajdhani, Shatabdi)
            {"num": "20171", "name": "Vande Bharat Express (NDLS-BPL)", "type": "PREMIUM_PASSENGER", "prio": 1, "speed": 130, "origin": "NDLS", "dest": "BPL", "line": "DOWN", "base_min": 360},
            {"num": "12952", "name": "Mumbai Rajdhani Express", "type": "PREMIUM_PASSENGER", "prio": 1, "speed": 130, "origin": "NDLS", "dest": "MMCT", "line": "DOWN", "base_min": 990},
            {"num": "12002", "name": "Bhopal Shatabdi Express", "type": "PREMIUM_PASSENGER", "prio": 1, "speed": 130, "origin": "NDLS", "dest": "RKMP", "line": "DOWN", "base_min": 375},
            {"num": "20172", "name": "Vande Bharat Express (BPL-NDLS)", "type": "PREMIUM_PASSENGER", "prio": 1, "speed": 130, "origin": "BPL", "dest": "NDLS", "line": "UP", "base_min": 1260},
            {"num": "12951", "name": "Mumbai Rajdhani Express (UP)", "type": "PREMIUM_PASSENGER", "prio": 1, "speed": 130, "origin": "MMCT", "dest": "NDLS", "line": "UP", "base_min": 510},
            
            # Express / Superfast Trains
            {"num": "12414", "name": "Pooja Superfast Express", "type": "EXPRESS", "prio": 2, "speed": 110, "origin": "JAT", "dest": "AII", "line": "DOWN", "base_min": 240},
            {"num": "12918", "name": "Gujarat Sampark Kranti", "type": "EXPRESS", "prio": 2, "speed": 110, "origin": "NZM", "dest": "ADI", "line": "DOWN", "base_min": 810},
            {"num": "12618", "name": "Mangala Lakshadweep SF", "type": "EXPRESS", "prio": 2, "speed": 110, "origin": "NZM", "dest": "ERS", "line": "DOWN", "base_min": 570},
            {"num": "12413", "name": "Pooja Superfast (UP)", "type": "EXPRESS", "prio": 2, "speed": 110, "origin": "AII", "dest": "JAT", "line": "UP", "base_min": 390},
            {"num": "12917", "name": "Gujarat Sampark Kranti (UP)", "type": "EXPRESS", "prio": 2, "speed": 110, "origin": "ADI", "dest": "NZM", "line": "UP", "base_min": 630},
            {"num": "12780", "name": "Goa Express (UP)", "type": "EXPRESS", "prio": 2, "speed": 110, "origin": "VSG", "dest": "NZM", "line": "UP", "base_min": 420},

            # Suburban Local (MEMU / EMU)
            {"num": "04408", "name": "Delhi - Palwal EMU", "type": "SUBURBAN", "prio": 3, "speed": 80, "origin": "NDLS", "dest": "PWL", "line": "DOWN", "base_min": 450},
            {"num": "04914", "name": "Ghaziabad - Palwal MEMU", "type": "SUBURBAN", "prio": 3, "speed": 80, "origin": "GZB", "dest": "PWL", "line": "DOWN", "base_min": 540},
            {"num": "04407", "name": "Palwal - Delhi EMU (UP)", "type": "SUBURBAN", "prio": 3, "speed": 80, "origin": "PWL", "dest": "NDLS", "line": "UP", "base_min": 480},
            {"num": "04913", "name": "Palwal - Ghaziabad MEMU (UP)", "type": "SUBURBAN", "prio": 3, "speed": 80, "origin": "PWL", "dest": "GZB", "line": "UP", "base_min": 570},

            # Scheduled Container Rakes
            {"num": "CONRAJ-91", "name": "Container Rajdhani High-Speed (TKD-MDPT)", "type": "CONTAINER_FREIGHT", "prio": 4, "speed": 100, "origin": "TKD", "dest": "MDPT", "line": "DOWN", "base_min": 720},
            {"num": "CONT-332", "name": "Inbound ICD Container (JNPT-TKD)", "type": "CONTAINER_FREIGHT", "prio": 4, "speed": 100, "origin": "PWL", "dest": "TKD", "line": "UP", "base_min": 1080}
        ]

        for t in TRAIN_TEMPLATES:
            base_time = t["base_min"]
            sec_list = SECTIONS if t["line"] == "DOWN" else list(reversed(SECTIONS))
            curr_time = base_time

            for sec in sec_list:
                km_dist = abs(sec["end_km"] - sec["start_km"])
                transit_min = max(4, int(round((km_dist / t["speed"]) * 60)))
                entry_m = curr_time
                exit_m = curr_time + transit_min

                s_dt = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(minutes=entry_m)
                e_dt = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(minutes=exit_m)

                raw_list.append({
                    "train_number": t["num"],
                    "train_name": t["name"],
                    "service_date": today_str,
                    "train_type": t["type"],
                    "origin": t["origin"],
                    "destination": t["dest"],
                    "section_id": sec["id"],
                    "line_or_road": t["line"],
                    "planned_entry": s_dt.isoformat(),
                    "planned_exit": e_dt.isoformat(),
                    "entry_minute": entry_m,
                    "exit_minute": exit_m,
                    "min_clearance_before_min": 15,
                    "min_clearance_after_min": 15,
                    "priority_class": t["prio"],
                    "speed_kmh": t["speed"],
                    "source_system": "TIMETABLE_WTT",
                    "timetable_edition": "WTT-NR-2026-V2"
                })

                curr_time += transit_min + 2

        return raw_list

    def normalize(self, raw_data: List[Dict[str, Any]]) -> List[IntegratedTimetablePath]:
        normalized: List[IntegratedTimetablePath] = []
        now = datetime.now(timezone.utc)

        for r in raw_data:
            tr_type = getattr(TrainTypeEnum, r["train_type"], TrainTypeEnum.EXPRESS)
            line = getattr(LineOrRoadEnum, r["line_or_road"], LineOrRoadEnum.DOWN)

            path = IntegratedTimetablePath(
                train_number=r["train_number"],
                train_name=r["train_name"],
                service_date=r["service_date"],
                train_type=tr_type,
                origin=r["origin"],
                destination=r["destination"],
                section_id=r["section_id"],
                line_or_road=line,
                planned_entry=r["planned_entry"],
                planned_exit=r["planned_exit"],
                entry_minute=r["entry_minute"],
                exit_minute=r["exit_minute"],
                min_clearance_before_min=r["min_clearance_before_min"],
                min_clearance_after_min=r["min_clearance_after_min"],
                priority_class=r["priority_class"],
                speed_kmh=r["speed_kmh"],
                source_system="TIMETABLE_WTT",
                train_category="PREMIUM" if r["priority_class"] == 1 else ("SUBURBAN" if r["priority_class"] == 3 else "EXPRESS"),
                headway_buffer_min=15,
                last_sync=now.isoformat(),
                validation_status="VALID"
            )
            normalized.append(path)

        return normalized

    def validate(self, normalized_records: List[IntegratedTimetablePath]) -> Tuple[List[IntegratedTimetablePath], List[Dict[str, Any]]]:
        valid_records: List[IntegratedTimetablePath] = []
        issues: List[Dict[str, Any]] = []

        for p in normalized_records:
            p_issues = []
            if p.exit_minute <= p.entry_minute:
                p_issues.append("Train exit minute must exceed entry minute")
            if p.min_clearance_before_min < 10 or p.min_clearance_after_min < 10:
                p_issues.append("Headway safety margin below Indian Railways standard 10m threshold")

            if p_issues:
                issues.append({
                    "train_number": p.train_number,
                    "section": p.section_id,
                    "source": "TIMETABLE",
                    "issues": p_issues
                })
            valid_records.append(p)

        return valid_records, issues
