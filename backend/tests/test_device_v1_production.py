from datetime import datetime, timedelta, timezone

import jwt
from fastapi.testclient import TestClient

from app import factory
from app.routes import device as device_routes

TEST_DEVICE_JWT_SECRET = "unit-test-secret-with-32-plus-bytes"


def _make_test_client(monkeypatch) -> TestClient:
    # Lifespan startup validates this secret before app boots.
    monkeypatch.setattr(factory, "DEVICE_JWT_SECRET", TEST_DEVICE_JWT_SECRET)
    return TestClient(factory.create_app())


def test_register_v1_is_idempotent_and_returns_signed_jwt(monkeypatch):
    async def fake_postgrest_get(table: str, query: str):
        assert table == "devices"
        assert "hardware_fingerprint_hash=eq." in query
        return [
            {
                "id": "dev-001",
                "device_name": "Existing Device",
                "os_type": "windows",
                "app_version": "1.0.0",
            }
        ]

    patch_calls = []

    async def fake_postgrest_patch(table: str, query: str, payload: dict):
        patch_calls.append((table, query, payload))

    async def fake_postgrest_insert(table: str, payload: dict):
        raise AssertionError("insert should not be called for idempotent re-registration")

    async def fake_insert_audit_log(**_kwargs):
        return None

    monkeypatch.setattr(device_routes, "DEVICE_JWT_SECRET", TEST_DEVICE_JWT_SECRET)
    monkeypatch.setattr(device_routes, "postgrest_get", fake_postgrest_get)
    monkeypatch.setattr(device_routes, "postgrest_patch", fake_postgrest_patch)
    monkeypatch.setattr(device_routes, "postgrest_insert", fake_postgrest_insert)
    monkeypatch.setattr(device_routes, "insert_audit_log", fake_insert_audit_log)

    with _make_test_client(monkeypatch) as client:
        response = client.post(
            "/api/v1/devices/register",
            json={
                "hardware_fingerprint": "ABC-123",
                "device_name": "Updated Name",
                "os_type": "windows",
                "app_version": "1.2.3",
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["device_id"] == "dev-001"
    assert body["is_new"] is False
    assert isinstance(body["device_token"], str) and body["device_token"]

    decoded = jwt.decode(body["device_token"], TEST_DEVICE_JWT_SECRET, algorithms=["HS256"])
    assert decoded["device_id"] == "dev-001"
    assert decoded["type"] == "device"

    assert len(patch_calls) == 1
    table, query, payload = patch_calls[0]
    assert table == "devices"
    assert "id=eq.dev-001" in query
    assert payload["status"] == "online"


def test_heartbeat_v1_rejects_revoked_jwt(monkeypatch):
    now = datetime.now(timezone.utc)
    revoked_after = now - timedelta(seconds=10)
    stale_iat = int((now - timedelta(hours=1)).timestamp())

    token = jwt.encode(
        {
            "sub": "dev-001",
            "device_id": "dev-001",
            "device_name": "Edge Node 1",
            "hardware_fingerprint_hash": "abc",
            "type": "device",
            "iat": stale_iat,
            "exp": int((now + timedelta(hours=1)).timestamp()),
        },
        TEST_DEVICE_JWT_SECRET,
        algorithm="HS256",
    )

    async def fake_postgrest_get(table: str, _query: str):
        assert table == "devices"
        return [
            {
                "id": "dev-001",
                "is_active": True,
                "jwt_issued_after": revoked_after.isoformat(),
            }
        ]

    async def fake_postgrest_patch(_table: str, _query: str, _payload: dict):
        raise AssertionError("patch should not be called when token is revoked")

    monkeypatch.setattr(device_routes, "DEVICE_JWT_SECRET", TEST_DEVICE_JWT_SECRET)
    monkeypatch.setattr(device_routes, "postgrest_get", fake_postgrest_get)
    monkeypatch.setattr(device_routes, "postgrest_patch", fake_postgrest_patch)

    with _make_test_client(monkeypatch) as client:
        response = client.put(
            "/api/v1/devices/heartbeat",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 401
    assert "revoked" in response.json()["error"].lower()


def test_legacy_device_routes_are_disabled_by_default(monkeypatch):
    monkeypatch.setattr(device_routes, "LEGACY_DEVICE_TOKEN_APIS_ENABLED", False)

    with _make_test_client(monkeypatch) as client:
        response = client.post("/api/device-register", json={"device_token": "legacy-token"})

    assert response.status_code == 410
    assert "legacy" in response.json()["error"].lower()
