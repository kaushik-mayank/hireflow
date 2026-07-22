import logging
import os
from pathlib import Path

from fastapi import FastAPI, APIRouter
from fastapi.staticfiles import StaticFiles
from starlette.middleware.cors import CORSMiddleware

from database import ensure_indexes, UPLOAD_DIR
from seed import seed_if_empty

import routes_auth
import routes_jobs
import routes_candidates
import routes_ai
import routes_dashboard
import routes_admin
import routes_reports


# ----------------------------
# App Initialization
# ----------------------------
app = FastAPI(title="HireFlow API")

api_router = APIRouter(prefix="/api")


# ----------------------------
# ROOT (IMPORTANT FIX)
# ----------------------------
@app.get("/")
async def root():
    return {
        "status": "HireFlow API running",
        "docs": "/docs",
        "api": "/api"
    }


@app.get("/health")
async def health():
    return {"status": "ok"}


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

app.include_router(api_router)


# ----------------------------
# STATIC FILES (UPLOADS)
# ----------------------------
if UPLOAD_DIR and Path(UPLOAD_DIR).exists():
    app.mount(
        "/uploads",
        StaticFiles(directory=str(UPLOAD_DIR)),
        name="uploads"
    )


# ----------------------------
# CORS
# ----------------------------
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


# ----------------------------
# LOGGING
# ----------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)


# ----------------------------
# STARTUP EVENT
# ----------------------------
@app.on_event("startup")
async def startup() -> None:
    await ensure_indexes()
    await seed_if_empty()
    logger.info("HireFlow API started, indexes ensured, seed checked")
