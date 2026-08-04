# HireFlow — Cycle 2 Audit (Phase 8, read-only)

**Date:** 2026-08-04 · **Author:** Claude (senior engineer) · **Scope:** read-only. No source file was modified.
**Purpose:** ground-truth the code before Phases 9–15, reconcile it against `PROJECT_PLAN_CYCLE2.md`, and lock the design.

> Where the plan and the code disagree, the code wins and I say so in §5.

---

## 1. Auth reality check

### 1.1 The app-issued JWT
Minted in `backend/auth.py:create_token`. Claims — **exactly**:
```
{ userId, email, role, name, exp }        # HS256, 7-day expiry, JWT_SECRET
```
- `role` is **derived, not stored**: `role = effective_role(user)` → `"admin"` iff the user's email/uid is on the platform allowlist (`admin_identity.py`), else `"hr"`. The DB `users.role` field ("hr"/"admin", set only by `seed.py`) is **never read for auth** — `effective_role`/`is_admin_identity` ignore it.
- There is **no `org_id` in the token today.**

### 1.2 🔑 The most important finding for Cycle 2
`get_current_user` (`auth.py:45`) uses the JWT **only to obtain `userId`**, then **re-fetches the full user document from Mongo** and returns *that*:
```python
user = await users.find_one({"id": payload.get("userId")}, {"_id": 0})
```
**Consequence:** every route that depends on `get_current_user` receives the *live* DB user doc. After the migration adds `org_id`/`org_role`/`status`, those fields are present on the user object **without any JWT change**. This means:
- **Legacy JWTs already work** — they carry `userId`; the DB doc supplies org fields. The plan's "JWT gains org_id, with a fallback so we don't log everyone out" (§9/Phase 9) is **unnecessary for backend enforcement**. I recommend **not** touching the JWT at all (see §5, conflict C1). Lower risk than planned.
- Backend org-scoping reads `user["org_id"]` from this doc — trustworthy, server-side, always fresh.
- The **frontend** never decodes the JWT; it gets the user from `GET /api/auth/me` → `_public_user`. So the *only* contract change the frontend needs is **adding `org_role` (and `status`, maybe `org_id`) to `_public_user`**.

### 1.3 Where `role` / identity is read or written
| Location | Reads/writes | Notes |
|---|---|---|
| `auth.py:create_token` | writes JWT `role` = `effective_role` | derived from allowlist |
| `auth.py:require_admin` | reads `is_admin_identity(user)` | gates `/admin/*` — **platform admin only, keep untouched** |
| `auth.py:get_current_user` | checks `user.get("is_active", 1)` → 403 "Account deactivated" | ⚠️ separate from planned `status` field (§5, C3) |
| `routes_auth.py:_public_user` | returns `{id,name,email,role,company}` | `role`=`effective_role`. **Frontend's whole view of identity.** |
| `routes_auth.py:firebase_exchange` | find-or-create user; sets `role="hr"` (via `HR_ROLE`) on create | **org creation must be added here for new managers** (§4.1) |
| `admin_identity.py` | allowlist match on email/firebase_uid | the platform-admin concept; **orthogonal to org roles** |
| `App.js:AdminRoute` | `user?.role !== "admin"` → redirect | platform-admin guard (frontend mirror). Keep. |
| `Layout.jsx` | `user?.role === "admin"` → shows purple Platform Admin section + badge | keep; manager UI is a *new* concept keyed on `org_role` |
| `seed.py` | writes `role:"admin"`/`"hr"` | cosmetic; ignored by auth |

**Vocabulary is currently clean:** `role` = platform ("admin"/"hr", allowlist-derived). Cycle 2's `org_role` ("manager"/"recruiter") is a **new, separate** field. No collision as long as new code never overloads `role`.

### 1.4 Current signup / login / verify / reset sequence (post Sessions 14–16)
- **Signup** (`Signup.jsx` + `firebase.js:firebaseSignUp`): Firebase-only. `createUserWithEmailAndPassword` → `updateProfile(displayName)` → `sendEmailVerification` → `signOut`. Frontend shows "verify your email". **No backend call at signup.** Optional company stashed in `localStorage` (`pendingCompanyKey`). The app/DB account is created **lazily on first verified login**.
- **Login** (`Login.jsx` + `firebase.js:firebaseSignIn`): `signInWithEmailAndPassword` → `reload()` → check `emailVerified` → `getIdToken(true)` → **Step 2** `POST /api/auth/firebase`. Two steps with **distinct errors** (credential vs "trouble reaching the server"). Legacy bcrypt fallback (`/api/auth/login`) for pre-Firebase/demo accounts.
- **`POST /api/auth/firebase`** (`routes_auth.py`): 503 if backend `FIREBASE_PROJECT_ID` unset; verify token via JWKS (`firebase_auth.py`, `pyjwt`+`cryptography`, **no firebase-admin**); find-or-create user; gate on `REQUIRE_EMAIL_VERIFICATION` (default true) → returns `{verified:false}` if unverified else `{verified:true, token, user}`. Backfills name/company.
- **Verify:** enforced server-side via the token's `email_verified` claim; frontend `firebaseSignIn` resends + blocks unverified.
- **Reset:** `ForgotPassword.jsx` → Firebase `sendPasswordResetEmail`, anti-enumeration (same confirmation for unknown emails). **Industry-standard; leave as-is.**
- **CORS** (`server.py`): `allow_credentials=False` (bearer-token API), known origins baked in (`hireflow.cortinix.com`, vercel, localhost) + `CORS_ORIGINS` env + `CORS_ORIGIN_REGEX` (default `*.vercel.app`).

---

## 2. Data-access inventory (the security core)

**Universal truth today: every query is scoped by `user_id`. There is no `org_id` anywhere.** Below, each query with its current scoping and what Cycle 2 needs. **Every row marked 🔴 leaks across orgs if left unchanged** (once multiple users share an org, `user_id` scoping hides an org-mate's data the plan says a manager must see, and — worse — after migration two different orgs' data is only separated by `user_id`, so a *route that forgets org scoping* would expose it).

### 2.1 `routes_jobs.py`
| Endpoint | Current query | Cycle 2 need |
|---|---|---|
| `GET /jobs` | `jobs.find({user_id})` | 🔴 org+scope: manager → all org jobs; recruiter → assigned (`job_assignments`) + own (`origin=personal`). `scope=assigned\|mine\|all`. |
| `POST /jobs` | insert `{user_id,…}` | add `org_id`, `created_by`, `origin` (`org` if manager, `personal` if recruiter). |
| `GET /jobs/{id}` | `find({id,user_id})` → 404 | 🔴 `resolve_job_access`; return `effective_permissions` + `jd_source`. |
| `PUT /jobs/{id}` | `find({id,user_id})` then update | 🔴 permission-gate (`can_edit_job_meta`/manager); JD edits by a permitted recruiter → **`job_jd_overrides`, not `jobs`** (§5.3). |
| `DELETE /jobs/{id}` | `find({id,user_id})`; cascades candidates+transitions | 🔴 manager/owner only; recruiter never deletes assigned. |
| `GET /jobs/{id}/activity` | `find({id,user_id})` | 🔴 org+access scope. |
| `_counts_for_jobs` | `candidates.find({job_id:$in})` | fine once job ids are already access-filtered. |

### 2.2 `routes_candidates.py`
| Endpoint | Current | Cycle 2 need |
|---|---|---|
| `POST /candidates/upload/{job_id}` | `find({id,user_id})`; inserts candidate (source mandatory) | 🔴 `resolve_job_access` + `can_upload_candidates`; stamp `org_id`, `sourced_by`, `assignment_id`. |
| `GET /candidates/job/{job_id}` | `find({id,user_id})`; returns all `candidates.find({job_id})` | 🔴 access-scope; **filter to caller's own sourced candidates unless manager or `can_view_team_candidates`**. |
| `GET /candidates/{id}` | `_owns_candidate` → job.user_id, **403** | 🔴 org+access; **return 404 not 403** (§5, C2). |
| `PUT /candidates/{id}/stage` | `_owns_candidate` | 🔴 `can_move_stage`/`can_reject_candidates`; stamp `stage_transitions.actor_id` + `org_id`; write `activity_events`. |
| `PUT /candidates/bulk-stage` | filters to `jobs.find({id:$in,user_id})` | 🔴 org+per-job permission. |
| `POST /candidates/{id}/note`, `DELETE /candidates/{id}` | `_owns_candidate` | 🔴 access + permission. |
| `_owns_candidate` / `_move_stage` | user_id ownership; `moved_by=user["name"]` | needs `actor_id` (id, not just name) for per-recruiter reports. |

### 2.3 `routes_ai.py`
| Endpoint | Current | Cycle 2 need |
|---|---|---|
| `POST /ai/rank` | `jobs.find({id,user_id})`; ranks all `candidates.find({job_id})` | 🔴 access + `can_use_ai`; **use caller's JD view** (org or personal override); scope candidates. |
| `POST /ai/enhance-jd` | no ownership (operates on posted text) | `can_use_ai`; fine otherwise. |
| `_get_owned_candidate` (rank-adjacent: questions/email/summary/compare/structure) | candidate→job.user_id, **403** | 🔴 org+access + `can_use_ai`; **404 not 403**; JD view = caller's; record which JD text was used on the analysis (§5.3). |

### 2.4 `routes_dashboard.py`
`GET /dashboard`: `jobs.find({user_id})` + `candidates.find({job_id:$in})`. 🔴 Must become **role-aware**: manager → org counters (open roles, unassigned, active users, candidates this week, hires this month, past-deadline/idle assignments); recruiter → own + assigned counters. Additive response keys so the existing personal shape still renders.

### 2.5 `routes_reports.py` (Phase-5 rewrite)
`GET /reports`: `jobs.find({user_id})`, `candidates.find({job_id:$in},{resume_text:0})`, `stage_transitions.find({candidate_id:$in})`. Pure-function analytics (`_time_to_hire`, `_funnel`, `_source_effectiveness`, `_aging_postings`, `_quota_tracker`, `_insights`). 🔴 Two new endpoints: `GET /reports/mine` (recruiter, current logic but org+own-scoped) and `GET /reports/team` (manager, org-wide + per-recruiter split) + `export.csv`. **Reuse the existing pure functions** — they already take plain dicts, so per-recruiter grouping wraps them.

### 2.6 `routes_feedback.py`, `routes_admin.py`
- Feedback: add `org_id` on submit (additive); `/admin/feedback` stays platform-admin, org-agnostic.
- `/admin/*`: **do not touch.** Platform-admin allowlist concept — orthogonal.

**Summary:** ~22 queries across 5 modules are `user_id`-scoped and every one needs org+assignment scoping via a single new `permissions.py::resolve_job_access`. This is exactly the plan's §5.2 pattern and is the highest-risk surface — hence the "grep test proves no route reads jobs/candidates by id without resolve_job_access" guard.

---

## 3. Frontend inventory

### 3.1 Routing & guards (`App.js`)
- `BrowserRouter` → `<AppRoutes>` inside `ErrorBoundary > AuthProvider > Suspense`.
- Guards: `PrivateRoute` (token), `PublicRoute` (redirect signed-in to `/dashboard`), `AdminRoute` (`user?.role !== "admin"` → `/dashboard`). **These are the reuse templates.** New guards needed: `ManagerRoute` (`user?.org_role === "manager"`), and the public `/accept-invite` (no guard, its own token check).
- Lazy-load pattern is established — **new manager pages must be lazy** (plan §15: recruiter bundle must not carry manager-only code).
- Routes to add: `/accept-invite` (public), `/team`, `/team/:userId`, `/assignments` (manager); reports stays `/reports` but becomes role-aware.

### 3.2 Layout / sidebar (`Layout.jsx`)
- Fixed navy sidebar, sections rendered as `<NavLink className={navItem}>`. Existing sections: **Hiring** (Dashboard/Jobs/Reports), **Support** (Send Feedback), and **Platform Admin** (purple accent + border, shown when `isAdmin = user?.role === "admin"`) with a purple "Admin" badge near the logo.
- Cycle 2 adds a **Team** section (Team, Assignments) shown when `user?.org_role === "manager"` — **built exactly like the existing conditional Admin block but in the default (non-purple) accent** (Team is a customer feature, purple stays reserved for Platform Admin).
- `Topbar`, `PageBody`, `Sidebar` all reusable unchanged.

### 3.3 Components to reuse (no new visual language)
`components/ui.jsx`: `Button` (variants primary/secondary/ghost/danger/subtle), `AIButton` (amber = AI), `Card`, `Avatar`, `StageBadge`, `ScoreBadge`, `Pill` (green/red/amber/gray), `SourceBadge`, `Modal` (scroll-lock, focus), `EmptyState`, `Skeleton`, `ProgressBar`, `Spinner`. Plus `config/sources.js` (`CANDIDATE_SOURCES`, `sourceMeta`) and `constants.js` (`STAGES`, `STAGE_COLORS`, `fmtDate`, `SUPPORT_EMAIL`, `pendingCompanyKey`). **Target progress bars → `ProgressBar`; assignee avatars → `Avatar`; permission toggles → plain checkboxes styled like existing filters; deadlines → `Pill` amber/coral.**

### 3.4 `Reports.jsx` data contract (extend without touching its visual language)
- Fetches `reportsApi.get()` → `GET /reports`. Renders from this exact shape:
```
{ time_to_hire:{per_job[],overall_avg,total_hires,recent_avg,previous_avg},
  funnel:[{stage,count,pct_of_total,conversion_from_previous,drop_off,drop_off_pct}],
  biggest_drop_off, sources:[{source,candidates,hired,hire_rate,avg_score}],
  has_source_data, postings_over_time:[{week,open,closed}],
  aging_postings:[{job,job_id,days_since_activity,no_candidates,candidates,hired,needed}],
  quota_tracker:[{job,needed,hired,in_pipeline,remaining,complete,status}],
  insights:[{tone:"positive|attention|neutral", text}],
  totals:{jobs,open_jobs,candidates,hired,unanalyzed} }
```
- Panels: `HeadlineStats`, `Insights`, `Funnel` (CSS bars), time-to-hire (recharts `BarChart`), source table, postings `AreaChart`, aging list, quota table. **Handles empty (`totals.jobs===0` first-run screen), failed fetch, loading.**
- **Plan for Cycle 2:** manager `/reports` = a superset payload from `GET /reports/team` (per-recruiter arrays wrapping these same shapes) rendered with the *same* panel components; recruiter `/reports` = `GET /reports/mine` = today's payload, org+own-scoped. **No new chart library, no new panel styling.**

### 3.5 `api.js`
Axios instance + request interceptor (attaches Bearer) + response interceptor (401 → redirect **only** for non-`/auth/` requests with an existing session — the Session-16 fix). Existing API groups: `authApi, jobsApi, candidatesApi, aiApi, dashboardApi, adminApi, reportsApi, feedbackApi`. **Add `orgApi, invitesApi, teamApi, assignmentsApi` in the same shape.**

---

## 4. Migration plan (`backend/scripts/migrate_orgs.py`)

Modelled on `scripts/reset_accounts.py` (dry-run default, `--confirm` to write, stdlib only, reads `MONGO_URL`/`DB_NAME` from `.env`).

**Idempotency key:** a user is "migrated" iff `user.get("org_id")` is set. Re-runs skip them. Every write is `$set` of additive fields → safe to run twice.

**Order of operations (per un-migrated user):**
1. Create `organizations` doc: `name = user.company or f"{user.name}'s Team"`, `owner_user_id=user.id`, `plan="free_beta"`, `seat_limit=25`, `status="active"`. (Deterministic org id per user so a re-run after a partial failure re-attaches rather than duplicating — check for an existing org with `owner_user_id` first.)
2. `users`: `$set org_id, org_role="manager", status="active", invited_by=null, activated_at=created_at`.
3. `jobs.update_many({user_id:u.id, org_id:{$exists:false}}, $set org_id, created_by=u.id, origin="org")`.
4. `candidates`: for that user's job ids → `$set org_id, sourced_by=u.id`.
5. `stage_transitions`: for those candidate ids → `$set org_id, actor_id=u.id` (best-effort; historical `moved_by` is a name only).
6. `feedback.update_many({user_id:u.id}, $set org_id)`.

**Dry-run output:** counts of users to migrate, orgs to create, jobs/candidates/transitions/feedback to stamp; prints a **rollback plan** at the top.

**Rollback story:** all changes are **additive fields + new org docs**, so rollback = `$unset` the added fields on users/jobs/candidates/transitions/feedback and delete orgs whose `owner_user_id` was auto-created. A `--rollback` mode does exactly that (also dry-run by default). No existing field is mutated, so app code on the old build keeps working throughout.

**`ensure_indexes`:** extend with the §3.3 indexes (all additive; `create_index` is idempotent).

**Seed rewrite (`seed.py`):** produce **one demo org**: manager "Sarah Chen" (owner) + 2 recruiters (invited→active), the existing 3 jobs assigned across recruiters with targets/deadlines/permissions, candidates stamped `org_id`/`sourced_by`, plus a few `activity_events` so `/reports/team` is demonstrable on a fresh DB. Keep it occupation-diverse (nurse/forklift/engineer) as today. Gated by `SEED_ON_STARTUP` and empty-collection check (unchanged).

---

## 5. Conflicts between the plan and the code (code wins)

- **C1 — JWT changes are unnecessary (recommend skipping).** Plan §9/Phase 9: "JWT gains `org_id` + `org_role`, with a fallback so we don't log everyone out." **Reality:** `get_current_user` re-reads the DB user, so org fields are available without touching the JWT, and legacy JWTs already work. **Recommendation:** do **not** add org claims to the JWT; only extend `_public_user` (and `/auth/me`) with `org_role`/`status`/`org_id` for the frontend. Less code, no session-invalidation risk. *(If you still want it in the token for future stateless checks, fine — but it's not required and I'd rather not.)*
- **C2 — Cross-ownership is 403 today, plan wants 404.** `_owns_candidate` and `_get_owned_candidate` return **403 "Not authorized"**; `jobs` returns 404. Plan §2/§4 mandates 404 for cross-org. **Recommendation:** standardize on **404** in `resolve_job_access` for all cross-org/cross-access reads (don't confirm existence). This is a behaviour change to the candidate/AI routes — noted so it's deliberate, not silent.
- **C3 — Two "active" concepts.** `get_current_user` gates on `users.is_active` (int 0/1). Plan introduces `users.status` ("invited"/"active"/"disabled") and wants suspension to 401. **Recommendation:** in Phase 10, gate on **both** (`is_active != 0` AND `status != "disabled"`), migration sets `status="active"` for everyone, and suspension sets `status="disabled"`. Do **not** repurpose `is_active`. Keeps legacy rows valid. Flag: long-term these should unify, but that's a Cycle-3 cleanup (additive rule).
- **C4 — `stage_transitions` records `moved_by` as a name, not an id.** Per-recruiter report accuracy on *historical* data is limited; going forward we add `actor_id`. Not a blocker; reports must tolerate missing `actor_id` on old rows (Cycle-1 "candidate predating the field" test discipline).
- **C5 — `activity_events` overlaps `stage_transitions`.** Plan wants a broad append-only `activity_events`. Stage changes are already in `stage_transitions`. **Recommendation:** write `activity_events` at mutation points as the plan says (it captures uploads/assignments/AI/close that `stage_transitions` doesn't), but **derive stage-based KPIs from `stage_transitions`** to avoid double-counting and keep the funnel definitions identical to Cycle 1. Net: `activity_events` powers throughput/idle/activity panels; `stage_transitions` stays the funnel/time source of truth.
- **C6 — `ai_usage_log` has no `org_id`.** Plan §8.1 reuses it per-recruiter. It has `user_id`; org attribution is a join via user→org. **Recommendation:** stamp `org_id` on new `ai_usage_log` writes (additive) so team AI-usage panels don't need a per-row user lookup; old rows join via user.
- **C7 — `firebase_exchange` create path must create an org.** Today it creates a bare `hr` user. Plan §4.1.4 wants org+manager creation on first manager login. **Recommendation:** in Phase 9/10, when the create branch runs *and there is no invitation context*, create the org + set `org_role="manager"`, `owner_user_id`, in a compensating sequence (Atlas supports real transactions on its replica set; if we avoid `firebase-admin` we can still use Motor's `start_session`/`with_transaction`). Invited users take the accept-invite path instead and never hit this branch.

No conflict found in: design-system freeze, recharts-only, `firebase-admin` exclusion, `/admin/*` separation, additive-schema rule — all consistent with the code.

---

## 6. Risks, open questions, and answers to the §12 decisions

### 6.1 My answers to the seven decisions (confirm/challenge)
1. **Seat limit 25, soft-block** — ✅ confirm. Enforce server-side on invite create (409 with seat count).
2. **Recruiters create own jobs (`origin=personal`)** — ⚠️ confirm *with a caution*. It roughly doubles the scoping logic (every job/candidate/report query must union "assigned" + "own", and manager reports must include personal jobs read-only). Happy to build it, but if you want a tighter, faster Cycle 2 I'd **defer personal jobs to Cycle 3** and make Cycle 2 assignment-only. Your call — flagging the cost.
3. **Manager can promote a recruiter to manager; owner not demotable** — ✅ confirm. Add invariant: an org always has **≥1 active manager** (block the last manager's suspend/remove/demote).
4. **Default suspend; hard-remove behind typed confirmation + reassignment** — ✅ confirm.
5. **`APP_URL` env var** — ✅ confirm, **mandatory** for invites (`APP_URL=https://hireflow.cortinix.com`). Invites cannot send without it; the invite-create endpoint should 500 with a clear server log + the copy-link fallback still returns the link so the manager isn't blocked.
6. **SMTP may be unconfigured → copy-link fallback mandatory** — ✅ confirm. `email_service.is_configured()` already exists; mirror the Cycle-1 feedback pattern (persist first, best-effort send, surface "email couldn't be sent" + copy link).
7. **Manager sees candidate-level data by default; peers gated by `can_view_team_candidates`** — ✅ confirm. Consistent with the privacy policy (the org is the data controller). Recruiter default `can_view_team_candidates=false`.

### 6.2 Things I think are worth a second look
- **The JWT change (C1)** is the one place I'd actively push back on the plan — it adds risk for no backend benefit. Confirm you're happy to skip it.
- **404-vs-403 (C2)** is a deliberate behaviour change to existing candidate/AI routes; confirm you want existing single-tenant callers to now get 404 on cross-access (they can't hit it today, so no live impact).
- **Personal jobs (decision 2)** is the biggest scope/complexity lever — see above.
- **Historical per-recruiter accuracy (C4)** — team reports over data that predates Cycle 2 will attribute everything to the migrated manager (the only actor that existed). That's correct but worth stating in the UI ("history before your team was set up is attributed to the account owner").

### 6.3 Risks
- **Scoping regressions** — 22 queries change; the grep-guard test + one cross-org isolation test per resource (jobs/candidates/AI/reports/dashboard) is the safety net. Highest risk in the cycle.
- **Reverse-order test isolation** — the stub-merge pattern (Session-8) must be followed for any new test module that stubs `database`/`fastapi`/`groq`, or reverse-order runs break again.
- **N+1 in reports** — team reports must use aggregation, not Python loops over recruiters (Cycle-1 handover item); easy to regress.
- **Not runnable here** — no live Mongo/Firebase/SMTP/Groq in this environment. Migration and org-creation transaction behaviour can be unit-tested with stubs but **must be dry-run against a copy** before production (runbook item).

---

## 7. Revised phase breakdown (file-level, with effort + dependencies)

Effort: S ≈ half a sitting, M ≈ one sitting, L ≈ needs sub-dividing.

**Phase 9 — Data model, scoping & migration (L → split 9a/9b)** — *depends on: nothing*
- 9a: `models.py` (+Org/Invitation/Assignment/Override pydantic + request models), `database.py` (collections + §3.3 indexes), **`permissions.py`** (`require_org_member`, `require_manager`, `resolve_job_access`, `require_permission`), `routes_auth.py` (`_public_user` +org fields; `firebase_exchange` org creation — C7), `scripts/migrate_orgs.py`, `seed.py` rewrite. Tests: migration idempotency + rollback, seed integrity, `_public_user` shape, legacy-JWT compat.
- 9b: apply `resolve_job_access` org+scope to **every** query in `routes_jobs/candidates/ai/dashboard/reports` (C2 → 404). Tests: **one cross-org isolation test per resource**, grep-guard (no id-lookup without resolve), permission-denied stubs. *This is the security spine — do not rush.*

**Phase 10 — Invitation & first-login auth (M)** — *depends on: 9*
- `routes_orgs.py` (invite CRUD, members), `routes_auth.py` (`/accept-invite`, verification bypass scoped to a valid invite — explicit arg, never global), `email_service.py` (invite template), `get_current_user` suspension check (C3), rate limits. Frontend `pages/AcceptInvite.jsx` + `api.js` `invitesApi`. Tests: happy path + 9 edge cases + token replay/expiry/wrong-email + suspended-401.

**Phase 11 — Team management UI (M)** — *depends on: 10*
- `pages/Team.jsx`, `pages/TeamMember.jsx`, add-user modal, seat counter, suspend/reactivate, remove-with-reassignment; `Layout.jsx` Team section; `api.js` `teamApi`. Reuse `Modal/Card/Avatar/Pill/EmptyState`. Tests: backend contract + guard mirroring; manual checklist in PROGRESS.

**Phase 12 — Assignments, permissions & personal JD (L → split 12a/12b)** — *depends on: 9,11*
- 12a: `routes_assignments.py` (upsert/list/delete, targets/deadlines), permission enforcement wired across jobs/candidates/AI (one test per flag proving refusal). Assignment drawer UI.
- 12b: `job_jd_overrides` end-to-end (`PUT/DELETE /jobs/{id}/jd-override`, read-path resolution, AI uses caller's JD + records which text), "admin updated the JD" notice, personal badge/reset. Tests: override isolation (manager+peer see org JD), AI-JD selection, reassignment-on-remove.

**Phase 13 — Recruiter experience (M)** — *depends on: 12*
- `Jobs.jsx`/`JobDetail.jsx`/`Dashboard.jsx`: Assigned/My split, target+deadline widgets, disabled-with-tooltip controls, graceful 403, dashboard tiles. Tests: permission-mirroring, empty states.

**Phase 14 — Manager reports (L → split 14a/14b)** — *depends on: 9,12*
- 14a: `activity_events` writes at every mutation point; `routes_reports.py` `GET /reports/team` (aggregation-based, reuse pure functions), insights, low-sample suppression.
- 14b: manager `Reports.jsx` view (per-recruiter panels, filters), `export.csv` (stdlib `csv`). Tests: 5 mandatory edge cases per metric + golden-payload fixture.

**Phase 15 — Recruiter reports, hardening & handover (M)** — *depends on: all*
- `GET /reports/mine` + recruiter view, N+1 sweep (aggregations), index verification, bundle check (manager pages lazy, not in recruiter bundle), full regression (forward + reverse), `PROJECT_PLAN.md`/`PROGRESS.md` final, **owner runbook** (env vars incl. `APP_URL`, migration command, deploy order migrate→backend→frontend, rollback).

**Critical path:** 9a → 9b → 10 → 12 → 14; 11 and 13 can slot alongside once their dependency lands. 9b is the linchpin.

---

## 8. Bottom line for Phase 8
The codebase is **cleaner for this than the plan assumes**: identity already flows from the live DB doc (so no JWT surgery, C1), roles are already cleanly separated (platform `role` vs new `org_role`), and the report/analytics functions are already pure and reusable. The real work is (a) one `permissions.py` + org-scoping across ~22 queries with a per-resource isolation test, and (b) the invitation/assignment/reports features built from existing primitives. Three deliberate behaviour changes to confirm before Phase 9: **skip the JWT change (C1), standardize on 404 (C2), and the personal-jobs scope decision (§6.1.2).**
