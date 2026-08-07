# HireFlow Cycle 2 — Deployment & Handover Runbook

Organisations, managers/recruiters, assignments, per-assignment permissions,
personal JD overrides, and manager/recruiter reports. **All schema changes are
additive**; existing users, jobs and candidates keep working.

> Product wording is **Admin** = org manager, **User** = recruiter. In code they
> are `org_role: "manager" | "recruiter"`. The separate *platform* admin panel
> (`/admin/*`, purple) is unchanged and unrelated.

---

## 1. Environment variables (backend)

| Var | Needed for | Notes |
|---|---|---|
| `MONGO_URL`, `DB_NAME` | everything | unchanged |
| `JWT_SECRET` | sessions | unchanged — **do not rotate** during rollout (invalidates live sessions) |
| `FIREBASE_PROJECT_ID` | manager sign-up **and recruiter first-login** | already set in prod; recruiters now also use Firebase to set their first password |
| `GROQ_API_KEY` | AI features | unchanged |
| `CORS_ORIGINS` / `CORS_ORIGIN_REGEX` | browser API access | unchanged |

**No longer required for onboarding:** `APP_URL` and SMTP. Cycle 2 does **not**
send invitation emails — admins store approved emails and users set their own
password on first sign-in. (`APP_URL`/SMTP are still fine to keep for other uses;
the dormant emailed-invite code in `invites.py` is reserved for a future cycle.)

**Firebase console — enable email-link sign-in (for recruiter first-login):**
In Firebase Authentication → Sign-in method, enable **Email/Password** and turn on
**Email link (passwordless sign-in)**; add your frontend domain under **Authorized
domains**. This powers the recruiter "verify your email → set password" step. If
it is *not* enabled, the app **falls back** to letting an approved recruiter set a
password directly (no hard failure) — but then the email isn't verified up front,
so enable it for the intended flow.

No new frontend env vars.

---

## 2. Rollout order (do not reorder)

1. **Migrate — dry run:** `python backend/scripts/migrate_orgs.py`
   (dry-run is the default; it only prints what it *would* do and a rollback plan).
2. **Review the dry-run output.** Confirm the org-per-existing-user counts and the
   backfill counts (jobs/candidates/transitions/feedback) look right.
3. **Migrate — commit:** `python backend/scripts/migrate_orgs.py --confirm`
   (idempotent and re-runnable; safe to run twice — it skips users that already
   have an `org_id`).
4. **Deploy the backend.**
5. **Deploy the frontend** (`CI=true yarn build` must pass — see §4).
6. Smoke-test the flows in §5.

**Rollback:** `python backend/scripts/migrate_orgs.py --rollback` removes the
org fields it added. Because every change is additive, rolling back the *code*
(previous backend/frontend build) also leaves the app working on the old paths;
the new collections simply go unused. Never delete the new collections to roll
back — just redeploy the previous build.

---

## 3. New collections & indexes

New: `organizations`, `invitations` (dormant), `job_assignments`,
`job_jd_overrides`, `activity_events`. All indexes are created idempotently by
`ensure_indexes()` on backend startup (see `database.py`) — **no manual index
step**. After the first boot, verify in Mongo:

```
db.job_assignments.getIndexes()   # expect (job_id,user_id) unique
db.invitations.getIndexes()       # expect partial-unique (org_id,email) status=pending
db.candidates.getIndexes()        # expect (org_id, sourced_by, stage)
db.activity_events.getIndexes()   # expect (org_id, created_at) and (actor_id, created_at)
```

⚠️ **Owner verification item:** index creation and the migration have **not been
run against a real database in development** (offline environment). Do the dry-run
against a **copy** of production first.

---

## 4. Frontend build / bundle

- Build gate: **`cd frontend && CI=true yarn build`** must pass (warnings are
  errors under CI). All Cycle-2 frontend was written to that bar and checked for
  unused imports/dangling refs, but ⚠️ **was not built in the dev environment
  (no Node)** — build once before deploying.
- Bundle: new pages are **lazy-loaded** (`Team`, `Reports`→`TeamReport`/`MyProgress`
  via component import, `JobDetail`→`AssignmentPanel`). The manager-only `Team`
  route and `TeamReport` are only imported where used, so a recruiter's initial
  bundle does not pull the team-management screens on load. Confirm with
  `source-map-explorer` if you want a hard number (owner step).

---

## 5. Smoke tests after deploy

**Admin (manager):**
1. Sign in → sidebar shows **Team**. Open it → **Add user** (single + paste a
   list). Seat counter increments; duplicates/invalids are reported.
2. Open a job → **Team** tab → **Assign** one or several recruiters with
   permissions/targets/deadline. Edit and remove an assignment.
3. **Reports → Team** → panels render; change the date range; **CSV** buttons
   download. **Remove** an active member with reassignment → their assignments
   and candidates move to the chosen teammate.

**User (recruiter):**
1. On the login page, enter the approved email → **Set your password** →
   land in the app as a User. (An unknown email gets "ask your admin / Sign up".)
2. Jobs list shows only assigned roles, with deadline/target chips and **no**
   Create button. Controls you lack (upload/move/reject/AI) are disabled with a
   tooltip on the job page and the Kanban board; the API also refuses (403).
3. If granted `can_edit_jd`: JD Preview → **Make my own version**; if the admin
   later edits the shared JD, a notice appears. **Reports** shows *My targets &
   deadlines* + your personal pipeline (never a colleague comparison).

---

## 6. Security posture (verified by 305 offline tests)

- Every job/candidate/AI/report read is org+assignment scoped; cross-org access
  returns **404** (never confirms another org's data).
- Every permission flag is enforced **server-side** (upload, move, reject, AI,
  edit-JD, view-team-candidates, close, edit-meta) — the UI gating is UX only.
- Suspended (`status="disabled"`) users are rejected on **every** request (401).
- `onboarding-status` returns only a coarse status; suspended accounts read as
  `not_approved`.

---

## 7. Known follow-ups (not blocking)

- `/team/:userId` member **detail** page (list + actions ship; a dedicated
  per-member page does not).
- Report queries use one-query-per-collection + in-memory grouping (not N+1);
  converting the heaviest to Mongo **aggregation pipelines** is a perf follow-up
  at large data volumes.
- `is_active` (int) and `status` (string) still coexist (gated on both).
- Emailed invites + plan/seat purchase flow: a future cycle (dormant `invites.py`
  is the starting point).
