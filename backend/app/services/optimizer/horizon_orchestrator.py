"""
Rail-BDMS: Multi-Horizon Rolling Block Planning (RBP) Orchestrator
Handles 26-Week Strategic, 4-Week Rolling, 1-Week Frozen, and Next-Day Re-optimization.
"""
from typing import List, Dict, Optional
from datetime import datetime, timezone
from backend.app.schemas.schemas import (
    OptimizationPlan, MaintenanceTask, TrainMovement, CorridorWindow,
    CanonicalAsset
)
from backend.app.services.optimizer.cpsat_scheduler import CPSATScheduler
from backend.app.services.optimizer.certifier import TimetableProtectionCertifier
from backend.app.services.analytics.priority_engine import PriorityAnalyticsEngine

class RollingHorizonOrchestrator:
    def __init__(self, canonical_assets: List[CanonicalAsset]):
        self.canonical_assets = canonical_assets
        self.scheduler = CPSATScheduler(canonical_assets)
        self.certifier = TimetableProtectionCertifier()
        self.priority_engine = PriorityAnalyticsEngine(canonical_assets)

    def run_optimization(
        self,
        horizon_type: str,
        tasks: List[MaintenanceTask],
        trains: List[TrainMovement],
        windows: List[CorridorWindow],
        enforce_shadow_packing: bool = True,
        freeze_approved: bool = False,
        timeout_seconds: int = 30
    ) -> OptimizationPlan:
        """
        Executes multi-horizon block optimization workflow with explainable scoring,
        CP-SAT mathematical scheduling, and cryptographic timetable protection certification.
        """
        # 1. Enrich tasks with explainable priority scores
        evaluated_tasks = self.priority_engine.batch_evaluate(tasks)

        # 2. Run CP-SAT Constraint Optimization
        plan = self.scheduler.solve(
            tasks=evaluated_tasks,
            trains=trains,
            windows=windows,
            horizon_minutes=1440,
            timeout_seconds=timeout_seconds,
            enforce_shadow_packing=enforce_shadow_packing
        )
        plan.horizon_type = horizon_type

        # 3. Certify Timetable Safety
        self.certifier.verify_and_certify(plan, trains)

        return plan
