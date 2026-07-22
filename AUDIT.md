# HireFlow — Phase 0 Discovery & Audit

**Date:** 2026-07-23
**Scope:** Read-only. No source files were modified.
**Auditor:** Claude (senior full-stack engineer role)

---

## 0. Environment constraints found (blocking, read first)

| Thing | Status | Impact |
|---|---|---|
| `git` repo | **Not initialized.** No `.git` anywhere. `git.exe` is installed. | The "small, reviewable commits" rule cannot be honoured until `git init` is run. Needs your go-ahead (see Open Questions). |
| `node` / `npm` / `yarn` | **Not installed on this machine.** | Frontend cannot be built, run, or lint-checked locally. The "run/build at phase boundaries" sanity check is impossible for the frontend until Node is installed. |
| `frontend/node_modules` | **Absent** (0 packages). | Same as above. |
| `python` | Present, but resolves to the Windows Store shim (`WindowsApps\python.exe`). Unverified whether a real interpreter + backend deps are installed. | Backend may not be runnable locally either. |
| Repo path nesting | Project root is `.../Hireflow/hireflow-main 22072027/hireflow-main 22072027/` (doubled folder). | Real root = the inner folder (holds `.gitignore`, `README.md`, `backend/`, `frontend/`). All new root files go there. |

---

## 1. Repo map

### Stack
- **Frontend:** React **19.0.0** on **Create React App + CRACO** (`react-scripts` 5.0.1, `@craco/craco` 7.1.0). **Not Vite, not Next.js.**
  - ➜ **Env var syntax is `process.env.REACT_APP_*`, NOT `import.meta.env.VITE_*`.** This directly overrides the Firebase snippet given in the Phase 2 brief.
- **Routing:** `react-router-dom` 7.5.1, `BrowserRouter`, all routes declared in [App.js](frontend/src/App.js).
- **State:** React Context only ([AuthContext.jsx](frontend/src/context/AuthContext.jsx)). `@tanstack/react-query` and `swr` are in `package.json` but **unused** — dead weight in the bundle.
- **Styling:** Tailwind CSS 3.4.17 with a custom token palette in [tailwind.config.js](frontend/tailwind.config.js). Plus hand-rolled primitives in [ui.jsx](frontend/src/components/ui.jsx) and a few global classes in [index.css](frontend/src/index.css).
- **shadcn/ui:** `components.json` + ~40 files in `src/components/ui/*.jsx` exist, but the app imports from `@/components/ui` (the single `ui.jsx` file), **not** the shadcn folder. Effectively unused scaffolding.
- **Charts:** `recharts` 3.6.0.
- **Toasts:** `sonner` (mounted in `App.js`). Note a second, unused toast system also exists (`hooks/use-toast.js` + `components/ui/toast(er).jsx`).
- **HTTP:** `axios` with interceptors in [api.js](frontend/src/api.js).
- **Backend:** **FastAPI** (0.110.1) + **Motor/MongoDB** (Atlas). Modular routers.
- **AI provider:** **Groq** (`groq>=0.9.0`, `AsyncGroq`), default model `llama-3.3-70b-versatile`. (PRD.md claims Claude Sonnet — stale, no longer true.)
- **Hosting:** Render (per your brief). `.emergent/emergent.yml` present — scaffolded by Emergent.
- **Path alias:** `@` → `frontend/src` (set in both `craco.config.js` and `jsconfig.json`).

### Folder structure (project root)
```
backend/          FastAPI app — server.py + 7 route modules + auth/db/models/ai_service/seed
  data/uploads/   3 stray uploaded PDFs committed into the tree
frontend/
  src/pages/      12 page components (+ pages/admin/ with 5 more)
  src/components/ Layout.jsx, ui.jsx, ui/ (unused shadcn)
  src/context/    AuthContext.jsx
memory/PRD.md     Build log (partly stale)
tests/, test_reports/, test_result.md
```

### Design system (must be preserved — Phase 1 marketing site matches this)
- **Fonts:** DM Sans (UI), DM Mono (resume/JD text), loaded from Google Fonts via `@import` in `index.css`.
- **Palette tokens:** `navy #0f1629`, `navy-2 #1a2340`, `indigo #4f6ef7` (primary), `indigo-light #e8edff`, `amber #f59e0b` (**AI accent convention**), `teal #0d9488`, `coral #ef4444`, `purple #7c3aed`, `green #16a34a`, plus a gray ramp.
- **Shadows:** `soft` / `card` / `lift`. **Animations:** `fade-in`, `slide-in`, `shimmer`.
- **Layout convention:** fixed 240px (`w-60`) navy sidebar → `ml-60` main → sticky white `Topbar` → `PageBody` capped at `max-w-[980px]`.
- **AI convention:** anything AI-powered uses the amber `.ai-btn` style (`#fffbeb` bg / `#fde68a` border / `#92400e` text) — consistent across the app.
- **Auth pages convention:** split screen, `w-[45%]` navy brand panel (left, hidden under `lg`) + gray-50 form panel (right), blurred indigo/purple radial blobs. **This is the pattern the marketing site should extend.**

---

## 2. Auth flow, end to end

### Current shape
1. **Signup** — [Signup.jsx](frontend/src/pages/Signup.jsx) → `POST /api/auth/signup` → [routes_auth.py](backend/routes_auth.py).
2. **Login** — [Login.jsx](frontend/src/pages/Login.jsx) → `POST /api/auth/login`.
3. Backend returns `{ token, user }`. Token is a **JWT** (HS256, 7-day expiry) signed with `JWT_SECRET`, created in [auth.py:28](backend/auth.py#L28).
4. Frontend stores it in **`localStorage["hireflow_token"]`** ([AuthContext.jsx:33](frontend/src/context/AuthContext.jsx#L33)); axios request interceptor attaches `Authorization: Bearer …`.
5. On boot, `AuthContext` calls `GET /api/auth/me` to rehydrate the user.
6. Response interceptor: any **401** clears the token and hard-redirects to `/login` ([api.js:17](frontend/src/api.js#L17)).
7. **Passwords:** bcrypt. **Sessions:** stateless JWT — no server-side session store, no refresh token, no revocation list.
8. **Guards:** `PrivateRoute` / `PublicRoute` / `AdminRoute` in [App.js:28-48](frontend/src/App.js#L28-L48). `AdminRoute` checks `user?.role !== "admin"` **client-side**; the backend independently enforces via `require_admin` ([auth.py:63](backend/auth.py#L63)) — so the real gate is server-side, which is correct.

### Roles that exist today
Exactly two: **`"hr"`** and **`"admin"`**. Hardcoded as string literals; no enum, no constant. `"hr"` is the working end-user role.

### 🔴 THE BUG — anyone can register as admin

Three independent code paths allow it:

1. **[models.py:11](backend/models.py#L11)** — `SignupRequest.role: str = "hr"` — `role` is a **client-supplied field on the public signup body**.
2. **[routes_auth.py:28](backend/routes_auth.py#L28)** — the whitelist explicitly *includes* admin:
   ```python
   role = body.role if body.role in ("hr", "admin") else "hr"
   ```
3. **[Signup.jsx:117-123](frontend/src/pages/Signup.jsx#L117-L123)** — the public signup form literally ships an **"Admin" option in a `<select>`**:
   ```jsx
   <select value={form.role} onChange={set("role")} ...>
     <option value="hr">HR User</option>
     <option value="admin">Admin</option>
   </select>
   ```

**Repro (no UI needed):** `POST /api/auth/signup` with `{"name":"x","email":"x@x.com","password":"password1","role":"admin"}` → returns a token whose `role` is `admin` → full platform admin: every user's PII, every resume, every job, role changes for other users.

**Severity: critical.** Publicly exploitable privilege escalation on a live, hosted product handling candidate PII.

### Secondary escalation path
**[routes_admin.py:116](backend/routes_admin.py#L116)** — `PUT /admin/users/{id}/role` lets any admin promote any user to admin. Requires admin already, so it's a persistence/lateral-movement vector rather than the initial breach. Phase 2 must decide whether this endpoint survives at all once admin is file-pinned.

### Where "admin" gets created today
Only in the seeder: [seed.py:24](backend/seed.py#L24) → `admin@hireflow.com` / `Admin@1234`. Runs via `seed_if_empty()` on startup, guarded by `users.count_documents({}) > 0`.

---

## 3. AI prompt templates — verbatim (for Phase 4 niche-bias review)

All live in [ai_service.py](backend/ai_service.py). Called via `call_ai(system_message, prompt)` → Groq. Seven total; the four you named are marked ⭐.

Bias verdict up front: **the prompts are structurally decent** (they already say "role-specific", "infer from the JD") but carry **four concrete corporate-office assumptions**, flagged inline below.

### 3.1 ⭐ JD Enhancement — `ENHANCE_SYSTEM` / `build_enhance_prompt` ([ai_service.py:129-140](backend/ai_service.py#L129-L140))
```
SYSTEM: "You are an expert job description writer who creates clear, inclusive, structured JDs."

USER:
Improve and professionally format the following job description for the role "{title}".
Make it well structured with sections (Overview, Responsibilities, Requirements, Nice to have, Benefits where inferable),
clear, inclusive language, and compelling tone. Keep it truthful to the input — do not invent specifics like salary.

ORIGINAL JOB DESCRIPTION:
{jd_text[:6000]}

Return ONLY the enhanced job description as plain text (you may use markdown headings and bullet points). No commentary.
```
> ⚠️ **Bias:** hardcoded section list is white-collar shaped. A forklift or ICU nursing post needs *Shift Pattern, Certifications/Licences, Physical Requirements, Pay Rate, Location/Site* — none of which are in the list, and "Nice to have" is a tech-recruiting idiom.

### 3.2 ⭐ Resume Ranking — `RANK_SYSTEM` / `build_rank_prompt` ([ai_service.py:78-107](backend/ai_service.py#L78-L107))
```
SYSTEM: "You are an expert technical recruiter and resume screener. You evaluate candidate
resumes against a job description objectively and return strict JSON only."

USER:
Evaluate each candidate against the JOB DESCRIPTION below.

JOB DESCRIPTION:
{jd_text[:6000]}

CANDIDATES:
--- CANDIDATE id={id} ---
NAME: {name}
RESUME:
{resume_text[:6000]}

For EACH candidate return an object with:
- id: the candidate id exactly as given
- score: integer 0-100 (overall match)
- summary: 2-3 sentence assessment
- matched_skills: array of strings (skills present that match the JD)
- missing_skills: array of strings (key JD skills the candidate lacks)
- red_flags: array of strings (gaps, job hopping, missing requirements, or [] if none)

Return ONLY a JSON array of these objects. No prose, no markdown.
```
> ⚠️ **Bias (worst offender):** `"expert **technical** recruiter"` primes tech screening for every vertical. And **`"job hopping"` as a stock red flag is actively harmful** in hospitality, construction, agency nursing, gig and seasonal work, where short tenures are the norm — this will systematically down-rank blue-collar candidates.
> ✅ Schema is clean and must be preserved: the UI reads `ai_score`, `ai_summary`, `matched_skills`, `missing_skills`, `red_flags`.

### 3.3 ⭐ Screening Questions — `QUESTIONS_SYSTEM` / `build_questions_prompt` ([ai_service.py:110-126](backend/ai_service.py#L110-L126))
```
SYSTEM: "You are an expert interviewer who writes sharp, role-specific screening questions."

USER:
Based on this job description and candidate resume, generate 6-8 tailored screening questions.

JOB DESCRIPTION:
{jd_text[:4000]}

CANDIDATE RESUME:
{resume_text[:4000]}

Return ONLY a JSON array of objects, each with:
- type: one of "Technical", "Behavioral", "Experience", "Culture Fit"
- question: the question text (specific to this candidate's background and the role)

No prose, no markdown.
```
> ⚠️ **Bias:** the **closed 4-value `type` enum is the sharpest constraint in the codebase.** "Technical" and "Culture Fit" are corporate-tech categories; a CDL driver or line cook needs *Safety, Certification/Licensing, Availability & Shifts, Physical Requirements, Compliance*. **Phase 4 caveat:** widening this enum is the one place a schema change may be genuinely necessary — needs a UI-render check first.

### 3.4 ⭐ Reject/Select Email — `EMAIL_SYSTEM` / `build_email_prompt` ([ai_service.py:143-158](backend/ai_service.py#L143-L158))
```
SYSTEM: "You are an expert HR communication writer who drafts warm, professional recruiting emails."

USER:
Draft a {email_type} email.

Candidate name: {name}
Role: {job_title}
Company: {company or 'our company'}
Candidate summary: {ai_summary or 'N/A'}

Return ONLY a JSON object with:
- subject: the email subject line
- body: the full email body (professional, warm, ready to send, with greeting and sign-off placeholder)

No prose, no markdown.
```
> ⚠️ **Bias:** register is fixed at "professional, warm" regardless of vertical, and the prompt is **starved of context** — it never sees the JD or industry, only a job title. A shift-work rejection and a director-level rejection come out identically toned.

### 3.5 Candidate Compare — `COMPARE_SYSTEM` / `build_compare_prompt` ([ai_service.py:161-182](backend/ai_service.py#L161-L182))
```
SYSTEM: "You are an expert hiring manager who compares candidates objectively for a role."
USER: Compare these two candidates for the role. / JOB DESCRIPTION / CANDIDATE A (name): score= / CANDIDATE B (name): score=
Return ONLY a JSON object with: recommendation, reasoning (2-4 sentences),
candidate_a_strengths (array), candidate_b_strengths (array). No prose, no markdown.
```
> Reasonably neutral.

### 3.6 Deep Summary — `SUMMARY_SYSTEM` / `build_summary_prompt` ([ai_service.py:185-204](backend/ai_service.py#L185-L204))
```
SYSTEM: "You are an expert recruiter writing a deep, structured candidate analysis."
USER: Write a deep candidate analysis for this person against the role. / JOB DESCRIPTION / CANDIDATE RESUME
Return ONLY a JSON object with: overall_fit, strengths (array), concerns (array),
experience_highlights (array), recommendation: one of "Strong Yes","Yes","Maybe","No". No prose, no markdown.
```
> Reasonably neutral.

### 3.7 Pipeline Health — `HEALTH_SYSTEM` / `build_health_prompt` ([ai_service.py:207-218](backend/ai_service.py#L207-L218))
```
SYSTEM: "You are an expert hiring operations analyst who reviews recruiting pipeline health."
USER: Analyze this hiring pipeline data and give a concise, actionable health report.
PIPELINE DATA (JSON): {stats}
Provide a short report (plain text, 4-7 sentences) covering: overall health, bottlenecks,
candidates needing action, and 2-3 concrete recommendations. Be specific and reference the numbers.
No markdown headers, just clear prose.
```
> Neutral (operates on numbers). **Relevant to Phase 5** — this is already a working "auto-generated written insight" generator that the Reports overhaul can reuse instead of building new.

### Other niche-bias found outside the prompts
- **[seed.py](backend/seed.py)** — every seeded job and candidate is tech/design (Senior Frontend Engineer, Product Designer, React/Figma). `SAMPLE_RESUME` hardcodes *"building scalable products"*, *"Senior role at TechCorp"*, *"B.S. Computer Science"*. This is what a demo viewer sees first.
- **Placeholder copy** — `"you@company.com"`, `"Acme Corp"`, `"Jane Doe"` on Login/Signup.
- **`department`** as the sole job-grouping field (models.py, JobCreate) — trades/healthcare think in *site*, *shift*, *ward*, *location*.
- **Login.jsx brand panel** — *"0 HR bloat"*, *"7 AI touchpoints"* — SaaS-insider voice, not universal.

---

## 4. Reports / Dashboard page

### ⚠️ Correction to a stated premise
The brief says the 4 graphs are "random/placeholder". **They are not.** [routes_reports.py](backend/routes_reports.py) computes all four from **real MongoDB data** scoped to the logged-in user, and [Reports.jsx](frontend/src/pages/Reports.jsx) already renders proper empty states. (PRD.md line 48 also wrongly calls Reports a "coming soon placeholder" — stale.) Phase 5 is therefore an **upgrade of working analytics**, not a replacement of fakes. That's good news: less to build, more to build *on*.

### The 4 current panels — [Reports.jsx](frontend/src/pages/Reports.jsx)
| # | Panel | Viz | Source | Real? |
|---|---|---|---|---|
| 1 | **Time-to-Hire (avg days)** | horizontal `BarChart` | `_time_to_hire()` — days from `candidate.uploaded_at` → latest `stage_transitions` row with `to_stage="Selected"`, averaged per job | ✅ Real |
| 2 | **Stage Funnel** | custom CSS bars (not recharts) | `_stage_funnel()` — `Counter` over `candidate.stage` across all 10 stages | ✅ Real |
| 3 | **Top Missing Skills** | horizontal `BarChart` | `_skill_gap()` — counts `missing_skills` on Rejected candidates; **falls back to all analyzed candidates** if there are no rejections | ✅ Real (AI-derived) |
| 4 | **Hiring Quota Tracker** | HTML table + `ProgressBar` | `_quota_tracker()` — hired vs `openings_needed`, plus in-pipeline count | ⚠️ Mostly real — **`est_completion` is a hardcoded fantasy: `now + 14 days × remaining`** ([routes_reports.py:74-77](backend/routes_reports.py#L74-L77)). Only genuinely fake number on the page. |

### Data actually available for the Phase 5 rebuild
- `candidates`: `uploaded_at`, `analyzed_at`, `stage`, `ai_score`, `matched/missing_skills`, `red_flags`, `notes[]`
- `stage_transitions`: `from_stage`, `to_stage`, `moved_at`, `moved_by`, `note` — **full timestamped audit trail, per candidate.** This is the gold: it supports real per-stage dwell time, drop-off rates, and stalled-pipeline detection.
- `jobs`: `created_at`, `updated_at`, `status` (active/paused/closed), `openings_needed`, `deadline`
- **`STAGES` is a clean 10-stage ordered list** → a true conversion funnel with per-stage drop-off is straightforwardly derivable.
- ❌ **No `source` field on candidates.** **Source-effectiveness analytics from the Phase 5 brief is not currently possible** without a schema addition + UI to capture it. Flagging now for your decision.

### Main Dashboard ([Dashboard.jsx](frontend/src/pages/Dashboard.jsx) / [routes_dashboard.py](backend/routes_dashboard.py))
Separate and fully real: stats (active jobs, hired, in pipeline, contact pending, avg score), per-job summary, action items, upcoming interviews. No changes needed.

---

## 5. Demo account exposure

**Seeded** by [seed.py](backend/seed.py) on startup when the `users` collection is empty:

| Role | Email | Password |
|---|---|---|
| admin | `admin@hireflow.com` | `Admin@1234` |
| hr | `sarah@hireflow.com` | `Sarah@1234` |

Plus 2 demo jobs and 6 demo candidates owned by the HR user.

### 🔴 Public exposure
**[Login.jsx:106-110](frontend/src/pages/Login.jsx#L106-L110)** renders a **"Demo accounts" card on the public login page listing both sets of credentials in plain text — including the admin's.** Anyone who loads `/login` on the live site gets working admin credentials.

That is the single fastest live exploit path in the product — faster than the signup bug, since it needs no crafted request. **Phase 2 removes this card while keeping the seeded accounts functional.** Combined with the Atlas leak in §6, treat `Admin@1234` as burned: it should be rotated to a new secret, not merely hidden.

---

## 6. 🔴 Secrets exposure (out-of-scope but urgent)

**[backend/.env](backend/.env) contains live, working production credentials in plaintext:**

1. **MongoDB Atlas connection string with embedded username and password** — a real cluster, real password, `Hireflow:<password>@cluster0.…mongodb.net`. **This is your production candidate-PII database.**
2. **`JWT_SECRET`** — the real signing key. Anyone holding it can forge a valid admin token for any user id, bypassing every auth check in the product.

`.gitignore` does cover `.env` (line 84) — **but** the repo has no git history to verify against, and these values are sitting in a folder that has clearly been zipped and passed around (`hireflow-main 22072027` ×2). Assume compromised.

**Recommended, needs your action (not something I should do unilaterally):**
- Rotate the Atlas password and restrict cluster network access to Render's egress IPs.
- Rotate `JWT_SECRET` (this invalidates all existing sessions — expected and fine).
- Rotate the seeded `Admin@1234` password.
- Confirm on Render that the real values are set as environment variables and that `.env` is not baked into the deployed image.

**Also:** `frontend/.env` sets `REACT_APP_BACKEND_URL=http://localhost:8000`. Anything prefixed `REACT_APP_` is **inlined into the public JS bundle** — this is exactly why the Phase 2 rule "admin-check logic stays server-side only" is correct, and why the Firebase config (public by design) is safe there but an admin identity is not.

---

## 7. 🔴 Backend will not boot with the committed `.env`

[ai_service.py:10](backend/ai_service.py#L10) reads `os.environ["GROQ_API_KEY"]` — a hard `KeyError` if absent. But `backend/.env` defines:
```
GROK_API_KEY=your-grok-api-key-from-console.x.ai   # ← GROK, not GROQ, and a placeholder value
AI_MODEL=grok-2-latest                             # ← an x.ai Grok model id, not a Groq model id
```
Two separate faults: **the variable name is misspelled** (Grok/x.ai vs Groq/GroqCloud — different companies), and **the model id belongs to the wrong provider.** Because `server.py` → `routes_ai` → `ai_service` at import time, this is a **startup crash, not a lazy failure**: the entire API dies, not just the AI endpoints.

Render presumably has the correct `GROQ_API_KEY` set, which is why production runs. But local dev is broken out of the box, and the `AI_MODEL` override would break Render too if it were ever copied up. Trivial fix, deferred to Phase 7 (or sooner on your word).

---

## 8. Performance bottlenecks (code inspection only — not yet fixed)

Ranked by expected impact.

**Frontend**
1. **Zero code-splitting.** [App.js](frontend/src/App.js) statically imports all 12 page components including the 5 admin pages. Every HR user downloads the entire admin panel + recharts on first paint. `React.lazy` + `Suspense` is the single highest-leverage fix, and it is a **prerequisite for Phase 1** — otherwise the marketing site bloats the app bundle exactly as the brief warns.
2. **Unused heavy dependencies shipped:** `@tanstack/react-query`, `swr` (both unused), `framer-motion`, `embla-carousel-react`, `vaul`, `react-day-picker`, `input-otp`, `cmdk`, `recharts`, plus ~40 unused shadcn components. Likely a large fraction of the bundle is dead code.
3. ~~`lodash: "4.18.1"` does not exist~~ — **retracted 2026-07-23.** Verified against the registry: `4.18.1` is real and is the current latest. No issue. (`lodash` is still worth checking for *actual use* during the Phase 6 dependency prune.)
4. **Google Fonts `@import` at the top of [index.css](frontend/src/index.css)** — a render-blocking request that CSS `@import` makes serial. Should be a `<link rel="preconnect">` + `<link>` in `index.html`.
5. **No `React.memo` / `useMemo`** anywhere. The Kanban board ([CandidateBoard.jsx](frontend/src/pages/CandidateBoard.jsx), 221 lines) re-renders every card on any drag/state change.
6. **`AuthContext` value is a fresh object literal every render** ([AuthContext.jsx:45](frontend/src/context/AuthContext.jsx#L45)) → forces a re-render of every consumer on any parent render.
7. **Auth waterfall:** boot → render → `useEffect` → `GET /auth/me` → *then* the page's own fetch. Two serial round-trips before content.

**Backend**
8. **N+1 query in Time-to-Hire** — [routes_reports.py:33](backend/routes_reports.py#L33) awaits `stage_transitions.find_one()` **inside a per-candidate loop**. One DB round-trip per hired candidate. Should be a single `$in` query or an aggregation.
9. **N+1 query in Jobs list** — [routes_jobs.py:28-29](backend/routes_jobs.py#L28-L29) awaits `_job_stats()` per job, each a separate `candidates.find()`. A recruiter with 30 postings triggers 31 queries on every page load. **Likely a direct cause of your reported slowness.**
10. **N+1 in bulk stage update** — [routes_candidates.py:168-175](backend/routes_candidates.py#L168-L175), two queries per candidate id in a loop.
11. **Full-collection scans in the admin panel** — `_enrich_users()` and `/admin/analytics` pull **every** job, candidate and AI log into Python memory (`.to_list(100000)`) and aggregate with `Counter`. Fine at demo scale, falls over as the platform grows. PRD.md already acknowledges this.
12. **Missing indexes.** [database.py:26-32](backend/database.py#L26-L32) indexes `users.email`, `jobs.user_id`, `candidates.job_id`, etc. — but **nothing on `candidates.stage`, `candidates.uploaded_at`, `jobs.status`, or `jobs.created_at`**, all of which the dashboard/reports filter and sort on.
13. **AI results are never cached.** Re-ranking re-calls Groq for every candidate; only `reanalyze=False` + a `analyzed_at: None` filter prevents repeat work, and there is no content-hash check — an unchanged JD still costs a full re-run.
14. **Resume storage — resolved 2026-07-23. No persistent disk needed; your read was right.** Traced end to end:
    - **The extracted resume *text* lives in MongoDB** (`candidates.resume_text`, written at [routes_candidates.py:85](backend/routes_candidates.py#L85)). **Every feature that matters reads from there** — AI ranking, questions, summary, compare, the resume preview in [CandidateDetail.jsx:126](frontend/src/pages/CandidateDetail.jsx#L126) (renders `cand.resume_text`), and the admin resume list. **Nothing breaks on a deploy.**
    - **The PDF *binary* is written to the local disk** (`UPLOAD_DIR / {uuid}.pdf`) and only the filename is kept in Mongo as `pdf_path`. Grepped every usage: `pdf_path` is written on upload and read **only** to `os.remove()` the file on candidate deletion. **No route, page or component ever serves or reads it back.** So the binaries are effectively write-only, and losing them on redeploy is currently invisible.
    - ⚠️ **Two consequences to note, neither urgent:** (a) `PRD.md` lists *"in-app PDF viewer/serving in candidate detail"* as a P2 backlog item — that feature **cannot be built on the current storage** and would need object storage (S3/GCS) or GridFS, not a Render disk. (b) [server.py:67-72](backend/server.py#L67-L72) mounts `/uploads` as **unauthenticated `StaticFiles`** — any PDF still on disk is fetchable by URL with no auth check. Unguessable UUIDs make this low-risk today and nothing links to it, but it is an open PII endpoint by design.

---

## 9. Bugs & code-quality issues found (logged, not fixed)

**Functional**
- **`ComingSoon.jsx` is orphaned** — [ComingSoon.jsx](frontend/src/pages/ComingSoon.jsx) exists but is imported nowhere. Dead component. (Phase 1 adds a *public* coming-soon page; this in-app one may be repurposed or removed — will confirm before deleting.)
- **Catch-all route `<Route path="*" → /dashboard>`** ([App.js:70](frontend/src/App.js#L70)) — redirects *everything* unknown to `/dashboard`, which then bounces unauthenticated users to `/login`. **This will swallow every new public marketing route in Phase 1** unless restructured. Key Phase 1 constraint.
- **CORS misconfiguration** — [server.py:78-84](backend/server.py#L78-L84) sets `allow_credentials=True` with `allow_origins` defaulting to `"*"`. Browsers **reject** that combination outright. Works now only because `CORS_ORIGINS` is explicitly set; the default is a trap.
- **CORS middleware added after routers** — works in Starlette, but is fragile ordering.
- **`update_job` strips falsy values** — [routes_jobs.py:72](backend/routes_jobs.py#L72) filters `if v is not None`, so clearing a field back to empty is impossible; also `status` can be set to any arbitrary string (no whitelist).
- **`red_flags`/`missing_skills` may be non-lists** — `_build_rank_set_doc` trusts the model's JSON shape without validating array-ness before writing to Mongo.
- **`Modal` doesn't lock body scroll** or trap focus — background scrolls behind the overlay; a11y gap.
- **No route-level error boundary** — one thrown render error blanks the whole app.

**Dead / stale**
- `frontend/src/components/ui/*.jsx` (~40 shadcn files) — unused.
- `hooks/use-toast.js` + `components/ui/toast.jsx`/`toaster.jsx` — second toast system, unused (`sonner` is the real one).
- `constants/testIds/` — defined, seemingly unused.
- **`requirements.txt` has an entire duplicated dependency block** (lines 1-27 then 28-41), with `fastapi`, `uvicorn`, `pymongo`, `motor`, `bcrypt` etc. listed twice. Also carries `boto3`, `pandas`, `numpy`, `jq`, `typer`, `python-jose`, `passlib`, `openai` — **none imported anywhere**. Slows every Render build.
- **`backend/data/uploads/*.pdf`** — 3 real uploaded resumes sitting in the tree. If these are real candidate CVs, that's a PII-in-repo problem.
- **`PRD.md` is stale** — claims Claude Sonnet 4.5 (it's Groq/Llama now) and calls Reports/admin "coming soon" (both are built).
- `Layout({ children, fullWidth })` — `fullWidth` accepted but never used ([Layout.jsx:97](frontend/src/components/Layout.jsx#L97)).
- `_ai_usage_summary(total, user_map)` — `total` parameter never used ([routes_admin.py:215](backend/routes_admin.py#L215)).
- `@app.on_event("startup")` — deprecated in modern FastAPI; should be a `lifespan` handler.

**Trivial (typo-level, still untouched per read-only rule)**
- `Login.jsx` / `Signup.jsx` hardcode `© 2026 HireFlow Inc.`
- `AdminRoute` sends non-admins to `/dashboard` with no explanation toast.

---

## 10. Phase-by-phase implications (carry into planning)

- **Phase 1** — Must restructure the `path="*"` catch-all before adding public routes. Marketing pages must be `React.lazy`-loaded so they don't enter the app bundle. Reuse the Login/Signup split-panel visual language. **`/` currently redirects to `/dashboard`; the marketing Home takes over `/`** — a routing change worth calling out explicitly since it changes what a logged-out visitor sees first.
- **Phase 2** — **Use `process.env.REACT_APP_FIREBASE_*`, not `import.meta.env.VITE_*`.** Env vars must be set on the Render *frontend* service at **build time** (CRA inlines them; they are not runtime-readable). Firebase auth must **replace or bridge** the existing bcrypt+JWT system — the backend currently verifies its own JWTs, so it will need to verify **Firebase ID tokens** via the Firebase Admin SDK instead (`firebase-admin` is **not** in `requirements.txt`; it will need adding). This is the largest architectural decision in the whole engagement and I'll bring you a recommendation before writing code.
- **Phase 3** — No email infrastructure exists at all. `boto3` is installed but unused (SES is an option). Groq is the only outbound service. Will need a genuinely new integration; I'll propose the lightest option that fits.
- **Phase 4** — Schemas to preserve exactly: rank `{id,score,summary,matched_skills,missing_skills,red_flags}`, questions `{type,question}`, email `{subject,body}`, summary `{overall_fit,strengths,concerns,experience_highlights,recommendation}`. The screening-question `type` enum is the one likely-necessary schema change.
- **Phase 5** — Better foundation than expected (real data, not mocks). `stage_transitions` supports true funnel + dwell-time + stalled-job detection. `build_health_prompt` is a ready-made written-insight generator. **Source effectiveness is blocked** on a missing `source` field.
- **Phase 6** — Start with items 1, 9, 12 in §8 (code-splitting, jobs-list N+1, missing indexes); highest impact for least risk.
- **Phase 7** — Sweep §9.

---

## 11. Open questions — ANSWERED 2026-07-23

| # | Question | Decision |
|---|---|---|
| 1 | `git init`? | ✅ **Yes.** Done — repo initialised on `main`, baseline commit `11383e9`. `.env` files verified untracked. |
| 2 | Install Node? | ✅ **Yes.** Node v24.18.0 + npm 11.16.0 were already on the machine (just off my shell's PATH); yarn 1.22.22 installed to match `packageManager`. Frontend is now buildable/verifiable. |
| 3 | Rotate Atlas password + `JWT_SECRET`? | ❌ **No — do not rotate any existing key or password.** Owner's decision, made with the §6 exposure in view. §6 stays on record as a known accepted risk; I will not rotate anything. |
| 4 | Firebase migration strategy? | ✅ **Firebase-signin bridged to the existing JWT.** Firebase handles credentials/signup/reset; the backend continues to mint and verify its own JWTs. Avoids forcing password resets on existing users. |
| 5 | Candidate `source` field? | ✅ **Add it.** Schema + capture UI. Unblocks Phase 5 source-effectiveness analytics. |
| 6 | Remove `backend/data/uploads/*.pdf`? | ❌ **Keep the files.** No deletion. |
| 7 | Render persistent disk? | ✅ **Not needed — confirmed by code trace.** See §8.14: resume *text* is in MongoDB and drives every feature; the PDF binaries on disk are never read back. Two follow-on notes recorded there. |

---

## 12. Backlog / Not in scope (parked)

Everything in §9 not already claimed by a phase: shadcn cleanup, duplicate toast system, `requirements.txt` dedupe, `lifespan` migration, `Modal` focus trap, error boundaries, `update_job` falsy-value handling, `PRD.md` refresh, unused-dependency pruning.
