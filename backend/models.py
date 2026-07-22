from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List


# ---------- Auth ----------
class SignupRequest(BaseModel):
    name: str
    email: EmailStr
    password: str = Field(min_length=8)
    company: Optional[str] = None
    # NOTE: `role` is deliberately absent. It used to be accepted here, which
    # let anyone register as an admin. Admin is decided server-side only, by
    # admin_identity.py. Do not add it back.


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class FirebaseAuthRequest(BaseModel):
    """Exchange a Firebase ID token for this app's own JWT."""
    id_token: str
    name: Optional[str] = None
    company: Optional[str] = None


# ---------- Jobs ----------
class JobCreate(BaseModel):
    title: str
    department: Optional[str] = None
    openings_needed: int = 1
    jd_text: Optional[str] = None
    deadline: Optional[str] = None
    status: str = "active"


class JobUpdate(BaseModel):
    title: Optional[str] = None
    department: Optional[str] = None
    openings_needed: Optional[int] = None
    jd_text: Optional[str] = None
    jd_enhanced: Optional[str] = None
    deadline: Optional[str] = None
    status: Optional[str] = None


# ---------- Candidates ----------
class StageUpdate(BaseModel):
    stage: str
    note: Optional[str] = None


class NoteUpdate(BaseModel):
    note: str


class BulkStageUpdate(BaseModel):
    candidate_ids: List[str]
    stage: str
    note: Optional[str] = None


# ---------- AI ----------
class RankRequest(BaseModel):
    job_id: str
    reanalyze: bool = False


class EnhanceJDRequest(BaseModel):
    jd_text: str
    title: str = "this role"


class QuestionsRequest(BaseModel):
    candidate_id: str


class EmailRequest(BaseModel):
    candidate_id: str
    email_type: str  # "interview invite" | "rejection" | etc.


class CompareRequest(BaseModel):
    candidate_id_a: str
    candidate_id_b: str


class SummaryRequest(BaseModel):
    candidate_id: str


# ---------- Feedback ----------
class FeedbackRequest(BaseModel):
    type: str  # "review" | "bug" | "feature"
    subject: str = Field(min_length=1, max_length=200)
    message: str = Field(min_length=1, max_length=5000)


class FeedbackStatusUpdate(BaseModel):
    status: str  # "new" | "read" | "actioned"
