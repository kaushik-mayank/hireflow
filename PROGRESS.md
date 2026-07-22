# HireFlow — Progress Log

> **Resuming a session? Read this file and PROJECT_PLAN.md first, then AUDIT.md for detail.**
> Newest entries at the top.

**Project root:** `.../Hireflow/hireflow-main 22072027/hireflow-main 22072027/` (note the doubled folder name — the *inner* one is the real root)
**Current phase:** 🏁 **Phases 0–7 complete.** Outstanding items are listed under "Handover" below.
**Last updated:** 2026-07-23

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
