# HireFlow — Project Plan (Phases 0–7)

**Engagement:** Surgical upgrade of a live, working HR SaaS product. Extend and harden — not a rewrite.
**Project root:** `.../Hireflow/hireflow-main 22072027/hireflow-main 22072027/`
**Started:** 2026-07-23

---

## Standing rules (apply to every phase)

- [ ] **Read before editing.** Never edit an unopened file. Grep to confirm existing patterns before adding more of the same.
- [ ] **Preserve the design system.** Reuse existing tokens (`navy`/`indigo`/`amber` AI accent), spacing, `ui.jsx` primitives. No new visual language for new pages.
- [ ] **No unrelated refactors.** Log strays under "Backlog / Not in scope" in PROGRESS.md.
- [ ] **Small, reviewable commits** per logical unit — *unblocked: repo initialised on `main`, baseline `11383e9`.*
- [ ] **Secrets discipline.** Follow Phase 2 credential instructions exactly; they override generic env-file instinct.
- [ ] **Ask before destructive actions** — deleting files, dropping DB fields, removing routes. Confirm in writing first.
- [ ] **Persist memory.** Keep PROJECT_PLAN.md + PROGRESS.md current. Read both at the start of every session.
- [ ] **Stop at phase boundaries.** Build/sanity-check, update PROGRESS.md, summarise, then wait for "continue".
- [ ] **Universal-niche mandate.** All copy, labels, placeholders and AI prompts must work for nurses, warehouse staff, chefs, drivers, teachers, engineers alike — never assume "office job". Fix violations wherever found, even outside the current phase.

---

## Phase 0 — Discovery & Audit (read-only) ✅ COMPLETE

- [x] Map repo: frameworks, folders, routing, state, styling
- [x] Trace auth flow end to end; confirm the admin-signup bug
- [x] Locate + quote verbatim all AI prompt templates
- [x] Locate Reports/Dashboard; identify the 4 graphs and their data sources
- [x] Locate demo account and its public exposure
- [x] Log performance bottlenecks (code inspection)
- [x] Log obvious bugs / dead code
- [x] Write AUDIT.md
- [x] Write PROJECT_PLAN.md
- [x] Write PROGRESS.md
- [ ] **Await go-ahead** ⬅ *currently here*

**Key findings:** admin escalation via `role` on public signup (3 code paths); admin creds printed on the public login page; live Atlas + JWT secrets in `backend/.env`; backend won't boot locally (`GROQ_API_KEY` vs `GROK_API_KEY`); Reports data is **real, not mocked** (premise correction); no Node/npm and no git repo on this machine.

---

## Phase 1 — Public Marketing Site ⬜ NOT STARTED

Public, unauthenticated routes funnelling into the existing auth flow. Must not touch app internals.

- [ ] **Restructure the `path="*"` catch-all** in `App.js` first — it currently swallows all unknown routes to `/dashboard` and would eat every public route
- [ ] Persistent public header (Register / Login in the corner) + public footer
- [ ] **Home** — hero, problem statement, feature highlights (JD enhancement, AI resume ranking, screening questions, comparison, reject/select email automation, dashboard/analytics), social proof, CTA
- [ ] **Pricing** — clearly "in testing / early access". No implication of live billing
- [ ] **About** — mission/story, clearly-marked placeholder copy for personal/company facts
- [ ] **Careers** — generic "we're hiring" placeholder, structure only
- [ ] **Reviews/Testimonials** — data-driven from an array of testimonial objects; marked placeholders for now
- [ ] **Privacy Policy** — real, complete, SaaS-handling-candidate-PII appropriate (data collected, third parties, candidate data handling, privacy contact email). Marked as requiring your legal review
- [ ] **Coming Soon** — teaser panel (icons + short descriptions): resume database integrations, email account connection, bulk email, calendar interview scheduling, external job-portal posting
- [ ] All marketing copy **role-switch-aware** (rotate/generically reference nursing, warehouse, trades, hospitality, engineering — never corporate-only)
- [ ] `React.lazy` all marketing routes so they stay out of the authenticated app bundle
- [ ] Verify responsive behaviour (desktop + mobile)
- [ ] Verify no leakage into or interference with authenticated routing/guards
- [ ] Update PROGRESS.md, summarise, **stop**

**Note:** `/` currently redirects to `/dashboard`. Marketing Home takes over `/` — confirm before switching.

---

## Phase 2 — Auth Overhaul: Firebase, Role Lockdown, Hardcoded Admin ⬜ NOT STARTED

- [x] **Migration strategy decided: Firebase-signin bridged to the existing JWT.** Firebase owns credentials, signup, verification and password reset. On successful Firebase sign-in the frontend exchanges the Firebase ID token at a new backend endpoint, which verifies it, looks up/creates the matching `users` record, and returns **the app's existing JWT** — so `AuthContext`, the axios interceptor, `get_current_user` and every existing route keep working unchanged. Existing users are **not** forced to reset passwords.
  - [ ] Add `firebase-admin` to `requirements.txt` (absent today) to verify Firebase ID tokens server-side
  - [ ] New endpoint (e.g. `POST /api/auth/firebase`) — verify ID token → find-or-create user → mint existing JWT
  - [ ] Keep the legacy bcrypt login path working during transition (existing accounts)
- [ ] **Close every admin-escalation path:**
  - [ ] `models.py` — remove `role` from `SignupRequest`
  - [ ] `routes_auth.py:28` — public signup hardcoded to `"hr"`, never client-settable
  - [ ] `Signup.jsx` — remove the Admin option / the whole role `<select>`
  - [ ] Audit `routes_admin.py PUT /users/{id}/role` — decide whether it survives
  - [ ] Audit every remaining path that can write `role` (API, forms, DB defaults)
- [ ] **Hardcoded admin identity:**
  - [ ] Git-ignored `admin.credentials.json` (or `server/config/admin.credentials.py`) holding the admin's Firebase UID / email
  - [ ] Committed `admin.credentials.example.json` with placeholder values
  - [ ] Add to `.gitignore` (note: `*credentials.json*` is already covered — verify)
  - [ ] Backend grants admin **only** on a match against this file. Never a client-settable field
  - [ ] Admin-check logic **server-side only** — nothing in the frontend bundle (`REACT_APP_*` is public)
- [ ] **Firebase Authentication:**
  - [ ] ⚠️ **Use `process.env.REACT_APP_FIREBASE_*` — this is CRA/craco, NOT Vite.** The `import.meta.env.VITE_*` snippet in the brief does not apply
  - [ ] Email/password signup + verification email if feasible
  - [ ] Login
  - [ ] Forgot Password via `sendPasswordResetEmail`
  - [ ] Friendly error states in existing UI style (wrong password, user not found, weak password, email already in use) — never raw Firebase error strings
  - [ ] Wire Firebase auth state into the **existing** AuthContext/role logic — no parallel system
  - [ ] Backend: verify Firebase ID tokens (needs `firebase-admin`, currently absent from `requirements.txt`)
- [ ] **Admin panel** (reachable only by the hardcoded identity):
  - [ ] Platform stats: total profiles/candidates, open vs closed postings, total HR users, signups over time
  - [ ] User management: list HR accounts, flag/deactivate
  - [ ] Resume access: view stored resume JSON for support/moderation
  - [ ] Visually consistent but clearly distinct (Admin badge/theme accent)
  - *(Much of this already exists in `pages/admin/*` — extend rather than rebuild)*
- [ ] **Demo account:** keep it and its seed data fully working; remove every public-facing hint — **`Login.jsx:106-110` prints both demo logins including the admin's**
- [ ] Update PROGRESS.md, summarise (exact env var names, Firebase console checks needed), **stop**

---

## Phase 3 — Support / Feedback Loop ⬜ NOT STARTED

Target inbox: **connecting800@gmail.com**

- [ ] In-dashboard entry point: "Send Feedback / Report an Issue / Suggest a Feature"
- [ ] Form: type (review / bug / feature request), subject, message body, auto-attached account email
- [ ] Delivery consistent with the existing stack — no heavy new email infra if a simpler option fits (note: **no email infrastructure exists today**; `boto3` is installed but unused)
- [ ] Proper from/reply-to headers so it doesn't trivially hit spam
- [ ] Success/failure toast (use `sonner`, the app's real toast system)
- [ ] Persist submissions to the DB as well, so the Phase 2 admin panel can list them later
- [ ] Update PROGRESS.md, summarise (any third-party credentials you must provision), **stop**

---

## Phase 4 — Universal-Niche Audit of All AI Prompts ⬜ NOT STARTED

Source: AUDIT.md §3 (all 7 prompts quoted verbatim).

- [ ] **JD enhancement** — hardcoded section list is white-collar shaped; needs shift pattern, certifications/licences, physical requirements, pay rate, site/location where relevant
- [ ] **Resume ranking** — drop `"technical recruiter"` framing; **remove `"job hopping"` as a stock red flag** (systematically penalises hospitality, construction, agency nursing, gig, seasonal work)
- [ ] **Screening questions** — the closed `type` enum (`Technical`/`Behavioral`/`Experience`/`Culture Fit`) is the tightest constraint; needs Safety, Certification/Licensing, Availability & Shifts, Compliance. **The one place a schema change may be genuinely necessary — check UI rendering first**
- [ ] **Reject/select email** — fixed "professional, warm" register; prompt is starved of context (never sees the JD or industry)
- [ ] Also review: compare, deep summary, pipeline health (broadly neutral)
- [ ] Instruct models to **infer** tone/skills/screening focus from the given job title, description and industry rather than a fixed template
- [ ] **Preserve response schemas exactly** so existing UI rendering doesn't break
- [ ] Fix niche bias found outside the prompts: `seed.py` (all-tech demo data, "TechCorp"/"B.S. Computer Science"), placeholder copy (`you@company.com`, `Acme Corp`), `department`-only job grouping, Login brand-panel copy
- [ ] Test each rewritten prompt against ≥3 very different postings (e.g. ICU Registered Nurse, Warehouse Forklift Operator, Backend Software Engineer)
- [ ] Paste sample outputs into PROGRESS.md
- [ ] Update PROGRESS.md, summarise, **stop**

---

## Phase 5 — Reports Page Overhaul ⬜ NOT STARTED

⚠️ **Premise correction:** the current 4 graphs are **real data, not random placeholders** (AUDIT.md §4). This is an upgrade of working analytics. The only fake number is `est_completion` (hardcoded `now + 14 days × remaining`).

- [ ] Time-to-hire per posting + average across postings *(already exists — improve)*
- [ ] Pipeline conversion funnel (applied → screened → interviewed → offered → hired) with **per-stage drop-off rates** — `stage_transitions` has a full timestamped audit trail to support this
- [ ] Source effectiveness — ✅ **unblocked, approved.** Add a `source` field to candidates (schema default + capture UI on upload; backfill existing rows as `Unknown`), then report which channel yields more qualified/hired candidates
- [ ] Open vs closed postings over time; **flag aging open postings** with no movement
- [ ] Auto-generated plain-language written insight section under the charts — **`build_health_prompt` already does exactly this and can be reused**
- [ ] Replace the fabricated `est_completion` estimate with something defensible or remove it
- [ ] Keep `recharts` — do not introduce a second charting library
- [ ] Graceful empty/low-data states (new accounts must not see broken/empty charts)
- [ ] Update PROGRESS.md, summarise, **stop**

---

## Phase 6 — Performance Pass ⬜ NOT STARTED

Checklist seeded from AUDIT.md §8, highest impact first.

- [ ] **Code-splitting / lazy-loading routes** — `App.js` statically imports all 12 pages incl. the 5 admin pages; every HR user downloads the admin panel
- [ ] **Jobs-list N+1** — `routes_jobs.py:28-29` runs one query per job; 30 postings = 31 queries per page load. Likely a direct cause of the reported slowness
- [ ] **Missing DB indexes** — nothing on `candidates.stage`, `candidates.uploaded_at`, `jobs.status`, `jobs.created_at`
- [ ] Time-to-hire N+1 (`routes_reports.py:33`) and bulk-stage N+1 (`routes_candidates.py:168`)
- [ ] Prune unused heavy deps (`@tanstack/react-query`, `swr`, `framer-motion`, `embla-carousel`, `vaul`, ~40 unused shadcn components)
- [ ] Check whether `lodash` is actually imported anywhere (the version pin is fine — `4.18.1` is real and current; my earlier "does not exist" note was wrong and is retracted)
- [ ] Move the render-blocking Google Fonts `@import` out of `index.css` into `<link>` tags
- [ ] Memoize expensive renders (Kanban board, resume lists, comparison views); stabilise the `AuthContext` value object
- [ ] Reduce the boot auth waterfall (render → `/auth/me` → page fetch)
- [ ] Cache AI results so unchanged inputs don't re-run ranking
- [ ] Image optimization / lazy-loading where applicable
- [ ] Measure before/after (load time, bundle size) — record in PROGRESS.md
- [ ] Update PROGRESS.md, summarise with numbers, **stop**

---

## Phase 7 — Bug Bash & Final QA ⬜ NOT STARTED

- [ ] Fix remaining minor bugs from AUDIT.md §9 / PROGRESS.md backlog
- [ ] Fix the `GROQ_API_KEY` / `GROK_API_KEY` mismatch + wrong `AI_MODEL` (AUDIT.md §7) *(may be pulled earlier)*
- [ ] Fix the `allow_credentials=True` + `allow_origins="*"` CORS trap
- [ ] Dedupe `requirements.txt`; drop unimported packages
- [ ] Full click-through QA: signup → login → forgot password → hiring flow → reports → admin panel → marketing pages → coming soon → feedback form, on desktop **and** one mobile viewport
- [ ] Confirm the demo account works directly but is exposed nowhere (nav, footer, login page, marketing site)
- [ ] Confirm colour/design consistency across every page added in Phases 1–5
- [ ] Final PROGRESS.md + PROJECT_PLAN.md update; add a "what I'd tackle next" list

---

## Cross-phase decisions — ALL RESOLVED 2026-07-23

1. ✅ **git** — initialised on `main`; baseline commit `11383e9`. `.env` verified untracked. Commit per logical unit from Phase 1 on.
2. ✅ **Toolchain** — Node v24.18.0 + npm 11.16.0 (already installed, was off-PATH) + yarn 1.22.22. Frontend is buildable and verifiable locally.
3. ❌ **No key/password rotation.** Owner's explicit decision with the exposure in view. The `backend/.env` Atlas password and `JWT_SECRET` stay as-is. **Do not rotate anything.** Recorded as accepted risk in AUDIT.md §6 — do not re-litigate.
4. ✅ **Firebase-signin bridged to the existing JWT** (not a full replacement). Firebase owns credentials, signup, password reset; the backend keeps minting/verifying its own JWTs. No forced password resets for existing users.
5. ✅ **Add a candidate `source` field** — schema + capture UI. Phase 5 source-effectiveness is unblocked.
6. ✅ **Keep `backend/data/uploads/*.pdf`.** No deletion.
7. ✅ **No Render persistent disk needed** — verified by code trace (AUDIT.md §8.14). Resume text lives in MongoDB and drives every feature; PDF binaries are never read back. Two follow-on notes recorded there (a future PDF-viewer feature would need object storage; `/uploads` is an unauthenticated static mount).
