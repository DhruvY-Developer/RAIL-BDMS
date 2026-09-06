"""
Rail-BDMS: End-to-End Division-Scale Simulation Benchmark (TASK-801)
Simulates busy Northern Railway division (NZM-PWL-RDI):
- Ingests 60+ cross-departmental demands (TMS, SMMS, TDMS)
- Resolves disparate asset references (chainage, point IDs, mast IDs)
- Computes multi-factor explainable priority scores
- Solves weekly block allocation with OR-Tools CP-SAT
- Formulates multi-department Shadow Blocks
- Cryptographically certifies Timetable Protection Invariant
"""
import sys
import os
import time

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from backend.app.schemas.schemas import DepartmentEnum
from backend.app.services.ingestion.mock_data import (
    generate_canonical_assets, generate_maintenance_tasks,
    generate_train_movements, generate_corridor_windows
)
from backend.app.services.analytics.priority_engine import PriorityAnalyticsEngine
from backend.app.services.optimizer.horizon_orchestrator import RollingHorizonOrchestrator

def run_benchmark():
    print("=" * 70)
    print("RAIL-BDMS: END-TO-END DIVISION SIMULATION BENCHMARK")
    print("Division: Northern Railway Delhi Division (NZM - PWL - RDI HDN Corridor)")
    print("=" * 70)
    
    t0 = time.time()
    
    # 1. Ingestion
    assets = generate_canonical_assets()
    tasks = generate_maintenance_tasks(assets)
    trains = generate_train_movements()
    windows = generate_corridor_windows()
    
    print(f"[*] Ingested {len(assets)} Canonical Assets across 10 Stations")
    print(f"[*] Ingested {len(tasks)} Maintenance Demands (TMS: {len([t for t in tasks if t.department == DepartmentEnum.ENGINEERING])}, SMMS: {len([t for t in tasks if t.department == DepartmentEnum.S_AND_T])}, TDMS: {len([t for t in tasks if t.department == DepartmentEnum.TRD])})")
    print(f"[*] Ingested {len(trains)} Timetable Train Movements (Vande Bharat, Rajdhani, Suburban, Goods)")
    print(f"[*] Ingested {len(windows)} Candidate Maintenance Corridor Windows")
    
    # 2. Priority Analytics
    prio_engine = PriorityAnalyticsEngine(assets)
    eval_tasks = prio_engine.batch_evaluate(tasks)
    print(f"[*] Computed Explainable Priority Scores for {len(eval_tasks)} demands")
    
    # 3. CP-SAT Scheduling & Shadow Block Packing
    orchestrator = RollingHorizonOrchestrator(assets)
    plan = orchestrator.run_optimization(
        horizon_type="WEEKLY",
        tasks=eval_tasks,
        trains=trains,
        windows=windows,
        enforce_shadow_packing=True,
        timeout_seconds=30
    )
    
    t_total = time.time() - t0
    
    print("-" * 70)
    print("BENCHMARK RESULTS & KPIS:")
    print(f"  Solver Status                 : {plan.solver_status}")
    print(f"  Total Solver Execution Time   : {plan.solve_time_ms} ms (Total End-to-End: {round(t_total, 2)}s)")
    print(f"  Total Tasks Scheduled         : {len(plan.assignments)} / {len(tasks)}")
    print(f"  Shadow Block Groups Formed    : {len(plan.shadow_groups)}")
    print(f"  Separate Possessions Avoided  : {plan.kpis.get('separate_blocks_avoided', 0)}")
    print(f"  Corridor Hours Saved          : {plan.kpis.get('corridor_hours_saved', 0)} hours")
    print(f"  Corridor Utilization Score    : {plan.kpis.get('corridor_utilization_pct', 0)}%")
    print(f"  Timetable Clashes             : {plan.kpis.get('timetable_conflicts', 0)} (ZERO CLASH INVARIANT)")
    print(f"  SHA-256 Safety Certificate    : {plan.certificate.certificate_id} [{plan.certificate.hash_sha256[:16]}...]")
    print("-" * 70)
    
    # Assertions
    assert plan.kpis.get("timetable_conflicts", 0) == 0, "Timetable conflicts must be strictly 0"
    assert len(plan.shadow_groups) >= 2, "Shadow block groups must be formed"
    assert plan.solve_time_ms <= 30000, "Solver execution must be <= 30s"
    assert plan.certificate.verified_zero_clash is True, "Timetable protection certificate must be valid"
    
    print("[SUCCESS] ALL BENCHMARK METRICS SATISFIED!")

if __name__ == "__main__":
    run_benchmark()
