from sqlalchemy import Column, Integer, String, Text, Float, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    phone = Column(String(30), nullable=True)
    district = Column(String(100), nullable=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False)  # citizen, university, industry, govt, expert, admin
    organization = Column(String(150), nullable=True)  # for university/industry
    primary_sector = Column(String(80), nullable=True)
    expertise = Column(Text, nullable=True)
    support = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    challenges = relationship("Challenge", back_populates="citizen")
    solutions = relationship("Solution", back_populates="university")


class OTPStore(Base):
    __tablename__ = "otp_store"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(100), unique=True, index=True, nullable=False)
    otp = Column(String(6), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)


class Challenge(Base):
    __tablename__ = "challenges"

    id = Column(Integer, primary_key=True, index=True)

    # NULLABLE for guest submissions (guests don't have a user ID)
    citizen_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    # NEW: display name for guests (e.g., "Guest User")
    submitter_name = Column(String(100), nullable=True)

    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)
    source_language = Column(String(10), default="en", nullable=False)
    category = Column(String(50), nullable=True)
    priority_score = Column(Integer, default=50)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    voice_url = Column(String(255), nullable=True)

    # CHANGED to Text (was String(255)) — supports multiple comma-separated files
    image_url = Column(Text, nullable=True)

    status = Column(String(30), default="SUBMITTED")
    # SUBMITTED → AI_PROCESSED → PUBLISHED → IN_PROGRESS → PILOT → DEPLOYED

    duplicate_of = Column(Integer, ForeignKey("challenges.id"), nullable=True)
    is_genuine = Column(Boolean, nullable=True)
    authenticity_score = Column(Float, nullable=True)
    authenticity_evidence = Column(Text, nullable=True)
    matched_universities = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    citizen = relationship("User", back_populates="challenges")
    solutions = relationship("Solution", back_populates="challenge")


class Solution(Base):
    __tablename__ = "solutions"

    id = Column(Integer, primary_key=True, index=True)
    challenge_id = Column(Integer, ForeignKey("challenges.id"), nullable=False)
    university_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String(200), nullable=False)
    proposal = Column(Text, nullable=False)
    ai_score = Column(Float, nullable=True)
    ai_explanation = Column(Text, nullable=True)
    expert_score = Column(Float, nullable=True)
    status = Column(String(30), default="PENDING")
    expert_best_selected = Column(Boolean, default=False, nullable=False)
    required_industry_sector = Column(String(80), nullable=True)
    required_expertise = Column(Text, nullable=True)
    required_technology = Column(Text, nullable=True)
    required_support = Column(Text, nullable=True)
    budget_estimate = Column(String(100), nullable=True)
    timeline = Column(String(100), nullable=True)
    team_size = Column(Integer, nullable=True)
    team_members = Column(Text, nullable=True)
    mentor_name = Column(String(150), nullable=True)
    mentor_department = Column(String(100), nullable=True)
    mentor_designation = Column(String(100), nullable=True)
    mentor_employee_id = Column(String(100), nullable=True)
    mentor_email = Column(String(150), nullable=True)
    mentor_contact = Column(String(30), nullable=True)
    project_stage = Column(String(50), default="Development")
    # PENDING → AI_SCREENED → SELECTED → PILOT → DEPLOYED
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    challenge = relationship("Challenge", back_populates="solutions")
    university = relationship("User", back_populates="solutions")


class IndustryPartnership(Base):
    __tablename__ = "industry_partnerships"

    id = Column(Integer, primary_key=True, index=True)
    solution_id = Column(Integer, ForeignKey("solutions.id"), nullable=False)
    industry_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    status = Column(String(30), default="PARTNER_SELECTED")
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class CollaborationWorkspace(Base):
    __tablename__ = "collaboration_workspaces"

    id = Column(Integer, primary_key=True, index=True)
    challenge_id = Column(Integer, ForeignKey("challenges.id"), nullable=False)
    solution_id = Column(Integer, ForeignKey("solutions.id"), nullable=False)
    industry_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    stage = Column(String(50), default="Development")
    progress = Column(Integer, default=0)
    prototype_status = Column(String(40), default="DEVELOPMENT")
    prototype_file_url = Column(String(500), nullable=True)
    prototype_file_name = Column(String(255), nullable=True)
    prototype_feedback = Column(Text, nullable=True)
    prototype_updated_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    government_review_status = Column(String(40), default="PENDING", nullable=False)
    government_review_reason = Column(Text, nullable=True)
    government_review_comment = Column(Text, nullable=True)
    government_reviewed_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    government_reviewed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class WorkspaceMessage(Base):
    __tablename__ = "workspace_messages"

    id = Column(Integer, primary_key=True, index=True)
    workspace_id = Column(Integer, ForeignKey("collaboration_workspaces.id"), nullable=False)
    sender_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    message = Column(Text, nullable=False)
    parent_id = Column(Integer, ForeignKey("workspace_messages.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class WorkspaceTask(Base):
    __tablename__ = "workspace_tasks"

    id = Column(Integer, primary_key=True, index=True)
    workspace_id = Column(Integer, ForeignKey("collaboration_workspaces.id"), nullable=False)
    title = Column(String(200), nullable=False)
    assigned_to = Column(String(120), nullable=True)
    due_date = Column(String(30), nullable=True)
    status = Column(String(30), default="NOT_STARTED")
    progress = Column(Integer, default=0)
    feedback = Column(Text, nullable=True)


class WorkspaceDocument(Base):
    __tablename__ = "workspace_documents"

    id = Column(Integer, primary_key=True, index=True)
    workspace_id = Column(Integer, ForeignKey("collaboration_workspaces.id"), nullable=False)
    uploaded_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    filename = Column(String(255), nullable=False)
    file_url = Column(String(500), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    recipient_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    challenge_id = Column(Integer, ForeignKey("challenges.id"), nullable=True)
    solution_id = Column(Integer, ForeignKey("solutions.id"), nullable=True)
    workspace_id = Column(Integer, ForeignKey("collaboration_workspaces.id"), nullable=True)
    event_type = Column(String(40), nullable=False)
    title = Column(String(200), nullable=False)
    message = Column(Text, nullable=False)
    is_read = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class WorkspaceActivity(Base):
    __tablename__ = "workspace_activities"

    id = Column(Integer, primary_key=True, index=True)
    workspace_id = Column(Integer, ForeignKey("collaboration_workspaces.id"), nullable=False, index=True)
    actor_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    event_type = Column(String(40), nullable=False)
    message = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())