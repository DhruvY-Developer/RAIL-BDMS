"""
Rail-BDMS: Realistic Indian Railways Synthetic Data Generator
Corridor: Northern Railway Delhi Division (NZM - PWL - RDI HDN Section)
"""
import uuid
import random
from typing import List, Dict, Tuple
from datetime import datetime, timedelta, timezone
from backend.app.schemas.schemas import (
    CanonicalAsset, MaintenanceTask, TrainMovement, CorridorWindow,
    DepartmentEnum, SourceSystemEnum, AssetTypeEnum, LineOrRoadEnum,
    SafetyClassEnum, MachineTypeEnum, TaskStatusEnum, TrainTypeEnum,
    RawAssetDemand
)

STATIONS = [
    {"code": "NDLS", "name": "New Delhi", "km": 0.000, "lat": 28.6428, "lon": 77.2197},
    {"code": "NZM", "name": "Hazrat Nizamuddin", "km": 7.100, "lat": 28.5892, "lon": 77.2530},
    {"code": "OKA", "name": "Okhla", "km": 11.200, "lat": 28.5583, "lon": 77.2728},
    {"code": "TKD", "name": "Tuglakabad Yard", "km": 17.500, "lat": 28.5085, "lon": 77.2910},
    {"code": "FDB", "name": "Faridabad", "km": 28.800, "lat": 28.4089, "lon": 77.3178},
    {"code": "FDN", "name": "Faridabad New Town", "km": 31.900, "lat": 28.3842, "lon": 77.3195},
    {"code": "BVH", "name": "Ballabgarh", "km": 36.400, "lat": 28.3412, "lon": 77.3245},
    {"code": "AST", "name": "Asaoti", "km": 46.200, "lat": 28.2562, "lon": 77.3298},
    {"code": "PWL", "name": "Palwal", "km": 57.800, "lat": 28.1487, "lon": 77.3325},
    {"code": "RDI", "name": "Rundhi", "km": 67.300, "lat": 28.0671, "lon": 77.3489},
]

SECTIONS = [
    {"id": "NZM-OKA", "from": "NZM", "to": "OKA", "start_km": 7.1, "end_km": 11.2},
    {"id": "OKA-TKD", "from": "OKA", "to": "TKD", "start_km": 11.2, "end_km": 17.5},
    {"id": "TKD-FDB", "from": "TKD", "to": "FDB", "start_km": 17.5, "end_km": 28.8},
    {"id": "FDB-FDN", "from": "FDB", "to": "FDN", "start_km": 28.8, "end_km": 31.9},
    {"id": "FDN-BVH", "from": "FDN", "to": "BVH", "start_km": 31.9, "end_km": 36.4},
    {"id": "BVH-AST", "from": "BVH", "to": "AST", "start_km": 36.4, "end_km": 46.2},
    {"id": "AST-PWL", "from": "AST", "to": "PWL", "start_km": 46.2, "end_km": 57.8},
    {"id": "PWL-RDI", "from": "PWL", "to": "RDI", "start_km": 57.8, "end_km": 67.3},
]

def generate_canonical_assets() -> List[CanonicalAsset]:
    assets: List[CanonicalAsset] = []
    
    # 1. Track Segments (TMS - Engineering)
    for sec in SECTIONS:
        for line in [LineOrRoadEnum.UP, LineOrRoadEnum.DOWN]:
            # Generate 2-3 segments per section
            km_span = sec["end_km"] - sec["start_km"]
            sub_spans = 2
            sub_len = km_span / sub_spans
            for i in range(sub_spans):
                s_km = round(sec["start_km"] + i * sub_len, 3)
                e_km = round(sec["start_km"] + (i + 1) * sub_len, 3)
                asset_id = f"TRK-{sec['id']}-{line.value}-S{i+1}"
                
                # Interpolate Lat/Lon
                from_stn = next(s for s in STATIONS if s["code"] == sec["from"])
                to_stn = next(s for s in STATIONS if s["code"] == sec["to"])
                frac = (i + 0.5) / sub_spans
                lat = round(from_stn["lat"] + frac * (to_stn["lat"] - from_stn["lat"]), 6)
                lon = round(from_stn["lon"] + frac * (to_stn["lon"] - from_stn["lon"]), 6)
                
                assets.append(CanonicalAsset(
                    source_system=SourceSystemEnum.TMS,
                    source_asset_id=asset_id,
                    asset_type=AssetTypeEnum.TRACK_SEGMENT,
                    department=DepartmentEnum.ENGINEERING,
                    section_id=sec["id"],
                    station_from=sec["from"],
                    station_to=sec["to"],
                    chainage_from=s_km,
                    chainage_to=e_km,
                    line_or_road=line,
                    route_class="HDN",
                    criticality_class="CLASS_A" if "TKD" in sec["id"] or "FDB" in sec["id"] else "CLASS_B",
                    latitude=lat,
                    longitude=lon,
                    status="OPERATIONAL",
                    last_inspected="2026-08-15"
                ))

    # 2. Turnouts & Point Machines (SMMS - S&T)
    for stn in STATIONS[1:]: # Stations with crossover yards
        for pt_num in ["101A", "102B", "105A", "108B"]:
            line = LineOrRoadEnum.UP if "A" in pt_num else LineOrRoadEnum.DOWN
            s_km = round(stn["km"] - 0.250 if "A" in pt_num else stn["km"] + 0.250, 3)
            sec_match = next((s for s in SECTIONS if s["from"] == stn["code"] or s["to"] == stn["code"]), SECTIONS[0])
            
            assets.append(CanonicalAsset(
                source_system=SourceSystemEnum.SMMS,
                source_asset_id=f"PT-{stn['code']}-{pt_num}",
                asset_type=AssetTypeEnum.TURNOUT,
                department=DepartmentEnum.S_AND_T,
                division="DELHI",
                section_id=sec_match["id"],
                station_from=stn["code"],
                station_to=sec_match["to"] if sec_match["from"] == stn["code"] else sec_match["from"],
                chainage_from=s_km,
                chainage_to=round(s_km + 0.080, 3),
                line_or_road=line,
                criticality_class="CLASS_A",
                latitude=stn["lat"],
                longitude=stn["lon"],
                status="OPERATIONAL"
            ))

    # 3. Signals (SMMS - S&T)
    for sec in SECTIONS:
        for line in [LineOrRoadEnum.UP, LineOrRoadEnum.DOWN]:
            sig_id = f"SIG-{sec['id']}-{line.value}-01"
            stn_ref = next(s for s in STATIONS if s["code"] == sec["from"])
            assets.append(CanonicalAsset(
                source_system=SourceSystemEnum.SMMS,
                source_asset_id=sig_id,
                asset_type=AssetTypeEnum.SIGNAL,
                department=DepartmentEnum.S_AND_T,
                division="DELHI",
                section_id=sec["id"],
                station_from=sec["from"],
                station_to=sec["to"],
                chainage_from=sec["start_km"] + 0.5,
                chainage_to=sec["start_km"] + 0.5,
                line_or_road=line,
                criticality_class="CLASS_A",
                latitude=stn_ref["lat"],
                longitude=stn_ref["lon"]
            ))

    # 4. OHE Masts & Cantilevers (TDMS - TRD)
    for sec in SECTIONS:
        for line in [LineOrRoadEnum.UP, LineOrRoadEnum.DOWN]:
            for mast_idx in [10, 25, 40]:
                mast_km = round(sec["start_km"] + (mast_idx / 50.0) * (sec["end_km"] - sec["start_km"]), 3)
                mast_id = f"MAST-{sec['id']}-{line.value}-{mast_idx}"
                from_stn = next(s for s in STATIONS if s["code"] == sec["from"])
                assets.append(CanonicalAsset(
                    source_system=SourceSystemEnum.TDMS,
                    source_asset_id=mast_id,
                    asset_type=AssetTypeEnum.OHE_MAST,
                    department=DepartmentEnum.TRD,
                    division="DELHI",
                    section_id=sec["id"],
                    station_from=sec["from"],
                    station_to=sec["to"],
                    chainage_from=mast_km,
                    chainage_to=mast_km,
                    line_or_road=line,
                    criticality_class="CLASS_B",
                    latitude=from_stn["lat"] + 0.005,
                    longitude=from_stn["lon"] + 0.003
                ))

    return assets

def generate_maintenance_tasks(assets: List[CanonicalAsset]) -> List[MaintenanceTask]:
    random.seed(42)
    tasks: List[MaintenanceTask] = []
    
    # Task Templates by Department
    tms_templates = [
        {"type": "IMR_RAIL_FRACTURE_REPAIR", "desc": "Urgent IMR ultrasonic rail weld flaw renewal & fishplate clamping", "dur": 120, "min_dur": 90, "max_dur": 150, "machine": MachineTypeEnum.NONE, "safety": SafetyClassEnum.SAFETY_CRITICAL, "power": False, "sig": False},
        {"type": "PLAIN_TRACK_TAMPING_CSM", "desc": "Continuous Action Tamping Machine (CSM) track lifting & lining", "dur": 180, "min_dur": 120, "max_dur": 240, "machine": MachineTypeEnum.CSM, "safety": SafetyClassEnum.OPERATIONAL_DEFECT, "power": False, "sig": False},
        {"type": "DEEP_SCREENING_BCM", "desc": "Ballast Cleaning Machine (BCM) shoulder and trackbed deep screening", "dur": 240, "min_dur": 180, "max_dur": 300, "machine": MachineTypeEnum.BCM, "safety": SafetyClassEnum.ROUTINE, "power": True, "sig": True},
        {"type": "TURNOUT_PACKING_UNIMAT", "desc": "Points and crossing tamping & packing by UNIMAT-4S machine", "dur": 150, "min_dur": 120, "max_dur": 180, "machine": MachineTypeEnum.UNIMAT, "safety": SafetyClassEnum.SAFETY_CRITICAL, "power": False, "sig": True},
    ]
    
    smms_templates = [
        {"type": "POINT_MACHINE_OVERHAUL", "desc": "Point machine 143mm stroke inspection, friction clutch test & motor brush change", "dur": 120, "min_dur": 90, "max_dur": 150, "machine": MachineTypeEnum.NONE, "safety": SafetyClassEnum.SAFETY_CRITICAL, "power": False, "sig": True},
        {"type": "SIGNAL_LED_REPLACEMENT", "desc": "Main line automatic aspect unit replacement & focusing check", "dur": 90, "min_dur": 60, "max_dur": 120, "machine": MachineTypeEnum.NONE, "safety": SafetyClassEnum.OPERATIONAL_DEFECT, "power": False, "sig": True},
        {"type": "AXLE_COUNTER_CALIBRATION", "desc": "Digital Axle Counter (DAC) track sensor voltage & phase adjustment", "dur": 120, "min_dur": 90, "max_dur": 150, "machine": MachineTypeEnum.NONE, "safety": SafetyClassEnum.SAFETY_CRITICAL, "power": False, "sig": True},
    ]
    
    tdms_templates = [
        {"type": "OHE_CANTILEVER_ADJUSTMENT", "desc": "OHE cantilever stagger, contact wire height & dropper adjustment by Tower Wagon", "dur": 150, "min_dur": 120, "max_dur": 180, "machine": MachineTypeEnum.TOWER_WAGON, "safety": SafetyClassEnum.OPERATIONAL_DEFECT, "power": True, "sig": False},
        {"type": "SECTION_INSULATOR_OVERHAUL", "desc": "OHE section insulator runners replacement & arc-trap clearance check", "dur": 120, "min_dur": 90, "max_dur": 150, "machine": MachineTypeEnum.NONE, "safety": SafetyClassEnum.SAFETY_CRITICAL, "power": True, "sig": False},
        {"type": "ANNUAL_OHE_POWER_BLOCK", "desc": "Annual 25kV traction power isolation, jumper tightening & neutral section check", "dur": 180, "min_dur": 120, "max_dur": 240, "machine": MachineTypeEnum.TOWER_WAGON, "safety": SafetyClassEnum.ROUTINE, "power": True, "sig": False},
    ]

    now = datetime.now(timezone.utc)
    
    # 1. Engineering Tasks (TMS)
    for asset in [a for a in assets if a.department == DepartmentEnum.ENGINEERING]:
        tmpl = random.choice(tms_templates)
        due_days = random.randint(-5, -1) if "IMR" in tmpl["type"] else random.choice([-3, -1, 0, 1, 2, 4, 6, 8, 12, 16, 21, 27])
        due_dt = now + timedelta(days=due_days)
        tasks.append(MaintenanceTask(
            source_system=SourceSystemEnum.TMS,
            source_task_id=f"TMS-WO-{len(tasks)+1001}",
            asset_id=asset.asset_id,
            department=DepartmentEnum.ENGINEERING,
            task_type=tmpl["type"],
            description=f"{tmpl['desc']} at {asset.section_id} ({asset.line_or_road.value} Line, km {asset.chainage_from})",
            created_at=(now - timedelta(days=random.randint(5, 30))).isoformat(),
            due_at=due_dt.isoformat(),
            latest_completion_date=(due_dt + timedelta(days=5)).isoformat(),
            estimated_duration_min=tmpl["dur"],
            min_duration_min=tmpl["min_dur"],
            max_duration_min=tmpl["max_dur"],
            requires_traffic_block=True,
            requires_ohe_isolation=tmpl["power"],
            requires_signal_disconnection=tmpl["sig"],
            requires_line_occupation=True,
            required_crew_type="P_WAY_GANG_04",
            required_machine_type=tmpl["machine"],
            safety_class=tmpl["safety"],
            status=TaskStatusEnum.PENDING
        ))

    # 2. S&T Tasks (SMMS)
    for asset in [a for a in assets if a.department == DepartmentEnum.S_AND_T]:
        tmpl = random.choice(smms_templates)
        due_days = random.choice([-4, -2, 0, 1, 3, 5, 7, 10, 15, 19, 24, 28])
        due_dt = now + timedelta(days=due_days)
        tasks.append(MaintenanceTask(
            source_system=SourceSystemEnum.SMMS,
            source_task_id=f"SMMS-WO-{len(tasks)+1001}",
            asset_id=asset.asset_id,
            department=DepartmentEnum.S_AND_T,
            task_type=tmpl["type"],
            description=f"{tmpl['desc']} on {asset.source_asset_id} ({asset.section_id})",
            created_at=(now - timedelta(days=random.randint(4, 20))).isoformat(),
            due_at=due_dt.isoformat(),
            latest_completion_date=(due_dt + timedelta(days=3)).isoformat(),
            estimated_duration_min=tmpl["dur"],
            min_duration_min=tmpl["min_dur"],
            max_duration_min=tmpl["max_dur"],
            requires_traffic_block=True,
            requires_ohe_isolation=tmpl["power"],
            requires_signal_disconnection=tmpl["sig"],
            requires_line_occupation=True,
            required_crew_type="SIGNAL_MAINTENANCE_DEPOT_02",
            required_machine_type=tmpl["machine"],
            safety_class=tmpl["safety"],
            status=TaskStatusEnum.PENDING
        ))

    # 3. TRD / Electrical Tasks (TDMS)
    for asset in [a for a in assets if a.department == DepartmentEnum.TRD]:
        tmpl = random.choice(tdms_templates)
        due_days = random.choice([-3, -1, 0, 2, 4, 6, 8, 11, 14, 18, 23, 29])
        due_dt = now + timedelta(days=due_days)
        tasks.append(MaintenanceTask(
            source_system=SourceSystemEnum.TDMS,
            source_task_id=f"TDMS-WO-{len(tasks)+1001}",
            asset_id=asset.asset_id,
            department=DepartmentEnum.TRD,
            task_type=tmpl["type"],
            description=f"{tmpl['desc']} at {asset.section_id} (Mast {asset.source_asset_id})",
            created_at=(now - timedelta(days=random.randint(3, 25))).isoformat(),
            due_at=due_dt.isoformat(),
            latest_completion_date=(due_dt + timedelta(days=7)).isoformat(),
            estimated_duration_min=tmpl["dur"],
            min_duration_min=tmpl["min_dur"],
            max_duration_min=tmpl["max_dur"],
            requires_traffic_block=True,
            requires_ohe_isolation=tmpl["power"],
            requires_signal_disconnection=tmpl["sig"],
            requires_line_occupation=True,
            required_crew_type="TRD_POWER_CREW_01",
            required_machine_type=tmpl["machine"],
            safety_class=tmpl["safety"],
            status=TaskStatusEnum.PENDING
        ))

    return tasks

def generate_train_movements(days: int = 1, start_offset_days: int = 0) -> List[TrainMovement]:
    """
    Generates realistic timetable train movements in relative horizon minutes (0 to 1440 min per day).
    Supports multi-day scheduling across 24-hour, 7-day, and 30-day planning horizons.
    """
    trains: List[TrainMovement] = []
    
    TRAIN_TEMPLATES = [
        # Premium Passenger
        {"num": "20171", "name": "Vande Bharat Express (NDLS-BPL)", "type": TrainTypeEnum.PREMIUM_PASSENGER, "prio": 1, "speed": 130, "origin": "NDLS", "dest": "BPL", "line": LineOrRoadEnum.DOWN, "base_min": 360}, # 06:00
        {"num": "12952", "name": "Mumbai Rajdhani Express", "type": TrainTypeEnum.PREMIUM_PASSENGER, "prio": 1, "speed": 130, "origin": "NDLS", "dest": "MMCT", "line": LineOrRoadEnum.DOWN, "base_min": 990}, # 16:30
        {"num": "12002", "name": "Bhopal Shatabdi Express", "type": TrainTypeEnum.PREMIUM_PASSENGER, "prio": 1, "speed": 130, "origin": "NDLS", "dest": "RKMP", "line": LineOrRoadEnum.DOWN, "base_min": 375}, # 06:15
        {"num": "20172", "name": "Vande Bharat Express (BPL-NDLS)", "type": TrainTypeEnum.PREMIUM_PASSENGER, "prio": 1, "speed": 130, "origin": "BPL", "dest": "NDLS", "line": LineOrRoadEnum.UP, "base_min": 1260}, # 21:00
        {"num": "12951", "name": "Mumbai Rajdhani Express (UP)", "type": TrainTypeEnum.PREMIUM_PASSENGER, "prio": 1, "speed": 130, "origin": "MMCT", "dest": "NDLS", "line": LineOrRoadEnum.UP, "base_min": 510},  # 08:30
        
        # Express Trains
        {"num": "12414", "name": "Pooja Superfast Express", "type": TrainTypeEnum.EXPRESS, "prio": 2, "speed": 110, "origin": "JAT", "dest": "AII", "line": LineOrRoadEnum.DOWN, "base_min": 240},
        {"num": "12918", "name": "Gujarat Sampark Kranti", "type": TrainTypeEnum.EXPRESS, "prio": 2, "speed": 110, "origin": "NZM", "dest": "ADI", "line": LineOrRoadEnum.DOWN, "base_min": 810},
        {"num": "12618", "name": "Mangala Lakshadweep SF", "type": TrainTypeEnum.EXPRESS, "prio": 2, "speed": 110, "origin": "NZM", "dest": "ERS", "line": LineOrRoadEnum.DOWN, "base_min": 570},
        {"num": "12413", "name": "Pooja Superfast (UP)", "type": TrainTypeEnum.EXPRESS, "prio": 2, "speed": 110, "origin": "AII", "dest": "JAT", "line": LineOrRoadEnum.UP, "base_min": 390},
        {"num": "12917", "name": "Gujarat Sampark Kranti (UP)", "type": TrainTypeEnum.EXPRESS, "prio": 2, "speed": 110, "origin": "ADI", "dest": "NZM", "line": LineOrRoadEnum.UP, "base_min": 630},
        {"num": "12780", "name": "Goa Express (UP)", "type": TrainTypeEnum.EXPRESS, "prio": 2, "speed": 110, "origin": "VSG", "dest": "NZM", "line": LineOrRoadEnum.UP, "base_min": 420},

        # Suburban Local (MEMU / EMU)
        {"num": "04408", "name": "Delhi - Palwal EMU", "type": TrainTypeEnum.SUBURBAN, "prio": 3, "speed": 80, "origin": "NDLS", "dest": "PWL", "line": LineOrRoadEnum.DOWN, "base_min": 450}, # 07:30
        {"num": "04914", "name": "Ghaziabad - Palwal MEMU", "type": TrainTypeEnum.SUBURBAN, "prio": 3, "speed": 80, "origin": "GZB", "dest": "PWL", "line": LineOrRoadEnum.DOWN, "base_min": 540}, # 09:00
        {"num": "04407", "name": "Palwal - Delhi EMU (UP)", "type": TrainTypeEnum.SUBURBAN, "prio": 3, "speed": 80, "origin": "PWL", "dest": "NDLS", "line": LineOrRoadEnum.UP, "base_min": 480}, # 08:00
        {"num": "04913", "name": "Palwal - Ghaziabad MEMU (UP)", "type": TrainTypeEnum.SUBURBAN, "prio": 3, "speed": 80, "origin": "PWL", "dest": "GZB", "line": LineOrRoadEnum.UP, "base_min": 570}, # 09:30

        # High Priority Freight & Coal Rakes
        {"num": "CONRAJ-91", "name": "Container Rajdhani High-Speed (TKD-MDPT)", "type": TrainTypeEnum.CONTAINER_FREIGHT, "prio": 4, "speed": 100, "origin": "TKD", "dest": "MDPT", "line": LineOrRoadEnum.DOWN, "base_min": 720}, # 12:00
        {"num": "COAL-44", "name": "Coal Rake Dedicated Freight (Dadri-PNP)", "type": TrainTypeEnum.GOODS_FREIGHT, "prio": 5, "speed": 75, "origin": "PWL", "dest": "TKD", "line": LineOrRoadEnum.UP, "base_min": 870}, # 14:30
        {"num": "BCN-8812", "name": "Covered Freight Grain Rake", "type": TrainTypeEnum.GOODS_FREIGHT, "prio": 5, "speed": 75, "origin": "NDLS", "dest": "MTJ", "line": LineOrRoadEnum.DOWN, "base_min": 1140}, # 19:00
        {"num": "CONT-332", "name": "Inbound ICD Container (JNPT-TKD)", "type": TrainTypeEnum.CONTAINER_FREIGHT, "prio": 4, "speed": 100, "origin": "PWL", "dest": "TKD", "line": LineOrRoadEnum.UP, "base_min": 1080}, # 18:00
    ]

    base_midnight = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

    for d in range(days):
        day_idx = start_offset_days + d
        day_date = base_midnight + timedelta(days=day_idx)
        today_str = day_date.strftime("%Y-%m-%d")

        for t_tmpl in TRAIN_TEMPLATES:
            # Generate block timings across all sections in the corridor
            base_time = t_tmpl["base_min"]
            
            # Traverse sections in order
            sec_list = SECTIONS if t_tmpl["line"] == LineOrRoadEnum.DOWN else list(reversed(SECTIONS))
            curr_time = base_time
            
            for sec in sec_list:
                km_dist = abs(sec["end_km"] - sec["start_km"])
                transit_min = max(4, int(round((km_dist / t_tmpl["speed"]) * 60)))
                
                entry_m = curr_time
                exit_m = curr_time + transit_min
                
                entry_dt = day_date + timedelta(minutes=entry_m)
                exit_dt = day_date + timedelta(minutes=exit_m)

                trains.append(TrainMovement(
                    train_number=f"{t_tmpl['num']}{f'-D{day_idx}' if day_idx > 0 else ''}",
                    train_name=t_tmpl["name"],
                    service_date=today_str,
                    train_type=t_tmpl["type"],
                    origin=t_tmpl["origin"],
                    destination=t_tmpl["dest"],
                    section_id=sec["id"],
                    line_or_road=t_tmpl["line"],
                    planned_entry=entry_dt.isoformat(),
                    planned_exit=exit_dt.isoformat(),
                    entry_minute=entry_m,
                    exit_minute=exit_m,
                    min_clearance_before_min=15,
                    min_clearance_after_min=15,
                    priority_class=t_tmpl["prio"],
                    speed_kmh=t_tmpl["speed"]
                ))
                
                curr_time += transit_min + 2 # 2 min inter-station headway

    return trains

def generate_corridor_windows(days: int = 1, start_offset_days: int = 0) -> List[CorridorWindow]:
    """
    Candidate standard maintenance windows (e.g. Night corridor 00:30-04:30 and Mid-day lull 11:30-14:00).
    Supports multi-day generation with temporal day offsets.
    """
    windows: List[CorridorWindow] = []
    
    CANDIDATE_SLOTS = [
        {"start_m": 30, "end_m": 270, "label": "Night Mega Corridor (00:30 - 04:30)"}, # 240 min
        {"start_m": 690, "end_m": 840, "label": "Mid-Day Traffic Lull (11:30 - 14:00)"}, # 150 min
        {"start_m": 1290, "end_m": 1410, "label": "Late Evening Window (21:30 - 23:30)"}, # 120 min
    ]
    
    base_midnight = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    
    for d in range(days):
        day_idx = start_offset_days + d
        day_date = base_midnight + timedelta(days=day_idx)

        for sec in SECTIONS:
            for line in [LineOrRoadEnum.UP, LineOrRoadEnum.DOWN]:
                for slot in CANDIDATE_SLOTS:
                    s_dt = day_date + timedelta(minutes=slot["start_m"])
                    e_dt = day_date + timedelta(minutes=slot["end_m"])
                    windows.append(CorridorWindow(
                        corridor_window_id=f"CW-{sec['id']}-{line.value}-D{day_idx}-{slot['start_m']}",
                        section_id=sec["id"],
                        line_or_road=line,
                        window_start=s_dt.isoformat(),
                        window_end=e_dt.isoformat(),
                        start_minute=slot["start_m"],
                        end_minute=slot["end_m"],
                        available_duration_min=slot["end_m"] - slot["start_m"],
                        allowed_block_type="MULTI_DEPARTMENT",
                        timetable_version="WTT-NR-2026-V2"
                    ))
                    
    return windows

def generate_raw_demands_for_reconciliation(assets: List[CanonicalAsset]) -> List[RawAssetDemand]:
    """
    Generates test raw demands to exercise the 4-tier asset identity resolution engine
    """
    demands: List[RawAssetDemand] = []
    
    # 1. Exact Match Candidate (Tier 1)
    tms_asset = assets[0]
    demands.append(RawAssetDemand(
        source_system=SourceSystemEnum.TMS,
        source_asset_id=tms_asset.source_asset_id,
        raw_reference=tms_asset.source_asset_id,
        department=DepartmentEnum.ENGINEERING,
        section_id=tms_asset.section_id,
        station_from=tms_asset.station_from,
        station_to=tms_asset.station_to,
        line_or_road=tms_asset.line_or_road,
        chainage_from=tms_asset.chainage_from,
        chainage_to=tms_asset.chainage_to
    ))
    
    # 2. Hierarchy Match Candidate (Tier 2)
    demands.append(RawAssetDemand(
        source_system=SourceSystemEnum.SMMS,
        source_asset_id="UNKNOWN_SIG_REF_99",
        raw_reference="Signal near NZM starter UP",
        department=DepartmentEnum.S_AND_T,
        section_id="NZM-OKA",
        station_from="NZM",
        station_to="OKA",
        line_or_road=LineOrRoadEnum.UP
    ))
    
    # 3. Chainage Overlap >= 90% (Tier 3)
    target_sec = assets[1]
    demands.append(RawAssetDemand(
        source_system=SourceSystemEnum.TMS,
        source_asset_id="TMS_FIELD_PWAY_124",
        raw_reference=f"km {target_sec.chainage_from}/{int((target_sec.chainage_to-target_sec.chainage_from)*1000)}",
        department=DepartmentEnum.ENGINEERING,
        section_id=target_sec.section_id,
        line_or_road=target_sec.line_or_road,
        chainage_from=target_sec.chainage_from + 0.005,
        chainage_to=target_sec.chainage_to - 0.005
    ))

    # 4. Spatial Proximity <= 25m (Tier 4)
    demands.append(RawAssetDemand(
        source_system=SourceSystemEnum.TDMS,
        source_asset_id="TDMS_MAST_GPS_P2",
        raw_reference="OHE Mast Near Faridabad Yard Crossover",
        department=DepartmentEnum.TRD,
        section_id="TKD-FDB",
        line_or_road=LineOrRoadEnum.DOWN,
        latitude=28.4090, # close to FDB lat 28.4089
        longitude=77.3179
    ))
    
    # 5. Ambiguous / Unresolved Case (Routes to Manual Reconciliation)
    demands.append(RawAssetDemand(
        source_system=SourceSystemEnum.SMMS,
        source_asset_id="SMMS_REMODELED_TURNOUT_X",
        raw_reference="Remodeled Turnout near unknown siding",
        department=DepartmentEnum.S_AND_T,
        section_id="UNKNOWN_SECTION",
        line_or_road=LineOrRoadEnum.YARD_LINE,
        chainage_from=999.0,
        chainage_to=999.1
    ))

    return demands
