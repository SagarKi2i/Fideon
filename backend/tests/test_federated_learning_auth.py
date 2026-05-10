from datetime import datetime, timedelta, timezone

import jwt
from fastapi.testclient import TestClient

from app import factory
from app.routes import federated_learning as fl_routes

TEST_DEVICE_JWT_SECRET = "unit-test-secret-with-32-plus-bytes"


def _make_test_client(monkeypatch) -> TestClient:
    monkeypatch.setattr(factory, "DEVICE_JWT_SECRET", TEST_DEVICE_JWT_SECRET)
    return TestClient(factory.create_app())


def _make_device_jwt(device_id: str = "dev-001", iat: int | None = None) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": device_id,
        "device_id": device_id,
        "type": "device",
        "iat": iat if iat is not None else int(now.timestamp()),
        "exp": int((now + timedelta(hours=1)).timestamp()),
    }
    return jwt.encode(payload, TEST_DEVICE_JWT_SECRET, algorithm="HS256")


def test_federated_learning_accepts_bearer_device_jwt(monkeypatch):
    async def fake_postgrest_get(table: str, query: str):
        if table == "devices":
            return [{"id": "dev-001", "is_active": True, "jwt_issued_after": None}]
        if table == "training_feedback":
            return []
        raise AssertionError(f"unexpected table: {table}")

    monkeypatch.setattr(fl_routes, "DEVICE_JWT_SECRET", TEST_DEVICE_JWT_SECRET)
    monkeypatch.setattr(fl_routes, "postgrest_get", fake_postgrest_get)

    token = _make_device_jwt("dev-001")
    with _make_test_client(monkeypatch) as client:
        response = client.get(
            "/api/federated-learning?action=get-feedback",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert isinstance(body["feedback"], list)


def test_federated_learning_rejects_revoked_bearer_jwt(monkeypatch):
    now = datetime.now(timezone.utc)
    revoked_after = now - timedelta(seconds=10)
    stale_iat = int((now - timedelta(hours=1)).timestamp())

    async def fake_postgrest_get(table: str, _query: str):
        if table == "devices":
            return [{"id": "dev-001", "is_active": True, "jwt_issued_after": revoked_after.isoformat()}]
        raise AssertionError(f"unexpected table: {table}")

    monkeypatch.setattr(fl_routes, "DEVICE_JWT_SECRET", TEST_DEVICE_JWT_SECRET)
    monkeypatch.setattr(fl_routes, "postgrest_get", fake_postgrest_get)

    token = _make_device_jwt("dev-001", iat=stale_iat)
    with _make_test_client(monkeypatch) as client:
        response = client.get(
            "/api/federated-learning?action=get-feedback",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 401
    assert "revoked" in response.json()["error"].lower()


def test_federated_learning_legacy_header_still_works(monkeypatch):
    async def fake_get_device_by_token(token: str):
        assert token == "legacy-device-token"
        return {"id": "legacy-dev-001", "is_active": True}

    async def fake_postgrest_get(table: str, query: str):
        if table == "training_feedback":
            assert "device_id=eq.legacy-dev-001" in query
            return []
        raise AssertionError(f"unexpected table: {table}")

    monkeypatch.setattr(fl_routes, "get_device_by_token", fake_get_device_by_token)
    monkeypatch.setattr(fl_routes, "postgrest_get", fake_postgrest_get)

    with _make_test_client(monkeypatch) as client:
        response = client.get(
            "/api/federated-learning?action=get-feedback",
            headers={"x-device-token": "legacy-device-token"},
        )

    assert response.status_code == 200
    assert response.json()["success"] is True
