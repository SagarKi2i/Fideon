from fastapi import HTTPException
from fastapi.testclient import TestClient

from app import factory
from app.routes import tenants as tenants_routes

TEST_DEVICE_JWT_SECRET = "unit-test-secret-with-32-plus-bytes"


def _make_test_client(monkeypatch) -> TestClient:
    # Lifespan startup validates this secret before app boots.
    monkeypatch.setattr(factory, "DEVICE_JWT_SECRET", TEST_DEVICE_JWT_SECRET)
    return TestClient(factory.create_app())


def _valid_tenant_payload() -> dict:
    return {
        "name": "Acme Insurance",
        "plan": "starter",
        "admin_email": "admin@acme.com",
        "admin_password": "supersecret123",
        "admin_full_name": "Acme Admin",
        "metadata": {"source": "unit_test"},
    }


def test_create_tenant_success(monkeypatch):
    async def fake_get_user_context(_authorization):
        return {
            "user": {"id": "requester-1"},
            "user_id": "requester-1",
            "role": "admin",
            "tenant_id": "tenant-existing-1",
        }

    async def fake_postgrest_get(table: str, query: str):
        if table == "user_roles":
            return [{"role": "admin"}]
        if table == "tenants":
            return []
        if table == "app_users":
            return [{"user_id": "auth-user-1"}]
        raise AssertionError(f"Unexpected postgrest_get call: table={table} query={query}")

    async def fake_postgrest_insert(table: str, payload: dict):
        assert table == "tenants"
        assert payload["name"] == "Acme Insurance"
        return [{"id": "tenant-1", "created_at": "2026-03-17T00:00:00Z"}]

    patch_calls = []

    async def fake_postgrest_patch(table: str, query: str, payload: dict):
        patch_calls.append((table, query, payload))

    async def fake_insert_audit_log(**_kwargs):
        return None

    async def fake_upsert_admin_role(admin_user_id: str):
        assert admin_user_id == "auth-user-1"

    class _FakeResponse:
        def __init__(self, status_code: int, body: dict, text: str = ""):
            self.status_code = status_code
            self._body = body
            self.text = text

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
        response = client.post(
            "/api/v1/tenants",
            headers={"Authorization": "Bearer admin-token"},
            json=_valid_tenant_payload(),
        )

    assert response.status_code == 201
    body = response.json()
    assert body["success"] is True
    assert body["tenant"]["id"] == "tenant-1"
    assert body["admin_user"]["id"] == "auth-user-1"
    assert body["admin_user"]["role"] == "admin"
    assert len(patch_calls) == 2
    assert patch_calls[0][0] == "app_users"
    assert patch_calls[0][2]["tenant_id"] == "tenant-1"
    assert patch_calls[1][0] == "tenants"
    assert patch_calls[1][2]["metadata"]["admin_user_id"] == "auth-user-1"


def test_create_tenant_rejects_non_object_metadata(monkeypatch):
    async def fake_get_user_context(_authorization):
        return {
            "user": {"id": "requester-1"},
            "user_id": "requester-1",
            "role": "admin",
            "tenant_id": "tenant-existing-1",
        }

    async def fake_postgrest_get(table: str, _query: str):
        if table == "user_roles":
            return [{"role": "admin"}]
        if table == "tenants":
            return []
        return []

    monkeypatch.setattr(tenants_routes, "get_user_context", fake_get_user_context)
    monkeypatch.setattr(tenants_routes, "postgrest_get", fake_postgrest_get)

    payload = _valid_tenant_payload()
    payload["metadata"] = "not-an-object"

    with _make_test_client(monkeypatch) as client:
        response = client.post(
            "/api/v1/tenants",
            headers={"Authorization": "Bearer admin-token"},
            json=payload,
        )

    assert response.status_code == 400
    assert "metadata" in response.json()["error"].lower()


def test_create_tenant_rolls_back_if_linking_fails(monkeypatch):
    async def fake_get_user_context(_authorization):
        return {
            "user": {"id": "requester-1"},
            "user_id": "requester-1",
            "role": "admin",
            "tenant_id": "tenant-existing-1",
        }

    async def fake_postgrest_get(table: str, _query: str):
        if table == "user_roles":
            return [{"role": "admin"}]
        if table == "tenants":
            return []
        return []

    async def fake_postgrest_insert(table: str, _payload: dict):
        assert table == "tenants"
        return [{"id": "tenant-1", "created_at": "2026-03-17T00:00:00Z"}]

    rollback_calls = []

    async def fake_rollback_provisioning(tenant_id: str, admin_user_id: str):
        rollback_calls.append((tenant_id, admin_user_id))

    async def fake_link_admin_user_to_tenant(_admin_user_id: str, _tenant_id: str, _admin_full_name: str):
        raise HTTPException(status_code=500, detail="link failure")

    class _FakeResponse:
        def __init__(self, status_code: int, body: dict, text: str = ""):
            self.status_code = status_code
            self._body = body
            self.text = text

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
    monkeypatch.setattr(tenants_routes, "_rollback_provisioning", fake_rollback_provisioning)
    monkeypatch.setattr(tenants_routes, "_link_admin_user_to_tenant", fake_link_admin_user_to_tenant)
    monkeypatch.setattr(tenants_routes.httpx, "AsyncClient", lambda timeout=30: _FakeAsyncClient())

    with _make_test_client(monkeypatch) as client:
        response = client.post(
            "/api/v1/tenants",
            headers={"Authorization": "Bearer admin-token"},
            json=_valid_tenant_payload(),
        )

    assert response.status_code == 500
    assert "link failure" in response.json()["error"].lower()
    assert rollback_calls == [("tenant-1", "auth-user-1")]


def test_create_tenant_idempotency_replay(monkeypatch):
    async def fake_get_user_context(_authorization):
        return {
            "user": {"id": "requester-1"},
            "user_id": "requester-1",
            "role": "admin",
            "tenant_id": "tenant-existing-1",
        }

    async def fake_postgrest_get(table: str, _query: str):
        if table == "tenants":
            return [
                {
                    "id": "tenant-1",
                    "slug": "acme-insurance-abc12345",
                    "name": "Acme Insurance",
                    "is_active": True,
                    "created_at": "2026-03-17T00:00:00Z",
                    "metadata": {
                        "plan": "starter",
                        "provisioned_by": "requester-1",
                        "admin_user_id": "auth-user-1",
                        "admin_email": "admin@acme.com",
                        "admin_full_name": "Acme Admin",
                    },
                }
            ]
        return []

    monkeypatch.setattr(tenants_routes, "get_user_context", fake_get_user_context)
    monkeypatch.setattr(tenants_routes, "postgrest_get", fake_postgrest_get)

    with _make_test_client(monkeypatch) as client:
        response = client.post(
            "/api/v1/tenants",
            headers={
                "Authorization": "Bearer admin-token",
                "x-idempotency-key": "onboarding-req-0001",
            },
            json=_valid_tenant_payload(),
        )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["idempotent_replay"] is True
    assert body["tenant"]["id"] == "tenant-1"
