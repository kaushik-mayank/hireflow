"""Feedback, bug reports and feature requests from inside the product.

Every submission is written to MongoDB **first**, then emailed. If SMTP is
misconfigured or the relay is down the message is still captured and visible in
the admin panel — feedback is never lost to a mail failure.
"""

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from database import feedback, users
from auth import get_current_user, require_admin
from models import FeedbackRequest, FeedbackStatusUpdate
import email_service

router = APIRouter(prefix="/feedback", tags=["feedback"])

TYPES = {
    "review": "Review",
    "bug": "Bug report",
    "feature": "Feature request",
}
STATUSES = ("new", "read", "actioned")

# Light abuse guard — a real person does not file 15 reports an hour.
RATE_LIMIT_PER_HOUR = 15


def _compose(doc: dict) -> tuple[str, str]:
    label = TYPES.get(doc["type"], doc["type"])
    subject = f"[HireFlow] {label}: {doc['subject']}"
    body = "\n".join([
        f"{label} submitted from HireFlow",
        "",
        f"From:    {doc.get('user_name') or 'Unknown'} <{doc.get('user_email') or 'unknown'}>",
        f"Company: {doc.get('company') or '—'}",
        f"User ID: {doc.get('user_id')}",
        f"Sent:    {doc.get('created_at')}",
        "",
        f"Subject: {doc['subject']}",
        "",
        "-" * 60,
        doc["message"],
        "-" * 60,
        "",
        "Reply directly to this email to respond to the sender.",
    ])
    return subject, body


@router.post("")
async def submit_feedback(
    body: FeedbackRequest,
    request: Request,
    user: dict = Depends(get_current_user),
):
    if body.type not in TYPES:
        raise HTTPException(status_code=400, detail="Please choose a valid message type")
    if not body.subject.strip() or not body.message.strip():
        raise HTTPException(status_code=400, detail="Subject and message are both required")

    hour_ago = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    recent = await feedback.count_documents({"user_id": user["id"], "created_at": {"$gte": hour_ago}})
    if recent >= RATE_LIMIT_PER_HOUR:
        raise HTTPException(
            status_code=429,
            detail="You've sent a lot of messages recently. Please try again in a little while.",
        )

    doc = {
        "id": str(uuid.uuid4()),
        "user_id": user["id"],
        # The account email is attached automatically — the user never types it.
        "user_email": user.get("email"),
        "user_name": user.get("name"),
        "company": user.get("company"),
        "type": body.type,
        "subject": body.subject.strip(),
        "message": body.message.strip(),
        "status": "new",
        "email_sent": False,
        "user_agent": request.headers.get("user-agent"),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    # Persist before sending, so a mail failure cannot lose the submission.
    await feedback.insert_one(doc)
    doc.pop("_id", None)

    subject, text = _compose(doc)
    sent = await email_service.send_email(
        to=email_service.FEEDBACK_TO,
        subject=subject,
        body=text,
        # From stays the authorised sender for SPF/DKIM; replying reaches the user.
        reply_to=doc.get("user_email"),
    )
    if sent:
        await feedback.update_one({"id": doc["id"]}, {"$set": {"email_sent": True}})

    return {"success": True, "id": doc["id"], "email_sent": sent}


@router.get("/mine")
async def my_feedback(user: dict = Depends(get_current_user)):
    items = await feedback.find(
        {"user_id": user["id"]}, {"_id": 0}
    ).sort("created_at", -1).to_list(100)
    return items


# ---------------------------------------------------------------------------
# Admin
# ---------------------------------------------------------------------------

@router.get("/admin")
async def list_feedback(
    admin: dict = Depends(require_admin),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    status: str | None = Query(None),
    type: str | None = Query(None),
):
    query: dict = {}
    if status in STATUSES:
        query["status"] = status
    if type in TYPES:
        query["type"] = type

    total = await feedback.count_documents(query)
    items = await feedback.find(query, {"_id": 0}).sort("created_at", -1).skip(
        (page - 1) * page_size
    ).limit(page_size).to_list(page_size)

    all_users = await users.find({}, {"_id": 0, "id": 1, "is_active": 1}).to_list(5000)
    active = {u["id"]: bool(u.get("is_active", 1)) for u in all_users}
    for it in items:
        it["user_active"] = active.get(it.get("user_id"))

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": items,
        "counts": {
            "new": await feedback.count_documents({"status": "new"}),
            "email_failed": await feedback.count_documents({"email_sent": False}),
        },
        "email_configured": email_service.is_configured(),
    }


@router.put("/admin/{feedback_id}/status")
async def set_feedback_status(
    feedback_id: str,
    body: FeedbackStatusUpdate,
    admin: dict = Depends(require_admin),
):
    if body.status not in STATUSES:
        raise HTTPException(status_code=400, detail="Invalid status")
    result = await feedback.update_one({"id": feedback_id}, {"$set": {"status": body.status}})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Feedback not found")
    return {"success": True, "status": body.status}
