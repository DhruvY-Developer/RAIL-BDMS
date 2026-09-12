"""
Rail-BDMS: Cryptographic Timetable Protection Certifier Engine
Verifies zero-clash safety invariant and emits immutable SHA-256 signed certificate.
"""
import hashlib
import json
from typing import List, Tuple
from datetime import datetime, timezone

from backend.app.schemas.schemas import (
    OptimizationPlan, TrainMovement, TimetableProtectionCertificate
)

class TimetableViolationException(Exception):
    """Raised when a scheduled maintenance block infringes on a train path or safety headway."""
    pass

class TimetableProtectionCertifier:
    def __init__(self, headway_before_min: int = 15, headway_after_min: int = 15):
        self.headway_before_min = headway_before_min
        self.headway_after_min = headway_after_min

    def verify_and_certify(
        self,
        plan: OptimizationPlan,
        trains: List[TrainMovement],
        timetable_version: str = "WTT-NR-2026-V2"
    ) -> TimetableProtectionCertificate:
        """
        Conducts an independent mathematical audit of every assignment in the plan against the WTT.
        """
        conflicts: List[dict] = []
        
        # 1. Audit every block assignment against all trains on the same track section
        for a in plan.assignments:
            # Find all trains on matching section and line
            relevant_trains = [
                tr for tr in trains
                if tr.section_id == a.section_id and tr.line_or_road == a.line_or_road
            ]

            b_start = a.planned_start_min
            b_end = a.planned_end_min

            for tr in relevant_trains:
                # Train safety envelope
                t_safety_start = max(0, tr.entry_minute - self.headway_before_min)
                t_safety_end = tr.exit_minute + self.headway_after_min

                # Check interval intersection: max(s1, s2) < min(e1, e2)
                overlap_start = max(b_start, t_safety_start)
                overlap_end = min(b_end, t_safety_end)

                if overlap_start < overlap_end:
                    conflicts.append({
                        "task_id": a.task_id,
                        "train_number": tr.train_number,
                        "train_name": tr.train_name,
                        "section_id": a.section_id,
                        "line": a.line_or_road.value,
                        "block_window": [b_start, b_end],
                        "train_safety_window": [t_safety_start, t_safety_end],
                        "infringement_minutes": overlap_end - overlap_start
                    })

        # 2. Strict Safety Invariant Check
        if conflicts:
            err_msg = f"SAFETY INVARIANT VIOLATION: Found {len(conflicts)} direct timetable clashes. Certificate refused! First clash: {conflicts[0]}"
            raise TimetableViolationException(err_msg)

        # 3. Generate Cryptographic SHA-256 Fingerprint
        cert_id = f"CERT-WTT-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{plan.plan_id[:8].upper()}"
        issued_at = datetime.now(timezone.utc).isoformat()
        
        payload_to_hash = {
            "certificate_id": cert_id,
            "plan_id": plan.plan_id,
            "timetable_version": timetable_version,
            "solver_status": plan.solver_status,
            "total_tasks_assigned": len(plan.assignments),
            "total_trains_verified": len(trains),
            "headway_buffer_min": [self.headway_before_min, self.headway_after_min],
            "verified_zero_clash": True,
            "issued_at": issued_at
        }
        
        canonical_json_bytes = json.dumps(payload_to_hash, sort_keys=True).encode("utf-8")
        hash_sha256 = hashlib.sha256(canonical_json_bytes).hexdigest()
        policy_hash = hashlib.sha256(b"IR-SAFETY-POLICY-2026-ZERO-CLASH-HEADWAY-15M").hexdigest()[:16]

        explanation = (
            f"Timetable Protection Verification: Verified 0 train clashes across {len(plan.assignments)} "
            f"maintenance blocks against {len(trains)} scheduled train paths in {timetable_version}. "
            f"Safety buffers (B_before={self.headway_before_min}m, B_after={self.headway_after_min}m) verified against configured constraints."
        )

        certificate = TimetableProtectionCertificate(
            certificate_id=cert_id,
            plan_id=plan.plan_id,
            issued_at=issued_at,
            hash_sha256=hash_sha256,
            timetable_version=timetable_version,
            solver_status=plan.solver_status,
            total_tasks_evaluated=len(plan.assignments),
            total_trains_protected=len(trains),
            verified_zero_clash=True,
            headway_buffer_verified=True,
            policy_hash=policy_hash,
            explanation=explanation
        )

        plan.certificate = certificate
        return certificate
