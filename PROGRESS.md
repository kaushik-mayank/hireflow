# HireFlow — Progress Log

> **Resuming a session? Read this file and PROJECT_PLAN.md first, then AUDIT.md for detail.**
> Newest entries at the top.

**Project root:** `.../Hireflow/hireflow-main 22072027/hireflow-main 22072027/` (note the doubled folder name — the *inner* one is the real root)
**Current phase:** Phase 0 complete → awaiting go-ahead for Phase 1
**Last updated:** 2026-07-23

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

1. **`git init`?** No repo exists, so the "small, reviewable commits" rule can't be honoured. Shall I initialise one and commit the current state as a baseline?
2. **Install Node 18+/yarn?** Otherwise I write frontend code unverified and you run the builds.
3. **Rotate the Atlas password and `JWT_SECRET` now?** I'd put this ahead of all phase work.
4. **Firebase strategy** — full replacement of bcrypt+JWT, or Firebase-signin bridged to the existing JWT? Existing bcrypt passwords **cannot** transfer to Firebase, so a full swap forces password resets for current users. Shapes all of Phase 2; I have a recommendation ready.
5. **Add a candidate `source` field?** (unblocks Phase 5 source effectiveness)
6. **Are `backend/data/uploads/*.pdf` real candidate resumes?** Three PDFs sit in the tree. If real, that's PII in the repo — removal needs your approval.
7. **Is a Render persistent disk mounted for `backend/data/uploads`?** If not, uploaded resumes are silently lost on every deploy.

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
- **`<Route path="*">` → `/dashboard`** swallows all unknown routes — **must be restructured before Phase 1** or it eats every marketing route
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
- **`lodash: "4.18.1"` does not exist** (lodash tops out at 4.17.x) — a clean install may fail outright. Verify before any dependency work
- **Resume PDFs written to Render's ephemeral local disk** — likely silent data loss on deploy unless a disk is mounted
