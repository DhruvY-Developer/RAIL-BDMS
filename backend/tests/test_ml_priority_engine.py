"""
Rail-BDMS Requirement 2 Test Suite: AI/ML Maintenance Criticality, Urgency & Priority Engine
Verifies ML model training, artifact serialization, calibrated risk inference,
availability impact, operational traffic exposure, explainability decomposition,
safety override invariant, cold-start fallback handling, and REST endpoints.
"""
import pytest
import numpy as np
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.schemas.schemas import (
    CanonicalAsset, MaintenanceTask, SafetyClassEnum, DepartmentEnum,
    SourceSystemEnum, MachineTypeEnum, AssetTypeEnum, LineOrRoadEnum
)
from backend.app.services.ml.feature_extractor import FeatureExtractor, FEATURE_NAMES
from backend.app.services.ml.training_pipeline import train_and_evaluate_model
from backend.app.services.ml.inference_service import InferenceService
from backend.app.services.analytics.priority_engine import PriorityAnalyticsEngine

client = TestClient(app)

@pytest.fixture
def sample_asset():
    return CanonicalAsset(
        asset_id="TEST-AST-01",
        source_system=SourceSystemEnum.TMS,
        source_asset_id="TKD-SW-101",
        asset_type=AssetTypeEnum.TRACK_SEGMENT,
        department=DepartmentEnum.ENGINEERING,
        section_id="TKD-FDB",
        station_from="TKD",
        station_to="FDB",
        chainage_from=18.5,
        chainage_to=19.5,
        line_or_road=LineOrRoadEnum.DOWN,
        route_class="HDN",
        criticality_class="CLASS_A",
        last_inspected="2026-08-01"
    )

@pytest.fixture
def inference_engine(sample_asset):
    return InferenceService([sample_asset])

# =========================================================================
# 1. Model Training & Serialization Tests
# =========================================================================
def test_ml_model_training_and_serialization():
    meta = train_and_evaluate_model()
    assert meta["model_name"] == "RailRisk"
    assert meta["model_version"] == "v1.0"
    assert meta["data_mode"] == "Prototype ML Model — Synthetic Training Data"
    assert meta["split_strategy"].startswith("Chronological")
    assert "metrics" in meta
    assert meta["metrics"]["f1_score"] >= 0.70
    assert meta["metrics"]["roc_auc"] >= 0.85
    assert len(meta["feature_importances"]) == 17

def test_inference_service_loading_and_metadata(inference_engine):
    meta = inference_engine.get_metadata()
    assert meta["model_name"] == "RailRisk"
    assert "feature_names" in meta
    assert len(meta["feature_names"]) == 17
    assert inference_engine.model is not None

# =========================================================================
# 2. Feature Extraction & Robustness (Missing Values & Unknown Categories)
# =========================================================================
def test_feature_extractor_robustness():
    extractor = FeatureExtractor([]) # No asset lookup
    
    # Task with completely unknown/missing fields
    bare_task = MaintenanceTask(
        source_system=SourceSystemEnum.TMS,
        source_task_id="TMS-UNK-999",
        asset_id="NON_EXISTENT_ASSET",
        department=DepartmentEnum.ENGINEERING,
        task_type="UNKNOWN_TASK_TYPE",
        description="Unknown task with minimal data",
        created_at="invalid-date",
        due_at="invalid-date",
        latest_completion_date="invalid-date",
        estimated_duration_min=120,
        min_duration_min=60,
        max_duration_min=180
    )
    
    f_dict = extractor.extract_features_dict(bare_task)
    assert len(f_dict) == 17
    for name in FEATURE_NAMES:
        assert name in f_dict
        assert isinstance(f_dict[name], (int, float))
        assert not np.isnan(f_dict[name])

# =========================================================================
# 3. AI Risk Prediction, Classification & Cold-Start
# =========================================================================
def test_ai_risk_prediction_output_structure(inference_engine, sample_asset):
    now = datetime.now(timezone.utc)
    task = MaintenanceTask(
        source_system=SourceSystemEnum.TMS,
        source_task_id="TMS-REG-101",
        asset_id=sample_asset.asset_id,
        department=DepartmentEnum.ENGINEERING,
        task_type="PLAIN_TRACK_TAMPING_CSM",
        description="Routine tamping",
        created_at=now.isoformat(),
        due_at=(now + timedelta(days=5)).isoformat(),
        latest_completion_date=(now + timedelta(days=7)).isoformat(),
        estimated_duration_min=120,
        min_duration_min=90,
        max_duration_min=150,
        safety_class=SafetyClassEnum.OPERATIONAL_DEFECT
    )
    
    pred = inference_engine.predict_task(task, simulated_now=now)
    assert 0.0 <= pred["ai_risk_score"] <= 100.0
    assert pred["ai_risk_class"] in ["LOW", "MODERATE", "HIGH", "CRITICAL"]
    assert 0.0 <= pred["ai_priority_score"] <= 100.0
    assert pred["prediction_horizon"] == "7 Days"
    assert "RailRisk" in pred["model_version"]
    assert len(pred["ai_contributing_factors"]) > 0

def test_cold_start_handling(inference_engine):
    now = datetime.now(timezone.utc)
    unknown_task = MaintenanceTask(
        source_system=SourceSystemEnum.TMS,
        source_task_id="TMS-NEW-001",
        asset_id="TOTALLY_NEW_UNSEEN_ASSET",
        department=DepartmentEnum.ENGINEERING,
        task_type="PLAIN_TRACK_TAMPING_CSM",
        description="Task on unseen asset",
        created_at=now.isoformat(),
        due_at=(now + timedelta(days=3)).isoformat(),
        latest_completion_date=(now + timedelta(days=5)).isoformat(),
        estimated_duration_min=120,
        min_duration_min=90,
        max_duration_min=150,
        safety_class=SafetyClassEnum.OPERATIONAL_DEFECT
    )
    
    pred = inference_engine.predict_task(unknown_task, simulated_now=now)
    assert pred["is_cold_start"] is True
    assert pred["ai_confidence_level"] == "INSUFFICIENT_HISTORY"

# =========================================================================
# 4. Safety-First Prioritization & Override Invariant
# =========================================================================
def test_safety_critical_override_protection(inference_engine, sample_asset):
    now = datetime.now(timezone.utc)
    
    # Even if due far in future (low urgency), safety critical IMR defect cannot be downgraded
    imr_task = MaintenanceTask(
        source_system=SourceSystemEnum.TMS,
        source_task_id="TMS-IMR-999",
        asset_id=sample_asset.asset_id,
        department=DepartmentEnum.ENGINEERING,
        task_type="RAIL_FRACTURE_IMR_EMERGENCY",
        description="Immediate Removal Ultrasonic Rail Flaw",
        created_at=now.isoformat(),
        due_at=(now + timedelta(days=10)).isoformat(),
        latest_completion_date=(now + timedelta(days=12)).isoformat(),
        estimated_duration_min=120,
        min_duration_min=90,
        max_duration_min=150,
        safety_class=SafetyClassEnum.SAFETY_CRITICAL,
        criticality_score=95.0,
        urgency_score=85.0
    )
    
    pred = inference_engine.predict_task(imr_task, simulated_now=now)
    # Priority floor must be >= 85
    assert pred["ai_priority_score"] >= 85.0
    assert pred["ai_risk_class"] in ["HIGH", "CRITICAL"]
    assert "SAFETY OVERRIDE ENFORCED" in pred["ai_explanation"]

# =========================================================================
# 5. Explainability Decomposition
# =========================================================================
def test_explainability_corresponds_to_features(inference_engine, sample_asset):
    now = datetime.now(timezone.utc)
    task = MaintenanceTask(
        source_system=SourceSystemEnum.TMS,
        source_task_id="TMS-EXP-101",
        asset_id=sample_asset.asset_id,
        department=DepartmentEnum.ENGINEERING,
        task_type="RAIL_FRACTURE_IMR_REPAIR",
        description="Emergency rail weld fracture",
        created_at=(now - timedelta(days=25)).isoformat(),
        due_at=(now - timedelta(days=15)).isoformat(), # 15 days overdue!
        latest_completion_date=(now - timedelta(days=12)).isoformat(),
        estimated_duration_min=180,
        min_duration_min=120,
        max_duration_min=240,
        safety_class=SafetyClassEnum.SAFETY_CRITICAL
    )
    
    pred = inference_engine.predict_task(task, simulated_now=now)
    factors = pred["ai_contributing_factors"]
    assert len(factors) == 5
    top_feature_names = [f["feature"] for f in factors]
    # Defect severity and days overdue should be among top contributors
    assert any("defect_severity" in fn or "days_overdue" in fn for fn in top_feature_names)
    assert len(pred["ai_explanation"]) > 10

# =========================================================================
# 6. Required Demonstration Scenario (Tasks A, B, C)
# =========================================================================
def test_demo_scenario_differentiation(inference_engine):
    demo = inference_engine.get_demo_scenario()
    assert "tasks" in demo
    assert len(demo["tasks"]) == 3
    
    task_a = demo["tasks"][0]["prediction"]
    task_b = demo["tasks"][1]["prediction"]
    task_c = demo["tasks"][2]["prediction"]
    
    # Task A: Critical (~91-96%)
    assert task_a["ai_risk_score"] >= 80.0
    assert task_a["ai_priority_score"] >= 85.0
    assert task_a["ai_risk_class"] == "CRITICAL"
    
    # Task B: Moderate (~40-65%)
    assert 30.0 <= task_b["ai_risk_score"] <= 75.0
    assert 40.0 <= task_b["ai_priority_score"] <= 75.0
    
    # Task C: Low (~4-25%)
    assert task_c["ai_risk_score"] <= 30.0
    assert task_c["ai_priority_score"] <= 35.0
    assert task_c["ai_risk_class"] == "LOW"
    
    # Monotonicity check
    assert task_a["ai_risk_score"] > task_b["ai_risk_score"] > task_c["ai_risk_score"]
    assert task_a["ai_priority_score"] > task_b["ai_priority_score"] > task_c["ai_priority_score"]

# =========================================================================
# 7. REST API Endpoints Verification
# =========================================================================
def test_api_ml_metadata():
    res = client.get("/api/v1/ml/metadata")
    assert res.status_code == 200
    data = res.json()
    assert data["model_name"] == "RailRisk"
    assert data["model_version"] == "v1.0"
    assert data["prediction_horizon"] == "7 Days"
    assert data["data_mode"] == "Prototype ML Model — Synthetic Training Data"
    assert "metrics" in data
    assert "feature_importances" in data

def test_api_ml_prioritized_tasks():
    res = client.get("/api/v1/ml/prioritized-tasks")
    assert res.status_code == 200
    tasks = res.json()
    assert len(tasks) > 0
    # Verify sorted descending by ai_priority_score
    priors = [t["ai_priority_score"] for t in tasks if t.get("ai_priority_score") is not None]
    assert priors == sorted(priors, reverse=True)
    # Verify both deterministic priority_score and ai_priority_score exist
    assert tasks[0]["priority_score"] is not None
    assert tasks[0]["ai_priority_score"] is not None

def test_api_ml_explain():
    # Fetch first task ID
    tasks_res = client.get("/api/v1/tasks")
    task_id = tasks_res.json()[0]["task_id"]
    
    res = client.get(f"/api/v1/ml/explain/{task_id}")
    assert res.status_code == 200
    exp = res.json()
    assert exp["task_id"] == task_id
    assert "ai_risk_score" in exp
    assert "ai_risk_class" in exp
    assert "deterministic_score" in exp
    assert "top_contributing_factors" in exp
    assert "availability_impact_score" in exp
    assert "traffic_exposure_score" in exp
    assert exp["prediction_horizon"] == "7 Days"

def test_api_ml_demo_scenario():
    res = client.get("/api/v1/ml/demo-scenario")
    assert res.status_code == 200
    data = res.json()
    assert len(data["tasks"]) == 3
    assert data["tasks"][0]["demo_id"] == "TASK_A"
    assert data["tasks"][1]["demo_id"] == "TASK_B"
    assert data["tasks"][2]["demo_id"] == "TASK_C"

def test_api_ml_monitoring():
    res = client.get("/api/v1/ml/monitoring")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "OPERATIONAL_HEALTHY"
    assert "feature_averages" in data
    assert "total_predictions_served" in data

def test_api_overview_kpis_contains_ml_intelligence():
    res = client.get("/api/v1/overview/kpis")
    assert res.status_code == 200
    kpis = res.json()
    assert "ml_intelligence" in kpis
    assert kpis["ml_intelligence"]["model_name"] == "RailRisk"
    assert kpis["ml_intelligence"]["prediction_horizon"] == "7 Days"
