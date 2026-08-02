"""Delete user accounts (and optionally all their data) from MongoDB.

DESTRUCTIVE. Run manually and deliberately — there is no undo.

    cd backend
    python scripts/reset_accounts.py                 # dry run: shows counts only
    python scripts/reset_accounts.py --confirm       # delete USERS only
    python scripts/reset_accounts.py --confirm --all # also delete jobs/candidates/etc.

Reads MONGO_URL / DB_NAME from backend/.env (same as the app).

IMPORTANT — this only clears the app's MongoDB. Firebase Authentication users
are separate: to fully reset test signups, also delete them in the Firebase
console (Authentication -> Users). The "email already exists" error is Firebase
state, not database state, so wiping here does not remove Firebase accounts.

After wiping, if SEED_ON_STARTUP is true the demo data re-seeds on the next
backend start. Set SEED_ON_STARTUP=false first if you want to stay empty.
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import (  # noqa: E402
    users, jobs, candidates, stage_transitions, ai_usage_log, login_activity, feedback,
)

# Collections cleared by --all, in a sensible order (children before parents).
RELATED = [
    ("stage_transitions", stage_transitions),
    ("candidates", candidates),
    ("jobs", jobs),
    ("ai_usage_log", ai_usage_log),
    ("login_activity", login_activity),
    ("feedback", feedback),
]


async def main() -> None:
    confirm = "--confirm" in sys.argv
    wipe_all = "--all" in sys.argv

    user_count = await users.count_documents({})
    print(f"users: {user_count}")
    for name, coll in RELATED:
        print(f"{name}: {await coll.count_documents({})}")

    if not confirm:
        print(
            "\nDry run — nothing deleted. Re-run with --confirm to delete users"
            + (", and add --all to also delete jobs/candidates/etc." if not wipe_all else " and all related data (--all).")
        )
        return

    deleted = (await users.delete_many({})).deleted_count
    print(f"\nDeleted {deleted} users.")
    if wipe_all:
        for name, coll in RELATED:
            n = (await coll.delete_many({})).deleted_count
            print(f"Deleted {n} {name}.")

    print(
        "\nDone. Remember to also delete test users in the Firebase console if you "
        "want a completely clean slate, and set SEED_ON_STARTUP=false to prevent re-seeding."
    )


if __name__ == "__main__":
    asyncio.run(main())
