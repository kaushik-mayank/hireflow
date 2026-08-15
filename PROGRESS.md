# HireFlow — Progress Log

> **Resuming a session? Read this file and PROJECT_PLAN.md first, then AUDIT.md for detail.**
> Newest entries at the top.

**Project root:** `.../Hireflow/hireflow-main 22072027/hireflow-main 22072027/` (note the doubled folder name — the *inner* one is the real root)
**Current phase:** 🟢 **Cycle 4 — sticky controls / large-list UX polish (frontend-only). Owner env steps still pending: `CI=true yarn build`, migration vs DB copy, enable Firebase email-link.** Live: frontend `https://hireflow.cortinix.com`, backend `https://hireflow-w04l.onrender.com`.
**Last updated:** 2026-08-15

---

## Session 35 — 2026-08-15 — Cycle 4: sticky controls for large candidate/data lists (UX polish)

**Frontend-only, no backend change** (319 offline tests unchanged). No redesign — same components, styling and behaviour; only positioning changed so key controls stay reachable while scrolling long lists.

### Enabling infra (additive, no visual change)
- **`components/Layout.jsx` — `Topbar`** now publishes its own height as a CSS variable **`--topbar-h`** on `:root` (via a `ResizeObserver`). This lets any page pin a sub-header directly below the (already sticky) Topbar with `top: var(--topbar-h)` — robust across pages, no hard-coded pixel offsets. Purely additive; the Topbar looks and behaves exactly as before.

### Job Panel (`pages/JobDetail.jsx`) — the primary request
- The **analyse action moved from the Upload card into the candidate filters row** (kept its exact `AIButton` design + "Analyze All / Analyse Selected (N)" behaviour), so it sits with the filters.
- **Tabs + filters + the analyse action + the bulk-move bar are now wrapped in one sticky container** that pins just below the Topbar (`sticky; top: var(--topbar-h)`, page-coloured background) while the **candidate list scrolls beneath**. The **Upload zone scrolls away** as intended (not sticky). Everything else (candidate cards, JD/Team/Activity tabs, permissions, closed-job read-only) is unchanged.

### Broader audit — same pattern on the other high-volume, filterable list pages
Made the **filter/search bars sticky** (pinned below the Topbar while the list scrolls) on:
- **`pages/Jobs.jsx`** (search + status + "hiring for" combo),
- **`pages/admin/AdminUsers.jsx`** (search + role + status),
- **`pages/admin/AdminResumes.jsx`** (search + pagination),
- **`pages/admin/AdminFeedback.jsx`** (status + type + pagination).

### Deliberately NOT changed (with reasons)
- **Sticky table headers were not added.** Those tables live inside `overflow-x-auto` cards; making `thead` sticky against the window scroll doesn't work reliably there without imposing a fixed table height (an internal scroll region) — a structural change that risked regressions for limited benefit. The sticky **filter/search bars** deliver the core "controls stay reachable" win cleanly.
- **Low-volume screens left alone** (Team ≤ seat limit, per-recruiter Reports tables, Dashboard) — sticky controls there would add chrome without real benefit.
- **CandidateBoard** already uses an internal scroll region with its own sticky column headers — untouched.

### Honest notes
- **No `CI=true yarn build`** here (no Node) — static-checked (no unused imports; JobDetail JSX balances). Needs the owner build + deploy, then a quick QA: open a job with many candidates → scroll → tabs/filters/analyse/bulk stay pinned below the header, upload zone scrolls away; same for the Jobs and admin list filter bars.

---

## Session 34 — 2026-08-09 — Cycle 3 fixes from owner testing (3 items)

Backend offline-tested (**319 pass forwards AND reverse**, +4); frontend written, not built here.

1. **Close-job confirmation is now a proper modal.** Replaced the raw `window.confirm(...)` on the Jobs card with the existing `Modal` component and professional SaaS copy ("… will be marked Closed. It stays in your Jobs list and every candidate and record is kept, but it stops accepting activity …"). `Jobs.jsx` (`closeTarget` state + `doClose`).
2. **Closed jobs are read-only (not just labelled).** Backend now blocks writes on a closed job — `permissions.ensure_job_open(access)` raises **409** and is called in `upload_resumes`, `update_stage`, `rank`; `bulk_update_stage` skips closed-job candidates; `get_candidate` returns the job `status`. The job stays fully **viewable** (get_job/board/candidate all work). Frontend surfaces it (existing banner/notification style): a **"This job is closed"** banner on `JobDetail`, disabled upload/analyse/bulk-move/delete; the Kanban board + panel become view-only with a closed banner; `CandidateDetail` disables stage moves with a closed note. **Resume viewing and other read-only AI aids still work on closed jobs.**
3. **Resume "Download PDF" now downloads directly** (no browser print/Save-as-PDF dialog). New backend endpoint **`GET /candidates/{id}/resume.pdf`** generates the PDF server-side from the cached structured resume (falls back to raw text) using **reportlab** (already a dependency; imported lazily so the offline test suite stays reportlab-free). Frontend downloads the blob via `candidatesApi.resumePdf` and removed the old `window.print()` path + print-only clone. New `resume_pdf.py` mirrors the `ResumeView` sections.

### Files
- Backend: `permissions.py` (ensure_job_open), `routes_candidates.py` (guards + `status` in job payload + `resume.pdf` endpoint), `routes_ai.py` (rank guard), **`resume_pdf.py`** (NEW). Tests: `test_org_isolation.py` (+4: upload/move/rank blocked on closed, closed-job still readable; `fastapi.responses` stub gained `Response`).
- Frontend: `api.js` (resumePdf), `pages/Jobs.jsx` (close modal + Close/read-only), `pages/JobDetail.jsx`, `pages/CandidateBoard.jsx`, `pages/CandidateDetail.jsx` (download + closed read-only).

### Honest notes
- **No `CI=true yarn build`** here (no Node) — static-checked (no unused imports); owner must build + deploy.
- PDF is generated server-side with reportlab: the layout mirrors the on-screen `ResumeView` sections but is a fresh PDF (not a pixel copy of the HTML), and needs one manual QA after deploy (View Resume → Download PDF downloads a file directly; closed job blocks upload/move and shows the banner; close-job modal reads professionally).

---

## Session 33 — 2026-08-09 — Cycle 3 (candidate/resume, Kanban, analysis, job lifecycle)

**Cycle 2 is CLOSED** — owner reviewed and verified. Cycle 3 read `PROJECT_PLAN_CYCLE2.md` (baseline) + this PROGRESS (source of truth) first, then implemented the smallest safe changes. Backend offline-tested (**315 pass forwards AND reverse**, +2); frontend written, **not built here** (no Node).

### 1. Resume view consolidated → one **"View Resume"** + PDF download
- `CandidateDetail.jsx`: removed the old raw-text toggle (`resumeOpen`/`<pre>`); the single **"View Resume"** button opens the existing formatted viewer (`ResumeView` via `POST /ai/structure`, cached). Modal title "Formatted Resume" → **"Resume"**; footer "Print / Save PDF" → **"Download PDF"** (unchanged mechanism: `window.print()` on the print-only `ResumeView` clone → the browser's *Save as PDF*; no new dependency). Nothing is labelled "Formatted View" anymore. Removed now-unused icons (`ChevronDown/Up`, `LayoutTemplate`, `Printer`).
- **Decision / important:** the `structure` endpoint is **no longer gated by `can_use_ai`** (`routes_ai.structure_resume` now uses `resolve_candidate_access` directly). Rationale: since this is the *sole* resume view, gating it would strip resume access from a recruiter without the AI flag — a regression. The generative AI **tools** (rank / questions / summary / email / compare) stay gated. Reuses the existing `ResumeView` design — no new resume UI.

### 2. Kanban starts at **Shortlisted** + admin-defined stages
- `CandidateBoard.jsx`: board columns now start at `"Shortlisted"` (`STAGES.slice(indexOf("Shortlisted"))`) then the rest of the default pipeline, then the job's `custom_stages`. Candidates before Shortlisted don't appear on the board. **Admin-added stages** reuse the **existing per-job `custom_stages`** mechanism (Session 31/32) — no new stage system. Drag + panel moves still validate against `can_move_stage`.

### 3. **Analyse All** vs **Analyse Selected**
- `RankRequest.candidate_ids` (optional); `routes_ai.rank_candidates` scopes to those ids (re-analysing them) when present, else the existing "all un-analysed" behaviour. `aiApi.rank(jobId, { candidateIds })`.
- `JobDetail.jsx`: the top analyse button reads **"Analyze All Candidates"** with no selection, and **"Analyse Selected Candidates (N)"** when candidates are ticked — sending only the selected ids. Existing per-candidate visibility/permission scoping preserved.

### 4. Job lifecycle — **Pause** and **Close** (close ≠ delete)
- Backend already supported `status` `active|paused|closed` and never deletes on close; **no backend change needed**. `Jobs.jsx`: the card now offers **Pause/Reactivate** (temporary) and a distinct **Close** action (terminal, with confirm). **Closed jobs stay in the Jobs panel** marked "Closed" (list query has no status filter; the status dropdown already has "Closed"); closed cards show View only (no pause/close). Data preserved.

### 5. Kanban on the **User (recruiter) side** — already available, verified
- No code change required. The board route `/jobs/:id/board` is a `PrivateRoute` (not manager-gated), the "Kanban Board" button in `JobDetail` is unconditional, and `CandidateBoard` gates only on `effective_permissions` (not role). So recruiters already reach and use the **same** shared component per their permissions (drag when `can_move_stage`). Verified by inspection; documented rather than duplicated (per the "reuse existing architecture" rule).

### Files
- Backend: `models.py` (RankRequest), `routes_ai.py` (rank candidate_ids + ungate structure). Tests: `test_org_isolation.py` (+2: rank-selected, view-resume-ungated; existing rank bodies got `candidate_ids=None`).
- Frontend: `api.js` (aiApi.rank), `pages/CandidateDetail.jsx`, `pages/CandidateBoard.jsx`, `pages/JobDetail.jsx`, `pages/Jobs.jsx`.

### What was NOT done / honest notes
- **No `CI=true yarn build`** here (no Node) — static-checked (no unused imports); owner must build + deploy for the changes to appear live.
- "Download PDF" uses the browser print-to-PDF path (existing mechanism), not a bundled PDF generator — no new dependency, per the "prefer existing architecture / no unnecessary deps" rules.
- Board candidate **count** in its subtitle is still the job's total (includes pre-shortlist) — left unchanged to avoid touching unrelated UI.
- Backend suite verified; frontend requires the owner's manual QA (resume view + PDF, board-from-Shortlisted for admin **and** user, analyse all/selected, pause vs close, closed-stays-listed).

---

## Session 32 — 2026-08-08 — Fixes from owner testing (4 items) + personal jobs

Backend offline-tested (**313 pass forwards AND reverse**); frontend written, not built here.

1. **Target-label wording (recruiter job cards).** "Sourced N / Shortlist N" (read like already-achieved) → **"Sourcing target: N" / "Shortlisting target: N"**; due date unchanged.
2 & 3. **Recruiters can create their own jobs (personal jobs).** This was the "only an admin can do this" error. Now:
   - **`create_job`** is `require_org_member` (not manager): a manager creates an **org** job (`origin="org"`, visible to the org + assigned recruiters); a recruiter creates a **personal** job (`origin="personal"`, visible only to them).
   - **`permissions.resolve_job_access`** — a personal job resolves only for its creator (`scope="owner"`, full perms); everyone else, **including the org's manager, gets 404**.
   - **`permissions.visible_jobs_query`** (NEW) — the single visibility filter used by **list_jobs, dashboard, reports, pipeline-health**: manager → all org jobs + own personal; recruiter → assigned org jobs + own personal. Personal jobs never leak to anyone else. (Replaces the old `accessible_job_ids`-based logic in those routes.)
   - **update/delete job** now allow `scope in ("manager","owner")` so a recruiter can manage their own personal job.
   - Frontend: **Create button shown to recruiters** (labelled "Create My Job"), pause/reactivate available on owned personal cards, a **"Personal" tag** on those cards, recruiter empty state offers create. `JobCreate` already worked once the backend allowed it.
4. **Custom stages on the candidate page.** Root cause: the `get_candidate` change that returns the job's `custom_stages` was **written but never committed** (so the live candidate API omitted it). Committed now; `CandidateDetail`'s "Move to other stage" dropdown already renders `defaults + cand.job.custom_stages`. (Board + job page already had it.) Custom stages remain **per-job** — each job carries its own list.

### Files
- Backend: `permissions.py`, `routes_jobs.py`, `routes_dashboard.py`, `routes_reports.py`, `routes_ai.py`, `routes_candidates.py` (get_candidate commit) + tests (`test_org_isolation.py`: personal-job suite; matcher gained `$or`/`$ne`, FakeColl gained delete_many).
- Frontend: `pages/Jobs.jsx`.

### Note on prior ledger
The earlier "Assigned/My tabs N/A — personal jobs are Cycle 3" note is now **superseded**: recruiter personal jobs ship in Cycle 2 per this request. Managers still never see them.

### Owner action items (unchanged)
1. **`CI=true yarn build`** and deploy. 2. Enable Firebase email-link (Runbook §1). 3. Migration dry-run → confirm vs a DB copy.

---

## Session 31 — 2026-08-08 — Owner-requested enhancements (6 items)

All additive; existing behaviour preserved. Backend offline-tested (**309 pass forwards AND reverse**); frontend written but **not built here**.

1. **Per-job custom stages.** Managers add extra pipeline stages (e.g. L1/L2/L3) at job create/edit on top of the defaults. Backend: `JobCreate/JobUpdate.custom_stages` (sanitised — trim/dedupe/cap 12/drop default collisions); candidate moves (single + **bulk**) validate against defaults + that job's custom stages; `get_candidate` returns the job's `custom_stages`. Frontend: JobCreate input; JobDetail/CandidateBoard/CandidateDetail render `STAGES + custom_stages` (board column colour falls back for custom stages).
2. **"Hiring for" (company/client) on a job.** `JobCreate/JobUpdate.hiring_for`; shown on job cards, the job subtitle, and used by the filter below. Lets an agency working several clients tell jobs apart.
3. **Company filter in the Jobs panel.** A combo (type-or-pick `<datalist>`) that filters jobs by `hiring_for`, alongside the existing title search + status dropdown.
4. **Team-report member filter (manager).** `Reports → Team` gains an "All members / <name>" dropdown that filters every per-recruiter panel to one teammate.
5. **Manager candidate visibility + "sourced by" filter.** Managers already see all org candidates on a job; added a **manager-only "Sourced by" filter** (teammate dropdown) on the job's candidate list plus a "by <name>" label on each row.
6. **Recruiter first-login rework + the reported bug.**
   - **Bug fixed (backend):** an activated recruiter with an unverified Firebase email is **no longer bounced to "verify your email"** on later logins — the verification gate now applies to public *manager* sign-ups only (recruiters are exempt; +1 test).
   - **Flow (frontend):** first login now **verifies the email first** via a Firebase **email-link**, then shows **create-password**, then straight into the app; afterwards it's **password-only, no verification**. If email-link sign-in isn't enabled on the Firebase project, it **falls back** to setting a password directly (still no lockout). Unapproved email → professional message: *"You don't have an approved account yet. Contact your company's manager — or sign up as admin."*

### Files
- Backend: `models.py`, `routes_jobs.py`, `routes_candidates.py`, `routes_auth.py` (+ tests in `test_org_isolation.py`, `test_org_and_auth.py`).
- Frontend: `pages/JobCreate.jsx`, `pages/Jobs.jsx`, `pages/JobDetail.jsx`, `pages/CandidateBoard.jsx`, `pages/CandidateDetail.jsx`, `components/TeamReport.jsx`, `pages/Login.jsx`, `lib/firebase.js`.

### Owner action items (updated)
1. **`CI=true yarn build`** (covers all frontend batches incl. Session 31).
2. **Enable Firebase "Email link (passwordless sign-in)"** + authorized domains, so the recruiter verify-email step works (see `CYCLE2_RUNBOOK.md` §1). Without it the app safely falls back to create-password.
3. Migration dry-run → `--confirm` against a DB copy (unchanged).

---

## 📋 Cycle 2 completion status (updated Session 30)

| Phase | Status | Notes |
|---|---|---|
| 8 — Re-audit & design lock | ✅ Done | `CYCLE2_AUDIT.md` |
| 9 — Data model, scoping, migration | ✅ Done | JWT change intentionally **skipped** (confirmed C1). Migration script written; **not yet run vs real Mongo** |
| 10 — Auth & onboarding | ✅ Done (reworked) | Approved-email + first-login create-password (owner decision). Emailed-invite code kept dormant |
| 11 — Team management UI | ✅ Done | add/bulk, suspend/reactivate, seats, sidebar, **remove-with-reassignment** (Session 30). *Follow-up:* dedicated `/team/:userId` page (list + all actions already ship) |
| 12 — Assignments, permissions, JD | ✅ Done | drawer, toggles/targets/deadlines, **bulk assign**, API, enforcement across jobs/candidates/AI, JD overrides, **"admin updated the JD" notice** (Session 30) |
| 13 — Recruiter experience | ✅ Done | disabled-with-tooltip everywhere (job/candidate/board), graceful 403s, recruiter job list w/ deadline+targets, role-aware controls, recruiter empty states. Permission enforcement has per-flag tests. (*Assigned/My tabs N/A — personal jobs are Cycle 3.*) |
| 14 — Manager reports | ✅ Done | throughput, quality-of-sourcing, target attainment, deadline health, workload, roles-needing-attention, activity, AI-usage, insights; **date-range filter**; **CSV export** (stdlib csv); `activity_events` at every mutation. *Follow-up:* single golden-payload fixture test (per-metric edge tests exist) |
| 15 — Recruiter reports, hardening, handover | 🟢 Mostly | **`/reports/mine` + MyProgress** recruiter view; **`CYCLE2_RUNBOOK.md`** (env, migration, rollout, rollback, smoke tests); N+1 avoided (one-query-per-collection + in-memory grouping — aggregation-pipeline conversion is a documented perf follow-up). **Owner-only (need real env): run migration vs a DB copy; `CI=true yarn build` + bundle/source-map check; index verification on live Mongo** |

**Cross-cutting caveats (unchanged, important):** the frontend has **never been built here** (no Node) — **`CI=true yarn build` is the outstanding gate**; and **nothing has run against real Mongo/Firebase/SMTP** — backend verification is offline unit + stub-route tests (**305 pass forwards AND reverse**). See `CYCLE2_RUNBOOK.md` for the exact owner steps.

---

## Session 30 — 2026-08-05 — Cycle 2 completion: 11/12 leftovers, 14b, 15 + runbook

Owner asked to complete all remaining phases. Implemented the outstanding items across four tested batches.

### Backend (305 offline tests pass forwards AND reverse; +19 this session)
- **Phase 11:** `DELETE /orgs/members/{id}` now takes `reassign_to` — an active member's assignments move to the target recruiter (or are revoked) and their sourced candidates are re-attributed, then the member is disabled; pending approvals still just delete. Last-active-admin guard kept.
- **Phase 12:** `POST /jobs/{id}/assignments/bulk` (assign one job to many; idempotent; skip-with-reason). `get_job` returns `jd_org_updated` when a recruiter's personal JD override predates the admin's last JD edit (`update_job` stamps `jd_updated_at` only on JD changes).
- **Phase 14b:** `team_reports.py` gained `quality_of_sourcing`, `roles_needing_attention`, `activity_summary`; `/reports/team` now returns those + `ai_usage` (from `ai_usage_log`) and honours `range_days`; new **`GET /reports/team/export.csv`** (stdlib csv, per-panel) and **`GET /reports/mine`** (recruiter's own targets/deadlines/throughput/activity — never a leaderboard). `activity_events` now also written on `job_created`/`job_closed`.

### Frontend (written; ⚠️ not built here)
- `TeamReport.jsx` expanded to all panels + a **date-range toggle** + per-panel **CSV** downloads (blob via the auth interceptor).
- `Team.jsx` **remove-with-reassignment** modal (pick who inherits the work, or leave unassigned).
- `AssignmentPanel.jsx` assign modal now **multi-selects** teammates (bulk assign).
- `JobDetail.jsx` shows the **"admin updated the JD"** notice.
- New `MyProgress.jsx` renders the recruiter's `/reports/mine` targets & deadlines above their personal analytics.
- `api.js`: `assignmentsApi.bulkUpsert`, `orgsApi.removeMember(id, reassign_to)`, `reportsApi.team(range)/teamCsv/mine`.

### Handover
- **`CYCLE2_RUNBOOK.md`** (new): env vars, migrate→backend→frontend rollout, rollback, index checks, per-role smoke tests, security posture, known follow-ups.

### What remains (owner, needs a real environment — see runbook)
1. **`CI=true yarn build`** (+ optional bundle/source-map check).
2. **Run `migrate_orgs.py` dry-run → `--confirm` against a copy of production**, then verify indexes on live Mongo.
3. Manual QA per the runbook §5.

---

## Session 29 — 2026-08-05 — Cycle 2 status audit + Phase 13 recruiter job list

Owner asked whether everything is complete. Audited against the plan: **not complete** — see the ledger above (added this session). Then cleared one concrete Phase 13 gap.

### Recruiter job list (Phase 13)
- **`routes_jobs.list_jobs`**: for a recruiter, attaches their active assignment's **`my_deadline`** + **`my_targets`** to each job card (managers get neither — they see all org jobs). One extra query, keyed in memory.
- **`pages/Jobs.jsx`**: role-aware — the **Create New Job** button and per-card **pause/reactivate** show for managers only; recruiter cards show **deadline + target** chips; recruiter empty state reads "No roles assigned yet" (not "create a job"); subtitle adapts. Removed a **pre-existing unused `MoreVertical` import** (would fail `CI=true`).
- Tests: `test_org_isolation.py` **+2** (recruiter card carries deadline/targets; manager card has none). **296 offline tests pass forwards AND reverse** (294 → 296).

### Honest status
- Frontend not built here (static-checked only). Backend offline-tested. The ledger above is now the single source of truth for what remains (Phases 11 leftovers, 12 leftovers, 13 finish, 14b, 15).

### Owner action items
1. **Run `CI=true yarn build`** (covers Sessions 22/24/26/27/28/29).
2. Decide priority for the remaining work: I'd suggest **14b (manager reports)** and **15 (hardening + runbook)** next, since those are the largest gaps and 15 gates a safe production rollout.

---

## Session 28 — 2026-08-05 — Cycle 2: enforce candidate permission flags (backend) + gate candidate/board UI

**Security gap found & fixed:** `can_upload_candidates`, `can_move_stage` and `can_reject_candidates` were defined and shown in the assign drawer but **not enforced on the write endpoints** — a recruiter without them could still upload / move / reject via the API. The mandate is "every permission toggle has a backend check + test," so this was a real hole, now closed.

### Backend (offline-tested — the real enforcement)
- **`routes_candidates.py`**:
  - `upload_resumes` → `require_permission(can_upload_candidates)` (403 before any file is read).
  - `update_stage` → requires `can_reject_candidates` when the target stage is **Rejected**, else `can_move_stage`.
  - `bulk_update_stage` → same per-job check; candidates on jobs the caller can't move are **skipped** (the batch doesn't fail wholesale).
  - `get_candidate` now returns `effective_permissions` + `access_scope` so the UI can gate controls.
- Tests: `test_org_isolation.py` **+5** — upload/move/reject denied without the flag (403), move allowed with it, and `get_candidate` exposes effective_permissions. **294 offline tests pass forwards AND reverse** (289 → 294).

### Frontend (⚠️ not built here) — reflect the flags everywhere candidates are actioned
- **`CandidateDetail.jsx`**: stage buttons (Select/Schedule/On Hold gated on `can_move_stage`, Reject on `can_reject_candidates`), the "move to other stage" select, all **AI Actions** + the "Formatted view" (an AI call) gated on `can_use_ai` — each disabled with a tooltip + an explanatory line, instead of a 403 after clicking.
- **`CandidateBoard.jsx`**: drag-to-move disabled when `!can_move_stage` (cards non-draggable, view-only banner); the slide-in panel's move buttons (Reject vs move) and AI buttons gated the same way.

Backend remains the real gate; the UI gating is UX so recruiters see *why* a control is unavailable.

### What was NOT verified (honesty)
- **No `CI=true yarn build`** here — static checks only (all new symbols referenced; no unused imports).
- Gating reads `job/candidate.effective_permissions` from the API; a manager (all-true) and legacy responses (undefined → allowed) are never locked out.

### Owner action items
1. **Run `CI=true yarn build`** (covers Sessions 22/24/26/27/28) and paste any errors.
2. QA: a recruiter without move/reject/upload/AI sees those controls disabled with a tooltip on the candidate page AND the Kanban board, and the API refuses them (403) if bypassed.

---

## Session 27 — 2026-08-05 — Cycle 2 frontend: permission-gated controls + team-report view

Continuing "finish the pending frontend" (owner confirmed the deployed app builds). Two pieces, both frontend-only (no backend change; 289 offline backend tests unchanged).

### Phase 13 — permission-aware controls on the job page (`pages/JobDetail.jsx`)
Drives off `job.effective_permissions` (already returned by `GET /jobs/{id}`; managers get all-true, undefined defaults to allowed so legacy responses never lock anyone out). A recruiter now sees a control **disabled with a reason** instead of clicking and getting a 403:
- **Upload zone** — disabled + "Adding candidates isn't enabled for you / Ask your admin" when `!can_upload_candidates`.
- **Analyze All (AI)** — disabled with tooltip when `!can_use_ai`.
- **Bulk move stage** — disabled with tooltip when `!can_move_stage`.
Backend enforcement is unchanged and remains the real gate; this is UX, not security.

### Phase 14 frontend — manager team report (`components/TeamReport.jsx` + `pages/Reports.jsx`)
- **`TeamReport.jsx`** (NEW): consumes `GET /reports/team` and renders **insights**, **team throughput** table (sourced/shortlisted/interviewed/hired + rates, "—" below the 5-sample floor), **target attainment** (ProgressBar per set target with met/on_track/at_risk/missed pill), **deadline health** (overdue-first, red overdue pills), and **workload balance**. Own loading / failed ("server problem, not you") / empty ("no teammates yet") states.
- **`Reports.jsx`**: managers get an **Overview | Team** toggle in the Topbar (recruiters never see it); the Team view short-circuits before the personal-overview early-returns, so it works even if the manager has no jobs of their own. `reportsApi.team()` added.

### What was NOT verified (honesty)
- **No `CI=true yarn build`** here (no Node) — static checks only (no unused imports / dangling refs in the edited files; confirmed each new symbol is referenced).
- TeamReport uses tables + ProgressBar rather than recharts for the first cut (lower risk, same tokens) — a charted version can follow if wanted.
- Per-candidate AI/stage controls on **CandidateDetail/Board** are not yet permission-gated (only the job-page controls are) — follow-on.

### Owner action items
1. **Run `CI=true yarn build`** (covers Sessions 22/24/26/27) and paste any errors.
2. QA: a recruiter lacking a permission sees the control disabled with a tooltip (not a 403); a manager opens **Reports → Team** and sees per-recruiter throughput/targets/deadlines/workload.

---

## Session 26 — 2026-08-05 — Cycle 2 fix: recruiter first-login (email-first sign-in + create-password)

**Owner-reported gap:** an admin-approved teammate had no way to set a password from the **login** page — my Phase 10b design quietly assumed they'd use `/signup`. Required industry-standard flow: on login, enter email → if approved-but-new, a **"create your password"** screen; if not recognised, a **professional "ask your admin / sign up"** message; otherwise the normal password prompt.

### Backend (offline-tested)
- **`POST /auth/onboarding-status`** (public) → `{status}`:
  - `needs_setup` — user exists, admin-approved, **no credentials yet** (no `firebase_uid`/`password_hash`).
  - `registered` — has credentials → ask for password.
  - `not_approved` — no such account (or suspended → kept neutral).
  Returns only a coarse status (no name/org). Revealing "set a password" vs "unknown" is the intended, owner-requested behaviour of admin-approved onboarding.
- **`models.py`** `OnboardingCheck`.
- Tests: `test_org_and_auth.py` +4 (not_approved / needs_setup / registered / disabled-is-neutral). **289 offline tests pass forwards AND reverse** (285 → 289).

### Frontend (⚠️ NOT built here — no Node)
- **`pages/Login.jsx`** rewritten as an **email-first, 3-state** flow: `email` → (`onboarding-status`) → `create` (new password + confirm + strength meter → `firebaseCreateAccount` → `/auth/firebase` → straight into the app) or `password` (normal sign-in; legacy-password + Session-15 "server failure ≠ wrong password" rules preserved). A "← email" affordance changes the address. `not_approved` shows the professional message only after a real sign-in miss; a mid-flow `email-already-in-use` on create falls back to signing in.
- **`lib/firebase.js`** `firebaseCreateAccount(email, password)` — creates the account and returns a fresh ID token (no verification email; approved recruiters skip it), leaving them signed in for immediate exchange.
- **`api.js`** `authApi.onboardingStatus`.
- Checked: no unused imports / dangling refs in the edited files.

### What was NOT verified (honesty)
- **No `CI=true yarn build`** and no runtime click-through of the new login flow — the main gap. Static checks only.
- Backend onboarding-status has **no rate limit** yet — it's an email-existence oracle by design; add throttling before heavy exposure (Phase 15 hardening).

### Owner action items
1. **Run `CI=true yarn build`** (now covers Sessions 22, 24, 26) and paste any errors.
2. QA the flow: approved email → login → **Set your password** → lands in app as a User; unknown email → login → professional "ask your admin / Sign up" message; existing user → normal password sign-in; new manager still uses **Sign up** (verify email) then signs in.

---

## Session 25 — 2026-08-05 — Cycle 2 Phase 14a (backend): manager team-report API

**Why this, not Phase 13:** three frontend batches are already stacked awaiting an owner build; adding a fourth (Phase 13 is almost entirely recruiter-UX frontend) would pile on unverifiable code. Phase 14's *backend* is independent and fully offline-testable, so it was pulled forward. Phase 13 + the Phase 14 charts will be built together once the build loop is available.

### What was built (backend only — fully offline-tested)
- **`team_reports.py`** (NEW — pure, no DB/network): the per-recruiter manager panels, with the KPI formulas written into the code and the Cycle-1 honesty discipline (rates withheld below a 5-item sample; a null target hides its panel, never shows 0):
  - `throughput_by_recruiter` — sourced / shortlisted / interviewed / hired per recruiter, using **furthest-stage-reached** (a now-Rejected candidate who reached Interview still counts), with shortlist/hire rates gated on sample ≥ 5.
  - `target_attainment` — actual-vs-target per assignment for each **set** target, with a **burn-down status** (met / on_track / at_risk / missed / no_deadline) comparing pace-achieved to pace-required against the deadline (§8.3).
  - `deadline_health` — assignments with a deadline, most-overdue first, no-deadline excluded.
  - `workload_balance` — open assignments + live candidate load per recruiter (idle recruiters shown, hired/rejected excluded).
  - `insights` — deterministic rule-based lines (overdue, at-risk, hires, idle recruiters).
- **`routes_reports.py`** — `GET /reports/team` (manager-only, org-scoped): fetches org recruiters / active assignments / candidates / transitions, runs the pure panels, enriches rows with member names + job titles, returns `{throughput, target_attainment, deadline_health, workload, insights, totals}`. The existing `GET /reports` (role-scoped personal/org report) is unchanged.

### Tests (offline; forwards AND reverse green)
- **`tests/test_team_reports.py`** (NEW, 18): each metric has the mandated **zero-data / single-item / divide-by-zero / naive-vs-aware-timestamp / candidate-predating-the-field** cases, plus on_track-vs-at_risk burn-down, overdue ordering, and rate-suppression at the sample floor.
- **`tests/test_org_isolation.py`** +2: `/reports/team` manager-scoped to its own org, and manager-only (recruiter → 403). Added `users` to that suite's + `test_reports.py`'s DB stubs (routes_reports now imports `users`/`job_assignments`).
- **285 offline tests pass forwards AND reverse** (265 → 285). All changed backend files `py_compile` clean.

### What was NOT verified (honesty)
- **Nothing against real Mongo.** Panels are pure-function + endpoint-reasoned; the aggregation over real transition volumes is untested for performance (N+1 is avoided — one transitions query, then in-memory grouping).
- **Deferred (Phase 14b):** funnel-by-recruiter, time-metrics per recruiter, source-effectiveness-by-recruiter, AI-usage-by-recruiter, `GET /reports/team/export.csv` (stdlib `csv`), `GET /reports/mine` (the current `/reports` already serves a recruiter's own view), and **all recharts frontend**.
- **Frontend Sessions 22 + 24 still unbuilt** — owner `CI=true yarn build` outstanding.

### Owner action items (carried)
1. **Run `CI=true yarn build`** (covers Sessions 22 + 24) and paste any errors.

---

## Session 24 — 2026-08-05 — Cycle 2 Phase 12 (frontend): assign panel + recruiter JD editor

**⚠️ Build status:** No Node here, so `CI=true yarn build` was NOT run. Written to match existing patterns; checked for unused imports / dangling refs. **Owner: run `CI=true yarn build` — this now covers both Session 22 (team UI + login) and this session.**

### What was built (frontend)
- **`components/AssignmentPanel.jsx`** (NEW) — manager-only panel shown in a new **"Team" tab on the job page**. Lists assigned recruiters (avatar, permissions count, deadline/target pills, edit + remove). **Assign modal**: pick a teammate (recruiters from `orgsApi.members`), toggle the **8 permission flags** (recruiter defaults pre-checked), set the 3 **targets** (shortlist/sourced/interview), a **deadline** and a note. Edit re-opens the modal prefilled; remove confirms then revokes. Uses `assignmentsApi.upsert/revoke`.
- **`pages/JobDetail.jsx`** — integrated the assign panel and the **recruiter personal-JD editor**:
  - New **Team tab** (managers only — driven by `job.access_scope === "manager"`).
  - In **JD Preview**, an assigned recruiter sees a **"Team version" / "Your version"** badge. With `can_edit_jd` they get **"Make my own version" / "Edit my version"** (opens a textarea modal → `assignmentsApi.setJdOverride` → reload) and, when personal, **"Reset to team version"** (`clearJdOverride`). The editor explains only they see it and their AI uses it.
  - Drove tab list + permissions off the backend's `access_scope`, `jd_source`, `effective_permissions` (already returned by `GET /jobs/{id}`).
  - Removed a **pre-existing unused `Sparkles` import** that would have failed `CI=true`.

### Design/architecture adherence
Reused `Modal/Card/Button/Avatar/Pill/Skeleton/EmptyState` and existing tokens/`sonner`; new panel is a self-contained component so JobDetail's working candidate/upload logic was untouched except for additive tabs/JD blocks. No new deps. "Admin/User" wording, `manager/recruiter` in code.

### What was NOT verified (honesty)
- **No `CI=true yarn build`** (no Node) and no runtime click-through — the main gap. Checked statically for unused imports (none in the new/edited files) and confirmed every new symbol is referenced.
- **No backend change** this session (265 offline backend tests unchanged from Session 23).
- Frontend has no automated tests in this repo (never has) — manual QA only.

### Owner action items
1. **Run `CI=true yarn build`** (covers Sessions 22 + 24) and paste any errors.
2. QA once built: as a manager, open a job → **Team** tab → assign a recruiter with specific permissions/targets/deadline → edit → remove. As that recruiter (with `can_edit_jd`), open the job → **JD Preview** → make a personal version → confirm AI rank/screening uses it → reset. A recruiter **without** `can_edit_jd` sees no editor; a recruiter never sees the **Team** tab.

---

## Session 23 — 2026-08-05 — Cycle 2 Phase 12 (backend): assignment API + personal JD overrides

**Context:** The permission spine + enforcement across jobs/candidates/AI/reports already exists (Phase 9). What was missing was any way to *create* assignments or a recruiter's personal JD. This session adds that API. (Most of Phase 11's team UI was already delivered in 10b; the remaining Phase 11 bit — remove-with-*reassignment* of an active member — is still deferred and now has the assignment API it needs.)

### What was built (backend only — fully offline-tested)
- **`permissions.py`** — `sanitize_permissions(raw)`: keep only the 8 known flags, coerce to bool, drop anything a client invents. Used when saving an assignment so permissions can never be widened by an unexpected key.
- **`routes_assignments.py`** (NEW) — two routers:
  - `POST /jobs/{id}/assignments` (manager) — **idempotent upsert** on (job, user): merges `DEFAULT_PERMISSIONS` + sanitized flags, stores targets (shortlist/sourced/interview), deadline, note, status; writes a `job_assigned` activity event. Guards: job in org (404), member in org (404), can't assign an Admin (400), can't assign a disabled member (400).
  - `GET /jobs/{id}/assignments` (manager) — active/paused assignments, enriched with each member's name/email/status.
  - `DELETE /jobs/{id}/assignments/{userId}` (manager) — soft-revoke (`status=revoked`) so the recruiter loses access via the existing spine; drops their personal JD override for that job (candidates they sourced are preserved, §4.3). 404 if none.
  - `GET /assignments/mine` (recruiter) — their active assignments with job basics + permissions/targets/deadline; empty for a manager.
  - `PUT /jobs/{id}/jd-override` (recruiter, **needs `can_edit_jd`**) — upserts `job_jd_overrides`; 403 without the flag, 400 if a manager tries (admins edit the shared JD directly), 404 cross-org. `DELETE` reverts to the org JD.
- **`server.py`** — registered both routers (before `routes_jobs`; paths are distinct so no shadowing).
- **`models.py`** — `AssignmentUpsert`, `JDOverrideUpdate`.
- **`frontend/src/api.js`** — `assignmentsApi` (listForJob, upsert, revoke, mine, setJdOverride, clearJdOverride). Client stubs only; no UI yet.

### Tests (offline; forwards AND reverse green)
- **`tests/test_assignments.py`** (NEW, 16): create-with-merged-perms (+ unknown-flag dropped), idempotent upsert, cross-org job 404, unknown/manager/disabled member guards, list enrichment, revoke (status + override drop) + 404, `mine` for recruiter vs empty-for-manager, JD override needs-permission 403 / saves-personal / manager-400 / cross-org-404 / clear-reverts.
- **`tests/test_permissions.py`** +1: `sanitize_permissions`.
- **265 offline tests pass forwards AND reverse** (248 → 265). All changed backend files `py_compile` clean.

### What was NOT verified (honesty)
- **Nothing against real Mongo.** Upsert/permission-merge/override logic is unit + stub-route tested only. The `(job_id,user_id)` unique index and the soft-revoke→re-upsert reactivation path are unexercised live.
- **No frontend UI** for assignments yet — only the `assignmentsApi` client methods were added (untested, but trivial axios wrappers). The assign drawer (permission toggles, targets, deadline, bulk assign) and the recruiter's JD-override editor are Phase 12 frontend.
- **Phase 10b frontend remains unbuilt here** — still needs the owner's `CI=true yarn build`.

### Owner action items (carried)
1. Still pending: `CI=true yarn build` for the Session 22 frontend (team UI + login), report errors.

---

## Session 22 — 2026-08-05 — Cycle 2 Phase 10b: team-management UI + recruiter first-login (frontend)

**⚠️ Build status:** This environment has **no Node/npm/yarn**, so `CI=true yarn build` could **not** be run. Code was written to match existing patterns exactly and reviewed for unused-import / dangling-reference issues (CRA fails the build on warnings under `CI=true`), but it is **unverified by a real build**. **Owner action: run `CI=true yarn build` and report any errors** — I'll fix them. Owner chose this path explicitly.

### The problem this fixes
The approved-email backend (Session 21) let admins approve recruiter emails, but the **frontend blocked them from ever signing in**: `firebaseSignIn` enforced email verification on the client (unverified → signs out, returns `idToken: null`) and `Login.jsx` bailed before calling the backend. An approved recruiter (who just set a password, so `emailVerified=false`) could never reach `firebase_exchange` to be activated.

### What changed (frontend)
- **`lib/firebase.js`** — added **`firebaseSignInRaw`** (signs in and returns the ID token *regardless* of email-verified, so the **backend** decides) and **`firebaseResendAndSignOut`** (resend link + clear session for the unverified-manager case). The verification-enforcing `firebaseSignIn` is kept for the signup "resend" button.
- **`pages/Login.jsx`** — now uses `firebaseSignInRaw` and **always exchanges with the backend**. Approved recruiters (unverified) get a session and land in the app; a public manager sign-up still gets `{verified:false}` → resend link + "verify your email" message. Legacy-password fallback and the Session-15 "server failure ≠ wrong password" rule preserved.
- **`pages/Signup.jsx`** — softened the verify-screen copy: "If your admin already added you to a team, you can sign in now — no verification needed." (No logic change.)
- **`api.js`** — added `orgsApi` (me, members, addMember, addMembersBulk, setMemberStatus, removeMember).
- **`pages/Team.jsx`** (NEW) — manager-only team page: seat counter (`used / limit`), **Add-user modal** with "One at a time" (email + optional name) and "Paste a list" (bulk textarea → shows added/skipped-with-reasons summary), members table (Member, Role=Admin/User, Status=Active/Pending sign-in/Suspended, Jobs, Candidates, Last active), row actions (suspend/reactivate active/suspended members; remove a not-yet-signed-in approval to free a seat; "You" on own row). Loading skeleton, empty state, and a load-**error** state that says it's a server/connection problem, not user error.
- **`App.js`** — added lazy `Team` + `/team` route behind a new **`ManagerRoute`** (org_role `manager`; recruiters/direct-URL → `/dashboard`). Distinct from `AdminRoute` (platform-admin panel).
- **`components/Layout.jsx`** — added a **manager-only "Team"** sidebar link under Hiring.

### Design/architecture adherence
Frozen design system respected: reused `Button/Card/Modal/Avatar/Pill/EmptyState/Skeleton/Topbar/PageBody`, indigo/navy tokens, `sonner` toasts, `fmtDate`. No new deps, no new colours. "Admin"/"User" in copy, `manager`/`recruiter` in code. Lazy-loaded like every other post-dashboard page.

### What was NOT verified (honesty)
- **No `CI=true yarn build` run** (no Node here) — the single most important gap. Also no runtime click-through.
- **No backend change** this session → backend suite unchanged (248 offline, still green from Session 21).
- Recruiter journey depends on Firebase being configured in the live env; the legacy-password path only covers pre-Firebase/demo accounts (e.g. seeded Nadia/Tom, who sign in and correctly land as Users).
- Frontend has **no automated tests** in this repo (never has); this UI is covered by manual QA only.

### Owner action items
1. **Run `CI=true yarn build`** in `frontend/` and paste any errors.
2. Manual QA once built: admin → Team → add one email + bulk paste; approved user signs up then signs in (should land in app as a User, no verification wall); suspend/reactivate/remove; recruiter must NOT see the Team link or `/team`.
3. Ensure Firebase is configured on the frontend env (it already is in prod) so recruiters can create passwords.

---

## Session 21 — 2026-08-04 — Cycle 2 Phase 10a REWORK: approved-email onboarding (no invite emails)

**Owner decision (supersedes Session 20's emailed-invite flow):** This release must NOT send invitation emails or use SMTP/tokens for onboarding. Instead an admin ("Manager") **stores approved recruiter emails** (typed one at a time or pasted/bulk-uploaded); only those emails may join the org, and each recruiter **sets their own password the first time they sign in**, then can change it via the normal reset. The emailed-token machinery is to be **kept dormant in code** for a future cycle (where admins purchase plans and formal invites return). Also required: **role is sticky** — an admin always signs in as admin, an approved user always as a recruiter.

### What changed vs Session 20
- **`routes_orgs.py` — rewritten** around approved emails, no tokens/email:
  - `POST /orgs/members` — approve one email (seat + duplicate guards); creates a recruiter placeholder `status="approved"`, `password_hash=None` (they set it themselves).
  - `POST /orgs/members/bulk` — approve many: server splits a typed/pasted/CSV blob on commas/semicolons/whitespace/newlines, validates + de-dupes, adds up to the remaining seats, and **returns every skipped entry with a reason** (invalid / already on team / already registered / seat limit reached).
  - `GET /orgs/members`, `PATCH /orgs/members/{id}` (suspend/reactivate — self + last-admin + cross-org guards), **`DELETE /orgs/members/{id}`** (remove an approved-but-not-activated email to free a seat; 409 for an already-active member — reassignment removal is a later update), `GET /orgs/me`.
  - **Removed**: `create_invite`/`resend`/`revoke`/public `GET /invites/{token}` (token + email).
- **`routes_auth.py`** — **removed `POST /auth/accept-invite`** and its throttle/messages. `firebase_exchange` now **activates an approved recruiter on first sign-in**: finds the `status in (approved, invited)` placeholder → sets `status="active"`, keeps their `org_id` + `org_role="recruiter"` (role stays sticky), and **bypasses email verification for them only** (the admin already vouched). A brand-new, unapproved email still becomes its own **manager** via public sign-up (unchanged), so admins always land as admin and approved users always as recruiter.
- **`server.py`** — dropped the public `/invites` router registration.
- **`email_service.py`** — removed the now-dead `build_invite_email`.
- **`models.py`** — `InviteCreate`/`AcceptInviteRequest` → **`MemberCreate`** + **`BulkMemberCreate`**; kept `MemberStatusUpdate`.
- **Kept dormant (reserved for a future cycle, documented in-file):** `invites.py` (token/hash/state helpers) and the `invitations` collection + its indexes. `auth.get_current_user` suspension gate (401 on `status="disabled"`) is unchanged and stays.

### Tests (offline; forwards AND reverse green)
- **`tests/test_org_and_auth.py` — rewritten (22)**: add-member happy/duplicate/existing/seat-limit, bulk parse+skip-reasons+seat cap, list/remove (approved frees seat, active→409, cross-org→404), suspend/self/last-admin/cross-org, `org_me` seats, **`firebase_exchange`**: approved recruiter activates (verified even if email unverified, joins admin's org, sticky recruiter role) / new unapproved email → own manager / unverified public manager → no session / suspended → 403, and the real `get_current_user` suspension gate.
- **`tests/test_invites.py` (12) kept** — the dormant token helpers still have full unit coverage so the future cycle inherits a tested base.
- **248 offline tests pass forwards AND reverse.** All changed files `py_compile` clean.

### What was NOT verified (honesty)
- **Nothing run against Mongo or real Firebase.** Approval/seat/activation logic is unit + stub-route tested only.
- **Trust simplification (intended for this pre-plan release):** approving an email lets whoever first signs in with that email (via Firebase) claim the recruiter seat, and their sign-in is accepted without a separate email-verification step. This is acceptable now because the admin explicitly vouches for the address; a stricter proof-of-ownership step is a future-cycle item (tracked with the dormant invite tokens).
- **No frontend** this session → no `yarn build`. Phase 10b wires the Add-user/bulk-upload UI, the team list with seats/suspend/remove, and the recruiter first-login (Firebase create-password) screen. Until then, approvals are API-only.
- Member **remove-with-reassignment** for *active* members stays deferred to Phase 11.

### Owner action items (updated)
- **`APP_URL` is no longer required** for onboarding (invite links are gone). Keep it only if you want it for other links; onboarding no longer 503s without it.
- **SMTP is not needed** for onboarding anymore. (Still used for the feedback email path.)
- Recruiters sign in through the same Firebase flow as admins; the frontend needs a "set your password" (first sign-in) path for approved users — Phase 10b.

---

## Session 20 — 2026-08-04 — Cycle 2 Phase 10a: invitation & first-login auth (backend)

**Scope split:** Phase 10 bundles backend auth + the `/accept-invite` page. The frontend can't be built here (no Node/npm locally), so this session did the **backend** (10a); the React page + `/team` invite hooks are **10b**. Backend-before-frontend, as the plan directs.

### What was built
- **`invites.py`** (NEW — pure core): 32-byte URL-safe token, **sha256-only storage** (`generate_token`/`hash_token`), `invite_reason` (valid/expired/revoked/accepted/unknown, with accepted>expired precedence), `expiry_from` (+7d), and rate-limit predicate/constants (`INVITES_PER_HOUR=20`, `ACCEPT_ATTEMPTS_PER_HOUR=10`). No FastAPI/Mongo — fully unit-tested.
- **`routes_orgs.py`** (NEW): manager router `/orgs` + public `/invites`.
  - `POST /orgs/invites` — seat-limit + rate-limit + duplicate-email guards; creates an `invited` placeholder member (reserves a seat) + a `pending` invitation; emails the link; returns `accept_url` **once** for the copy-link fallback + `email_sent`. Compensating delete if the invitation insert fails.
  - `GET /orgs/invites` (pending), `POST /orgs/invites/{id}/resend` (**rotates the token** so old links die; rate-limited), `DELETE /orgs/invites/{id}` (revoke + free the seat; 409 if already accepted).
  - `GET /orgs/members`, `PATCH /orgs/members/{id}` (suspend/reactivate; can't suspend self; org must keep ≥1 active admin; cross-org→404), `GET /orgs/me` (org name, plan, seats used/limit, my role).
  - `GET /invites/{token}` (public) — neutral validate: only a genuinely valid token returns the invitee's own email + org name; anything else is `{valid:false, reason}` with no PII.
- **`routes_auth.py`** — `POST /auth/accept-invite`: validates token state → per-token accept-attempt throttle → verifies Firebase token → **asserts token email == invite email** → activates the member (`firebase_uid`, `status=active`, `activated_at`) → marks invite accepted → mints the app JWT. **Email verification is bypassed only on this path** (holding the emailed token is the proof), never as a global flag.
- **`auth.py`** — `get_current_user` now rejects `status="disabled"` with **401 "Your access has been suspended."** on *every* request, so a suspend takes effect on the live session, not just at next login.
- **`email_service.py`** — `build_invite_email` (plain-text, single CTA + copy-paste fallback line). Uses the existing SMTP-optional `send_email` (returns False, never raises, when SMTP is unset).
- **`models.py`** — `InviteCreate`, `AcceptInviteRequest`, `MemberStatusUpdate`.
- **`server.py`** — registered `routes_orgs.router` + `routes_orgs.public_router`.

### Tests (all offline; forwards AND reverse green)
- **`tests/test_invites.py`** (12): token uniqueness/hash/expiry, every `invite_reason` state incl. precedence, rate-limit boundary.
- **`tests/test_org_and_auth.py`** (26): create/list/resend/revoke, seat limit, duplicate/other-org guards, APP_URL-missing 503, public validate (valid/expired-neutral/unknown), accept happy path + wrong-email/expired-410/already-accepted-409/firebase-503/bad-token-401, suspend member + can't-suspend-self + last-admin guard + cross-org 404, `org_me` seats, and the **real** `get_current_user` suspension gate (401 suspended / 403 platform-deactivated / active passes). Imports the real `auth` against stubbed `jwt`/`bcrypt`.
- Fixed two offline `_APIRouter` stubs to add `.patch` (routes_orgs uses PATCH) so cross-module import order stays green.
- **252 offline tests pass forwards AND reverse** (214 → 252). All changed files `py_compile` clean.

### What was NOT verified (honesty)
- **Nothing run against Mongo, real Firebase, or SMTP.** Token/seat/accept logic is unit + stub-route tested only. The unique partial index on `(org_id,email)` pending invites, the compensating-delete race path, and real email delivery are **unexercised live** — dry-run + a real invite must be exercised in the Phase 15 runbook.
- **No frontend** this session → no `yarn build`. `/accept-invite`, the Add-user modal, invite/seat UI, and suspend/reactivate controls are **Phase 10b/11**. Until then invites can be created via API but there's no page to accept them in the product.
- Member **remove-with-reassignment** (DELETE `/orgs/members/{id}`) is deliberately deferred to Phase 11 (needs the reassignment UI); only suspend/reactivate ships now.

### Owner action items
- **New backend env var `APP_URL`** (e.g. `https://hireflow.cortinix.com`) is now **required to send invites** — `POST /orgs/invites` returns a 503 with that message until it's set. Add it before Phase 10b ships.
- SMTP must be configured for invite emails to actually send; without it invites still create and the manager gets a **Copy invite link** value (`accept_url`) to share manually.

### Backlog / Not in scope (logged)
- `/login` returns 403 "deactivated" while `get_current_user` returns 401 "suspended" for a disabled user — both block; unify copy in a later cleanup.
- (Carried) `is_active` int vs `status` string coexist (C3); pre-Cycle-2 `stage_transitions` rows have no `actor_id`; `_get_owned_candidate` legacy name in routes_ai.

---

## Session 19 — 2026-08-04 — Cycle 2 Phase 9b: org+assignment scoping across every route

**Goal:** replace the last `user_id`-scoped reads with the org+assignment spine so cross-org data is unreachable. Backend-only; no frontend change (org UI is Phases 11/13).

### What changed (all through `permissions.py`, backend before frontend)
- **`routes_jobs.py`** — `list_jobs` → `require_org_member` + `accessible_job_ids` (manager = all org jobs, recruiter = active assignments only). `create_job` → `require_manager` (recruiters can't create; personal jobs are Cycle 3). `get_job`/`update_job`/`delete_job`/`activity` → `resolve_job_access`; edit/delete manager-only (403 for recruiter); delete cascades `job_assignments` + `job_jd_overrides`. `get_job` returns `effective_permissions`/`jd_source`/`access_scope`.
- **`routes_candidates.py`** — upload/list/detail/stage/note/delete/bulk all go through `resolve_job_access` / `resolve_candidate_access` + `candidate_scope_filter` (recruiter without `can_view_team_candidates` sees only their `sourced_by` rows). Uploads stamp `org_id`/`sourced_by`/`assignment_id` and write `activity_events`; stage moves log actor + event. `bulk-stage` org-scopes first, then resolves access once per job (cached) and drops rows the caller can't see.
- **`routes_ai.py`** — `rank` + all candidate AI tools (`questions`/`email`/`summary`/`structure`/`compare`) go through `resolve_job_access`/`resolve_candidate_access`, use `resolve_jd` (so a recruiter's **personal JD override** drives their AI), enforce **`can_use_ai`**, and stamp `org_id` on usage. `analyzed_jd_source` recorded on each rank so results stay explainable. `compare` now rejects cross-job pairs. `pipeline-health` org/role-scoped.
- **`routes_dashboard.py`** & **`routes_reports.py`** — role-scoped: manager → whole org; recruiter → assigned jobs + their sourced candidates (empty-state short-circuit when a recruiter has no assignments). Reports analytics stayed pure functions — only the two feeder queries changed.
- **`ai_service.py`** — `log_usage` gained `org_id` (C6): AI spend is now attributable per org.

### Enforcement invariant (now true)
Every job/candidate/AI/report route fetches by id **only** through `resolve_job_access` / `resolve_candidate_access`. Cross-org and no-assignment reads return **404** (never confirm another org's data). `routes_admin.py` (platform-admin, purple) is deliberately untouched.

### Tests
- **`tests/test_org_isolation.py`** (NEW, 14): route-level proofs that the routes actually call the spine — cross-org `get_job`/`get_candidate`/`rank` → 404; recruiter can't see another recruiter's candidate (404) or create a job (403); `can_use_ai=False` → 403 with a human message; dashboard/reports scoped to own org, recruiter-without-assignment empty. Offline stub-merge; imports the **real** `ai_service`/`resume_parser` (patches only the network fns) so it never shadows other suites.
- Fixed two pre-existing offline stubs broken by 9b's new imports: `test_permissions.py` (permissions now imports `candidates`) and `test_reports.py` (routes_reports now imports `permissions`, needs `job_assignments`/`job_jd_overrides` + a real `HTTPException` class in its `fastapi` stub).
- **214 offline tests pass forwards AND reverse** (200 → 214). All changed files `py_compile` clean.

### What was NOT verified (honesty)
- **Nothing run against a real DB or live server.** Enforcement is proven by unit + route-level stub tests, not integration. The two live-server suites (`backend_test.py`, `test_admin_reports.py`) still require a running backend and are excluded from the offline run.
- No frontend touched → no `yarn build` this session. The frontend still ignores `org_role`/`effective_permissions`/`access_scope`; wiring the recruiter UI + permission gates is Phases 11/13.
- Dashboard/reports apply the recruiter `sourced_by` filter uniformly (conservative — never over-shows). A recruiter holding `can_view_team_candidates` on a job still sees only their own in the aggregate dashboard; per-job candidate lists honour the flag correctly. Acceptable for Cycle 2; revisit if team-level recruiter dashboards are wanted.

### Backlog / Not in scope (logged)
- `_get_owned_candidate` in `routes_ai.py` kept its name but now returns `(cand, access, jd)` — fine, but the name is legacy; rename in a later cleanup.
- (Carried) `is_active` int vs `status` string coexist (C3); pre-Cycle-2 `stage_transitions` rows have no `actor_id`.

---

## Session 18 — 2026-08-04 — Cycle 2 Phase 9a: org data model, permissions, migration, seed

**Decisions confirmed by owner:** skip JWT changes (C1); standardize cross-org on **404** (C2); **jobs are assignment-only, manager-created — personal jobs deferred to Cycle 3** (removes the "own + assigned" union complexity).

**Goal:** additive org foundation with no change to existing route scoping yet. (Phase 9 is split 9a/9b as flagged in CYCLE2_AUDIT.md §7; this is 9a.)

### What was built
- **`database.py`** — new collections (`organizations`, `invitations`, `job_assignments`, `job_jd_overrides`, `activity_events`) + all §3.3 indexes, including the partial-unique index for one *pending* invite per `(org, email)`. All additive; `create_index` is idempotent.
- **`permissions.py`** (NEW — the enforcement spine): `require_org_member`, `require_manager`, `resolve_job_access` (manager → any org job full perms; recruiter → only via an active assignment; cross-org/no-access → **404**), `require_permission` (403 + human message, never a flag name), `resolve_jd` (personal override for the assigned recruiter, org JD for everyone else incl. manager). `DEFAULT_PERMISSIONS`/`MANAGER_PERMISSIONS`.
- **`routes_auth.py`** — `firebase_exchange` and the legacy signup/login now **create an org on first manager login** (compensating delete on partial failure; never half-creates); org-less accounts **self-heal** into manager+org on next login; `_public_user` exposes `org_id`/`org_role`/`status` (no JWT change — `get_current_user` reads the live doc). Login/exchange also reject `status="disabled"`.
- **`scripts/migrate_orgs.py`** (NEW) — idempotent, dry-run-by-default migration: each existing user → own org (manager), backfills `org_id` on their jobs/candidates/transitions/feedback; `--rollback` undoes it. Modelled on `reset_accounts.py`.
- **`seed.py`** (rewritten) — one demo org **Meridian Group** (manager Sarah + recruiters **Nadia**, **Tom**) with the 3 occupation-diverse jobs assigned across the recruiters (targets/deadlines/permissions; Tom has `can_edit_jd` to demo overrides), candidates stamped `sourced_by`, plus `activity_events`. Alex Admin keeps their own org (HireFlow Inc) + platform-admin allowlist.

### Tests
- **`tests/test_permissions.py`** (14 new): manager full access, cross-org 404, missing/no-org 404, recruiter assigned/unassigned/revoked, permission-merge, 403 human message, personal-JD resolution.
- **200 tests pass forwards AND in reverse** (186 baseline + 14). No isolation regression.
- Backend files `py_compile` clean.

### What was NOT verified (honesty)
- **Nothing executed against a real DB.** The migration and org-creation-on-login logic are unit-reasoned/stub-tested only. `migrate_orgs.py` and the new `seed.py` have **not** been run against Mongo — **must be dry-run against a copy before production** (runbook item, Phase 15). The partial-unique invitation index and the compensating-delete path are unexercised live.
- No frontend change in 9a → no rebuild run (frontend still branches only on platform `role`; org UI lands in Phases 11/13). The `org_role` field is now available on the user object for that.
- Existing routes still scope by `user_id` — **9b** replaces that with org+assignment scoping (the actual isolation work). Until 9b, no cross-org enforcement is active on jobs/candidates/AI/reports.

### Owner action items
- None yet. `APP_URL` env var arrives in Phase 10. Migration command + deploy order will be in the Phase 15 runbook; **do not run `migrate_orgs.py` in production until the full cycle is deployed** (it's forward-compatible but pair it with the code that uses org fields).

### Backlog / Not in scope (logged)
- `users.is_active` (int) vs `status` (string) still coexist (C3) — gated on both; unify in a later cleanup.
- `stage_transitions.moved_by` historical rows are names only (no `actor_id`) — per-recruiter attribution of pre-Cycle-2 history is limited.

---

## Session 17 — 2026-08-04 — Cycle 2 Phase 8: re-audit & design lock (read-only)

**Goal:** ground-truth the code before building org/manager/recruiter features; reconcile it against `PROJECT_PLAN_CYCLE2.md`; produce `CYCLE2_AUDIT.md`. **No source file changed** (docs only).

### What I read
Cycle 2 plan, `PROGRESS.md`, `PROJECT_PLAN.md`, `AUDIT.md`, then the actual code: `server.py`, `auth.py`, `database.py`, `admin_identity.py`, `firebase_auth.py`, `routes_auth/jobs/candidates/ai/dashboard/reports/feedback.py`, `models.py`, `seed.py`, `scripts/reset_accounts.py`; frontend `App.js`, `api.js`, `constants.js`, `AuthContext.jsx`, `Layout.jsx`, `lib/firebase.js`, `config/sources.js`, `Reports.jsx`, `Signup/Login/ForgotPassword`.

### Deliverable
**`CYCLE2_AUDIT.md`** — auth reality check, data-access inventory (22 `user_id`-scoped queries flagged for org+assignment scoping), frontend inventory (guards, sidebar, reusable primitives, exact `Reports.jsx` data contract), migration plan, plan-vs-code conflicts, §12 decision answers, revised file-level phase breakdown 9–15.

### Key findings (design decisions to confirm before Phase 9)
- **C1 — the JWT does not need `org_id`.** `get_current_user` re-reads the live DB user doc from the token's `userId`, so org fields are available with **no JWT change and no session invalidation**. Recommend **skipping** the planned JWT change; only extend `_public_user`/`/auth/me` with `org_role`/`status` for the frontend. Lower risk than the plan assumes.
- **C2 — standardize cross-access on 404.** Today candidate/AI routes return **403**; jobs return 404. Plan mandates 404 (don't confirm existence). This is a deliberate behaviour change to existing routes.
- **C3 — two "active" flags.** `is_active` (int) vs planned `status` (string). Gate on both; migration sets `status="active"`; suspension sets `status="disabled"`. Don't repurpose `is_active`.
- **C4–C7** — `stage_transitions.moved_by` is a name not an id (add `actor_id`); `activity_events` overlaps `stage_transitions` (use each for its own KPIs); `ai_usage_log` needs `org_id` stamping; `firebase_exchange` must create an org on first manager login.
- Roles are already cleanly separated: platform `role` (admin/hr, allowlist-derived, gates `/admin/*`) vs new `org_role` (manager/recruiter). No collision if new code never overloads `role`.
- `Reports.jsx` analytics are already pure functions on plain dicts → reusable for per-recruiter team reports with no new charts.

### §12 decisions — my answers
1 seat 25 ✅ · 2 recruiter own jobs ⚠️ confirm (biggest complexity lever; offered to defer to Cycle 3) · 3 promote-to-manager ✅ (+≥1-active-manager invariant) · 4 suspend default ✅ · 5 `APP_URL` ✅ mandatory · 6 copy-link fallback ✅ · 7 manager sees candidate data ✅.

### Not verified
Read-only phase — nothing executed. Migration/org-creation transaction behaviour reasoned about only; must be dry-run against a DB copy before production (runbook item). No live Mongo/Firebase/SMTP/Groq here.

### Owner action items (before Phase 9)
- Confirm/challenge **C1 (skip JWT change)**, **C2 (404)**, and **decision 2 (personal jobs)** — these change scope.
- New env var coming in Phase 10: **`APP_URL`** (invite links).

---

## Session 16 — 2026-08-02 — CORS: verified user still can't log in

### Symptom / console
`Access to XMLHttpRequest at 'https://hireflow-w04l.onrender.com/api/auth/firebase' from origin 'https://hireflow.cortinix.com' has been blocked by CORS policy: No 'Access-Control-Allow-Origin' header`. Also on `/api/auth/login`. A Firebase `signInWithPassword` 400 appeared on some attempts (a wrong-password/earlier-double-signup attempt — secondary).

### Root cause
The Render backend's `CORS_ORIGINS` did not include the live frontend origin `https://hireflow.cortinix.com` (they moved to a custom domain). Every browser API call — including the token exchange — was blocked, so a verified user with the right password still couldn't finish login. **This also confirms the Session-15 fix worked**: the app now reports the real problem ("trouble reaching the server") instead of a fake "invalid password".

### Fix (permanent, in code — `server.py`)
Key realisation: this API uses **bearer tokens (Authorization header), not cookies**, so credentialed CORS is unnecessary. Therefore:
- `allow_credentials=False` — removes the `*`+credentials trap and makes liberal origins safe (a cross-origin page can't read another origin's stored token).
- **Known production/local origins are baked into the code** (`hireflow.cortinix.com`, the Vercel app, `localhost:3000`) and merged with `CORS_ORIGINS` env — so a frontend domain change can never again silently break every call. The real frontend is allowed **even if the Render env is stale or empty**.
- `CORS_ORIGIN_REGEX` support, defaulting to `*.vercel.app` (preview deploys). Trailing slashes normalised.
- Verified the resolution logic in isolation: cortinix allowed with stale/empty env, vercel previews + localhost allowed, trailing-slash matches, unknown origins still blocked.

### Files changed
- `backend/server.py` — CORS config + middleware.
- `backend/.env.example` — CORS docs.

### Owner action
- **Redeploy the backend (Render).** That alone fixes it — no env change required (the origin is baked in). Optionally set `CORS_ORIGINS`/`CORS_ORIGIN_REGEX` for extra domains.
- If, after the CORS fix, a specific account still shows "email or password isn't correct" (Firebase 400), that account's Firebase password is likely from an earlier confused double-signup — use **Forgot password** to set a known one, or delete + recreate the Firebase user.

### Testing
- `server.py` compiles; CORS logic unit-verified in isolation; 186 backend tests unaffected.
- ⚠️ Not run against the live Render/browser — owner redeploys backend and confirms login.

---

## Session 15 — 2026-08-02 — Auth flow redesign (signup/login) + account reset tool

### Symptoms
1. Signup: "Couldn't create account" shown, **but** the verification email arrived; retrying the same email → "an account with this email already exists".
2. After verifying, login → "invalid email or password" even though Firebase shows the user created + verified.

### Root cause (one architectural flaw, two faces)
Both flows **conflated the Firebase step with the backend token-exchange step and masked backend/network failures as credential errors**:
- **Signup** (`Signup.jsx`): `firebaseSignUp` created the Firebase account + sent the email (success), THEN called `authApi.firebase(...)`. If that backend call failed (CORS / Render cold-start / 502 / transient), the catch showed "Could not create account" — but the Firebase account already existed, so a retry hit Firebase's `email-already-in-use`.
- **Login** (`Login.jsx`): `signInWithEmailAndPassword` succeeded, but if the subsequent `authApi.firebase` exchange failed, the **outer catch's fallback "Invalid email or password"** masked a server problem as a wrong password. The confusing double-signup also left the Firebase password set to the first attempt, compounding it.
- Render free-tier cold starts (~50s / 502 on first hit) made the backend exchange fail intermittently, which is what triggered it in the wild.

### Fix — industry-standard redesign (frontend only, no arch/UI change)
- **Signup now talks ONLY to Firebase.** `firebaseSignUp(name, email, password)` creates the account, sets `displayName` (so the name reaches the backend via the token's `name` claim), sends verification, and signs out. Signup then **always** shows the "verify your email" screen. The app/DB account is created lazily on first verified login. A backend hiccup can no longer report a created account as failed, and there's no retry trap.
- **Login separates the two steps with honest errors:**
  - Firebase auth failure → credential message ("That email or password isn't correct.") / mapped Firebase message.
  - Not verified → the verify message.
  - **Backend exchange failure → "We're having trouble reaching the server right now. Please try again in a moment."** (or the server's own detail) — never "invalid password".
- Optional **company** is stashed in localStorage at signup (`pendingCompanyKey`) and sent on the first login exchange, then cleared — so it survives the Firebase-only signup.
- `firebaseSignIn` keeps the Session-14 `reload()` + `getIdToken(true)` freshness fixes.
- Backend unchanged: `/auth/firebase` already find-or-creates and reads `name`/`company`.

### Account reset tool (owner runs it — NOT run here)
`backend/scripts/reset_accounts.py` — dry-run by default; `--confirm` deletes users, `--confirm --all` also deletes jobs/candidates/etc. **Important:** it only clears MongoDB. **Firebase Auth users are separate** — the "email already exists" is Firebase state, so old test users must also be deleted in the Firebase console (Authentication → Users). If `SEED_ON_STARTUP` is true the demo re-seeds on next start.

### Files changed
- `frontend/src/lib/firebase.js` — `firebaseSignUp` signature + Firebase-only behaviour.
- `frontend/src/pages/Signup.jsx` — Firebase-only signup; stash company; no backend call.
- `frontend/src/pages/Login.jsx` — two-step flow with distinct errors; carry/clear company.
- `frontend/src/constants.js` — `pendingCompanyKey` helper.
- `backend/scripts/reset_accounts.py` — new maintenance tool.

### ForgotPassword (reviewed, no change)
Already industry-standard: Firebase `sendPasswordResetEmail`, anti-enumeration (same confirmation for unknown emails), graceful "not configured" state. Left as-is.

### Testing
- `CI=true yarn build` clean (warnings-as-errors → confirms no unused imports after removing `firebaseSignOut` from Signup); 186 backend tests pass; reset script compiles.
- ⚠️ Not run end-to-end (no Firebase/live backend here). Owner must redeploy the **frontend** and re-test signup → verify → login. Backend unchanged (no redeploy needed for these fixes).

### Owner action items
1. Redeploy the frontend (Vercel).
2. To clear old accounts: run `reset_accounts.py --confirm` AND delete the corresponding users in the Firebase console.
3. Confirm Render `CORS_ORIGINS` includes the Vercel origin and `REACT_APP_BACKEND_URL` points at Render (these govern whether the login exchange can reach the backend at all).

---

## Session 14 — 2026-08-02 — Fix: verified users wrongly told "please verify"

### Symptom
New user signs up → verifies via the Firebase email link → returns and signs in → login incorrectly says "Please verify your email."

### Root cause (Firebase staleness, two points in `firebaseSignIn`)
`frontend/src/lib/firebase.js` `firebaseSignIn` read verification state without refreshing it:
1. **`cred.user.emailVerified` was read straight off `signInWithEmailAndPassword`** with no `reload()`. Right after the verification link is clicked, that property lags the server (stale `false`), so a just-verified user was blocked. **Primary trigger.**
2. **`getIdToken()` (no force-refresh)** could return the token minted at sign-in, whose `email_verified` claim is still `false`. The backend gates on `claims["email_verified"]`, so even if (1) passed it returned `{verified:false}` → same wrong message.

The app's own session is its JWT in AuthContext/localStorage (not Firebase `onAuthStateChanged`), so there was no listener-staleness angle — the bug was exactly these two reads.

### Fix (minimal, frontend-only, correct Firebase practice)
`firebaseSignIn` now:
- `await cred.user.reload()` before checking `emailVerified` (fetches current server state). Wrapped in try/catch → falls back to the un-reloaded value if reload fails.
- `getIdToken(true)` (force refresh) so the backend receives a token with the current `email_verified` claim.

No backend change needed — with a fresh token the existing `claims["email_verified"]` gate returns verified for a verified user.

### Messages improved (Phase 6, jargon-free)
`Login.jsx`:
- Unverified: "Please verify your email to continue. We've sent a new verification link to your inbox — open it, then sign in. **If you've just verified, give it a moment and try again.**"
- Backend-mismatch (now very rare): "Your email verification is still being confirmed. Please wait a moment and try signing in again." (was "Please verify your email first, then sign in.")

### Files changed
- `frontend/src/lib/firebase.js` — `firebaseSignIn`: add `reload()` + `getIdToken(true)`.
- `frontend/src/pages/Login.jsx` — two verification messages.

### Testing performed
- `CI=true yarn build` clean.
- Reasoned through the 4 scenarios (can't run Firebase locally): A verified-then-login now passes via reload(); B verify-then-immediate-login fixed by reload() hitting the server; C existing verified user unaffected (demo/admin still use the legacy fallback path); D genuinely-unverified user still correctly blocked + resent a link.
- ⚠️ Not run end-to-end (no Firebase project/browser here). **Owner must deploy the frontend and confirm the real verify→login journey.**

### Remaining note
Only the frontend needs redeploying (Vercel). Backend unchanged.

---

## Session 11 — 2026-07-25 — Live-testing hardening: remaining 4 items

Completed #1, #3, #4, #5 (2 and 6–9 were done in Session 10). All 9 items done.

| # | Item | Commit summary |
|---|---|---|
| 1 | Marketing placeholders + support email | `hireflow@cortinix.com` from one constant (SUPPORT_EMAIL in constants.js) used in About/Careers/Privacy/Signup/ErrorBoundary. All PlaceholderNote/owner-facing warnings removed incl. the Privacy "legal review" banner. **Fake testimonials emptied** rather than shown as real (fabrication avoided) — pages have honest empty states. |
| 3 | Resume source | Single config `src/config/sources.js` (11 sources w/ icon+colour). Mandatory dropdown at upload (client + server 400). `SourceBadge` on candidate list rows and profile header. Source filter in the list. Legacy values fall back via `sourceMeta()`. |
| 4 | Resume parsing | **Root-caused the email bug**: PDF text-extraction glues adjacent words, greedy regex eats them. Fixed by preferring the exact address from the embedded `mailto:` annotation. New `resume_parser.py`: PDF (text+annotations), DOCX (python-docx), TXT, images (best-effort OCR only if a free stack is present). Extracts + classifies LinkedIn/GitHub/portfolio. Upload accepts PDF/DOCX/DOC/TXT/PNG/JPG/WEBP. 10 parser tests incl. the exact `pedksmayank03`→`dksmayank03` case. |
| 5 | Resume viewer | AI structures the resume into compact JSON **once, cached on first view** (`POST /ai/structure`) — cost-efficient. `ResumeView` renders one consistent, printable layout; Print/Save-PDF via a hidden print-only clone + `@media print`. Raw text kept as fallback. |

### #2 Firebase (Session 10) — owner has since renamed the Render env vars
Owner confirmed the `REACT_APP_FIREBASE_*` rename is done. Once the frontend rebuilds, the silent legacy fallback stops and Firebase + email verification are enforced.

### Verified this session
- **182 offline tests pass** (118 prompts + 31 reports + 23 admin + 10 parser).
- `CI=true yarn build` clean after every commit.
- No `@example.com` / placeholder strings remain in `src`.

### ⚠️ Still not run end-to-end
No browser, backend, Firebase, SMTP or Groq key in this environment, so as before: nothing has been executed live. The AI-dependent paths (resume structuring, email drafting) are unit-tested at the prompt/normalisation level but the actual model calls are unrun.

### Owner to-dos / decisions carried
- **OCR**: left optional (free Tesseract path activates only if the host has it; `pytesseract`/`Pillow` are commented in requirements). No cloud provider wired, per "use a free lib if available, otherwise leave it."
- **`python-docx` added to requirements** — will install on next deploy.
- **Feedback inbox** `connecting800@gmail.com` left as-is (delivery config, not a user-facing support address). Say if it should become `hireflow@cortinix.com`.
- Privacy policy still merits a real legal review even though the on-page owner banner is gone.
- `.doc` (legacy binary Word) is accepted but not text-extractable by python-docx — stores blank text for manual entry.

---

## Session 10 — 2026-07-25 — Live-testing hardening (9-item request)

Owner supplied a 9-item list preparing for live user testing. Status:

| # | Item | Status |
|---|---|---|
| 1 | Remove marketing placeholders; support email → hireflow@cortinix.com | ⬜ TODO (unblocked) |
| 2 | Firebase auth bypass | ✅ DONE |
| 3 | Resume source: mandatory, single config, badges, filter | ⬜ TODO (unblocked) |
| 4 | Resume parsing: email bug, DOCX, links, OCR | ⬜ PARTIAL PLAN — non-OCR doable now; **OCR = cloud API, needs provider + key from owner** |
| 5 | Resume viewer from structured data | ⬜ TODO — approach chosen: **AI structured parse at upload** |
| 6 | JD Original/Enhanced tab bug | ✅ DONE |
| 7 | Candidate name → profile navigation | ✅ DONE |
| 8 | AI email formatting + auto-populate org/sender | ✅ DONE |
| 9 | Auto-scroll to generated AI content | ✅ DONE |

### #6/#7/#8/#9 — commit `<candidate-flow>`
Root causes + fixes in the commit message. Highlights: #6 was JobCreate overwriting `jd_text` with the enhanced text (original lost, Enhanced tab disabled) — now stored alongside as `jd_enhanced`. #8 email prompt now enforces greeting/paragraphs/signature with real org+sender, and the modal is controlled/editable.

### #2 Firebase — commit `<firebase-fix>` — ROOT CAUSE FOUND
**The env vars on Render were named `apiKey`, `authDomain`, `projectId`, … — bare Firebase keys.** CRA only inlines `REACT_APP_*`-prefixed vars, so they were invisible to the build, `isFirebaseConfigured` was false, and signup silently fell back to legacy bcrypt (→ instant dashboard, no Firebase). This is why "the issue existed even after setting the env variables."

Owner delegated the policy choice ("analyse and choose best option"). Chosen: **enforce Firebase + verified email**, keep legacy login for demo/admin.
- Frontend: loud console error when unconfigured; signup no longer silently creates bcrypt accounts (fails visibly unless `REACT_APP_ALLOW_PASSWORD_FALLBACK=true`); `firebaseSignIn` blocks unverified users and resends the link; new "verify your email" signup screen with resend.
- Backend `/auth/firebase`: saves name+company on any valid token but withholds the JWT until verified (`{verified:false}`), gated by `REQUIRE_EMAIL_VERIFICATION` (default true). Legacy `/auth/login` untouched → demo/admin unaffected.

### ⚠️ Owner must do — the actual fix for #2
Rename the Render **frontend** env vars (then rebuild):
| Current (wrong) | Correct |
|---|---|
| `apiKey` | `REACT_APP_FIREBASE_API_KEY` |
| `authDomain` | `REACT_APP_FIREBASE_AUTH_DOMAIN` |
| `projectId` | `REACT_APP_FIREBASE_PROJECT_ID` |
| `storageBucket` | `REACT_APP_FIREBASE_STORAGE_BUCKET` |
| `messagingSenderId` | `REACT_APP_FIREBASE_MESSAGING_SENDER_ID` |
| `appId` | `REACT_APP_FIREBASE_APP_ID` |
| `measurementId` | `REACT_APP_FIREBASE_MEASUREMENT_ID` |

Backend service also needs `FIREBASE_PROJECT_ID` (token verification) and optionally `REQUIRE_EMAIL_VERIFICATION=true`.

### Remaining plan
- **#1** marketing placeholders + `hireflow@cortinix.com` everywhere. Unblocked.
- **#3** source: replace free-text with a mandatory predefined list (single config module: LinkedIn, Indeed, Naukri, Company Careers Page, Employee Referral, Recruitment Agency, Offline Database, Walk-in, Campus Hiring, Internal Database, Other), store, badge in list, filter. Map old free-text values to "Other"/"Unknown".
- **#4** email regex fix (embedded `mailto:` link annotations via pypdf), DOCX (`python-docx`), extract hyperlinked LinkedIn/GitHub/portfolio from PDF annotations. **OCR blocked** on owner picking a cloud OCR provider + API key.
- **#5** viewer: one AI call at upload → compact structured JSON (contact/summary/experience/education/skills/links) stored on the candidate; a consistent printable React viewer renders it. Raw text kept as fallback.

### Verified this session
Backend compiles; 172 offline tests pass; `CI=true yarn build` clean after each batch. Nothing run end-to-end (no browser/backend/Firebase in this environment).

---

## Session 9 — 2026-07-23 — Phase 7: Bug bash & final QA

### Backend bugs fixed

| Bug | Impact |
|---|---|
| **`ai_service` crashed the entire API on startup** | `os.environ["GROQ_API_KEY"]` raised at import; `server.py` imports `routes_ai`, so one unconfigured integration took down **every endpoint**. Key now read lazily; `GROK_API_KEY` accepted as an alias with a warning naming the Groq/x.ai trap; an x.ai model id in `AI_MODEL` is called out at boot; AI endpoints return a clean **503** instead of a 500. |
| **CORS `"*"` + `allow_credentials=True`** | A combination browsers reject outright. Worked only because `CORS_ORIGINS` happened to be set. Credentials now enabled only with explicit origins. |
| **`seed_if_empty()` ungated** | Now respects `SEED_ON_STARTUP`. **Default unchanged**, so behaviour is identical today; set it false to guarantee demo data can never touch production. ← *the guard you asked about* |
| **`@app.on_event("startup")`** | Deprecated → `lifespan` handler. |
| **`update_job` dropped falsy values** | A field could never be cleared back to empty — `""` and `None` both looked like "not supplied". Now `exclude_unset`, plus a status whitelist instead of accepting any string. |
| **Unvalidated AI output written to Mongo** | `matched_skills`/`missing_skills`/`red_flags` were stored exactly as the model returned them, so a bare string or list of objects rendered as `[object Object]` or crashed `.map()`. Now coerced; scores clamped 0–100. |
| **`requirements.txt`** | Same block listed 2–3×, plus 10 unimported packages. Deduped and pruned — **pandas, numpy and boto3 dominated install time on every deploy**. Dev tooling removed from the production install. |

⚠️ **`cryptography` was deliberately KEPT** despite zero direct imports — PyJWT needs it for the RS256 Firebase verification. A naive prune would have broken sign-in. Commented in the file so nobody removes it later. **`reportlab` added** — the tests import it and it was missing.

### Frontend bugs fixed
- **`ErrorBoundary` at the root** — any thrown render error previously unmounted the whole tree, leaving a white page with no way back.
- **`Modal` locks body scroll**, and declares `role="dialog"` / `aria-modal`.
- Removed unused params (`Layout`'s `fullWidth`, `_ai_usage_summary`'s `total`).

### Final QA — what I could verify
| Check | Result |
|---|---|
| Demo account still works directly | ✅ Both accounts still seeded |
| Demo credentials exposed anywhere public | ✅ **Zero** in Login, Signup, marketing pages or shared components |
| Design consistency across new pages | ✅ The only hex values in every Phase 1–5 page are `#92400e`, `#f59e0b`, `#e5e7eb`, `#4f6ef7` — **all four existing design tokens.** No off-palette colour introduced |
| Offline test suite | ✅ 172 passing |
| Production build | ✅ `CI=true` clean, `main.js` 108.95 kB |

### ⚠️ Final QA — what I could NOT verify
**The full click-through QA in the brief was not performed.** No browser is available in this environment, and the backend was never started (no local dependencies; deliberately not booted against production Atlas). So across the whole engagement:

- **Nothing has been opened in a browser.** No page has been visually confirmed, at any viewport.
- **No backend endpoint has ever served a request.** Every route is syntax-checked and its logic unit-tested, but never executed.
- **No Firebase flow has run** — sign-up, sign-in and password reset are untested code.
- **No email has been sent** — SMTP is unconfigured locally.
- **No AI call has been made** — no working Groq key, so the Phase 4 prompt outputs remain ungenerated.

Everything is verified as far as static analysis, unit tests and a clean production build can take it. **That is not the same as working.** The handover list below is ordered accordingly.

---

## 🏁 Handover

### Do these first — nothing works in production without them
1. **Render backend env:** `FIREBASE_PROJECT_ID`, `ADMIN_EMAILS` (**the admin panel is unreachable until this is set** — the git-ignored credentials file does not exist on Render), and the `SMTP_*` group for feedback delivery. All documented in `backend/.env.example`.
2. **Render frontend env:** confirm `REACT_APP_FIREBASE_*` are set **before** the build — CRA inlines them at build time.
3. **Firebase console:** enable Email/Password sign-in, add your Render domain to Authorised domains, review the verification and reset email templates.
4. **Edit `backend/admin.credentials.json`** — currently points at `admin@hireflow.com`, whose password was publicly known from the old login page. Put your own email in.
5. **Run the click-through QA** listed above. Assume nothing is proven.

### Generate the Phase 4 evidence
```
cd backend && set GROQ_API_KEY=gsk_... && python tests/prompt_samples.py > ../prompt-samples.md
```

### Awaiting your decision
- **Delete the orphaned `components/ui/` (~40 shadcn files), `hooks/use-toast.js`, `constants/testIds/`, and the unused in-app `pages/ComingSoon.jsx`** — all verified unreferenced. *Will not shrink the bundle* (unreachable modules are never bundled); repo hygiene only.
- **Prune ~17 unused npm dependencies.** Same caveat — install speed, not runtime.
- **`/uploads` is an unauthenticated static mount** serving resume PDFs. Nothing links to it and filenames are unguessable UUIDs, but it is a path to candidate PII with no auth check. Removing it costs nothing functionally — say the word.
- **Replace placeholder copy**: About, Careers, Pricing, testimonials, and the four `@example.com` addresses.
- **Legal review of the privacy policy** — and confirm the §7 sub-processor list matches what you actually deploy.

### What I'd tackle next (beyond this engagement)
1. **Turn the Phase 1 "Coming Soon" items into real features** — bulk email and calendar scheduling are the two that would most change daily use.
2. **Move resume PDFs to object storage** (S3/GCS/GridFS). They currently sit on ephemeral disk and are never read back, which also blocks the PDF-viewer feature already on your backlog.
3. **Rotate the Atlas password and `JWT_SECRET`.** You declined this and that is your call, but they sat in plaintext in a folder that has been zipped and passed around. Recorded as accepted risk.
4. **Replace the admin panel's in-memory aggregation with MongoDB aggregation pipelines** — `_enrich_users` and `/admin/analytics` pull every record into Python. Fine now, won't scale.
5. **Add a real integration test suite.** `tests/backend_test.py` and `tests/test_admin_reports.py` hardcode `/app/frontend/.env`, a container path from the original scaffold, and fail at collection. Pre-existing, untouched.
6. **Profile and memoise the Kanban board** — carried from Phase 6; needs a browser profile to do correctly rather than speculatively.
7. **Cache AI ranking against a JD content hash** so an unchanged posting never pays for a re-run.
8. **Email verification enforcement** — Firebase sends the email but nothing currently gates on `email_verified`.

---

## Session 8 — 2026-07-23 — Phase 6: Performance pass

### 📊 Headline: entry bundle down 56%

| Measurement | Before | After | Change |
|---|---|---|---|
| `main.js` (gzip) | 246.15 kB | **108.37 kB** | **−137.8 kB (−56%)** |
| `main.css` (gzip) | 9.71 kB | 9.61 kB | −0.1 kB |
| Deferred chunks | 19 | 31 | recharts now a 105.9 kB on-demand chunk |

Against the **original Phase 0 baseline of 233.96 kB** this is **−54%**, even after adding a marketing site, Firebase, the feedback system and a much larger Reports page.

**Verified absent from `main.js`:** `recharts`, `d3-scale`, firebase auth (`identitytoolkit`), `QueryClient`.

### What actually moved the needle

1. **Route-level code splitting.** Only `Dashboard` stays eager — it's where every sign-in lands, so deferring it would trade bundle size for a spinner on the most common path. The decisive one was **Reports**: the only eager page importing recharts, so every user downloaded the entire charting library on sign-in whether or not they opened a chart. The six admin pages were also eager despite being reachable by **exactly one account on the platform**.
2. **Removed the `@tanstack/react-query` provider.** It wrapped the whole app but **no component ever called a react-query hook** — fetching is axios in `useEffect`. The library was bundled to supply a context with no consumers.
3. **Fonts were loaded twice and badly.** `index.html` pulled in **Inter, which nothing references** (Tailwind is configured for DM Sans), while the DM families came via a render-blocking `@import` at the top of `index.css` — which cannot even start until the stylesheet has itself downloaded. Now one `<link>` for the fonts actually in use.
4. **`AuthContext` value memoised.** It was a fresh object literal every render, so every consumer in the app re-rendered whenever the provider did, even when nothing about the session changed.

### Backend query fixes

| Fix | Before | After |
|---|---|---|
| `GET /jobs` | **One candidates query per job** — 30 postings = 31 round-trips per page load | 2 queries regardless of count |
| `PUT /candidates/bulk-stage` | 2 lookups per id, then an update + insert each — moving 50 candidates was **200+ round-trips** | Fixed query count + 2 bulk writes |
| Indexes | Nothing on `candidates.stage`/`uploaded_at` or `jobs.status`/`created_at`, despite every dashboard and reports request filtering on exactly those | Compound indexes covering the real access paths, plus sparse `users.firebase_uid` |

`GET /jobs` is the most likely cause of the slowness you reported.

### Deliberately NOT done — needs your decision
- **`frontend/src/components/ui/` (~40 shadcn files) is fully orphaned** — verified nothing imports from it. Same for `hooks/use-toast.js` and `constants/testIds/`. Deleting files needs your approval. **Note: removing them will not shrink the bundle** — webpack only bundles reachable modules, so they already cost nothing at runtime. It's a repo-hygiene and install-time win only.
- **Unused dependencies** confirmed unimported: `swr`, `framer-motion`, `embla-carousel-react`, `vaul`, `react-day-picker`, `input-otp`, `cmdk`, `lodash`, `date-fns`, `dayjs`, `react-hook-form`, `zod`, `@hookform/resolvers`, `next-themes`, `react-resizable-panels`, `class-variance-authority`, and now `@tanstack/react-query`. Same caveat — pruning `package.json` speeds installs, not runtime.

### Not done, and why
- **Render memoisation of the Kanban board.** Listed in the plan, but memoisation without profiling is speculative — `React.memo` silently does nothing if props include inline closures. This needs a browser profile I cannot run. Carried to Phase 7.
- **AI result caching** — ranking already skips analysed candidates unless `reanalyze` is set, so the remaining win is small and would need a JD content hash to be correct.

### ⚠️ Measurement caveat
Bundle sizes are **real and measured**. Backend improvements are **structural, not benchmarked** — the query counts are objectively reduced and the indexes objectively added, but with no local database and no production access I could not time before/after. The N+1 removals are the kind of change whose benefit grows with data volume.

### Also noted
`tests/backend_test.py` and `tests/test_admin_reports.py` fail at collection — they hardcode `/app/frontend/.env`, a container path from the original Emergent scaffold. **Pre-existing, unrelated to any of my changes.** Logged to backlog.

---

## Session 7 — 2026-07-23 — Prompt architecture correction + Phase 5

### 🔧 Correction first: the prompts were overfit to the three test niches

Owner pushed back, correctly. My Phase 4 rewrite wrote the three **validation** niches **into the production prompts** — the ranking prompt named *"ICU nurse, forklift operator, backend engineer"* and the questions prompt scripted what to ask a ward nurse vs a chef. That is illustration posing as architecture: it biases every evaluation toward the three examples I happened to pick and disadvantages roles resembling none of them.

**Replaced with an explicit two-stage design.** Every evaluative prompt now carries `JD_ANALYSIS_DIRECTIVE`, which derives a role profile from the description **first** — domain, function, seniority, engagement type, hard requirements, tools/systems, working context — then judges against *that* profile.

| Requirement | How it's met |
|---|---|
| Ranking driven by JD, not fixed categories | Scoring weights come from the derived profile; explicit "do not reward credentials the role did not ask for" |
| Questions adapt to the role | `type` labels are **free-form**, derived from the role's own vocabulary — not chosen from any list |
| Certifications/licences/tools extracted dynamically | `HARD REQUIREMENTS` and `TOOLS & SYSTEMS` are named profile dimensions, so they surface in any field |
| Industry-aware tenure judgement | Tenure judged against **derived ENGAGEMENT norms**. Frequent moves carry no signal for contract/agency/locum/seasonal/project work, and may carry some where the description implies long-horizon ownership. **Reasoned, not an allowlist of exempt sectors.** |
| No generic scoring template | `UNIVERSAL_CONTEXT` restated as a principle, not a sector list — a finite list silently excludes whatever it omits |

**Tests: 26 → 118.** The three original niches stay as regression fixtures. **Eight further industries added** — finance, legal, sales, marketing, manufacturing, construction, hospitality, education — run against all five evaluative prompts. None needed bespoke handling; *if adding an industry ever required a code change, that would be the bug.*

**New architectural guard:** no prompt template or system message may name a specific occupation. Whole-word matching, after a first attempt tripped on `"reward"` containing `"ward"`.

---

### Phase 5 — Reports overhaul

The old four panels were real data, but only two were decision-useful and one number was invented.

| Panel | What it does now |
|---|---|
| **Pipeline conversion funnel** | Per-stage counts, conversion rate and drop-off. Counts the **furthest stage each candidate reached**, not where they sit now — someone rejected after interview still counts at every stage they passed. Rejected/On Hold are outcomes, excluded from the progression. |
| **Time-to-hire** | Per posting and overall, plus a 30-day trend split so the page says whether it's improving |
| **Source effectiveness** | Now possible — `source` captured at upload |
| **Postings needing attention** | Open, unfilled, no candidate movement in 14+ days, longest-idle first. *This is the list that says what to do next.* |
| **Open vs closed postings** | 12-week area chart |
| **Insights** | Plain-language, auto-generated |

**`source` field added** (as you approved): free text with suggestions, so any channel works — job centre, notice board, walk-in, agency, not just office channels. Existing candidates group under `Unknown` rather than being dropped.

**Insights are rule-based, not an AI call.** They render on every page load, so they must be instant, free and identical for identical data. Percentage claims are **suppressed below a five-candidate sample** rather than reporting "100% conversion" off a single hire. The on-demand AI pipeline-health report is untouched.

**Removed the fabricated `est_completion`** — hardcoded as `now + 14 days × remaining`. It was the only invented number on the page.

**Fixed an N+1 query** — time-to-hire ran one transitions lookup per hired candidate inside a loop. All transitions now fetched once.

**Empty states at three levels:** no postings gets a first-run screen with a create action; each panel explains what would populate it; a failed fetch says so instead of rendering an empty axis.

### Verified
- **172 offline tests passing** (31 reports + 118 prompts + 23 admin), **and passing in reverse order** — which caught a real isolation bug I introduced: `test_reports` installed a `database` stub without `ai_usage_log`, and `test_prompts` then skipped creating its own. Stubs now merge instead of skipping.
- Reports tests cover the edge cases that would otherwise produce nonsense: no data, unparseable and timezone-naive timestamps, division by zero, hires with no recorded transition, candidates predating the `source` field, and the funnel never widening.
- `CI=true yarn build` clean. `main.js` 243.01 → **246.15 kB**. Still recharts only.

### ⚠️ Not verified
- **Backend still never started** — no deps locally, and not booting against production Atlas. All reports logic is unit-tested but the endpoint has never served a request.
- No browser check of the new Reports page.

---

## Session 6 — 2026-07-23 — Phase 4: Universal-niche AI prompt audit

All seven prompt templates rewritten. **Response schemas unchanged** — every JSON key the UI renders is identical, and 26 new tests assert it.

### The four substantive fixes

| Prompt | Was | Now |
|---|---|---|
| **Ranking** | `"expert technical recruiter"`; **`"job hopping"` in the stock red-flag list** | Occupation-neutral framing; explicit instruction **not** to penalise short tenures in agency, locum, seasonal, temporary, contract, hospitality, construction, events or gig work. Also told not to reward credentials the role never asked for. |
| **Screening questions** | Closed enum: `Technical`/`Behavioral`/`Experience`/`Culture Fit` | Open, role-appropriate labels incl. Safety, Certification, Compliance, Availability, Physical Requirements, Practical Skills |
| **JD enhancement** | Hardcoded white-collar section list | Menu spanning shift patterns, pay basis, site, certifications, physical requirements — include a section **only** where the input supports it |
| **Emails** | Saw only a job title → one fixed register | Receives the **job description**; matches tone and length to role and reader; bracketed placeholders instead of invented times/rates/locations |

`"job hopping"` was the worst offender — that single phrase systematically down-ranked blue-collar candidates for a career shape that is completely normal in their sector.

Compare, summary and pipeline-health got the same universal framing via a shared `UNIVERSAL_CONTEXT` constant; summary also carries the tenure guard.

### ✅ The question-enum concern from Phase 0 resolved — no schema change needed
The audit flagged widening the `type` enum as "the one place a schema change may be genuinely necessary". **It isn't.** The UI renders `q.type` as **free text inside a `Pill`** ([CandidateDetail.jsx:140](frontend/src/pages/CandidateDetail.jsx#L140), [CandidateBoard.jsx:203](frontend/src/pages/CandidateBoard.jsx#L203)) — never switched on, mapped to a lookup, or filtered. The vocabulary widens; the schema shape `{type, question}` is untouched; no frontend change was required.

### Demo seed data replaced
It was two software/design roles with resumes reading *"TechCorp"* and *"B.S. Computer Science"* — the first thing a prospect sees. Now **three genuinely different postings**: ICU Registered Nurse, Forklift Operator (night shift), Backend Software Engineer, with eight realistic candidates. One forklift candidate deliberately has **three short agency placements** — the exact shape the old prompt flagged — so the fix is demonstrable in the demo itself.

### Verified
- **26 offline prompt tests + 23 admin allowlist tests = 49 passing.** The prompt suite stubs `groq` and `database`, so it runs with no backend dependencies at all.
- Tests assert both directions: every schema key still requested, **and** the bias phrases are gone (`"job hopping"` absent, `"technical recruiter"` absent, old closed enum absent, white-collar-only section list absent).
- Tests confirm the JD actually reaches every prompt that takes one, across all three sample roles.
- `build_email_prompt` still works when a job has no description (`jd_text` optional).

### ⚠️ Live sample outputs NOT produced — needs your key
The brief asked for each rewritten prompt to be run against ≥3 very different postings with outputs pasted here. **I could not do this.** There is no working Groq key in this environment — `backend/.env` contains `GROK_API_KEY=your-grok-api-key-from-console.x.ai`, a placeholder, and for the wrong provider (Grok/x.ai vs Groq/GroqCloud).

Everything needed to produce them is committed. Run:

```
cd backend
set GROQ_API_KEY=gsk_...          # export GROQ_API_KEY=... on Unix
python tests/prompt_samples.py > ../prompt-samples.md
```

18 AI calls: enhance-JD, rank, questions, rejection email, interview invite and deep summary, for each of the three roles. **What to check in the output:**
1. The agency-placement forklift candidate gets **no "job hopping" red flag**.
2. Screening question `type` labels **differ by trade** — Safety/Certification for the warehouse role, Technical for the engineer.
3. Enhanced nursing and warehouse postings carry **shift and licence sections**; the engineering one is not forced to.
4. The three rejection emails **do not share one corporate register**.

Paste the result here when you have it.

---

## Session 5 — 2026-07-23 — Phase 3: Support / feedback loop

Users can send a **review, bug report or feature request** from inside the dashboard. Submissions reach **connecting800@gmail.com** and are persisted so the admin panel can work through them.

### Owner constraints confirmed this session
- ✅ Firebase env vars, Email/Password auth and `admin.credentials.json` — owner handling.
  - *Clarified:* `admin.credentials.json` holds **emails and Firebase UIDs only — there is no password field.** Passwords live in Firebase or the legacy bcrypt store.
- ✅ **Legacy JWT compatibility retained** — unchanged from Phase 2. `POST /auth/login` (bcrypt) still works, and Login falls back to it whenever Firebase has no matching account. Nothing about the existing JWT session model changed.
- ✅ **`seed_if_empty()` never run against production Atlas.** The backend was not booted at all. ⚠️ *Note:* it still auto-runs on every startup ([server.py:104](backend/server.py#L104)); it no-ops only because `users` is non-empty. **Offered to put it behind an explicit opt-in flag — awaiting your call.** Logged in Backlog.

### Delivery mechanism — and why
**Plain SMTP via stdlib `smtplib`. Zero new dependencies.** Provider-agnostic: Gmail app password, Resend, Brevo, Mailgun and SES SMTP all work by changing env vars alone. Chosen over adding a SendGrid/SES SDK because there was **no email infrastructure at all** and the brief asked not to introduce heavy infra where something simpler fits.

**Deliverability** (the brief's "don't trivially hit spam"):
- `From` is **always the authorised SMTP sender, never the submitter** — putting a submitter's address in `From` fails SPF/DKIM and lands in spam or gets rejected outright.
- The submitter goes in **`Reply-To`**, so hitting reply in the inbox still answers them.
- Explicit `Date` and `Message-ID` headers — both are common spam signals when absent.

**Never loses a message:** the submission is written to MongoDB **before** the send is attempted, and `send_email()` returns `False` rather than raising. If SMTP is unconfigured or the relay is down, the feedback is still captured, the admin list flags it as not emailed, and the user is told it was *received* rather than *sent*.

### New files
| File | Purpose |
|---|---|
| `backend/email_service.py` | SMTP transport, fails soft, blocking send pushed to a worker thread |
| `backend/routes_feedback.py` | `POST /feedback`, `GET /feedback/mine`, `GET /feedback/admin`, `PUT /feedback/admin/{id}/status` |
| `frontend/src/pages/Feedback.jsx` | Three-way type picker, char counters, and the user's own submission history |
| `frontend/src/pages/admin/AdminFeedback.jsx` | Filterable list, unread highlighting, read/actioned workflow, mailto reply, SMTP-unconfigured warning |
| `backend/.env.example` | **Every** backend variable documented |

New routes: `/feedback` (all users, "Support" section in sidebar) and `/admin/feedback` (admin only).

The **account email is attached automatically** — the user never types it. Rate limited to 15 submissions per user per hour.

### Verified
- **Email headers exercised directly**: `From` = authorised sender, `Reply-To` = submitter, `Date` and `Message-ID` present, and an unconfigured send returns `False` **without raising**.
- `connecting800@gmail.com` is **absent from every client bundle** — it's a backend default, so the owner's inbox isn't exposed in public JS.
- All backend files byte-compile; 23 admin allowlist tests still pass.
- `CI=true yarn build` clean.

### 📊 Bundle
`main.js` 238.64 → **243.01 kB** gzip (+4.37 kB). Both new pages are eagerly imported, matching the existing admin pages — Phase 6 splits them all together.

### ⚠️ Not verified
- **The FastAPI app still has not been started** (backend deps absent locally; not booting against production Atlas). `POST /feedback` is syntax-checked and its email layer unit-exercised, but **the endpoint has never run**.
- **No email has actually been sent.** SMTP is unconfigured locally, so the real send path is untested end to end.
- No browser check.

### What you need to set
SMTP is **not configured**, so nothing will be emailed until you set these on the Render **backend** service (all documented in `backend/.env.example`):

`SMTP_HOST` · `SMTP_PORT` · `SMTP_USER` · `SMTP_PASSWORD` · `SMTP_FROM` · optionally `SMTP_FROM_NAME`, `SMTP_USE_SSL`, `FEEDBACK_TO`

Until then, feedback is still captured and visible at `/admin/feedback`, which shows a banner explaining delivery is off. For Gmail specifically you need an **App Password** (not your account password) with 2FA enabled.

---

## Session 4 — 2026-07-23 — Phase 2: Auth overhaul, role lockdown, hardcoded admin

### Commits
| Hash | What |
|---|---|
| `0c5c4ed` | privilege-escalation fix + admin allowlist + Firebase token verifier |
| *(next)* | Firebase sign-in bridged to JWT, demo de-exposure, admin panel work |

---

### 🔒 The critical bug is closed

All three escalation paths shut:
| File | Was | Now |
|---|---|---|
| `models.py` | `SignupRequest.role` accepted from the client | field **removed entirely** |
| `routes_auth.py:28` | `role = body.role if body.role in ("hr","admin")` | constant `HR_ROLE`, never client input |
| `Signup.jsx` | **"Admin" option in a public dropdown** | role selector removed |
| `routes_admin.py` | `PUT /users/{id}/role` let any admin mint another | returns 403 with an explanation |

**Admin is now decided only by `backend/admin_identity.py`**, which matches the *authenticated* identity against an allowlist held outside the users collection. `require_admin` and `create_token` both consult it, so a row claiming `role="admin"` — **including one created through the old bug** — gets nothing.

Sources, merged:
1. `backend/admin.credentials.json` — git-ignored (template committed as `admin.credentials.example.json`)
2. `ADMIN_EMAILS` / `ADMIN_FIREBASE_UIDS` env vars

> **Deviation from the brief, with reason:** the brief specified a git-ignored file only. A git-ignored file **does not exist on Render** — it was never pushed — so the admin panel would be permanently unreachable in production. The env-var fallback is required for the hosted product to work. Both sources are backend-only and never reach the browser.

**Fails closed:** no configuration means nobody is an admin.

### 🧪 23 regression tests — `backend/tests/test_admin_identity.py`, all passing
Covers the escalation scenario itself, case/whitespace normalisation, prefix/suffix near-miss attacks (`xowner@…`, `owner@….evil.com`), null/empty identities, unedited example placeholders, malformed and non-object config files, the fail-closed path, and env-var merging.

### 🔑 Firebase — bridged, exactly as decided
Firebase owns credentials, verification and password resets. It does **not** own sessions: the frontend exchanges the Firebase ID token at `POST /auth/firebase` for the app's **existing JWT**, so `AuthContext`, the axios interceptor and every guard are untouched. **Existing users keep their passwords — no forced reset.**

**No Firebase service-account key is needed.** `backend/firebase_auth.py` verifies ID tokens directly against Google's public JWKS (RS256, checking `aud`/`iss`/`exp`/`sub`) using `pyjwt` + `cryptography`, both already dependencies. The only new backend config is **`FIREBASE_PROJECT_ID`, which is not a secret**. This deliberately avoids `firebase-admin` and the credential provisioning it would require.

**Graceful degradation:** when the Firebase env vars are absent the app falls back to the legacy password endpoints and Forgot Password explains resets are unavailable. This is what allows local development without a Firebase project.

**Login flow:** Firebase first; if Firebase has no such account, fall back to the legacy password endpoint. That is what keeps pre-Firebase users *and the demo accounts* working.

### 🚨 Demo credentials removed from the login page
`Login.jsx` was printing **working credentials for both the HR and the admin account in plain text on the public login page**. That card is gone. The seeded accounts still work for anyone who knows the details, per the brief.

**Verified:** zero occurrences of `Admin@1234`, `Sarah@1234`, `"Demo accounts"` or `admin@hireflow.com` across **every** built bundle.

### Admin panel
- Sidebar **Admin badge** + purple-accented "Platform Admin" section — visually distinct, never confused with an HR dashboard. *(Purple, not amber — amber means "AI" in this design system.)*
- User management: explanatory banner, role-toggle removed, allowlisted admins cannot be deactivated.
- **Fixed a real bug:** resume rows linked to `/candidates/:id`, which **403s for an admin who doesn't own that candidate** — broken for its actual purpose. Now opens a JSON viewer of the stored record via the new `GET /admin/resumes/{id}`.
- Added open/closed job counts and a 30-day signup series to `/admin/dashboard`.

### 📊 Bundle
| Asset | Before | After |
|---|---|---|
| `main.js` gzip | 237.85 kB | **238.64 kB** (+0.79 kB) |
| Firebase auth SDK | — | own **26.17 kB** deferred chunk |

Auth pages are lazy-loaded, so the SDK never enters the dashboard bundle. **Verified: `identitytoolkit` appears 0 times in `main.js`.**

### Verified
- `CI=true yarn build` compiles clean (warnings-as-errors).
- 23/23 backend allowlist tests pass.
- All six modified backend files byte-compile (`py_compile`).
- Credential files confirmed untracked; only the `.example` templates are staged.

### ⚠️ Not verified — read this
- **The FastAPI app was never started.** Backend dependencies (`fastapi`, `motor`) are not installed locally, and I deliberately **did not** boot the API against your production Atlas — `seed_if_empty()` runs on startup and would touch live data. So `/auth/firebase` has been syntax-checked and reasoned through, but **not executed**.
- **Firebase sign-in has never run.** No Firebase project config is available locally, so every Firebase path fell back to legacy. The whole Firebase flow is unexercised.
- **No browser check** — same as Phase 1.

---

## Session 3 — 2026-07-23 — Phase 1: Public marketing site

Built the full pre-login site. **No existing page, component or backend file was touched** — the only pre-existing file modified is `App.js` (routing), confirmed by `git diff --stat`.

### Commits
| Hash | What |
|---|---|
| `dc828fb` | marketing content data layer + shared UI primitives |
| `b682b78` | the 8 public pages + persistent shell |
| `ab61af7` | routing rewire, catch-all fix, lazy loading |

### New files (11)
| File | Purpose |
|---|---|
| `src/data/marketing.js` | **All editable copy** — features, steps, industries, testimonials, roadmap. Wording changes never need JSX edits. |
| `src/components/marketing.jsx` | Shared primitives: `Section`, `SectionHeading`, `Eyebrow`, `FeatureCard`, `LinkButton`, `CTABand`, `PageHero`, `TestimonialCard`, `Rating`, `PlaceholderNote`, `Prose` |
| `src/pages/marketing/MarketingLayout.jsx` | Persistent header + footer + `Outlet`, mobile menu, scroll-to-top |
| `src/pages/marketing/Home.jsx` | Hero, problem, features, how-it-works, industries, testimonials, roadmap teaser, CTA |
| `src/pages/marketing/Pricing.jsx` | Early-access tiers, no live billing |
| `src/pages/marketing/About.jsx` | Mission + values, placeholders marked |
| `src/pages/marketing/Careers.jsx` | Structure only, empty vacancy list |
| `src/pages/marketing/Reviews.jsx` | Data-driven, industry filter, average rating |
| `src/pages/marketing/Privacy.jsx` | Full policy, 15 sections |
| `src/pages/marketing/ComingSoon.jsx` | Roadmap teaser, no form |
| `src/pages/marketing/NotFound.jsx` | Auth-aware 404 |

### New routes
`/` · `/pricing` · `/about` · `/careers` · `/reviews` · `/privacy` · `/coming-soon` · `*` (404)

All are public and reachable **signed in or out** — the header swaps Log in/Register for a dashboard link. Only `/login` and `/signup` remain wrapped in `PublicRoute`.

### ⚠️ Routing behaviour changes (deliberate, flagged)
1. **`/` no longer redirects to `/dashboard`** — it now serves the marketing Home. This changes what a signed-in user sees if they navigate to the root. They reach the product via the header.
2. **`*` no longer silently redirects to `/dashboard`** — it renders a real 404 that links to the dashboard when signed in and to home when not. The old behaviour would have swallowed every marketing route, which is why it had to change.

`PrivateRoute`, `PublicRoute`, `AdminRoute` and every existing app/admin route are **unchanged**.

### Verified
- **`CI=true yarn build` compiles clean** — warnings-as-errors, so this also proves **zero ESLint warnings and zero webpack warnings**, including that every named import resolves (webpack errors on missing named exports).
- **Marketing code is genuinely absent from the app bundle** — grepped `main.js` for distinctive marketing strings (`registered nurse`, `Privacy policy`, `Placeholder content`, …): **0 hits**. Each page compiles to its own deferred chunk.
- **No demo credentials anywhere in the new marketing source** — grepped for `hireflow.com`, `Admin@1234`, `Sarah@1234`, "demo account". Clean. *(The pre-existing card in `Login.jsx:106-110` is still there and still ships in `main.js` — that is Phase 2's job.)*
- **Scope contained** — `git diff --stat` shows exactly one pre-existing file changed: `App.js` (+29/−3).

### 📊 Bundle impact
| Asset | Before | After | Δ |
|---|---|---|---|
| `main.js` (gzip) | 233.96 kB | **237.85 kB** | +3.89 kB |
| `main.css` (gzip) | 8.9 kB | 9.55 kB | +0.65 kB |
| Marketing chunks | — | 10 chunks, **~42.6 kB total** | deferred |

The +3.89 kB in `main.js` is `React.lazy`/`Suspense` wiring and the enlarged route tree, **not** marketing content. A signed-in user downloads none of the 42.6 kB.

### Universal-niche work
- Hero headline **cycles through 10 deliberately unlike roles** (registered nurse, forklift operator, backend engineer, line cook, delivery driver, retail supervisor, care assistant, CNC machinist, primary teacher, site electrician) — makes the promise visible rather than asserted. Respects `prefers-reduced-motion`.
- A dedicated **12-industry section** with concrete example roles.
- Testimonials span healthcare, logistics, trades, hospitality, corporate and education.
- Copy audited for office-default assumptions — e.g. scheduling is described as "built to handle shift patterns, not just nine-to-five", and pricing explicitly states a shift-work posting costs the same as a senior technical one.
- Roadmap adds **SMS/WhatsApp outreach** and **certification/licence tracking** — both far more relevant to trades, care and healthcare hiring than to office roles.

### Placeholder content (all clearly marked in-page)
Rendered with a neutral dashed `PlaceholderNote` — deliberately **not** amber, since amber means "AI" throughout this product and that convention is worth protecting.
- **Testimonials** — all 6 are invented; each card carries a "Sample — not a real customer" badge, driven by an `isPlaceholder` flag.
- **About** — story, values and contact address (`hello@example.com`).
- **Careers** — everything; `OPEN_ROLES` is empty so it renders an honest "no open positions" state. Contact `careers@example.com`.
- **Pricing** — every tier name, feature split and price is provisional; no tier shows a real number.
- **Privacy** — contact addresses (`privacy@example.com`, `support@example.com`), legal entity name, retention periods, sub-processor list.

### Privacy policy — needs your attention
Written to be genuinely accurate to how HireFlow works, not boilerplate. 15 sections covering data collected (including candidate PII from resumes), the controller/processor split (**you are the controller of candidate data, we are the processor**), retention, security, international transfers, cookies, and data-subject rights.

Two things worth reading yourself:
- **§5 discloses the AI processing plainly** — that resume text is transmitted to **Groq**, that output is assistive only, and that no candidate is rejected by automated processing. This is the section most likely to matter legally and it is stated honestly.
- **§7 lists sub-processors**: MongoDB Atlas, Render, Groq, Firebase, Google Fonts. **Firebase is listed although Phase 2 has not integrated it yet** — accurate by the time this ships, but confirm before publishing.

Carries a prominent red banner: **not written by a lawyer, requires legal review**.

### Not verified
- **No browser rendering check.** The build compiles and all imports resolve, but nothing here has been opened in a browser. Layout, spacing, responsive breakpoints and the hero rotation are unconfirmed. **This is the main thing to eyeball.**

---

## Session 2 — 2026-07-23 — Phase 0 follow-up: blockers cleared

All seven open questions answered by the owner. Setup actioned; **still no application source modified.**

### Decisions recorded (see PROJECT_PLAN.md "Cross-phase decisions")
1. ✅ git history — create it
2. ✅ install the Node toolchain
3. ❌ **do not rotate any existing key or password** — owner's decision, made with the exposure in view. **Accepted risk; do not re-raise.**
4. ✅ **Firebase-signin bridged to the existing JWT** (not a full replacement)
5. ✅ add a candidate `source` field
6. ✅ keep `backend/data/uploads/*.pdf`
7. ✅ resumes are DB-backed — no Render persistent disk needed

### What I did
- **`git init`** on `main` at the project root. Set local identity to `jsrrajpurohit <jsrrajpurohit@gmail.com>` (the repo's stray `.gitconfig` carried the scaffold identity `emergent-agent-e1`, which I did not use).
- **Verified before committing that no secrets were staged** — `git status --ignored` confirms `backend/.env` and `frontend/.env` are both ignored and untracked. This matters more than usual given decision #3.
- **Baseline commit `11383e9`** — 123 files, the app exactly as received plus the three Phase 0 audit docs. Establishes the diff baseline.
- **Toolchain:** Node **v24.18.0** and npm **11.16.0** turned out to be already installed — they were simply absent from my shell's inherited PATH, which is why Phase 0 reported them missing. `winget` confirmed no upgrade needed. Corepack couldn't activate yarn (EPERM writing to `Program Files` — needs admin), so installed **yarn 1.22.22** via `npm i -g yarn`, matching the project's declared `packageManager` exactly.
- **`yarn install`** run in `frontend/` — the project has **no lockfile at all** (neither `yarn.lock` nor `package-lock.json`), so this is a fresh resolution and will generate `yarn.lock`.
- **Answered Q7 by code trace** (below).

### Verified
- **Resume storage — your read was right, no persistent disk needed.** Traced end to end: `candidates.resume_text` (the extracted text) lives in **MongoDB** and is what every feature actually consumes — AI ranking, questions, summary, compare, the `CandidateDetail` resume preview, and the admin resume list. The PDF *binary* goes to local disk with only its filename in Mongo as `pdf_path`; grepping every usage shows `pdf_path` is **written on upload and read only to delete the file** — no route or component ever serves it back. Losing the binaries on redeploy is therefore invisible today. Full detail in AUDIT.md §8.14.
- **`.env` files are genuinely untracked** — confirmed, not assumed.

### Corrections to Phase 0
- 🔴 **Retracted: the `lodash@4.18.1` claim was wrong.** I stated that version doesn't exist and that a clean install would fail. Checked against the registry: **`4.18.1` is real and is the current latest.** No issue, and the Phase 6 task to "verify lodash" was a wasted item — narrowed to "check whether lodash is imported at all". AUDIT.md §8.3 and PROJECT_PLAN Phase 6 both corrected.
- **Node/npm were not actually missing** — they were installed but off my shell's PATH. The Phase 0 constraint was real for my session but overstated as a machine-level absence.

### New findings (logged, not fixed)
- **`/uploads` is mounted as unauthenticated `StaticFiles`** ([server.py:67-72](backend/server.py#L67-L72)) — any PDF still on disk is fetchable by URL with no auth check. Unguessable UUIDs and nothing linking to it make this low-risk today, but it is an open PII endpoint by design. → backlog.
- **A future PDF viewer/download is not buildable on current storage.** `PRD.md` lists "in-app PDF viewer/serving in candidate detail" as a P2 item; because binaries sit on ephemeral disk and are never served, that feature would need object storage (S3/GCS) or GridFS. → backlog.

### ✅ Toolchain verified — the app builds

- **`yarn install`** — exit 0 in 138s. Warnings only (deprecated transitive `workbox`/`jsdom` packages, peer-dep mismatches for `react-day-picker`, `recharts`, missing `typescript`). All benign for CRA 5; nothing blocks.
- **`yarn build`** — **`Compiled successfully.`** in 26s. react-scripts 5.0.1 works fine on Node 24 despite the age gap. **This is the first time the product has been verifiably built in this engagement**, so every phase from here can be sanity-checked for real.
- **`yarn.lock` created and committed.** The project previously had **no lockfile of any kind**, meaning every Render deploy re-resolved the dependency tree from scratch and could silently drift. Now pinned and reproducible. ⚠️ *This changes Render's install behaviour (lockfile-driven rather than fresh resolution) — flagged for the owner; trivially revertable by deleting the file.*

### 📊 Phase 6 performance baseline (measure against this)

Production build, gzipped:

| Asset | Size |
|---|---|
| `build/static/js/main.<hash>.js` | **233.96 kB** |
| `build/static/css/main.<hash>.css` | 8.9 kB |

**One single JS chunk — no code-splitting whatsoever**, exactly as predicted in AUDIT.md §8.1. Every visitor downloads all 12 pages, the 5 admin pages and recharts before seeing anything. This 233.96 kB figure is the number Phase 1 (lazy-loaded marketing routes) and Phase 6 must beat.

---

## Session 1 — 2026-07-23 — Phase 0: Discovery & Audit

### What I did
Read-only audit of the entire codebase. **No source files were modified.** Read every backend module, every page component, the routing, auth, styling config, and both `.env` files.

### Files created (3, all new — nothing existing was touched)
- `AUDIT.md` — full findings, 12 sections
- `PROJECT_PLAN.md` — Phases 0–7 as a living checklist
- `PROGRESS.md` — this file

### Files read (not modified)
`backend/`: `server.py`, `auth.py`, `database.py`, `models.py`, `seed.py`, `ai_service.py`, `routes_auth.py`, `routes_jobs.py`, `routes_candidates.py`, `routes_ai.py`, `routes_dashboard.py`, `routes_admin.py`, `routes_reports.py`, `requirements.txt`, `.env`
`frontend/`: `package.json`, `craco.config.js`, `tailwind.config.js`, `.env`, `src/App.js`, `src/api.js`, `src/constants.js`, `src/index.css`, `src/context/AuthContext.jsx`, `src/components/Layout.jsx`, `src/components/ui.jsx`, `src/pages/Login.jsx`, `src/pages/Signup.jsx`, `src/pages/Reports.jsx`, `src/pages/ComingSoon.jsx`
root: `.gitignore`, `memory/PRD.md`

### Verified
- **Stack confirmed by inspection, not assumption:** React 19 on **CRA + CRACO** (not Vite/Next). ⚠️ **Env vars are `process.env.REACT_APP_*`** — the `import.meta.env.VITE_*` snippet in the Phase 2 brief does not apply here.
- **AI provider is Groq/Llama**, not Claude — `PRD.md` says Claude and is stale.
- **The admin-signup bug is real and confirmed across 3 code paths** (see below).
- **Reports data is real, not mocked** — contradicts the brief's premise.
- Grepped for `firebase` — **zero hits.** Nothing to build on; Phase 2 is greenfield integration.
- Grepped for `marketing`/`pricing`/`careers`/`privacy` — **zero hits.** Phase 1 is entirely new.

### Not verified (couldn't be)
- **No build or run.** `node`, `npm`, `yarn` are **not installed** on this machine and `frontend/node_modules` is absent. Nothing frontend could be compiled or executed. `python` resolves only to the Windows Store shim.
- Live Render/Atlas behaviour — inspected from code only.

---

### 🔴 Critical findings

**1. Anyone can register as admin** (the bug named in the brief — confirmed)
Three paths: `models.py:11` exposes `role` on the public signup body; `routes_auth.py:28` whitelists `("hr", "admin")`; `Signup.jsx:117-123` ships an **"Admin" option in the public form's dropdown**. A single unauthenticated `POST /api/auth/signup` with `"role":"admin"` grants full platform admin — all users' PII, all resumes, all jobs. → Phase 2.

**2. Admin credentials are printed on the public login page**
`Login.jsx:106-110` renders a "Demo accounts" card listing `admin@hireflow.com / Admin@1234` in plain text on the live, unauthenticated login page. **Faster to exploit than the signup bug** — no crafted request needed. → Phase 2.

**3. Live production secrets in plaintext in `backend/.env`**
A working **MongoDB Atlas connection string with embedded password** (your production candidate-PII database) and the real **`JWT_SECRET`** (forge a token for any user). `.gitignore` covers `.env`, but there's no git history to verify against and this folder has clearly been zipped and moved around. **Assume compromised — rotate both.** Not something I'll act on unilaterally. → needs you, urgently, ahead of any phase.

**4. Backend cannot boot with the committed `.env`**
`ai_service.py:10` reads `os.environ["GROQ_API_KEY"]`, but `.env` defines `GROK_API_KEY` (different company — Grok/x.ai vs Groq/GroqCloud) with a placeholder value, plus `AI_MODEL=grok-2-latest`, a model id from the wrong provider. Import-time `KeyError` kills the whole API, not just AI endpoints. Render presumably has the right key set. → Phase 7, or sooner on your word.

---

### ⚠️ Premise corrections (worth knowing before Phase 5)

- **The Reports graphs are not random or placeholder.** All four are computed from real MongoDB data scoped to the logged-in user (`routes_reports.py`), and the page already has proper empty states. The **only** fabricated number is `est_completion` in the quota tracker — a hardcoded `now + 14 days × remaining`. Phase 5 is an upgrade of working analytics, not a replacement of fakes.
- **`PRD.md` is stale** — claims Claude Sonnet 4.5 (it's Groq/Llama) and calls Reports and `/admin/*` "coming soon" placeholders (both are fully built).

---

### Niche-bias found in AI prompts (detail + verbatim text in AUDIT.md §3)

The prompts are structurally better than expected — they already say "role-specific" and "infer from the JD". Four concrete problems:

1. **Ranking prompt: `"expert technical recruiter"`** primes tech screening for every vertical.
2. **Ranking prompt lists `"job hopping"` as a stock red flag** — actively harmful in hospitality, construction, agency nursing, gig and seasonal work, where short tenures are normal. This will systematically down-rank blue-collar candidates. Worst single offender.
3. **Screening questions have a closed 4-value `type` enum** (`Technical`/`Behavioral`/`Experience`/`Culture Fit`) — no room for Safety, Certification/Licensing, Availability & Shifts, Compliance. The one place a schema change may be genuinely necessary.
4. **JD enhancement hardcodes a white-collar section list** (Overview/Responsibilities/Requirements/Nice to have/Benefits) — no shift pattern, licences, physical requirements, pay rate, site.

Plus, outside the prompts: `seed.py` demo data is 100% tech/design ("TechCorp", "B.S. Computer Science"), placeholders are `you@company.com` / `Acme Corp`, jobs group only by `department` (trades think in site/shift/ward), and the Login brand panel reads as SaaS-insider ("0 HR bloat").

---

### Blocked

- **Phase 5 source-effectiveness analytics** — there is **no `source` field on candidates**. Needs a schema addition plus capture UI, or the metric drops from scope. Your call.
- **Commits** — repo is not git-initialised.
- **Frontend build verification** — no Node toolchain.

---

### Open questions for you
*(All seven answered — see Session 2 above.)*

---

## Backlog / Not in scope

Logged during Phase 0, deliberately **not** fixed (no unrelated refactors). Candidates for Phase 7.

**Dead code / cruft**
- ~40 unused shadcn components in `frontend/src/components/ui/` — app imports the single `ui.jsx` instead
- Second unused toast system (`hooks/use-toast.js` + `components/ui/toast.jsx`/`toaster.jsx`); `sonner` is the real one
- Unused deps: `@tanstack/react-query`, `swr`, plus likely `framer-motion`, `embla-carousel-react`, `vaul`, `react-day-picker`, `input-otp`, `cmdk`
- `constants/testIds/` — defined, seemingly unused
- `ComingSoon.jsx` — orphaned, imported nowhere (may be repurposed in Phase 1; **won't delete without asking**)
- `requirements.txt` has an entire **duplicated dependency block** (lines 1-27 then 28-41) and carries `boto3`, `pandas`, `numpy`, `jq`, `typer`, `python-jose`, `passlib`, `openai` — none imported. Slows every Render build
- `Layout({ fullWidth })` accepted but never used; `_ai_usage_summary(total, …)` param never used

**Correctness / robustness**
- **`seed_if_empty()` auto-runs on every backend startup** ([server.py:104](backend/server.py#L104)), gated only by `users` being non-empty. Owner asked that it never run against production Atlas — honoured, but nothing in code enforces it. **Offered to put it behind an explicit opt-in env flag; awaiting the call.**
- ~~`<Route path="*">` → `/dashboard` swallows all unknown routes~~ — **fixed in Phase 1**
- **CORS trap:** `allow_credentials=True` with `allow_origins` defaulting to `"*"` — browsers reject that combination outright; works now only because `CORS_ORIGINS` is set explicitly
- `update_job` filters `if v is not None`, so a field can never be cleared; `status` accepts any arbitrary string
- `_build_rank_set_doc` trusts the model's JSON shape — doesn't validate array-ness before writing to Mongo
- `@app.on_event("startup")` deprecated → should be a `lifespan` handler
- `Modal` doesn't lock body scroll or trap focus (a11y gap)
- No route-level error boundary — one render error blanks the app
- `© 2026 HireFlow Inc.` hardcoded in Login/Signup
- `AdminRoute` bounces non-admins with no explanation

**Performance** (full ranked list in AUDIT.md §8)
- No code-splitting; jobs-list N+1 (31 queries for 30 postings — likely your reported slowness); missing indexes on `candidates.stage`/`uploaded_at`, `jobs.status`/`created_at`; render-blocking font `@import`; no memoization; unstable `AuthContext` value; boot auth waterfall; no AI result caching
- ~~`lodash: "4.18.1"` does not exist~~ — **retracted, that version is real and current.** Narrowed to: check whether `lodash` is imported at all during the Phase 6 prune
- **`/uploads` is an unauthenticated `StaticFiles` mount** — any PDF on disk is fetchable by URL with no auth check (low risk today: unguessable UUIDs, nothing links to it)
- **A PDF viewer/download feature isn't buildable on current storage** — binaries sit on ephemeral disk and are never served; would need S3/GCS or GridFS. (`PRD.md` lists this as a P2 backlog item)
