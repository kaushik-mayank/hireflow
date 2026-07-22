# HireFlow — Product Requirements & Build Log

## Original Problem Statement
Build **HireFlow**, an AI-powered hiring platform for HR teams. Takes a team from zero to hired: create jobs with hiring quotas, upload resumes, let AI rank & analyze candidates, move them through a visual Kanban pipeline, generate screening questions, draft emails, and track progress from a single dashboard. AI is embedded at 7 points. Includes a full admin panel (deferred).

## User Choices (locked)
- **Stack:** React (CRA/craco) + FastAPI + MongoDB (instead of the spec's Node/SQLite/Vite)
- **AI:** Claude Sonnet 4.5 (`claude-sonnet-4-5-20250929`) via Emergent Universal LLM key
- **Scope phase 1:** Core hiring flow first; Admin panel + Reports deferred
- **Seed:** demo admin + HR accounts + sample jobs/candidates

## Design System (from user spec)
- Fonts: DM Sans (UI) + DM Mono (resume/JD text)
- Palette: navy #0f1629 sidebar, indigo #4f6ef7 primary, amber AI accents, teal/coral/purple/green for stages
- Layout: fixed 240px navy sidebar, gray-50 content, sticky white topbar, max-width 980px content body
- AI styling convention: amber buttons/badges (#fffbeb bg, #fde68a border, #92400e text)

## Architecture
- **Backend** (`/app/backend`): modular FastAPI — `server.py` (wiring + startup seed + /uploads static), `database.py` (motor, collections, indexes), `auth.py` (bcrypt + JWT 7d), `ai_service.py` (Claude via emergentintegrations + 7 prompt builders + JSON parser + usage logging), `models.py`, `routes_auth.py`, `routes_jobs.py`, `routes_candidates.py` (pypdf parse), `routes_ai.py`, `routes_dashboard.py`, `seed.py`.
- **Frontend** (`/app/frontend/src`): `App.js` (router + Private/Public/Admin routes + sonner Toaster), `api.js` (axios + interceptors), `context/AuthContext.jsx`, `components/Layout.jsx` (Sidebar/Topbar), `components/ui.jsx`, `constants.js`, pages: Login, Signup, Dashboard, Jobs, JobCreate, JobDetail, CandidateBoard (Kanban), CandidateDetail, ComingSoon.
- **DB collections:** users, jobs, candidates, stage_transitions, ai_usage_log, login_activity (uuid string `id` fields, no ObjectId exposure).

## Implemented (2026-05-30)

### Phase 1 — Core hiring flow
- ✅ Auth: signup/login/me, JWT+bcrypt, role (hr/admin), login_activity logging, auth guards
- ✅ Jobs: CRUD, hiring quota, pause/close, activity feed, per-job stats
- ✅ Candidates: multi-PDF upload (pypdf text extraction, name/email/phone regex), list/detail/delete, stage move + transitions, bulk stage move, notes
- ✅ 7 AI features (Claude Sonnet 4.5): rank, enhance-JD, screening questions, draft email, deep summary, compare candidates, pipeline-health
- ✅ Dashboard command center, Kanban board (drag-drop + quota celebration), candidate detail with AI actions
- ✅ Seed demo data; tested 100% (after bulk-stage route fix)

### Phase 2 — Admin panel + Reports (global admin)
- ✅ Admin Dashboard: platform stats (users, active HR 30d, jobs, resumes, AI calls), user-activity table, recent-login feed
- ✅ User Management: search/role/status filters, activate/deactivate (self-deactivation blocked; deactivated users blocked at login), role change hr<->admin
- ✅ Uploaded Resumes: global list across all HR users w/ pagination (50/page), job + HR-user join
- ✅ System Analytics: signups (line), jobs weekly (bar), resumes (area), AI usage (line) via Recharts + metric cards
- ✅ AI Usage: usage log table + summary cards (calls this month, total, most-used feature, most-active user). Dollar cost intentionally omitted per user; token estimates shown.
- ✅ Reports (HR-scoped): Time-to-Hire bar, Stage Funnel, Top Missing Skills bar, Hiring Quota tracker table
- ✅ Tested 100% backend (24/24) + frontend E2E; admin guards verified (HR→403/redirect)

## Backlog / Next Tasks
- **P2:** Edit Job page; in-app PDF viewer/serving in candidate detail; per-file upload progress bars
- **P3:** Real email sending (SendGrid/Resend) from candidate panel; deadline reminders; saved AI-output history; Mongo aggregation pipelines for admin analytics at scale (current in-memory fine <10k)

## Known Notes
- AI endpoints take 3-15s (real Claude calls).
- Reports & /admin/* are intentional "coming soon" placeholders.
