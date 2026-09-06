"""
Rail-BDMS: CTPC / Sr. DOM Authentication Test Suite
Verifies mandatory authentication endpoints for Delhi Control Office operations.
"""
from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)

def test_ctpc_login_success():
    """Verify that designated CTPC / Sr. DOM credentials log in successfully."""
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "CTPC", "password": "CTPC@123"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "SUCCESS"
    assert "token" in data
    assert data["user"]["username"] == "CTPC"
    assert data["user"]["role"] == "CTPC / Sr. DOM"
    assert data["user"]["office"] == "Delhi Control Office"
    assert data["user"]["division"] == "Delhi Division"

def test_ctpc_login_case_insensitivity_for_id():
    """Verify that officer ID is resilient to case ('ctpc' vs 'CTPC')."""
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "ctpc", "password": "CTPC@123"}
    )
    assert response.status_code == 200
    assert response.json()["status"] == "SUCCESS"

def test_ctpc_login_invalid_password():
    """Verify that invalid passwords are strictly rejected with 401."""
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "CTPC", "password": "wrong_password"}
    )
    assert response.status_code == 401
    assert "Access Denied" in response.json()["detail"]

def test_ctpc_login_invalid_username():
    """Verify that unauthorized usernames are strictly rejected."""
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "ADMIN", "password": "CTPC@123"}
    )
    assert response.status_code == 401
    assert "Access Denied" in response.json()["detail"]

def test_session_verify_and_logout():
    """Verify full session lifecycle: login -> verify -> logout -> verify fails."""
    # 1. Login
    login_res = client.post(
        "/api/v1/auth/login",
        json={"username": "CTPC", "password": "CTPC@123"}
    )
    token = login_res.json()["token"]

    # 2. Verify active session
    verify_res = client.get(f"/api/v1/auth/verify?token={token}")
    assert verify_res.status_code == 200
    assert verify_res.json()["status"] == "VALID"
    assert verify_res.json()["user"]["username"] == "CTPC"

    # 3. Logout
    logout_res = client.post("/api/v1/auth/logout", json={"token": token})
    assert logout_res.status_code == 200
    assert logout_res.json()["status"] == "SUCCESS"

    # 4. Verify fails after logout
    verify_after_logout = client.get(f"/api/v1/auth/verify?token={token}")
    assert verify_after_logout.status_code == 401
