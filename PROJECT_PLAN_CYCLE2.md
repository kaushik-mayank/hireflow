# HireFlow — Project Plan, Cycle 2 (Phases 8–15)

**Engagement type:** Surgical extension of a live, working product. **Not** a rewrite, **not** a redesign.
**Supersedes:** nothing. Cycle 1 (Phases 0–7 + Sessions 8–16) stays valid and is the baseline.
**Read first, every session:** `PROJECT_PLAN.md` (Cycle 1), `PROGRESS.md`, `AUDIT.md`, then this file.
**Live:** frontend `https://hireflow.cortinix.com` (Vercel) · backend `https://hireflow-w04l.onrender.com` (Render) · MongoDB Atlas · Firebase Auth · Groq (Llama).
**Stack (confirmed, do not assume otherwise):** React 19 + **CRA + CRACO** (`process.env.REACT_APP_*`, *not* Vite), Tailwind (DM Sans; navy/indigo tokens + amber = "AI" only), recharts (single charting lib), sonner toasts, axios + `AuthContext` JWT. Backend: FastAPI + Motor (async Mongo), app-issued JWT, Firebase ID-token bridge at `POST /api/auth/firebase` (verified via Google JWKS with `pyjwt`+`cryptography` — **`firebase-admin` is deliberately NOT a dependency**), `smtplib` email, Groq AI service.

---

## 1. Why Cycle 2 exists — the business change

HireFlow is being repositioned for **recruitment agencies and high-volume in-house recruitment teams**: one manager opens many roles and distributes them across several recruiters.

The single-tenant assumption ("every signed-up HR user is an island") is now wrong. Cycle 2 introduces **organisations with two in-product roles**:

| In-product role | Who | Gets in by |
|---|---|---|
| **Manager** (product calls it "Admin") | The person who buys/registers HireFlow — agency owner, HR manager | Public **sign-up** + Firebase email verification |
| **Recruiter** (product calls it "User") | Employees added by the manager | **Invitation only** — no public signup path |

There is **no public path to becoming a Manager of an existing organisation**, and **no public signup path for a Recruiter at all**.

> ### ⚠️ Naming collision — resolve it exactly this way
> Cycle 1 already has an "admin": the **platform owner** allowlist in `backend/admin_identity.py` (+ `admin.credentials.json` / `ADMIN_EMAILS`) that gates `/admin/*` — platform stats, all users, all resumes, feedback triage. **That is a different thing and must keep working untouched.**
>
> **Canonical vocabulary from here on:**
> - `platform_admin` — the allowlist superuser. Routes stay `/admin/*`. UI label: **"Platform Admin"** (purple accent, as today).
> - `manager` — org-level admin. New routes under `/team`, `/assignments`, plus a manager view of `/reports`. UI label: **"Admin"** (what the customer sees).
> - `recruiter` — org member. UI label: **"User"**.
>
> Code uses `platform_admin` / `manager` / `recruiter`. Customer-facing copy uses "Admin" / "User". Never blur the two in code.

---

## 2. Standing rules (Cycle 1 rules still apply; these are additions)

- [ ] **Read before editing.** Never edit an unopened file. Grep for the existing pattern first and copy it.
- [ ] **Design system is frozen.** No new colours, no new fonts, no new component library, no layout redesign. Reuse `components/ui.jsx` primitives and existing tokens only. Amber still means "AI".
- [ ] **Architecture is frozen.** Same routing model, same `AuthContext` + JWT session, same axios interceptor, same FastAPI router layout, same Mongo/Motor access style. New concerns = new collections + new route modules that look exactly like the old ones.
- [ ] **Backward compatibility is a hard requirement.** Existing accounts, jobs, candidates and the demo/seed data must keep working through every phase. Every phase ships behind data-safe migrations.
- [ ] **Every list/detail/report query is org-scoped and role-scoped server-side.** Never rely on the frontend to hide data. Cross-org access is a 404 (not a 403 — do not confirm existence).
- [ ] **Permissions are enforced on the server; the UI only mirrors them.** Every restricted control must have a matching backend check plus a test proving the API refuses it.
- [ ] **No unrelated refactors.** Log strays under "Backlog / Not in scope" in `PROGRESS.md`.
- [ ] **Small, reviewable commits** per logical unit, on `main`.
- [ ] **Ask before destructive actions** — deleting files, dropping fields, removing routes.
- [ ] **Universal-niche mandate holds.** No copy, label, placeholder or prompt may assume an office job. Assignment/target/report language must fit nurses, drivers, chefs, welders.
- [ ] **JD-driven AI mandate holds.** No occupation named in any prompt (enforced by tests).
- [ ] **Stop at every phase boundary.** Build, run tests, update `PROGRESS.md`, summarise, wait for "continue".
- [ ] **Honesty about verification.** Cycle 1's log is scrupulous about what was never executed. Keep that standard: state exactly what was run and what was only reasoned about.

---

## 3. Target data model

Additive only. **No existing field is removed or repurposed in Cycle 2.**

### 3.1 New collections

**`organizations`**
```
_id, name, owner_user_id, plan ("free_beta"), seat_limit (int, default 25),
status ("active"|"suspended"), created_at, updated_at
```

**`invitations`**
```
_id, org_id, email (lowercased), token_hash (sha256; raw token never stored),
invited_by (user_id), status ("pending"|"accepted"|"revoked"|"expired"),
expires_at (default +7d), accepted_at, created_at, resent_count, last_sent_at
```
Unique index on `(org_id, email)` for `status="pending"`.

**`job_assignments`**
```
_id, org_id, job_id, user_id, assigned_by, status ("active"|"paused"|"revoked"),
permissions {
  can_edit_jd            (bool, default false)  # personal override only — see §5.3
  can_edit_job_meta      (bool, default false)  # title, dept, location, salary
  can_upload_candidates  (bool, default true)
  can_move_stage         (bool, default true)
  can_reject_candidates  (bool, default true)
  can_use_ai             (bool, default true)   # rank / questions / summary / email
  can_view_team_candidates (bool, default false) # see other recruiters' candidates on this job
  can_close_job          (bool, default false)
},
targets { shortlist_target (int|null), sourced_target (int|null), interview_target (int|null) },
deadline (datetime|null), note (str|null), assigned_at, updated_at
```
Unique index on `(job_id, user_id)`.

**`job_jd_overrides`** — the "personal JD edit" requirement
```
_id, org_id, job_id, user_id, jd_text, jd_enhanced, updated_at
```
Read path: a recruiter viewing a job sees their override if one exists, else the org JD. Manager and every other user always see the org JD. **Overrides never write back to `jobs`.**

**`activity_events`** (append-only, powers manager KPIs without N+1 recomputation)
```
_id, org_id, actor_id, job_id, candidate_id, type
  ("candidate_uploaded"|"stage_changed"|"job_created"|"job_assigned"|"ai_used"|"job_closed"|"assignment_completed"),
meta {}, created_at
```
Indexed `(org_id, created_at)`, `(actor_id, created_at)`.

### 3.2 Fields added to existing collections

| Collection | New fields |
|---|---|
| `users` | `org_id`, `org_role` ("manager"\|"recruiter"), `status` ("invited"\|"active"\|"disabled"), `invited_by`, `activated_at`, `last_login_at` |
| `jobs` | `org_id`, `created_by` (user_id), `origin` ("org"\|"personal") — `personal` = a recruiter's own job, visible only to them **and their manager (read-only in reports)** |
| `candidates` | `org_id`, `sourced_by` (user_id), `assignment_id` (nullable) |
| `stage_transitions` | `org_id`, `actor_id` |
| `feedback` | `org_id` |

`users.role` ("hr"/"admin") is **left exactly as-is** and now means *platform* role only. Nothing new reads it for org decisions.

### 3.3 Indexes to add
`users(org_id, status)`, `users(email)` unique, `invitations(token_hash)`, `invitations(org_id, status)`, `jobs(org_id, status, created_at)`, `jobs(org_id, created_by)`, `job_assignments(org_id, user_id, status)`, `job_assignments(job_id)`, `candidates(org_id, sourced_by, stage)`, `activity_events(org_id, created_at)`.

### 3.4 Migration (idempotent, re-runnable, dry-run by default)
`backend/scripts/migrate_orgs.py`, modelled on the existing `scripts/reset_accounts.py`:
1. For every existing user without `org_id`: create an organisation named `"<name>'s Team"` (or company field if set), set `org_role="manager"`, `status="active"`, `owner_user_id`.
2. Backfill `org_id` + `created_by` on that user's jobs (`origin="org"`), `org_id` + `sourced_by` on their candidates, `org_id` on their stage transitions and feedback.
3. Report counts; `--confirm` to write; `--rollback-plan` printed at the top of the output.
4. Demo/seed accounts get the same treatment so the demo stays coherent. Extend `seed.py` to produce **one demo org: 1 manager + 2 recruiters + assignments with targets/deadlines** so the manager reports are demonstrable.

---

## 4. Auth & onboarding flow

### 4.1 Manager sign-up (only public signup that exists)
Unchanged from Session 15 in shape — **Firebase-only signup, lazy backend account creation**:
1. `/signup` → `firebaseSignUp(name, email, password)` → Firebase account + `displayName` + verification email → sign out → "verify your email" screen.
2. User clicks the link, returns to `/login`.
3. `firebaseSignIn` (`reload()` + `getIdToken(true)`) → `POST /api/auth/firebase`.
4. Backend find-or-create: **if the user does not exist, create org + manager in one transaction-like sequence** (create org, create user, set `owner_user_id`; on partial failure, delete the orphan and return 500 with a clear message). Mints the existing app JWT.
5. Signup form drops any role choice (already true) and keeps optional company name → becomes `organizations.name`.

### 4.2 Recruiter invitation (new)
1. Manager → `/team` → "Add user" (email, optional name). Seat limit checked.
2. Backend creates `users` row `status="invited"`, `org_role="recruiter"`, plus an `invitations` row with a **32-byte random token, stored only as sha256**. Email sent via existing `email_service.py` with `{APP_URL}/accept-invite?token=...`.
3. Recruiter opens the link → `GET /api/invites/{token}` returns `{org_name, email, valid, reason}` (no PII beyond their own email).
4. They set a password on `/accept-invite`:
   - Frontend calls Firebase `createUserWithEmailAndPassword(email, password)`.
   - Then `POST /api/auth/accept-invite` with `{token, firebase_id_token}`.
   - Backend verifies the Firebase token, asserts `token_email == invitation.email`, marks invitation accepted, sets `firebase_uid`, `status="active"`, `activated_at`, and mints the app JWT.
5. **Email verification is not required for invited users** — possession of the emailed invite link *is* the proof of email ownership. `REQUIRE_EMAIL_VERIFICATION` must be bypassed **only** on this path, only when a valid unexpired invitation matches the token's email. Implement as an explicit argument, never as a global flag flip.
6. Thereafter they use the normal `/login` and the existing Firebase **Forgot password** flow, unchanged.

**Edge cases that must each have a test and a friendly message:**
| Case | Behaviour |
|---|---|
| Token invalid / unknown | Neutral "This invitation link is no longer valid." + link to login |
| Token expired | Same message + "Ask your admin to resend the invitation." |
| Already accepted | Redirect to `/login` with "You've already set up your account — sign in." |
| Firebase account already exists for that email (`email-already-in-use`) | Switch the page to "Sign in to accept" — they authenticate with the existing password, then the same accept endpoint links the invite. Never leak whether the account exists to a stranger — this branch runs only after the token has already proved they hold the invite. |
| Invite revoked mid-flow | Neutral invalid message |
| Backend down after Firebase account creation | Same Session-15 lesson: **the two steps are separate and errors must be honest.** "We're having trouble reaching the server — your password is set, please sign in." Never "invalid password". |
| Weak password | Firebase's own rule, mapped to friendly copy; enforce ≥8 chars client-side first |
| Seat limit reached | Manager gets a clear 409 with the seat count |
| Email delivery fails | Invite still created; UI shows "Email couldn't be sent" + **Copy invite link** button (this is the SMTP-may-be-unconfigured reality from Cycle 1) |

### 4.3 Removal / suspension
- **Suspend** (`status="disabled"`) — the default, reversible: JWT checks status on every request → 401 with "Your access has been suspended." Their data stays; assignments pause.
- **Remove** — requires choosing a **reassignment target** for their active assignments and their sourced candidates, or explicitly leaving them unassigned. Never orphan data. Confirmation modal spells out what happens. Managers cannot remove themselves; an org must always have ≥1 active manager.
- Firebase user is **not** deleted by the app (out of scope; documented in the handover).

---

## 5. Permissions

### 5.1 Matrix (server-enforced)

| Capability | Manager | Recruiter (own job) | Recruiter (assigned job) |
|---|---|---|---|
| Create job | ✅ | ✅ (`origin="personal"`) | — |
| See job | all org jobs | own only | assigned only |
| Edit job meta | ✅ | ✅ | only if `can_edit_job_meta` |
| Edit JD | ✅ (org-wide) | ✅ (org-wide, it's theirs) | only if `can_edit_jd` → **personal override, never global** |
| Close/delete job | ✅ | ✅ | only if `can_close_job`; delete never |
| Upload candidates | ✅ | ✅ | if `can_upload_candidates` |
| Move stage / reject | ✅ | ✅ | if `can_move_stage` / `can_reject_candidates` |
| Use AI (rank, questions, summary, compare, emails) | ✅ | ✅ | if `can_use_ai` |
| See other recruiters' candidates on the job | ✅ | n/a | if `can_view_team_candidates` |
| Assign jobs / set targets & deadlines | ✅ | ❌ | ❌ |
| Add/suspend/remove users | ✅ | ❌ | ❌ |
| Team reports | ✅ | ❌ | ❌ |
| Own reports | ✅ | ✅ | ✅ |
| Platform admin panel `/admin/*` | only if also on the platform allowlist | ❌ | ❌ |

### 5.2 Enforcement pattern
One dependency module `backend/permissions.py` exposing:
```
require_org_member(user)
require_manager(user)
resolve_job_access(user, job_id) -> JobAccess(job, assignment|None, effective_permissions, scope)
require_permission(access, "can_edit_jd")
```
Every job/candidate/AI/report route goes through `resolve_job_access`. **No route may query `jobs` or `candidates` by id without it.** A grep-based test asserts this (same spirit as the "no occupation in prompts" guard).

### 5.3 The personal-JD rule (explicitly requested — get this exactly right)
When a recruiter with `can_edit_jd` edits the JD of an **assigned** job:
- The edit is written to `job_jd_overrides` keyed by `(job_id, user_id)`.
- Only that recruiter sees it. Manager and all other recruiters see the org JD.
- **AI calls made by that recruiter use their override**; AI calls by anyone else use the org JD. Store which text was used on the resulting analysis record so results are explainable.
- The UI shows a small neutral badge: "Your version — visible only to you" + a "Reset to the admin's version" action.
- Manager edits to the org JD do **not** silently wipe overrides; the recruiter sees "The admin updated this job description" with a diff-free "view/adopt latest" action.

---

## 6. Manager dashboard & pages

Same shell, same sidebar patterns, same cards. New sidebar section: **Team**.

**`/dashboard` (manager view)** — replaces the personal counters with org counters: open roles, roles unassigned (⚠️ actionable), active users, candidates this week, hires this month, assignments past deadline, assignments with no activity in 7+ days. Every tile links to a filtered list.

**`/team`** — user list (name, email, status, jobs assigned, candidates sourced, last active), Add user modal, resend/revoke invite, suspend/reactivate, remove-with-reassignment, seat usage `x / 25`.

**`/team/:userId`** — one recruiter: assignments with target progress bars, funnel, recent activity, quick reassign.

**`/jobs` (manager view)** — existing list + `Assigned to` column (avatars/initials), `Unassigned` filter, and an **Assign** action opening the assignment drawer: multi-select users, per-user permission toggles (sensible defaults), targets, deadline, note. Bulk-assign one job to several users, and one user to several jobs.

**`/reports` (manager view)** — see §8.

---

## 7. Recruiter dashboard

Unchanged in look and in every existing capability for **their own** jobs. Additions only:
- Job list is split (tabs or a filter chip, not a new layout): **Assigned to me** · **My jobs**.
- Assigned job cards show target progress (`12 / 20 shortlisted`), deadline with an at-risk state, and who assigned it.
- Controls the recruiter lacks permission for are **disabled with a tooltip explaining who to ask** — never hidden silently, never crashing on a 403.
- `/dashboard` gains "My targets" and "Deadlines this week".
- Personal-JD badge and reset action as per §5.3.

---

## 8. Reports & KPIs

Keep recharts. Keep the Cycle-1 empty/low-data discipline: **no percentage claims below a 5-item sample**, honest empty states, no fabricated numbers (remember `est_completion`). Rule-based insights stay rule-based (instant, free, deterministic); the on-demand AI pipeline-health report stays on demand.

**Shared filters:** date range (7/30/90/custom), user, job, status, source, department/location.

### 8.1 Manager report — panels
| Panel | Definition |
|---|---|
| Team throughput | Candidates sourced / screened / interviewed / hired per recruiter over the range |
| Target attainment | `sourced ÷ sourced_target`, `shortlisted ÷ shortlist_target` per assignment and per recruiter; on-track / at-risk / missed by burn-down against the deadline |
| Deadline health | Assignments by days remaining; overdue list, longest overdue first |
| Funnel by recruiter | Cycle-1 furthest-stage-reached funnel, split by recruiter, with per-stage drop-off |
| Quality of sourcing | Shortlist rate, interview rate, offer rate, hire rate per recruiter (rejection-after-screen % is the quality signal, not raw volume) |
| Time metrics | Time-to-first-candidate, time-to-shortlist, time-to-hire — per job and per recruiter, with the 30-day trend split |
| Source effectiveness | Existing panel, additionally sliceable by recruiter (uses `config/sources.js`) |
| Workload balance | Open assignments and active candidate load per recruiter — flags overload and idleness |
| Roles needing attention | Open, unfilled, no movement 14+ days, unassigned, or past deadline — the "what to do next" list |
| Activity | Events per day per recruiter from `activity_events`; last-active per user |
| AI usage | Calls per recruiter/job (cost visibility) — reuse the existing `ai_usage_log` |
| Insights | Rule-based plain-language lines, e.g. "3 roles have had no candidate movement in 2 weeks", "Priya is at 40% of her shortlist target with 3 days left" |

Exports: CSV per panel (server-generated, org-scoped). No new dependency — stdlib `csv`.

### 8.2 Recruiter report — panels
My target progress · my funnel · my time-to-shortlist vs my own 30-day baseline (**never a public leaderboard ranking against colleagues** — the manager sees comparisons, the recruiter sees their own trend) · my source effectiveness · my deadlines · assigned-vs-own split · my activity streak.

### 8.3 KPI formulas — write these down in code comments and tests
```
shortlist_rate      = shortlisted ÷ sourced                  (min sample 5)
target_attainment   = actual ÷ target                        (null target ⇒ panel hidden, not 0)
time_to_shortlist   = first "shortlisted" transition − candidate.uploaded_at
time_to_hire        = "hired" transition − job.created_at     (existing definition — do not change it)
deadline_risk       = required_daily_rate ÷ observed_daily_rate over the last 7 days
idle_days           = now − last activity_event on that job
```
Every metric must have: a zero-data test, a single-item test, a divide-by-zero test, a naive-vs-aware timestamp test, and a "candidate predating the field" test — exactly as Cycle 1's 31 report tests do.

---

## 9. API surface

**New**
```
POST   /api/orgs/invites                 (manager)  create + email invite
GET    /api/orgs/invites                 (manager)  list pending
POST   /api/orgs/invites/{id}/resend     (manager)
DELETE /api/orgs/invites/{id}            (manager)  revoke
GET    /api/invites/{token}              (public)   validate, minimal payload
POST   /api/auth/accept-invite           (public)   token + firebase id token → app JWT
GET    /api/orgs/members                 (manager)
PATCH  /api/orgs/members/{id}            (manager)  suspend / reactivate
DELETE /api/orgs/members/{id}            (manager)  remove + reassignment payload
GET    /api/orgs/me                      (any)      org name, seats, my role, my permissions
POST   /api/jobs/{id}/assignments        (manager)  create/update (idempotent upsert)
GET    /api/jobs/{id}/assignments        (manager)
DELETE /api/jobs/{id}/assignments/{uid}  (manager)
GET    /api/assignments/mine             (recruiter)
PUT    /api/jobs/{id}/jd-override        (recruiter, needs can_edit_jd)
DELETE /api/jobs/{id}/jd-override        (recruiter)
GET    /api/reports/team                 (manager)  + filters
GET    /api/reports/team/export.csv      (manager)
GET    /api/reports/mine                 (any)
```

**Changed (behaviour, not shape where avoidable)**
`GET /api/jobs` (org+assignment scoped, `scope=assigned|mine|all`), `GET/PUT /api/jobs/{id}` (permission-gated; returns `effective_permissions` and `jd_source: "org"|"personal"`), all `/api/candidates*` (org+assignment scoped, stamps `sourced_by`), all `/api/ai/*` (permission-gated, uses the caller's JD view), `/api/dashboard` (role-aware), `POST /api/auth/firebase` (creates org on first manager login).

Keep response shapes additive so existing components don't break. `/admin/*` untouched.

---

## 10. Phases

Each phase ends with: build green (`CI=true yarn build`), full test suite green, `PROGRESS.md` updated with what was **run** vs only reasoned about, a summary, then **stop**.

### Phase 8 — Re-audit & design lock (read-only) 🔍
- Re-read every backend module and every page; produce `CYCLE2_AUDIT.md`: current auth/JWT claims, every place `role` is read, every job/candidate query and its scoping, every frontend guard, the exact `Reports.jsx` panel/data contract, seed/demo shape.
- Produce the **exact** migration script plan and a list of every route that will change.
- Flag anything in this plan that conflicts with the code as it actually is. **Disagree with the plan where the code says otherwise — write it down rather than silently deviating.**
- Deliverables: `CYCLE2_AUDIT.md`, updated checklists, open questions. **No source edits.**

### Phase 9 — Data model, scoping & migration 🧱
Models, indexes, `permissions.py`, org-scoping on every existing query, `migrate_orgs.py` (dry-run first), seed rewrite to a 1-manager/2-recruiter demo org, JWT gains `org_id` + `org_role` (**with a fallback path for JWTs issued before this phase** — do not log everyone out).
Tests: migration idempotency, cross-org isolation (user A cannot read org B's job/candidate/report — one test per resource), legacy-JWT compatibility, seed integrity.

### Phase 10 — Invitation & first-login auth 🔑
Invite CRUD, tokens, email templates in `email_service.py`, `/accept-invite` page, verification bypass strictly scoped to a valid invite, suspension checks in `get_current_user`, every §4.2 edge case, copy-invite-link fallback, rate limits (invites per org per hour; accept attempts per token).
Tests: full happy path, all 9 edge cases, token replay, expired token, wrong-email token, suspended-user 401.

### Phase 11 — Team management UI 👥
`/team`, `/team/:userId`, add-user modal, invite states, suspend/reactivate, remove-with-reassignment, seat counter, sidebar "Team" section. Existing primitives only.
Tests: component-level guards + backend contract tests; manual checklist written into `PROGRESS.md`.

### Phase 12 — Assignments, permissions & personal JD 🎯
Assignment drawer, permission toggles with defaults, targets, deadlines, bulk assign, `job_assignments` API, permission enforcement across jobs/candidates/AI routes, `job_jd_overrides` end-to-end, "admin updated the JD" notice.
Tests: one test per permission flag proving the API refuses when false; override isolation (manager and peer see the org JD); AI uses the caller's JD; reassignment on removal.

### Phase 13 — Recruiter experience 🧑‍💼
Assigned/My tabs, target + deadline widgets on cards, disabled-with-tooltip controls, dashboard tiles, graceful 403 handling everywhere (no white screens — the root `ErrorBoundary` is a backstop, not a plan).
Tests: permission-mirroring tests; empty states for a brand-new recruiter with zero assignments.

### Phase 14 — Manager reports 📊
All §8.1 panels, filters, CSV export, `activity_events` writes wired at every mutation point, rule-based insights, low-sample suppression, empty states.
Tests: the five mandatory edge cases per metric, plus a fixture-based "golden numbers" test for the whole report payload.

### Phase 15 — Recruiter reports, hardening & handover ✅
§8.2 panels, N+1 sweep on all new queries (aggregation pipelines, not Python loops — see the Cycle-1 handover item), index verification, bundle check (new pages lazy-loaded; the manager-only bundle must not ship to recruiters), full regression run, `PROJECT_PLAN.md` + `PROGRESS.md` final update, owner runbook (env vars, migration command, rollout order, rollback).
Rollout order to document: **migrate (dry-run → confirm) → deploy backend → deploy frontend.**

---

## 11. Testing & error-handling standards

- **Backend:** pytest, offline (stub `groq`, Mongo, Firebase — follow the existing stub-merge pattern that fixed the reverse-order isolation bug). Suite must pass **in reverse order** too. Current baseline: 186 tests — Cycle 2 must only ever add.
- **Coverage floor per phase:** happy path, each permission denial, cross-org isolation, empty data, malformed/legacy documents, and the failure mode of every external call (SMTP down, Groq 503, Firebase unreachable, Mongo timeout).
- **Frontend:** `CI=true yarn build` must stay clean (warnings-as-errors). Every new fetch has a loading state, an empty state and an error state — and the error state says what actually failed. **The Session-15 lesson is a rule: never map a server/network failure onto a user-error message.**
- **Idempotency:** invite accept, assignment upsert and the migration script must all be safe to run twice.
- **No silent catches.** Log server-side with context; surface a human sentence client-side.

---

## 12. Decisions needed from the owner (ask early, don't guess)

1. Seat limit for the free beta — plan assumes **25**, soft-blocking with a clear message.
2. Can a recruiter create their **own** jobs? Plan assumes **yes** (`origin="personal"`, manager sees them in reports read-only). Confirm.
3. Can a manager be promoted from within the org (second manager)? Plan assumes **manager can promote a recruiter to manager**, but the owner cannot be demoted.
4. Removing a user: default to **suspend**, with hard-remove behind a typed confirmation. Confirm.
5. `APP_URL` for invite links — needs a new backend env var (`APP_URL=https://hireflow.cortinix.com`). Invites cannot be sent without it.
6. SMTP is currently the only delivery path and may be unconfigured — the copy-link fallback is therefore mandatory. Confirm that's acceptable for beta.
7. Should the manager see recruiters' *candidate-level* data by default? Plan assumes **yes** (they're the data controller); recruiters see peers' only with `can_view_team_candidates`.

## 13. Out of scope for Cycle 2
Billing/payments · SSO/SAML · per-org custom branding · notification centre / push · mobile app · Firebase user deletion from the app · object storage for PDF binaries · rotating the Atlas/JWT secrets (owner's standing decision — do not re-litigate).
