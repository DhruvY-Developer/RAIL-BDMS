"""
Rail-BDMS: Goods Train Forecast Source Adapter (Control Office / FOIS)
Ingests Freight Traffic Forecasts, expected goods train paths, forecast windows, and confidence metrics.
"""
from typing import List, Dict, Any, Tuple
from datetime import datetime, timedelta, timezone

from backend.app.schemas.integration import GoodsTrainForecast
from backend.app.services.ingestion.base_adapter import BaseSourceAdapter

class GoodsForecastAdapter(BaseSourceAdapter):
    def __init__(self):
        super().__init__(
            source_id="GOODS_FORECAST",
            source_name="Control Office / Goods Freight Forecast (FOIS)",
            department="Operating / Freight Operations Control",
            description="Dynamic Freight Traffic Forecasting, Expected Goods Rakes & Movement Window Predictions"
        )

    def fetch_raw(self) -> List[Dict[str, Any]]:
        raw_list: List[Dict[str, Any]] = []
        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        now = datetime.now(timezone.utc)

        # Realistic Indian Railways freight forecast windows for Delhi Division (NZM-PWL HDN corridor)
        FORECAST_DATA = [
            {
                "window": "00:00-04:00",
                "start_m": 0, "end_m": 240,
                "corridor": "NZM-PWL",
                "section": "NZM-OKA",
                "direction": "DOWN",
                "count": 2,
                "paths": ["COAL-44-DN", "BCN-GRAIN-88"],
                "confidence": 88.5,
                "impact": "LOW",
                "category": "COAL / GRAIN RAKES",
                "notes": "Night mega-block window: Freight can be diverted via Tuglakabad yard bypass."
            },
            {
                "window": "00:00-04:00",
                "start_m": 0, "end_m": 240,
                "corridor": "PWL-NZM",
                "section": "PWL-RDI",
                "direction": "UP",
                "count": 3,
                "paths": ["BOXN-IRON-102", "CONT-JNPT-332", "FLYASH-BULK-09"],
                "confidence": 84.0,
                "impact": "MODERATE",
                "category": "CONTAINER / FLYASH",
                "notes": "Expected arrival from Mathura / Western DFC feeder line."
            },
            {
                "window": "04:00-08:00",
                "start_m": 240, "end_m": 480,
                "corridor": "NZM-PWL",
                "section": "OKA-TKD",
                "direction": "BOTH",
                "count": 1,
                "paths": ["TKD-SHUNTER-04"],
                "confidence": 92.0,
                "impact": "LOW",
                "category": "CONTAINER SHUNTING",
                "notes": "Morning commuter peak hours: strictly regulated through Tuglakabad ICD."
            },
            {
                "window": "08:00-12:00",
                "start_m": 480, "end_m": 720,
                "corridor": "NZM-PWL",
                "section": "TKD-FDB",
                "direction": "DOWN",
                "count": 2,
                "paths": ["CONRAJ-91-DN", "TANKER-POL-11"],
                "confidence": 86.0,
                "impact": "MODERATE",
                "category": "CONTAINER / PETROLEUM (POL)",
                "notes": "High-priority petroleum tank wagon passage."
            },
            {
                "window": "12:00-16:00",
                "start_m": 720, "end_m": 960,
                "corridor": "NZM-PWL",
                "section": "FDB-FDN",
                "direction": "UP",
                "count": 4,
                "paths": ["COAL-DADRI-44", "BCN-FOOD-71", "CEMENT-BULK-18", "AUTO-RAKE-MARUTI-02"],
                "confidence": 89.0,
                "impact": "HIGH",
                "category": "COAL / AUTOMOBILE / CEMENT",
                "notes": "Mid-day freight corridor surge: auto rake out of Gurgaon/Faridabad cluster."
            },
            {
                "window": "16:00-20:00",
                "start_m": 960, "end_m": 1200,
                "corridor": "NZM-PWL",
                "section": "FDN-BVH",
                "direction": "BOTH",
                "count": 2,
                "paths": ["STEEL-COIL-40", "CONRAJ-92-UP"],
                "confidence": 91.5,
                "impact": "MODERATE",
                "category": "STEEL / CONTAINER",
                "notes": "Evening passenger peak: held at Ballabgarh loop line if required."
            },
            {
                "window": "20:00-24:00",
                "start_m": 1200, "end_m": 1440,
                "corridor": "NZM-PWL",
                "section": "BVH-AST",
                "direction": "DOWN",
                "count": 5,
                "paths": ["COAL-SUPER-1", "COAL-SUPER-2", "BCN-FERTILIZER", "CONT-TKD-ICD-88", "BALLAST-HOPPER-01"],
                "confidence": 87.0,
                "impact": "HIGH",
                "category": "HEAVY HAUL COAL / FERTILIZER",
                "notes": "Night freight surge into Northern thermal power plants."
            },
            {
                "window": "20:00-24:00",
                "start_m": 1200, "end_m": 1440,
                "corridor": "PWL-NZM",
                "section": "AST-PWL",
                "direction": "UP",
                "count": 3,
                "paths": ["EMPTY-RAKE-TKD", "MILITARY-SPECIAL-03", "BCN-FOOD-GRAIN"],
                "confidence": 85.0,
                "impact": "MODERATE",
                "category": "EMPTY RAKES / STRATEGIC",
                "notes": "Returning empty rakes to South-Eastern coalfields."
            }
        ]

        idx = 1
        for fc in FORECAST_DATA:
            raw_list.append({
                "forecast_reference_id": f"FOIS-FCST-DEL-2026-{idx:03d}",
                "forecast_date": today_str,
                "time_window": fc["window"],
                "start_minute": fc["start_m"],
                "end_minute": fc["end_m"],
                "corridor_id": fc["corridor"],
                "section_id": fc["section"],
                "direction": fc["direction"],
                "expected_goods_train_count": fc["count"],
                "expected_train_paths": fc["paths"],
                "confidence_pct": fc["confidence"],
                "operational_impact": fc["impact"],
                "train_category": fc["category"],
                "notes": fc["notes"],
                "source_agency": "Control Office / FOIS",
                "generation_timestamp": (now - timedelta(hours=2)).isoformat()
            })
            idx += 1

        return raw_list

    def normalize(self, raw_data: List[Dict[str, Any]]) -> List[GoodsTrainForecast]:
        normalized: List[GoodsTrainForecast] = []
        now = datetime.now(timezone.utc)

        for r in raw_data:
            fcst = GoodsTrainForecast(
                forecast_id=r["forecast_reference_id"],
                forecast_date=r["forecast_date"],
                time_window=r["time_window"],
                start_minute=r["start_minute"],
                end_minute=r["end_minute"],
                corridor_id=r["corridor_id"],
                section_id=r["section_id"],
                direction=r["direction"],
                expected_goods_train_count=r["expected_goods_train_count"],
                expected_train_paths=r["expected_train_paths"],
                confidence_pct=r["confidence_pct"],
                forecast_generated_at=r["generation_timestamp"],
                source="Control Office / Goods Freight Forecast (FOIS)",
                train_category=r["train_category"],
                is_simulated=True,
                operational_impact=r["operational_impact"],
                notes=r["notes"],
                last_sync=now.isoformat(),
                validation_status="VALID"
            )
            normalized.append(fcst)

        return normalized

    def validate(self, normalized_records: List[GoodsTrainForecast]) -> Tuple[List[GoodsTrainForecast], List[Dict[str, Any]]]:
        valid_records: List[GoodsTrainForecast] = []
        issues: List[Dict[str, Any]] = []

        for f in normalized_records:
            f_issues = []
            if f.expected_goods_train_count < 0:
                f_issues.append("Expected goods train count cannot be negative")
            if not (0.0 <= f.confidence_pct <= 100.0):
                f_issues.append("Confidence score out of 0-100% range")
            if not f.time_window:
                f_issues.append("Missing forecast time window")

            if f_issues:
                issues.append({
                    "forecast_id": f.forecast_id,
                    "source": "GOODS_FORECAST",
                    "issues": f_issues
                })
            valid_records.append(f)

        return valid_records, issues
