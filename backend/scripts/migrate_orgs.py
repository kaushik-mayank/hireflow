"""Cycle 2 migration: give every existing single-tenant user their own organisation.

Additive and idempotent. Dry-run by default.

    cd backend
    python scripts/migrate_orgs.py               # dry run: shows what WOULD change
    python scripts/migrate_orgs.py --confirm      # apply
    python scripts/migrate_orgs.py --rollback     # dry run of the rollback
    python scripts/migrate_orgs.py --rollback --confirm   # undo the migration

What it does, per existing user WITHOUT an org_id (the idempotency key — migrated
users are skipped, so re-running is safe):
  1. Create an `organizations` doc owned by that user (or reuse one already owned
     by them, so a re-run after a partial failure re-attaches rather than dupes).
  2. Set org_id, org_role="manager", status="active" on the user.
  3. Backfill org_id/created_by/origin on their jobs, org_id/sourced_by on their
     candidates, org_id/actor_id on those candidates' stage_transitions, org_id
     on their feedback.

Every write is a $set of NEW fields — no existing field is mutated — so the old
app build keeps working throughout, and rollback simply $unsets them and deletes
the auto-created orgs.

Reads MONGO_URL / DB_NAME from backend/.env (same as the app).
"""

import asyncio
import os
import sys
import uuid
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import (  # noqa: E402
    users, jobs, candidates, stage_transitions, feedback, organizations,
)

DEFAULT_SEAT_LIMIT = 25


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _org_name(user: dict) -> str:
    company = (user.get("company") or "").strip()
    if company:
        return company
    name = (user.get("name") or "").strip() or "My"
    return f"{name}'s Team"


async def _ensure_org(user: dict, write: bool) -> str:
    """Return the org id for this user's org, creating it if needed (idempotent)."""
    existing = await organizations.find_one({"owner_user_id": user["id"]}, {"_id": 0, "id": 1})
    if existing:
        return existing["id"]
    org_id = f"org-{uuid.uuid4()}"
    if write:
        now = _now()
        await organizations.insert_one({
            "id": org_id,
            "name": _org_name(user),
            "owner_user_id": user["id"],
            "plan": "free_beta",
            "seat_limit": DEFAULT_SEAT_LIMIT,
            "status": "active",
            "created_at": user.get("created_at") or now,
            "updated_at": now,
        })
    return org_id


async def migrate(write: bool) -> None:
    to_migrate = await users.find({"org_id": {"$exists": False}}, {"_id": 0}).to_list(100000)
    already = await users.count_documents({"org_id": {"$exists": True}})
    print(f"Users without an org: {len(to_migrate)}   (already migrated: {already})")
    if not to_migrate:
        print("Nothing to do.")
        return

    totals = {"orgs": 0, "users": 0, "jobs": 0, "candidates": 0, "transitions": 0, "feedback": 0}
    for u in to_migrate:
        org_id = await _ensure_org(u, write)
        totals["orgs"] += 1

        user_jobs = await jobs.find({"user_id": u["id"]}, {"_id": 0, "id": 1}).to_list(100000)
        job_ids = [j["id"] for j in user_jobs]
        cand_ids = []
        if job_ids:
            cand_ids = [
                c["id"] for c in
                await candidates.find({"job_id": {"$in": job_ids}}, {"_id": 0, "id": 1}).to_list(500000)
            ]

        totals["jobs"] += len(job_ids)
        totals["candidates"] += len(cand_ids)

        if write:
            await users.update_one({"id": u["id"]}, {"$set": {
                "org_id": org_id,
                "org_role": "manager",
                "status": "active",
                "invited_by": None,
                "activated_at": u.get("created_at") or _now(),
            }})
            totals["users"] += 1
            if job_ids:
                await jobs.update_many(
                    {"id": {"$in": job_ids}},
                    {"$set": {"org_id": org_id, "created_by": u["id"], "origin": "org"}},
                )
            if cand_ids:
                await candidates.update_many(
                    {"id": {"$in": cand_ids}},
                    {"$set": {"org_id": org_id, "sourced_by": u["id"]}},
                )
                r = await stage_transitions.update_many(
                    {"candidate_id": {"$in": cand_ids}},
                    {"$set": {"org_id": org_id, "actor_id": u["id"]}},
                )
                totals["transitions"] += r.modified_count
            fr = await feedback.update_many(
                {"user_id": u["id"]}, {"$set": {"org_id": org_id}}
            )
            totals["feedback"] += fr.modified_count
        else:
            totals["users"] += 1
            totals["transitions"] += len(cand_ids)  # upper bound for the preview

    verb = "Migrated" if write else "WOULD migrate"
    print(f"\n{verb}:")
    for k, v in totals.items():
        print(f"  {k}: {v}")
    if not write:
        print("\nDry run — nothing written. Re-run with --confirm to apply.")


async def rollback(write: bool) -> None:
    migrated = await users.count_documents({"org_id": {"$exists": True}})
    auto_orgs = await organizations.count_documents({})
    print(f"Users with org_id: {migrated}   Organisations: {auto_orgs}")
    if not write:
        print("\nDry run — would $unset org fields on users/jobs/candidates/"
              "stage_transitions/feedback and delete organisations. Re-run with "
              "--confirm to apply.")
        return
    await users.update_many({}, {"$unset": {
        "org_id": "", "org_role": "", "status": "", "invited_by": "", "activated_at": "",
    }})
    await jobs.update_many({}, {"$unset": {"org_id": "", "created_by": "", "origin": ""}})
    await candidates.update_many({}, {"$unset": {"org_id": "", "sourced_by": "", "assignment_id": ""}})
    await stage_transitions.update_many({}, {"$unset": {"org_id": "", "actor_id": ""}})
    await feedback.update_many({}, {"$unset": {"org_id": ""}})
    r = await organizations.delete_many({})
    print(f"Rolled back. Deleted {r.deleted_count} organisations and unset org fields.")


async def main() -> None:
    write = "--confirm" in sys.argv
    if "--rollback" in sys.argv:
        print("=== ROLLBACK ===")
        print("Removes org fields and deletes organisations created by the migration.\n")
        await rollback(write)
    else:
        print("=== MIGRATE TO ORGANISATIONS ===")
        print("Additive + idempotent. Rollback: python scripts/migrate_orgs.py --rollback --confirm\n")
        await migrate(write)


if __name__ == "__main__":
    asyncio.run(main())
