import os
from pathlib import Path
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]

# Collections
users = db.users
jobs = db.jobs
candidates = db.candidates
stage_transitions = db.stage_transitions
ai_usage_log = db.ai_usage_log
login_activity = db.login_activity

# Upload directory
UPLOAD_DIR = ROOT_DIR / "data" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


async def ensure_indexes() -> None:
    await users.create_index("email", unique=True)
    await jobs.create_index("user_id")
    await candidates.create_index("job_id")
    await stage_transitions.create_index("candidate_id")
    await ai_usage_log.create_index("user_id")
    await login_activity.create_index("user_id")
