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


class OnboardingCheck(BaseModel):
    """The login page asks this before showing a password field, so it can offer
    first-time password setup to an admin-approved recruiter, a normal sign-in to
    an existing account, or a clear 'ask your admin' message otherwise."""
    email: EmailStr


class FirebaseAuthRequest(BaseModel):
    """Exchange a Firebase ID token for this app's own JWT."""
    id_token: str
    name: Optional[str] = None
    company: Optional[str] = None


# ---------- Organisation / members (Cycle 2) ----------
#
# NOTE: This release does NOT send invitation emails. An admin ("Manager")
# stores approved recruiter emails (typed one at a time or pasted/bulk-uploaded);
# only those emails may join the org, and each approved user sets their own
# password the first time they sign in. The emailed-token invite machinery
# (invites.py, the `invitations` collection) is kept dormant for a future cycle
# where admins purchase plans and formal invites return.
class MemberCreate(BaseModel):
    """Admin approves a single recruiter email. No role field — approved users
    are always recruiters; admins arrive only through public sign-up."""
    email: EmailStr
    name: Optional[str] = None


class BulkMemberCreate(BaseModel):
    """Admin approves many recruiter emails at once. `text` is whatever they
    typed or pasted (or a CSV's contents) — the server splits it on commas,
    semicolons, whitespace and newlines, then validates and de-duplicates."""
    text: str


class MemberStatusUpdate(BaseModel):
    status: str  # "active" (reactivate) | "disabled" (suspend)


class MemberRemove(BaseModel):
    """Remove an active member, reassigning their work first so nothing is
    orphaned. `reassign_to` is another recruiter's id, or null to leave their
    jobs unassigned and their candidates attributed to them."""
    reassign_to: Optional[str] = None


class AssignmentUpsert(BaseModel):
    """A manager assigns a job to a recruiter with per-assignment permissions,
    targets and a deadline. Idempotent on (job, user): sending it again edits the
    existing assignment. `permissions` is a subset of the 8 flags — unknown keys
    are ignored server-side; omitted flags fall back to the recruiter defaults."""
    user_id: str
    permissions: Optional[dict] = None
    shortlist_target: Optional[int] = None
    sourced_target: Optional[int] = None
    interview_target: Optional[int] = None
    deadline: Optional[str] = None
    note: Optional[str] = None
    status: Optional[str] = None  # "active" | "paused"


class BulkAssignmentUpsert(BaseModel):
    """Assign one job to several recruiters at once with the same permissions,
    targets and deadline. Idempotent per (job, user), like the single upsert."""
    user_ids: List[str]
    permissions: Optional[dict] = None
    shortlist_target: Optional[int] = None
    sourced_target: Optional[int] = None
    interview_target: Optional[int] = None
    deadline: Optional[str] = None
    note: Optional[str] = None
    status: Optional[str] = None


class JDOverrideUpdate(BaseModel):
    """A recruiter's personal job-description override (needs can_edit_jd). Never
    written back to the shared job — only this recruiter sees/uses it."""
    jd_text: str
    jd_enhanced: Optional[str] = None


# ---------- Jobs ----------
class JobCreate(BaseModel):
    title: str
    department: Optional[str] = None
    openings_needed: int = 1
    jd_text: Optional[str] = None
    # The AI-enhanced description is stored ALONGSIDE the original, never in
    # place of it, so the job page can show both an "Original" and an
    # "Enhanced" tab. The original jd_text remains what the user actually typed.
    jd_enhanced: Optional[str] = None
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


class StructureRequest(BaseModel):
    candidate_id: str
    refresh: bool = False  # regenerate even if a cached structure exists


# ---------- Feedback ----------
class FeedbackRequest(BaseModel):
    type: str  # "review" | "bug" | "feature"
    subject: str = Field(min_length=1, max_length=200)
    message: str = Field(min_length=1, max_length=5000)


class FeedbackStatusUpdate(BaseModel):
    status: str  # "new" | "read" | "actioned"
