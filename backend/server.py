import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, APIRouter, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.cors import CORSMiddleware

from database import ensure_indexes, UPLOAD_DIR
from seed import seed_if_empty

import ai_service
import routes_auth
import routes_jobs
import routes_candidates
import routes_ai
import routes_dashboard
import routes_admin
import routes_reports
import routes_feedback


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# ----------------------------
# CORS configuration
# ----------------------------
# Browsers reject `Access-Control-Allow-Origin: *` together with
# `Allow-Credentials: true`, so the previous default of "*" with credentials on
# was a silent trap: it worked only because CORS_ORIGINS happened to be set.
# Credentials are now enabled only when explicit origins are listed.
_raw_origins = os.environ.get("CORS_ORIGINS", "").strip()
CORS_ORIGINS = [o.strip() for o in _raw_origins.split(",") if o.strip()]
ALLOW_CREDENTIALS = bool(CORS_ORIGINS) and "*" not in CORS_ORIGINS

if not CORS_ORIGINS:
    CORS_ORIGINS = ["*"]
    logger.warning(
        "CORS_ORIGINS is not set — allowing all origins with credentials disabled. "
        "Set it to your frontend URL(s) in production."
    )


# ----------------------------
# Startup / shutdown
# ----------------------------
# Seeding writes demo users, jobs and candidates. It only acts on a completely
# empty users collection, but that is a weak guarantee for a production
# database, so it can be switched off outright.
SEED_ON_STARTUP = os.environ.get("SEED_ON_STARTUP", "true").strip().lower() not in (
    "0", "false", "no", "off",
)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Replaces the deprecated @app.on_event("startup") hook."""
    await ensure_indexes()
    if SEED_ON_STARTUP:
        await seed_if_empty()
    else:
        logger.info("SEED_ON_STARTUP is disabled — skipping demo data seeding")
    logger.info(
        "HireFlow API started (indexes ensured, seeding %s, AI %s)",
        "enabled" if SEED_ON_STARTUP else "disabled",
        "configured" if ai_service.is_configured() else "NOT configured",
    )
    yield


app = FastAPI(title="HireFlow API", lifespan=lifespan)

api_router = APIRouter(prefix="/api")


# ----------------------------
# Error handling
# ----------------------------
@app.exception_handler(ai_service.AIUnavailable)
async def _ai_unavailable(_request: Request, exc: ai_service.AIUnavailable):
    """Surface a clear 503 rather than a 500 when the AI provider is unset."""
    return JSONResponse(status_code=503, content={"detail": str(exc)})


# ----------------------------
# ROOT
# ----------------------------
@app.get("/")
async def root():
    return {"status": "HireFlow API running", "docs": "/docs", "api": "/api"}


@app.get("/health")
async def health():
    return {"status": "ok", "ai_configured": ai_service.is_configured()}


# ----------------------------
# API ROUTES
# ----------------------------
@api_router.get("/")
async def api_root() -> dict:
    return {"message": "HireFlow API running under /api"}

api_router.include_router(routes_auth.router)
api_router.include_router(routes_jobs.router)
api_router.include_router(routes_candidates.router)
api_router.include_router(routes_ai.router)
api_router.include_router(routes_dashboard.router)
api_router.include_router(routes_admin.router)
api_router.include_router(routes_reports.router)
api_router.include_router(routes_feedback.router)

app.include_router(api_router)


# ----------------------------
# CORS
# ----------------------------
app.add_middleware(
    CORSMiddleware,
    allow_credentials=ALLOW_CREDENTIALS,
    allow_origins=CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ----------------------------
# STATIC FILES (UPLOADS)
# ----------------------------
# NOTE: this serves stored resume PDFs with no authentication — anyone holding
# a URL can fetch one. Filenames are unguessable UUIDs and nothing in the app
# links here (the UI renders `resume_text` from the database instead), so the
# practical risk is low, but it is an unauthenticated path to candidate PII.
# Left in place pending a decision; see PROGRESS.md.
if UPLOAD_DIR and Path(UPLOAD_DIR).exists():
    app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")
