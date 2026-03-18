from datetime import datetime, timezone
from typing import Optional
from urllib.parse import quote

from fastapi import APIRouter, Header, HTTPException, Request

from app.core.supabase import insert_audit_log, postgrest_get, postgrest_insert, postgrest_patch, verify_user

router = APIRouter()
VALID_REVIEW_STATUSES = {"pending", "approved", "rejected"}
VALID_DECISION_TYPES = {
    "quote_approval",
    "claim_decision",
    "submission_triage",
    "policy_review",
    "risk_assessment",
    "document_validation",
    "acord_parsing_review",
    "document_extraction_review",
    "endorsement_recommendation",
    "underwriting_recommendation",
    "fraud_flag_review",
    "settlement_recommendation",
    "compliance_exception",
    "coverage_gap_review",
    "renewal_strategy_review",
    "other",
}


async def _get_requester_role(authorization: Optional[str]) -> tuple[dict, Optional[str]]:
    requester = await verify_user(authorization)
    requester_roles = await postgrest_get(
        "user_roles", f"select=role&user_id=eq.{quote(requester['id'], safe='')}&limit=1"
    )
    requester_role = requester_roles[0].get("role") if requester_roles else None
    return requester, requester_role


def _require_admin(role: Optional[str]) -> None:
    if role not in {"admin", "global_admin"}:
        raise HTTPException(status_code=403, detail="Admin access required")


@router.post("/api/reviews")
async def create_review_request(request: Request, authorization: Optional[str] = Header(default=None)):
    requester, _ = await _get_requester_role(authorization)
    body = await request.json()

    pod_model_id = str(body.get("pod_model_id") or "").strip()
    pod_model_name = str(body.get("pod_model_name") or "").strip()
    domain = str(body.get("domain") or "").strip()
    decision_type = str(body.get("decision_type") or "").strip()
    title = str(body.get("title") or "").strip()
    summary = body.get("summary")
    ai_recommendation = body.get("ai_recommendation")
    confidence_score = body.get("confidence_score")
    threshold_exceeded = bool(body.get("threshold_exceeded", False))
    input_data = body.get("input_data") or {}
    output_data = body.get("output_data") or {}

    if not pod_model_id or not pod_model_name or not domain or not decision_type or not title:
        raise HTTPException(
            status_code=400,
            detail="pod_model_id, pod_model_name, domain, decision_type, and title are required",
        )
    if decision_type not in VALID_DECISION_TYPES:
        raise HTTPException(status_code=400, detail="Invalid decision_type")

    created = await postgrest_insert(
        "decision_reviews",
        {
            "user_id": requester["id"],
            "pod_model_id": pod_model_id,
            "pod_model_name": pod_model_name,
            "domain": domain,
            "decision_type": decision_type,
            "title": title,
            "summary": summary,
            "ai_recommendation": ai_recommendation,
            "confidence_score": confidence_score,
            "threshold_exceeded": threshold_exceeded,
            "input_data": input_data,
            "output_data": output_data,
            "status": "pending",
        },
    )

    review = created[0] if created else None
    await insert_audit_log(
        request=request,
        user_id=requester["id"],
        action="create_decision_review",
        resource_type="decision_review",
        resource_id=review.get("id") if review else None,
        details={"pod_model_id": pod_model_id, "decision_type": decision_type},
        previous_value=None,
        new_value={"status": "pending"},
    )

    return {"success": True, "review": review}


@router.get("/api/reviews/my")
async def list_my_reviews(
    status: Optional[str] = None,
    authorization: Optional[str] = Header(default=None),
):
    requester, _ = await _get_requester_role(authorization)
    query = f"select=*&user_id=eq.{quote(requester['id'], safe='')}&order=created_at.desc"
    if status:
        if status not in VALID_REVIEW_STATUSES:
            raise HTTPException(status_code=400, detail="Invalid status")
        query += f"&status=eq.{quote(status, safe='')}"
    rows = await postgrest_get("decision_reviews", query)
    return {"reviews": rows}


@router.get("/api/reviews")
async def list_all_reviews(
    status: Optional[str] = None,
    authorization: Optional[str] = Header(default=None),
):
    _, requester_role = await _get_requester_role(authorization)
    _require_admin(requester_role)

    query = "select=*&order=created_at.desc"
    if status:
        if status not in VALID_REVIEW_STATUSES:
            raise HTTPException(status_code=400, detail="Invalid status")
        query += f"&status=eq.{quote(status, safe='')}"
    rows = await postgrest_get("decision_reviews", query)
    return {"reviews": rows}


@router.get("/api/reviews/pending-count")
async def get_pending_review_count(authorization: Optional[str] = Header(default=None)):
    _, requester_role = await _get_requester_role(authorization)
    _require_admin(requester_role)
    rows = await postgrest_get("decision_reviews", "select=id&status=eq.pending")
    return {"count": len(rows)}


@router.post("/api/reviews/{review_id}/approve")
async def approve_review(
    review_id: str,
    request: Request,
    authorization: Optional[str] = Header(default=None),
):
    requester, requester_role = await _get_requester_role(authorization)
    _require_admin(requester_role)

    rows = await postgrest_get(
        "decision_reviews",
        f"select=*&id=eq.{quote(review_id, safe='')}&limit=1",
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Review not found")
    review = rows[0]
    if review.get("status") != "pending":
        raise HTTPException(status_code=400, detail="Only pending reviews can be approved")

    body = await request.json()
    reviewer_notes = (body.get("reviewer_notes") or "").strip() or None

    now_iso = datetime.now(timezone.utc).isoformat()
    await postgrest_patch(
        "decision_reviews",
        f"id=eq.{quote(review_id, safe='')}",
        {
            "status": "approved",
            "reviewer_id": requester["id"],
            "reviewer_notes": reviewer_notes,
            "reviewed_at": now_iso,
        },
    )

    await insert_audit_log(
        request=request,
        user_id=requester["id"],
        action="approve_decision_review",
        resource_type="decision_review",
        resource_id=review_id,
        details={"pod_model_id": review.get("pod_model_id"), "decision_type": review.get("decision_type")},
        previous_value={"status": "pending"},
        new_value={"status": "approved"},
    )
    return {"success": True}


@router.post("/api/reviews/{review_id}/reject")
async def reject_review(
    review_id: str,
    request: Request,
    authorization: Optional[str] = Header(default=None),
):
    requester, requester_role = await _get_requester_role(authorization)
    _require_admin(requester_role)

    rows = await postgrest_get(
        "decision_reviews",
        f"select=*&id=eq.{quote(review_id, safe='')}&limit=1",
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Review not found")
    review = rows[0]
    if review.get("status") != "pending":
        raise HTTPException(status_code=400, detail="Only pending reviews can be rejected")

    body = await request.json()
    reviewer_notes = (body.get("reviewer_notes") or "").strip() or None

    now_iso = datetime.now(timezone.utc).isoformat()
    await postgrest_patch(
        "decision_reviews",
        f"id=eq.{quote(review_id, safe='')}",
        {
            "status": "rejected",
            "reviewer_id": requester["id"],
            "reviewer_notes": reviewer_notes,
            "reviewed_at": now_iso,
        },
    )

    await insert_audit_log(
        request=request,
        user_id=requester["id"],
        action="reject_decision_review",
        resource_type="decision_review",
        resource_id=review_id,
        details={"pod_model_id": review.get("pod_model_id"), "decision_type": review.get("decision_type")},
        previous_value={"status": "pending"},
        new_value={"status": "rejected"},
    )
    return {"success": True}
