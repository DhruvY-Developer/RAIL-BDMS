"""
Rail-BDMS: Multi-Department Shadow Block Compatibility Graph Engine
Builds network graph of pending maintenance tasks and packs compatible tasks into Shadow Blocks.
"""
import networkx as nx
from typing import List, Dict, Tuple, Set
from backend.app.schemas.schemas import (
    MaintenanceTask, CanonicalAsset, ShadowBlockGroup, DepartmentEnum,
    MachineTypeEnum
)

class ShadowBlockCompatibilityEngine:
    def __init__(self, canonical_assets: List[CanonicalAsset]):
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

        # 1. Hard Rule: Must be on the same physical section and line/road
        if asset1.section_id != asset2.section_id:
            return False, f"Different sections ({asset1.section_id} vs {asset2.section_id})"
        if asset1.line_or_road != asset2.line_or_road:
            return False, f"Different track lines ({asset1.line_or_road.value} vs {asset2.line_or_road.value})"

        # 2. Hard Rule: Machine Exclusivity (cannot require the same specialized machine)
        if task1.required_machine_type != MachineTypeEnum.NONE and task1.required_machine_type == task2.required_machine_type:
            return False, f"Machine resource collision: Both require {task1.required_machine_type.value}"

        # 3. Hard Rule: Spatial proximity envelope (within 5 km on the same section)
        chainage_dist = abs(asset1.chainage_from - asset2.chainage_from)
        if chainage_dist > 6.0:
            return False, f"Spatial distance too large ({round(chainage_dist, 2)} km > 6.0 km protection limit)"

        # 4. Electrical / OHE Isolation Protocol Compatibility
        # Both requiring isolation is mutually synergistic (pack under 1 power cutoff)
        # One requiring isolation and the other being P-Way/S&T under power-off is safe
        power_state_note = "Standard traffic protection"
        if task1.requires_ohe_isolation or task2.requires_ohe_isolation:
            power_state_note = "Joint 25kV Traction Power Isolation clearance"

        # 5. Signalling Disconnection Compatibility
        sig_state_note = ""
        if task1.requires_signal_disconnection or task2.requires_signal_disconnection:
            sig_state_note = " + S&T Block Joint Disconnection"

        dept_mix = f"{task1.department.value} + {task2.department.value}"
        rationale = f"Compatible corridor possession on {asset1.section_id} ({asset1.line_or_road.value} Line) for {dept_mix} [{power_state_note}{sig_state_note}]"
        
        return True, rationale

    def build_compatibility_graph(self, tasks: List[MaintenanceTask]) -> nx.Graph:
        """
        Constructs NetworkX undirected graph where nodes are tasks and edges represent compatibility.
        """
        G = nx.Graph()
        for t in tasks:
            G.add_node(t.task_id, task=t)

        n = len(tasks)
        for i in range(n):
            for j in range(i + 1, n):
                t1, t2 = tasks[i], tasks[j]
                # Prioritize cross-department combinations
                is_compat, rationale = self.check_compatibility(t1, t2)
                if is_compat:
                    G.add_edge(t1.task_id, t2.task_id, rationale=rationale)

        return G

    def extract_shadow_block_groups(self, tasks: List[MaintenanceTask]) -> List[ShadowBlockGroup]:
        """
        Partitions compatible tasks into multi-department Shadow Block Groups.
        """
        task_map = {t.task_id: t for t in tasks}
        G = self.build_compatibility_graph(tasks)
        
        shadow_groups: List[ShadowBlockGroup] = []
        visited_nodes: Set[str] = set()

        # Find connected components with multi-department membership
        for component in nx.connected_components(G):
            comp_tasks = [task_map[tid] for tid in component if tid in task_map]
            
            # A true shadow block must span 2 or more distinct departments or consolidate 2+ major tasks
            depts = list(set(t.department for t in comp_tasks))
            
            if len(comp_tasks) >= 2 and len(depts) >= 2:
                # Determine lead department (Engineering > TRD > S&T)
                lead_dept = DepartmentEnum.ENGINEERING
                if DepartmentEnum.ENGINEERING in depts:
                    lead_dept = DepartmentEnum.ENGINEERING
                elif DepartmentEnum.TRD in depts:
                    lead_dept = DepartmentEnum.TRD
                else:
                    lead_dept = DepartmentEnum.S_AND_T

                first_asset = self.asset_lookup.get(comp_tasks[0].asset_id)
                sec_id = first_asset.section_id if first_asset else "NZM-PWL"
                line_road = first_asset.line_or_road if first_asset else comp_tasks[0].asset_id

                max_duration = max(t.estimated_duration_min for t in comp_tasks)
                sum_duration = sum(t.estimated_duration_min for t in comp_tasks)
                time_saved = sum_duration - max_duration

                rationale = f"Consolidated {len(comp_tasks)} tasks from {', '.join([d.value for d in depts])}. Corridor savings: {time_saved} minutes."

                group = ShadowBlockGroup(
                    lead_department=lead_dept,
                    section_id=sec_id,
                    line_or_road=line_road,
                    task_ids=[t.task_id for t in comp_tasks],
                    participating_departments=depts,
                    total_duration_min=max_duration,
                    corridor_time_saved_min=time_saved,
                    compatibility_score=1.0,
                    compatibility_rationale=rationale
                )
                shadow_groups.append(group)
                visited_nodes.update(component)

        return shadow_groups
