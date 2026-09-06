"""
Rail-BDMS: Explainable Priority Scoring & Duration / Overrun Analytics Engine
"""
from typing import List, Dict, Optional
from datetime import datetime, timezone
from backend.app.schemas.schemas import (
    MaintenanceTask, CanonicalAsset, SafetyClassEnum, DepartmentEnum,
    MachineTypeEnum
)

class PriorityAnalyticsEngine:
    def __init__(self, canonical_assets: List[CanonicalAsset]):
        self.asset_lookup: Dict[str, CanonicalAsset] = {a.asset_id: a for a in canonical_assets}

    def compute_criticality(self, task: MaintenanceTask, asset: Optional[CanonicalAsset]) -> float:
        """
        Computes Criticality score (0 - 100) based on route class, asset safety classification,
        and passenger / high-speed density.
        """
        base_score = 40.0
        
        # Asset Route Class Weight
        if asset:
            if asset.route_class == "HDN":  # High Density Network (130-160 km/h)
                base_score += 25.0
            elif asset.route_class == "HUN": # Highly Utilized Network
                base_score += 15.0
            else:
                base_score += 10.0
                
            if asset.criticality_class == "CLASS_A":
                base_score += 20.0
            elif asset.criticality_class == "CLASS_B":
                base_score += 10.0
        else:
            base_score += 20.0

        # Task Safety Level
        if task.safety_class == SafetyClassEnum.SAFETY_CRITICAL:
            base_score += 15.0
        elif task.safety_class == SafetyClassEnum.OPERATIONAL_DEFECT:
            base_score += 5.0

        return min(100.0, max(0.0, base_score))

    def compute_urgency(self, task: MaintenanceTask) -> float:
        """
        Computes Urgency score (0 - 100) based on overdue days, defect class, and escalation curves.
        """
        base_score = 30.0
        now = datetime.now(timezone.utc)
        
        try:
            due_dt = datetime.fromisoformat(task.due_at)
            days_diff = (now - due_dt).total_seconds() / 86400.0
            
            if days_diff > 0: # Overdue!
                # Rapid non-linear risk escalation for overdue days
                base_score += min(45.0, days_diff * 7.5)
            else:
                # Approaching due date within 3 days
                days_left = abs(days_diff)
                if days_left <= 3:
                    base_score += (3 - days_left) * 5.0
        except Exception:
            pass

        # Specific defect severity bonus
        if "IMR" in task.task_type:
            base_score += 25.0  # Immediate Removal Rail Fracture
        elif "POINT_MACHINE" in task.task_type or "SECTION_INSULATOR" in task.task_type:
            base_score += 15.0
        elif task.safety_class == SafetyClassEnum.SAFETY_CRITICAL:
            base_score += 10.0

        return min(100.0, max(0.0, base_score))

    def compute_shadow_opportunity(self, task: MaintenanceTask, all_tasks: List[MaintenanceTask]) -> float:
        """
        Computes Shadow Opportunity (0 - 100) by detecting co-located compatible tasks in the pipeline.
        """
        asset = self.asset_lookup.get(task.asset_id)
        if not asset:
            return 50.0

        same_sec_tasks = [
            t for t in all_tasks
            if t.task_id != task.task_id
            and self.asset_lookup.get(t.asset_id) is not None
            and self.asset_lookup[t.asset_id].section_id == asset.section_id
            and self.asset_lookup[t.asset_id].line_or_road == asset.line_or_road
        ]
        
        if not same_sec_tasks:
            return 20.0
            
        other_depts = set(t.department for t in same_sec_tasks if t.department != task.department)
        if len(other_depts) >= 2:
            return 95.0 # Multi-department 3-way packing opportunity!
        elif len(other_depts) == 1:
            return 80.0 # 2-department shadow opportunity
        else:
            return 50.0

    def estimate_quantiles_and_risk(self, task: MaintenanceTask) -> Dict[str, any]:
        """
        Estimates P50, P80, P95 duration quantiles and overrun risk percentage.
        """
        dur = task.estimated_duration_min
        
        # Heavy machines (BCM/CSM/Unimat) have higher historical variance
        variance_factor = 1.15
        if task.required_machine_type in [MachineTypeEnum.BCM, MachineTypeEnum.CSM]:
            variance_factor = 1.35
        elif task.required_machine_type == MachineTypeEnum.TOWER_WAGON:
            variance_factor = 1.25
            
        p50 = int(round(dur))
        p80 = int(round(dur * (1.0 + (variance_factor - 1.0) * 0.7)))
        p95 = int(round(dur * variance_factor))
        
        # Overrun risk probability (0.05 to 0.45)
        risk_score = 0.08
        if task.required_machine_type != MachineTypeEnum.NONE:
            risk_score += 0.12
        if task.requires_ohe_isolation and task.requires_signal_disconnection:
            risk_score += 0.15 # Complex joint isolation handoff
        if dur > 180:
            risk_score += 0.08

        return {
            "p50": p50,
            "p80": p80,
            "p95": p95,
            "overrun_risk_score": min(0.95, round(risk_score, 2))
        }

    def generate_explanation(self, task: MaintenanceTask, asset: Optional[CanonicalAsset], 
                             prio: float, crit: float, urg: float, shadow: float) -> str:
        """
        Produces natural language explainability string for Chief Controllers & Sr. DOM.
        """
        reasons = []
        if crit >= 80:
            reasons.append(f"High-density {asset.route_class if asset else 'HDN'} safety impact")
        if urg >= 75:
            reasons.append("Overdue / immediate safety defect")
        elif urg >= 50:
            reasons.append("Approaching maintenance window deadline")
            
        if shadow >= 75:
            reasons.append("Excellent multi-department shadow block consolidation candidate")
            
        if not reasons:
            reasons.append("Routine preventative maintenance cycle")

        summary_reason = "; ".join(reasons)
        return f"Priority {round(prio, 1)}/100 (Crit: {round(crit, 0)}, Urg: {round(urg, 0)}, Shadow: {round(shadow, 0)}). Rationale: {summary_reason}."

    def evaluate_task(self, task: MaintenanceTask, all_tasks: List[MaintenanceTask]) -> MaintenanceTask:
        """
        Evaluates and enriches a single maintenance task with composite priority score and analytics.
        """
        asset = self.asset_lookup.get(task.asset_id)
        crit = self.compute_criticality(task, asset)
        urg = self.compute_urgency(task)
        shadow = self.compute_shadow_opportunity(task, all_tasks)
        
        composite_priority = round(0.55 * crit + 0.35 * urg + 0.10 * shadow, 2)
        explanation = self.generate_explanation(task, asset, composite_priority, crit, urg, shadow)
        
        analytics = self.estimate_quantiles_and_risk(task)
        
        task.priority_score = composite_priority
        task.criticality_score = crit
        task.urgency_score = urg
        task.shadow_opportunity_score = shadow
        task.priority_explanation = explanation
        task.predicted_p50_duration_min = analytics["p50"]
        task.predicted_p80_duration_min = analytics["p80"]
        task.predicted_p95_duration_min = analytics["p95"]
        task.overrun_risk_score = analytics["overrun_risk_score"]
        
        return task

    def batch_evaluate(self, tasks: List[MaintenanceTask]) -> List[MaintenanceTask]:
        return [self.evaluate_task(t, tasks) for t in tasks]
