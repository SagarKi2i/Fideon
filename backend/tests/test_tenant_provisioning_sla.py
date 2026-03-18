from pathlib import Path
from time import perf_counter

from fastapi.testclient import TestClient

from app import factory
from app.routes import tenants as tenants_routes

TEST_DEVICE_JWT_SECRET = "unit-test-secret-with-32-plus-bytes"


def _make_test_client(monkeypatch) -> TestClient:
    monkeypatch.setattr(factory, "DEVICE_JWT_SECRET", TEST_DEVICE_JWT_SECRET)
    return TestClient(factory.create_app())


def _valid_payload() -> dict:
    return {
        "name": "SLA Tenant",
        "plan": "starter",
        "admin_email": "sla-admin@example.com",
        "admin_password": "supersecret123",
        "admin_full_name": "SLA Admin",
        "metadata": {"source": "sla_test"},
    }


def test_tenant_provisioning_warm_path_under_3s(monkeypatch):
    async def fake_get_user_context(_authorization):
        return {
            "user": {"id": "requester-1"},
            "user_id": "requester-1",
            "role": "admin",
            "tenant_id": "tenant-existing-1",
        }

    async def fake_postgrest_get(table: str, _query: str):
        if table == "tenants":
            return []
        if table == "app_users":
            return [{"user_id": "auth-user-1"}]
        return []

    async def fake_postgrest_insert(table: str, _payload: dict):
        assert table == "tenants"
        return [{"id": "tenant-sla-1", "created_at": "2026-03-17T00:00:00Z"}]

    async def fake_postgrest_patch(_table: str, _query: str, _payload: dict):
        return None

    async def fake_insert_audit_log(**_kwargs):
        return None

    async def fake_upsert_admin_role(_admin_user_id: str):
        return None

    class _FakeResponse:
        def __init__(self, status_code: int, body: dict):
            self.status_code = status_code
            self._body = body
            self.text = ""

        def json(self):
            return self._body

    class _FakeAsyncClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, *_args, **_kwargs):
            return _FakeResponse(status_code=200, body={"id": "auth-user-1"})

    monkeypatch.setattr(tenants_routes, "get_user_context", fake_get_user_context)
    monkeypatch.setattr(tenants_routes, "postgrest_get", fake_postgrest_get)
    monkeypatch.setattr(tenants_routes, "postgrest_insert", fake_postgrest_insert)
    monkeypatch.setattr(tenants_routes, "postgrest_patch", fake_postgrest_patch)
    monkeypatch.setattr(tenants_routes, "insert_audit_log", fake_insert_audit_log)
    monkeypatch.setattr(tenants_routes, "_upsert_admin_role", fake_upsert_admin_role)
    monkeypatch.setattr(tenants_routes.httpx, "AsyncClient", lambda timeout=30: _FakeAsyncClient())

    with _make_test_client(monkeypatch) as client:
        started = perf_counter()
        response = client.post(
            "/api/v1/tenants",
            headers={"Authorization": "Bearer admin-token"},
            json=_valid_payload(),
        )
        elapsed = perf_counter() - started

    assert response.status_code == 201
    assert elapsed < 3.0


def test_signup_wizard_persists_required_onboarding_fields():
    signup_path = (
        Path(__file__).resolve().parents[2]
        / "frontend"
        / "src"
        / "app-pages"
        / "Signup.tsx"
    )
    content = signup_path.read_text(encoding="utf-8")

    required_fragments = [
        "tenant_name",
        "plan:",
        "default_model_id",
        "device_profile",
        "signup_wizard_version",
    ]
    for fragment in required_fragments:
        assert fragment in content, f"Missing onboarding field marker: {fragment}"
