"""
Rail-BDMS: Deterministic Asset Identity Resolution Engine
Implements 4-Tier Matching Hierarchy for Cross-Departmental Identity Linking
"""
import math
from typing import List, Optional, Tuple
from backend.app.schemas.schemas import (
    CanonicalAsset, RawAssetDemand, IdentityResolutionResult,
    DepartmentEnum, SourceSystemEnum, LineOrRoadEnum
)

def haversine_distance_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Computes great-circle distance between two GPS coordinates in meters.
    """
    R = 6371000  # Radius of earth in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    
    a = math.sin(delta_phi / 2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def calculate_interval_overlap_ratio(s1: float, e1: float, s2: float, e2: float) -> float:
    """
    Computes Intersection over Union (IoU) of chainage intervals.
    """
    if s1 > e1:
        s1, e1 = e1, s1
    if s2 > e2:
        s2, e2 = e2, s2
        
    overlap_start = max(s1, s2)
    overlap_end = min(e1, e2)
    overlap_len = max(0.0, overlap_end - overlap_start)
    
    len1 = max(0.001, e1 - s1)
    len2 = max(0.001, e2 - s2)
    
    # Overlap relative to the requested demand length
    overlap_ratio = overlap_len / min(len1, len2)
    return min(1.0, overlap_ratio)

class AssetIdentityResolver:
    def __init__(self, canonical_assets: List[CanonicalAsset]):
        self.canonical_assets = canonical_assets
        # Build lookup tables for Tier 1
        self.asset_by_source: dict = {
            (a.source_system.value, a.source_asset_id): a for a in canonical_assets
        }

    def resolve_demand(self, demand: RawAssetDemand) -> IdentityResolutionResult:
        """
        Executes the 4-tier deterministic resolution algorithm on an inbound raw demand.
        """
        # --- TIER 1: Exact Enterprise Asset ID Match ---
        exact_key = (demand.source_system.value, demand.source_asset_id)
        if exact_key in self.asset_by_source:
            matched = self.asset_by_source[exact_key]
            return IdentityResolutionResult(
                resolved_asset_id=matched.asset_id,
                canonical_asset=matched,
                confidence_score=1.00,
                matched_tier="TIER_1_EXACT",
                rationale=f"Exact cross-system match for {demand.source_system.value} ID: {demand.source_asset_id}",
                requires_human_reconciliation=False
            )

        # --- TIER 2: Section ID + Line/Road + Station Hierarchy Match ---
        tier2_candidates = [
            a for a in self.canonical_assets
            if a.section_id == demand.section_id
            and a.line_or_road == demand.line_or_road
            and (not demand.station_from or a.station_from == demand.station_from)
            and (not demand.station_to or a.station_to == demand.station_to)
        ]
        
        # If filtered candidates narrow down to department/asset type match
        if tier2_candidates:
            # Check if there is a department-aligned asset in this section
            dept_matches = [a for a in tier2_candidates if a.department == demand.department]
            if len(dept_matches) == 1:
                matched = dept_matches[0]
                return IdentityResolutionResult(
                    resolved_asset_id=matched.asset_id,
                    canonical_asset=matched,
                    confidence_score=0.95,
                    matched_tier="TIER_2_HIERARCHY",
                    rationale=f"Resolved via Station-Section hierarchy ({demand.section_id} {demand.line_or_road.value}) for {demand.department.value}",
                    requires_human_reconciliation=False
                )

        # --- TIER 3: Chainage Interval Overlap >= 90% ---
        if demand.chainage_from is not None and demand.chainage_to is not None:
            best_overlap = 0.0
            best_asset: Optional[CanonicalAsset] = None
            
            for a in self.canonical_assets:
                if a.section_id == demand.section_id and a.line_or_road == demand.line_or_road:
                    overlap = calculate_interval_overlap_ratio(
                        demand.chainage_from, demand.chainage_to,
                        a.chainage_from, a.chainage_to
                    )
                    if overlap > best_overlap:
                        best_overlap = overlap
                        best_asset = a
                        
            if best_overlap >= 0.90 and best_asset:
                conf = round(0.90 + 0.08 * (best_overlap - 0.90) / 0.10, 3)
                return IdentityResolutionResult(
                    resolved_asset_id=best_asset.asset_id,
                    canonical_asset=best_asset,
                    confidence_score=conf,
                    matched_tier="TIER_3_CHAINAGE",
                    rationale=f"Chainage interval overlap {round(best_overlap * 100, 1)}% on [{best_asset.chainage_from}, {best_asset.chainage_to}] km",
                    requires_human_reconciliation=False
                )

        # --- TIER 4: Spatial GPS Buffer Proximity <= 25 Meters ---
        if demand.latitude is not None and demand.longitude is not None:
            closest_dist = float("inf")
            closest_asset: Optional[CanonicalAsset] = None
            
            for a in self.canonical_assets:
                if a.latitude is not None and a.longitude is not None:
                    dist = haversine_distance_meters(
                        demand.latitude, demand.longitude,
                        a.latitude, a.longitude
                    )
                    if dist < closest_dist:
                        closest_dist = dist
                        closest_asset = a
                        
            if closest_dist <= 25.0 and closest_asset:
                conf = round(0.85 + 0.04 * ((25.0 - closest_dist) / 25.0), 3)
                return IdentityResolutionResult(
                    resolved_asset_id=closest_asset.asset_id,
                    canonical_asset=closest_asset,
                    confidence_score=conf,
                    matched_tier="TIER_4_SPATIAL",
                    rationale=f"Spatial buffer proximity {round(closest_dist, 1)}m <= 25m to asset {closest_asset.source_asset_id}",
                    requires_human_reconciliation=False
                )

        # --- UNRESOLVED / ROUTE TO HUMAN RECONCILIATION QUEUE ---
        return IdentityResolutionResult(
            resolved_asset_id=None,
            canonical_asset=None,
            confidence_score=0.45,
            matched_tier="UNRESOLVED",
            rationale=f"Asset identity ambiguity (confidence 0.45 < 0.85 threshold). Routed to Chief Controller Manual Reconciliation Queue.",
            requires_human_reconciliation=True
        )

    def batch_resolve(self, demands: List[RawAssetDemand]) -> List[IdentityResolutionResult]:
        return [self.resolve_demand(d) for d in demands]
