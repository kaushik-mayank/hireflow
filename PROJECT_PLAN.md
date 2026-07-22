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

## Phase 1 — Public Marketing Site ✅ COMPLETE (2026-07-23)

Commits `dc828fb`, `b682b78`, `ab61af7`. Only pre-existing file touched: `App.js`.

- [x] **Restructured the `path="*"` catch-all** — now an auth-aware 404 instead of a silent `/dashboard` redirect
- [x] Persistent public header (Register / Login in the corner, dashboard link when signed in) + footer, with mobile menu
- [x] **Home** — hero with rotating job titles, problem, all 6 feature highlights, how-it-works, industries, social proof, roadmap teaser, CTA
- [x] **Pricing** — labelled early access; every tier shows an unset price, no billing implied
- [x] **About** — mission/story/values, company facts marked as placeholders
- [x] **Careers** — structure only; `OPEN_ROLES` empty so it renders an honest no-vacancies state
- [x] **Reviews** — fully data-driven from `TESTIMONIALS`; self-deriving industry filter + average rating
- [x] **Privacy Policy** — complete 15-section policy incl. candidate PII, Groq AI disclosure, sub-processors, retention, data rights; flagged for legal review
- [x] **Coming Soon** — 8-item roadmap teaser, icons + descriptions, no form
- [x] Copy is **role-switch-aware** — 10 rotating roles, 12-industry section, cross-sector testimonials
- [x] `React.lazy` on all marketing routes — verified 0 marketing strings in `main.js`
- [x] Verified no interference with authenticated routing/guards — all three guards unchanged
- [ ] ⚠️ **Responsive behaviour written but NOT visually verified** — no browser check was possible; carry into Phase 7 QA
- [x] Updated PROGRESS.md

**Behaviour changes to be aware of:** `/` now serves marketing Home (was → `/dashboard`); `*` now renders a 404 (was → `/dashboard`).

**Carried forward:** placeholder copy in About/Careers/Pricing/Privacy/testimonials needs your real content; contact addresses are all `@example.com`.

---

## Phase 2 — Auth Overhaul: Firebase, Role Lockdown, Hardcoded Admin ✅ COMPLETE (2026-07-23)

Commits `0c5c4ed` + follow-up. All items below done except where noted.

**Still needs you (see PROGRESS.md Session 4):**
- Set `FIREBASE_PROJECT_ID` on the Render **backend** service (not a secret, but required for `/auth/firebase` to work).
- Set `ADMIN_EMAILS` on the Render **backend** service — the git-ignored credentials file does not exist there, so **the admin panel is unreachable in production until this is set**.
- Confirm `REACT_APP_FIREBASE_*` are set on the Render **frontend** service *before* the build — CRA inlines them at build time.
- Firebase console: enable Email/Password sign-in, add your Render domain to Authorised domains, review the verification and password-reset email templates.
- Edit `backend/admin.credentials.json` — it currently points at `admin@hireflow.com` so the panel keeps working; that password is publicly known from the old login page.
- **Nothing Firebase-related has been executed.** Test sign-up, sign-in and password reset end to end.



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

## Phase 3 — Support / Feedback Loop ✅ COMPLETE (2026-07-23)

Target inbox: **connecting800@gmail.com**

- [x] In-dashboard entry point — `/feedback`, "Support" section in the sidebar
- [x] Form: type (review / bug / feature request), subject, message body, **auto-attached account email**
- [x] Delivery via stdlib `smtplib` — **zero new dependencies**, provider-agnostic
- [x] `From` = authorised sender (SPF/DKIM safe), `Reply-To` = submitter, explicit `Date` + `Message-ID`
- [x] Success/failure toast via `sonner`; distinguishes "received" from "sent" when SMTP is down
- [x] Persisted to MongoDB **before** sending, so a mail failure never loses a message
- [x] Admin listing at `/admin/feedback` with filters, read/actioned workflow and a mailto reply
- [x] Rate limited to 15/user/hour
- [x] Updated PROGRESS.md

**Credentials you must provision** (Render backend service): `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`. Gmail needs an **App Password** with 2FA on. Until set, feedback is captured but not emailed, and the admin page says so.

**Not verified:** the endpoint has never run and no email has actually been sent.

---

## Phase 4 — Universal-Niche Audit of All AI Prompts ✅ COMPLETE (2026-07-23)

All 7 prompts rewritten; schemas unchanged; 26 guard tests added. Demo seed data replaced with three cross-industry roles.

⚠️ **One item outstanding, blocked on you:** live sample outputs across the 3 niches were not produced — no working Groq key in this environment. Run `python backend/tests/prompt_samples.py` with `GROQ_API_KEY` set and paste the result into PROGRESS.md. Details in Session 6.

✅ **Resolved:** the screening-question enum needed **no** schema change — the UI renders `q.type` as free text, so widening the vocabulary was safe.



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

## Phase 5 — Reports Page Overhaul ✅ COMPLETE (2026-07-23)

Funnel with drop-off, time-to-hire + trend, source effectiveness, aging postings, open/closed over time, rule-based insights. `source` field added. Fabricated `est_completion` removed. N+1 fixed. 31 new tests.

---

## 🔑 Standing rule added 2026-07-23 — JD-driven AI, no hardcoded niches

**Applies to all future work.** AI evaluation criteria must be **derived from the job description at runtime**, never from occupations, industries or categories written into the code.

- Every evaluative prompt carries `JD_ANALYSIS_DIRECTIVE` (domain, function, seniority, engagement, hard requirements, tools, context) and judges against the profile it derives.
- Screening-question `type` labels are free-form, in the role's own vocabulary — not a list.
- Certifications, licences and tools are extracted dynamically, in any field.
- Tenure is judged against derived engagement norms — a short stint means different things for a contractor than an executive.
- **No prompt template or system message may name a specific occupation.** Enforced by tests.
- The 3 original niches are regression fixtures only; 11 industries are exercised. **Adding an industry must never require a code change.**



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

## Phase 6 — Performance Pass ✅ COMPLETE (2026-07-23)

**`main.js` 246.15 kB → 108.37 kB gzip (−56%).** Route-level code splitting (recharts and the admin panel now on-demand), unused react-query provider removed, double font loading fixed, `AuthContext` memoised. Backend: `GET /jobs` N+1 removed (31 round-trips → 2), bulk-stage N+1 removed (200+ → a handful), indexes added for the real access paths.

**Awaiting your call:** deleting the orphaned `components/ui/` folder + pruning ~17 unused dependencies. Neither shrinks the bundle (unreachable modules aren't bundled) — it's repo hygiene and install speed only.

**Carried to Phase 7:** Kanban render memoisation — needs a browser profile to do correctly rather than speculatively.



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
- [ ] **Visually verify the Phase 1 marketing pages** — they were built and compile clean but were never opened in a browser (responsive breakpoints, spacing, hero rotation)
- [ ] Replace Phase 1 placeholder copy: About story/values, Careers content, Pricing tiers, testimonials, and all four `@example.com` contact addresses
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
