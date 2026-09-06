"""
Rail-BDMS: Geospatial GIS Map & Live Train Radar Test Suite
Tests API key provisioning, key rotation, and real-time train coordinate computation.
"""
from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)

def test_gis_config_endpoint():
    """Verify GIS configuration returns active API key and corridor definitions."""
    response = client.get("/api/v1/gis/config")
    assert response.status_code == 200
    data = response.json()
    assert "api_key" in data
    assert data["api_key"].startswith("IR-GIS-DEL-")
    assert "available_layers" in data
    assert len(data["available_layers"]) >= 3
    assert "corridor_bounds" in data
    assert data["status"] == "ACTIVE_AUTHENTICATED"

def test_gis_api_key_regeneration():
    """Verify that regenerating the GIS API key issues a fresh authenticated key."""
    # 1. Fetch initial key
    initial_res = client.get("/api/v1/gis/config")
    initial_key = initial_res.json()["api_key"]

    # 2. Regenerate key
    regen_res = client.post("/api/v1/gis/api-key/regenerate")
    assert regen_res.status_code == 200
    regen_data = regen_res.json()
    assert regen_data["status"] == "SUCCESS"
    new_key = regen_data["new_api_key"]
    assert new_key.startswith("IR-GIS-DEL-")
    assert new_key != initial_key

    # 3. Subsequent config request reflects the new key
    updated_res = client.get("/api/v1/gis/config")
    assert updated_res.json()["api_key"] == new_key

def test_trains_live_positions_telemetry():
    """Verify live train telemetry returns valid geospatial positions, heading, and speed."""
    response = client.get("/api/v1/trains/live-positions")
    assert response.status_code == 200
    trains = response.json()
    assert isinstance(trains, list)
    assert len(trains) > 0

    first_train = trains[0]
    required_fields = [
        "train_number", "train_name", "priority_class", "line",
        "section_id", "lat", "lon", "speed_kmh", "heading",
        "progress_pct", "origin_stn", "destination_stn", "safety_status"
    ]
    for field in required_fields:
        assert field in first_train, f"Missing {field} in train telemetry"

    # Coordinates must be within Delhi - Palwal corridor bounding box (~28.0 to ~28.7 lat, ~77.1 to ~77.5 lon)
    assert 27.9 <= first_train["lat"] <= 28.8
    assert 77.0 <= first_train["lon"] <= 77.6
    assert 0 <= first_train["progress_pct"] <= 100
    assert first_train["speed_kmh"] >= 0
