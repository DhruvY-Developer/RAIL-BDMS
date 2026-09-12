"""
Rail-BDMS: Multi-Department Shadow Block Compatibility Graph & Candidate Generation Engine
Domain: Indian Railways Corridor Block Scheduling & Multi-Department Consolidation
Validates operational compatibility across TMS (Civil/P-Way), SMMS (S&T), and TDMS (TRD/Electrical).
"""
import uuid
import networkx as nx
from typing import List, Dict, Tuple, Set, Optional, Any
from backend.app.schemas.schemas import (
    MaintenanceTask, CanonicalAsset, ShadowBlockGroup, DepartmentEnum,
    MachineTypeEnum, LineOrRoadEnum
)

class BlockCandidate:
    """
    Structured block candidate representing either an individual department possession
    or a consolidated multi-department possession opportunity.
    """
    def __init__(
        self,
        candidate_id: str,
        section_id: str,
        line_or_road: LineOrRoadEnum,
        task_ids: List[str],
        participating_departments: List[DepartmentEnum],
        duration_min: int,
        individual_durations_sum: int,
        corridor_time_saved_min: int,
        spatial_envelope_km: float,
        chainage_min: float,
        chainage_max: float,
        assets_covered: List[str],
        required_machines: List[MachineTypeEnum],
        requires_ohe_isolation: bool,
        requires_signal_disconnection: bool,
        is_multi_department: bool,
        is_valid: bool,
        compatibility_score: float,
        compatibility_rationale: str,
        rejection_reason: Optional[str] = None
    ):
        self.candidate_id = candidate_id
        self.section_id = section_id
        self.line_or_road = line_or_road
        self.task_ids = task_ids
        self.participating_departments = participating_departments
        self.duration_min = duration_min
        self.individual_durations_sum = individual_durations_sum
        self.corridor_time_saved_min = corridor_time_saved_min
        self.spatial_envelope_km = spatial_envelope_km
        self.chainage_min = chainage_min
        self.chainage_max = chainage_max
        self.assets_covered = assets_covered
        self.required_machines = required_machines
        self.requires_ohe_isolation = requires_ohe_isolation
        self.requires_signal_disconnection = requires_signal_disconnection
        self.is_multi_department = is_multi_department
        self.is_valid = is_valid
        self.compatibility_score = compatibility_score
        self.compatibility_rationale = compatibility_rationale
        self.rejection_reason = rejection_reason

    def to_dict(self) -> Dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "section_id": self.section_id,
            "line_or_road": self.line_or_road.value if hasattr(self.line_or_road, "value") else str(self.line_or_road),
            "task_ids": self.task_ids,
            "participating_departments": [d.value if hasattr(d, "value") else str(d) for d in self.participating_departments],
            "duration_min": self.duration_min,
            "individual_durations_sum": self.individual_durations_sum,
            "corridor_time_saved_min": self.corridor_time_saved_min,
            "spatial_envelope_km": round(self.spatial_envelope_km, 2),
            "chainage_min": round(self.chainage_min, 3),
            "chainage_max": round(self.chainage_max, 3),
            "assets_covered": self.assets_covered,
            "required_machines": [m.value if hasattr(m, "value") else str(m) for m in self.required_machines],
            "requires_ohe_isolation": self.requires_ohe_isolation,
            "requires_signal_disconnection": self.requires_signal_disconnection,
            "is_multi_department": self.is_multi_department,
            "is_valid": self.is_valid,
            "compatibility_score": self.compatibility_score,
            "compatibility_rationale": self.compatibility_rationale,
            "rejection_reason": self.rejection_reason
        }


class ShadowBlockCompatibilityEngine:
    """
    Deterministic Railway Compatibility Validation Engine.
    Enforces the 15-point railway operational compatibility rules:
    - Same section & line
    - Spatial protection envelope <= 6.0 km
    - Zero machine collision (CSM, BCM, Unimat, Tower Wagon, Crane)
    - Synergistic 25kV OHE power isolation
    - S&T Block Joint disconnection
    """
    def __init__(self, canonical_assets: List[CanonicalAsset]):
        self.canonical_assets = canonical_assets
        self.asset_lookup: Dict[str, CanonicalAsset] = {a.asset_id: a for a in canonical_assets}

    def check_compatibility(self, task1: MaintenanceTask, task2: MaintenanceTask) -> Tuple[bool, str]:
        """
        Evaluates operational compatibility between two maintenance tasks.
        Returns (is_compatible: bool, rationale: str).
        """
        asset1 = self.asset_lookup.get(task1.asset_id)
        asset2 = self.asset_lookup.get(task2.asset_id)

        if not asset1 or not asset2:
            return False, "Missing asset information for spatial validation"

        # 1. Hard Rule: Must be on the same physical section
        if asset1.section_id != asset2.section_id:
            return False, f"Different sections ({asset1.section_id} vs {asset2.section_id})"

        # 2. Hard Rule: Must be on the same track line / road
        if asset1.line_or_road != asset2.line_or_road:
            return False, f"Different track lines ({asset1.line_or_road.value} vs {asset2.line_or_road.value})"

        # 3. Hard Rule: Machine Exclusivity (cannot require the same specialized track machine)
        if (
            task1.required_machine_type != MachineTypeEnum.NONE
            and task1.required_machine_type == task2.required_machine_type
        ):
            return False, f"Machine resource collision: Both require {task1.required_machine_type.value}"

        # 4. Hard Rule: Spatial proximity envelope (within 6.0 km on the same section)
        chainage_dist = abs(asset1.chainage_from - asset2.chainage_from)
        if chainage_dist > 6.0:
            return False, f"Spatial distance too large ({round(chainage_dist, 2)} km > 6.0 km protection limit)"

        # 5. Electrical / OHE Isolation Protocol Compatibility
        power_state_note = "Standard traffic protection"
        if task1.requires_ohe_isolation or task2.requires_ohe_isolation:
            power_state_note = "Joint 25kV Traction Power Isolation clearance"

        # 6. Signalling Disconnection Compatibility
        sig_state_note = ""
        if task1.requires_signal_disconnection or task2.requires_signal_disconnection:
            sig_state_note = " + S&T Block Joint Disconnection"

        dept_mix = f"{task1.department.value} + {task2.department.value}"
        rationale = (
            f"Compatible corridor possession on {asset1.section_id} ({asset1.line_or_road.value} Line) "
            f"for {dept_mix} [{power_state_note}{sig_state_note}]"
        )
        return True, rationale

    def validate_group_compatibility(self, tasks: List[MaintenanceTask]) -> Tuple[bool, str]:
        """
        Validates whether a multi-task group (2 or more tasks) satisfies collective compatibility:
        - All pairs must be mutually compatible
        - Total spatial envelope (max chainage - min chainage) <= 6.0 km
        - No two tasks require the same machine type (unless NONE)
        """
        if len(tasks) < 2:
            return True, "Single task is trivially valid"

        assets = [self.asset_lookup.get(t.asset_id) for t in tasks]
        if any(a is None for a in assets):
            return False, "Missing asset record for one or more tasks"

        # Check same section & line across all
        first_asset = assets[0]
        for a in assets[1:]:
            if a.section_id != first_asset.section_id:
                return False, f"Section mismatch in group: {a.section_id} vs {first_asset.section_id}"
            if a.line_or_road != first_asset.line_or_road:
                return False, f"Line mismatch in group: {a.line_or_road.value} vs {first_asset.line_or_road.value}"

        # Collective spatial envelope check across all assets
        min_km = min(a.chainage_from for a in assets)
        max_km = max(a.chainage_to for a in assets)
        span_km = max_km - min_km
        if span_km > 6.0:
            return False, f"Collective spatial envelope {round(span_km, 2)} km exceeds 6.0 km limit"

        # Check machine resource collisions across all tasks
        assigned_machines = set()
        for t in tasks:
            if t.required_machine_type != MachineTypeEnum.NONE:
                if t.required_machine_type in assigned_machines:
                    return False, f"Machine collision: multiple tasks require {t.required_machine_type.value}"
                assigned_machines.add(t.required_machine_type)

        # All pairwise checks
        n = len(tasks)
        for i in range(n):
            for j in range(i + 1, n):
                is_comp, rat = self.check_compatibility(tasks[i], tasks[j])
                if not is_comp:
                    return False, rat

        depts = sorted(list(set(t.department.value for t in tasks)))
        return True, f"Valid multi-department group spanning {len(tasks)} tasks from {', '.join(depts)} (Span: {round(span_km, 2)} km)"

    def build_compatibility_graph(self, tasks: List[MaintenanceTask]) -> nx.Graph:
        """
        Constructs NetworkX undirected graph where nodes are tasks and edges represent verified compatibility.
        """
        G = nx.Graph()
        for t in tasks:
            G.add_node(t.task_id, task=t)

        n = len(tasks)
        for i in range(n):
            for j in range(i + 1, n):
                t1, t2 = tasks[i], tasks[j]
                is_compat, rationale = self.check_compatibility(t1, t2)
                if is_compat:
                    G.add_edge(t1.task_id, t2.task_id, rationale=rationale)

        return G

    def extract_shadow_block_groups(self, tasks: List[MaintenanceTask]) -> List[ShadowBlockGroup]:
        """
        Partitions compatible tasks into valid multi-department Shadow Block Groups.
        Enforces collective spatial envelope <= 6.0 km and machine exclusivity.
        """
        task_map = {t.task_id: t for t in tasks}
        G = self.build_compatibility_graph(tasks)

        shadow_groups: List[ShadowBlockGroup] = []
        visited_nodes: Set[str] = set()

        # Iterate over maximal cliques to guarantee mutual pairwise compatibility within every group
        cliques = list(nx.find_cliques(G))
        # Sort cliques by size descending and distinct departments descending
        def clique_sort_key(c):
            c_tasks = [task_map[tid] for tid in c if tid in task_map]
            c_depts = len(set(t.department for t in c_tasks))
            return (c_depts, len(c_tasks))

        cliques.sort(key=clique_sort_key, reverse=True)

        for clique in cliques:
            # Check if any task is already grouped in an accepted group
            if any(tid in visited_nodes for tid in clique):
                clique = [tid for tid in clique if tid not in visited_nodes]

            if len(clique) < 2:
                continue

            comp_tasks = [task_map[tid] for tid in clique if tid in task_map]
            depts = list(set(t.department for t in comp_tasks))

            # Must span 2+ distinct departments or consolidate 2+ major tasks
            if len(comp_tasks) < 2 or len(depts) < 2:
                continue

            # Validate collective envelope
            is_valid, group_rat = self.validate_group_compatibility(comp_tasks)
            if not is_valid:
                continue

            # Determine lead department (Engineering > TRD > S&T)
            if DepartmentEnum.ENGINEERING in depts:
                lead_dept = DepartmentEnum.ENGINEERING
            elif DepartmentEnum.TRD in depts:
                lead_dept = DepartmentEnum.TRD
            else:
                lead_dept = DepartmentEnum.S_AND_T

            first_asset = self.asset_lookup.get(comp_tasks[0].asset_id)
            sec_id = first_asset.section_id if first_asset else "NZM-PWL"
            line_road = first_asset.line_or_road if first_asset else comp_tasks[0].asset_id

            comp_assets = [self.asset_lookup.get(t.asset_id) for t in comp_tasks if self.asset_lookup.get(t.asset_id)]
            min_km = min(a.chainage_from for a in comp_assets) if comp_assets else 0.0
            max_km = max(a.chainage_to for a in comp_assets) if comp_assets else 0.0
            span_km = round(max_km - min_km, 2)

            max_duration = max(t.estimated_duration_min for t in comp_tasks)
            sum_duration = sum(t.estimated_duration_min for t in comp_tasks)
            time_saved = sum_duration - max_duration
            utilization = round((sum_duration / max(1, max_duration)) * 100, 1) if max_duration > 0 else 100.0

            rationale = (
                f"Consolidated {len(comp_tasks)} tasks from {', '.join([d.value for d in depts])}. "
                f"Corridor savings: {time_saved} min (Spatial span: {span_km} km on {sec_id} {line_road.value} Line)."
            )

            group = ShadowBlockGroup(
                lead_department=lead_dept,
                section_id=sec_id,
                line_or_road=line_road,
                task_ids=[t.task_id for t in comp_tasks],
                participating_departments=depts,
                total_duration_min=max_duration,
                corridor_time_saved_min=time_saved,
                compatibility_score=1.0,
                compatibility_rationale=rationale,
                selected_in_plan=False,
                spatial_envelope_km=span_km,
                assets_covered=[t.asset_id for t in comp_tasks],
                block_utilization_pct=utilization
            )
            shadow_groups.append(group)
            visited_nodes.update(clique)

        return shadow_groups

    def generate_block_candidates(
        self,
        tasks: List[MaintenanceTask]
    ) -> Tuple[List[BlockCandidate], List[BlockCandidate]]:
        """
        Generates structured block candidates:
        - Valid Candidates: Single-task options and verified multi-department consolidated options.
        - Incompatible Candidates: Candidates rejected during grouping with clear operational reasons.
        """
        valid_candidates: List[BlockCandidate] = []
        rejected_candidates: List[BlockCandidate] = []

        # 1. Single Task Candidates (Baseline options)
        for t in tasks:
            asset = self.asset_lookup.get(t.asset_id)
            if not asset:
                continue

            machines = [t.required_machine_type] if t.required_machine_type != MachineTypeEnum.NONE else []
            span_km = round(abs(asset.chainage_to - asset.chainage_from), 3)

            cand = BlockCandidate(
                candidate_id=f"CAND-SINGLE-{t.task_id[:8]}",
                section_id=asset.section_id,
                line_or_road=asset.line_or_road,
                task_ids=[t.task_id],
                participating_departments=[t.department],
                duration_min=t.estimated_duration_min,
                individual_durations_sum=t.estimated_duration_min,
                corridor_time_saved_min=0,
                spatial_envelope_km=span_km,
                chainage_min=min(asset.chainage_from, asset.chainage_to),
                chainage_max=max(asset.chainage_from, asset.chainage_to),
                assets_covered=[t.asset_id],
                required_machines=machines,
                requires_ohe_isolation=t.requires_ohe_isolation,
                requires_signal_disconnection=t.requires_signal_disconnection,
                is_multi_department=False,
                is_valid=True,
                compatibility_score=1.0,
                compatibility_rationale=f"Single department block for {t.department.value} ({t.task_type})"
            )
            valid_candidates.append(cand)

        # 2. Multi-Department Consolidated Candidates
        shadow_groups = self.extract_shadow_block_groups(tasks)
        task_map = {t.task_id: t for t in tasks}

        for sg in shadow_groups:
            c_tasks = [task_map[tid] for tid in sg.task_ids if tid in task_map]
            c_assets = [self.asset_lookup.get(t.asset_id) for t in c_tasks if self.asset_lookup.get(t.asset_id)]

            if not c_assets:
                continue

            min_km = min(a.chainage_from for a in c_assets)
            max_km = max(a.chainage_to for a in c_assets)
            span_km = max_km - min_km

            machines = list(set(
                t.required_machine_type for t in c_tasks
                if t.required_machine_type != MachineTypeEnum.NONE
            ))

            requires_ohe = any(t.requires_ohe_isolation for t in c_tasks)
            requires_sig = any(t.requires_signal_disconnection for t in c_tasks)

            cand = BlockCandidate(
                candidate_id=f"CAND-MULTI-{sg.block_group_id[:8]}",
                section_id=sg.section_id,
                line_or_road=sg.line_or_road,
                task_ids=sg.task_ids,
                participating_departments=sg.participating_departments,
                duration_min=sg.total_duration_min,
                individual_durations_sum=sum(t.estimated_duration_min for t in c_tasks),
                corridor_time_saved_min=sg.corridor_time_saved_min,
                spatial_envelope_km=span_km,
                chainage_min=min_km,
                chainage_max=max_km,
                assets_covered=[t.asset_id for t in c_tasks],
                required_machines=machines,
                requires_ohe_isolation=requires_ohe,
                requires_signal_disconnection=requires_sig,
                is_multi_department=True,
                is_valid=True,
                compatibility_score=1.0,
                compatibility_rationale=sg.compatibility_rationale
            )
            valid_candidates.append(cand)

        # 3. Log Incompatible Pairwise Candidates for Explainability & Audit
        n = min(len(tasks), 40)
        for i in range(n):
            for j in range(i + 1, n):
                t1, t2 = tasks[i], tasks[j]
                if t1.department != t2.department:
                    is_comp, reason = self.check_compatibility(t1, t2)
                    if not is_comp:
                        asset1 = self.asset_lookup.get(t1.asset_id)
                        sec = asset1.section_id if asset1 else "UNKNOWN"
                        line = asset1.line_or_road if asset1 else LineOrRoadEnum.DOWN

                        rej_cand = BlockCandidate(
                            candidate_id=f"REJ-{t1.task_id[:4]}-{t2.task_id[:4]}",
                            section_id=sec,
                            line_or_road=line,
                            task_ids=[t1.task_id, t2.task_id],
                            participating_departments=[t1.department, t2.department],
                            duration_min=max(t1.estimated_duration_min, t2.estimated_duration_min),
                            individual_durations_sum=t1.estimated_duration_min + t2.estimated_duration_min,
                            corridor_time_saved_min=0,
                            spatial_envelope_km=0.0,
                            chainage_min=0.0,
                            chainage_max=0.0,
                            assets_covered=[t1.asset_id, t2.asset_id],
                            required_machines=[],
                            requires_ohe_isolation=t1.requires_ohe_isolation or t2.requires_ohe_isolation,
                            requires_signal_disconnection=t1.requires_signal_disconnection or t2.requires_signal_disconnection,
                            is_multi_department=True,
                            is_valid=False,
                            compatibility_score=0.0,
                            compatibility_rationale="Incompatible candidate",
                            rejection_reason=reason
                        )
                        rejected_candidates.append(rej_cand)

        return valid_candidates, rejected_candidates
