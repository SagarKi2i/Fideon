"""
W1 — Typed schema definitions for all PostgREST table call sites.

Using TypedDict (not dataclasses) so dicts returned by postgrest_get() can
be cast directly with no conversion overhead.

Usage:
    from app.core.db_types import AppUser, Device, UserRole
    rows = await postgrest_get("app_users", f"user_id=eq.{uid}")
    user: AppUser = rows[0]          # type checker now knows the shape

Rule: whenever a new column is added to a migration, update the TypedDict here.
PR checklist item: "Did you update db_types.py?"
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from typing_extensions import TypedDict


# ── Auth ──────────────────────────────────────────────────────────────────────

class AppUser(TypedDict, total=False):
    id: str                      # uuid — same as auth.users.id
    user_id: str                 # fk → auth.users.id (some tables use this column name)
    tenant_id: Optional[str]     # uuid
    full_name: Optional[str]
    status: str                  # "active" | "inactive" | "suspended"
    metadata: Optional[Dict[str, Any]]
    created_at: str
    updated_at: str


class UserRole(TypedDict, total=False):
    id: str
    user_id: str                 # fk → auth.users
    tenant_id: Optional[str]
    role: str                    # "global_admin" | "admin" | "user" | "viewer" | "guest"
    created_at: str


# ── Tenants ───────────────────────────────────────────────────────────────────

class Tenant(TypedDict, total=False):
    id: str                      # uuid PK
    name: str
    slug: str
    plan: str                    # "starter" | "professional" | "enterprise"
    seat_limit: Optional[int]
    created_at: str
    updated_at: str


# ── Devices ───────────────────────────────────────────────────────────────────

class Device(TypedDict, total=False):
    id: str
    user_id: str
    tenant_id: str
    device_name: str
    device_token: Optional[str]
    token_hash: Optional[str]    # sha256(device_token) — preferred lookup field
    status: str                  # "active" | "pending" | "inactive"
    is_active: bool
    os_type: Optional[str]
    app_version: Optional[str]
    last_heartbeat: Optional[str]
    metadata: Optional[Dict[str, Any]]
    created_at: str


# ── Models ────────────────────────────────────────────────────────────────────

class ModelCatalog(TypedDict, total=False):
    id: str
    model_id: str                # unique slug e.g. "quote-generation"
    domain: str
    provider: str
    version: str
    is_active: bool
    rag_collection_override: Optional[str]
    created_at: str


class ActivatedModel(TypedDict, total=False):
    id: str
    user_id: str
    tenant_id: str
    model_id: str                # fk → model_catalog.model_id
    activated_at: str


# ── Documents ─────────────────────────────────────────────────────────────────

class Document(TypedDict, total=False):
    id: str
    user_id: str
    tenant_id: str
    file_path: str               # Supabase Storage path
    doc_type: str                # "acord" | "pod" | "policy" | "generic"
    status: str                  # "uploaded" | "processing" | "done" | "failed"
    metadata: Optional[Dict[str, Any]]
    created_at: str


# ── Audit ─────────────────────────────────────────────────────────────────────

class AuditLog(TypedDict, total=False):
    id: str
    user_id: Optional[str]
    tenant_id: Optional[str]
    action: str
    resource_type: str
    resource_id: Optional[str]
    details: Optional[Dict[str, Any]]
    previous_value: Optional[Dict[str, Any]]
    new_value: Optional[Dict[str, Any]]
    ip_address: Optional[str]
    user_agent: Optional[str]
    integrity_hash: str          # SHA-256 — immutable after insert
    shap_values: Optional[Dict[str, float]]
    model_id: Optional[str]
    prediction: Optional[Dict[str, Any]]
    reasoning: Optional[str]
    created_at: str              # immutable (trigger blocks UPDATE)


class AuthAudit(TypedDict, total=False):
    id: str
    user_id: str
    email: str                   # stored for auth events only (not in audit_logs)
    role: str
    event: str                   # "login" | "logout" | "signup" | "refresh"
    action_code: str
    outcome_code: int
    resource_type: str
    resource_id: Optional[str]
    ip_address: Optional[str]
    integrity_hash: str
    created_at: str


# ── Workflows ─────────────────────────────────────────────────────────────────

class Workflow(TypedDict, total=False):
    id: str
    tenant_id: str
    name: str
    definition: Dict[str, Any]   # jsonb — workflow DAG
    created_by: str
    created_at: str
    updated_at: str


# ── Training ─────────────────────────────────────────────────────────────────

class TrainingJob(TypedDict, total=False):
    id: str
    tenant_id: str
    model_id: str
    status: str                  # "pending" | "running" | "done" | "failed"
    started_at: Optional[str]
    completed_at: Optional[str]
    metrics: Optional[Dict[str, Any]]
    created_at: str


# ── Notifications ─────────────────────────────────────────────────────────────

class Notification(TypedDict, total=False):
    id: str
    user_id: str
    tenant_id: str
    title: str
    body: str
    is_read: bool
    created_at: str
