from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import Optional


# ---------- USER SCHEMAS ----------
class UserCreate(BaseModel):
    name: str
    email: EmailStr
    password: str
    role: str  # citizen, university, industry, govt, expert, admin
    organization: Optional[str] = None
    primary_sector: Optional[str] = None
    expertise: Optional[str] = None
    support: Optional[str] = None


class UserLogin(BaseModel):
    email: str
    password: str


class DemoLoginRequest(BaseModel):
    email: EmailStr


class UserProfileUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    organization: Optional[str] = None
    district: Optional[str] = None


class OTPSendRequest(BaseModel):
    email: EmailStr


class OTPVerifyRequest(BaseModel):
    email: EmailStr
    otp: str
    name: Optional[str] = None


class UserOut(BaseModel):
    id: int
    name: str
    email: EmailStr
    phone: Optional[str] = None
    district: Optional[str] = None
    role: str
    organization: Optional[str] = None
    primary_sector: Optional[str] = None
    expertise: Optional[str] = None
    support: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


# ---------- CHALLENGE SCHEMAS ----------
class ChallengeCreate(BaseModel):
    title: str
    description: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class ChallengeOut(BaseModel):
    id: int
    citizen_id: Optional[int] = None        # ← CHANGED: now optional for guests
    submitter_name: Optional[str] = None    # ← NEW: display name for guests
    title: str
    description: str
    source_language: str = "en"
    category: Optional[str] = None
    priority_score: int
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    voice_url: Optional[str] = None
    image_url: Optional[str] = None
    status: str
    duplicate_of: Optional[int] = None
    is_genuine: Optional[bool] = None
    authenticity_score: Optional[float] = None
    authenticity_evidence: Optional[str] = None
    matched_universities: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


# ---------- SOLUTION SCHEMAS ----------
class SolutionCreate(BaseModel):
    challenge_id: int
    title: str
    proposal: str
    required_industry_sector: Optional[str] = None
    required_expertise: Optional[str] = None
    required_technology: Optional[str] = None
    required_support: Optional[str] = None
    budget_estimate: Optional[str] = None
    timeline: Optional[str] = None
    team_size: Optional[int] = None
    team_members: Optional[str] = None
    mentor_name: Optional[str] = None
    mentor_department: Optional[str] = None
    mentor_designation: Optional[str] = None
    mentor_employee_id: Optional[str] = None
    mentor_email: Optional[EmailStr] = None
    mentor_contact: Optional[str] = None
    project_stage: Optional[str] = "Development"


class SolutionOut(BaseModel):
    id: int
    challenge_id: int
    university_id: int
    title: str
    proposal: str
    ai_score: Optional[float] = None
    ai_explanation: Optional[str] = None
    expert_score: Optional[float] = None
    status: str
    expert_best_selected: bool = False
    required_industry_sector: Optional[str] = None
    required_expertise: Optional[str] = None
    required_technology: Optional[str] = None
    required_support: Optional[str] = None
    budget_estimate: Optional[str] = None
    timeline: Optional[str] = None
    team_size: Optional[int] = None
    team_members: Optional[str] = None
    mentor_name: Optional[str] = None
    mentor_department: Optional[str] = None
    mentor_designation: Optional[str] = None
    mentor_employee_id: Optional[str] = None
    mentor_email: Optional[EmailStr] = None
    mentor_contact: Optional[str] = None
    project_stage: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


# ---------- AUTH SCHEMAS ----------
class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    email: Optional[str] = None