from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os
import httpx

from database import engine, Base
from sqlalchemy import inspect, text
import models  # noqa — needed so tables get created

from routers import users, challenges, solutions, matching, collaboration, notifications, government, i18n

# Create all tables automatically
Base.metadata.create_all(bind=engine)

# Keep existing SQLite installations compatible when new AI analysis fields are added.
with engine.begin() as connection:
    existing_columns = {column["name"] for column in inspect(engine).get_columns("challenges")}
    for column_name, column_type in {
        "source_language": "VARCHAR(10) NOT NULL DEFAULT 'en'",
        "is_genuine": "BOOLEAN",
        "authenticity_score": "FLOAT",
        "authenticity_evidence": "TEXT",
        "matched_universities": "TEXT",
    }.items():
        if column_name not in existing_columns:
            connection.execute(text(f"ALTER TABLE challenges ADD COLUMN {column_name} {column_type}"))

with engine.begin() as connection:
    existing_user_columns = {column["name"] for column in inspect(engine).get_columns("users")}
    for column_name, column_type in {
        "phone": "VARCHAR(30)",
        "district": "VARCHAR(100)",
        "primary_sector": "VARCHAR(80)",
        "expertise": "TEXT",
        "support": "TEXT",
    }.items():
        if column_name not in existing_user_columns:
            connection.execute(text(f"ALTER TABLE users ADD COLUMN {column_name} {column_type}"))

with engine.begin() as connection:
    existing_message_columns = {column["name"] for column in inspect(engine).get_columns("workspace_messages")}
    if "parent_id" not in existing_message_columns:
        connection.execute(text("ALTER TABLE workspace_messages ADD COLUMN parent_id INTEGER"))

with engine.begin() as connection:
    existing_solution_columns = {column["name"] for column in inspect(engine).get_columns("solutions")}
    for column_name, column_type in {
        "required_industry_sector": "VARCHAR(80)",
        "required_expertise": "TEXT",
        "required_technology": "TEXT",
        "required_support": "TEXT",
        "budget_estimate": "VARCHAR(100)",
        "timeline": "VARCHAR(100)",
        "team_size": "INTEGER",
        "project_stage": "VARCHAR(50)",
        "expert_best_selected": "BOOLEAN NOT NULL DEFAULT 0",
        "team_members": "TEXT",
        "mentor_name": "VARCHAR(150)",
        "mentor_department": "VARCHAR(100)",
        "mentor_designation": "VARCHAR(100)",
        "mentor_employee_id": "VARCHAR(100)",
        "mentor_email": "VARCHAR(150)",
        "mentor_contact": "VARCHAR(30)",
    }.items():
        if column_name not in existing_solution_columns:
            connection.execute(text(f"ALTER TABLE solutions ADD COLUMN {column_name} {column_type}"))
            if column_name == "expert_best_selected":
                connection.execute(text(
                    "UPDATE solutions SET status = 'REVIEWED' WHERE status IN ('EXPERT_SELECTED', 'SELECTED')"
                ))

with engine.begin() as connection:
    existing_workspace_columns = {column["name"] for column in inspect(engine).get_columns("collaboration_workspaces")}
    for column_name, column_type in {
        "prototype_status": "VARCHAR(40) DEFAULT 'DEVELOPMENT'",
        "prototype_file_url": "VARCHAR(500)",
        "prototype_file_name": "VARCHAR(255)",
        "prototype_feedback": "TEXT",
        "prototype_updated_by": "INTEGER",
        "government_review_status": "VARCHAR(40) DEFAULT 'PENDING' NOT NULL",
        "government_review_reason": "TEXT",
        "government_review_comment": "TEXT",
        "government_reviewed_by": "INTEGER",
        "government_reviewed_at": "DATETIME",
    }.items():
        if column_name not in existing_workspace_columns:
            connection.execute(text(f"ALTER TABLE collaboration_workspaces ADD COLUMN {column_name} {column_type}"))

with engine.begin() as connection:
    existing_notification_columns = {column["name"] for column in inspect(engine).get_columns("notifications")}
    if "workspace_id" not in existing_notification_columns:
        connection.execute(text("ALTER TABLE notifications ADD COLUMN workspace_id INTEGER"))

# ---------- AI ENGINE URL ----------
AI_ENGINE_URL = "http://127.0.0.1:8001"


app = FastAPI(
    title="CollabX API",
    description="Connecting citizens, universities, government, industry, and experts to create public impact.",
    version="1.0.0",
)

# CORS — allow frontend to call backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve uploaded files
os.makedirs("uploads", exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# Register routers
app.include_router(users.router)
app.include_router(challenges.router)
app.include_router(solutions.router)
app.include_router(matching.router)
app.include_router(collaboration.router)
app.include_router(notifications.router)
app.include_router(government.router)
app.include_router(i18n.router)


@app.get("/")
def home():
    return {
        "message": "CollabX backend is running 🚀",
        "docs": "/docs",
        "health": "/health",
        "version": "1.0.0",
    }


@app.get("/health")
async def health():
    """
    Full health check: DB + AI engine connectivity.
    """
    # Check AI engine
    ai_status = "unknown"
    ai_message = ""
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            res = await client.get(f"{AI_ENGINE_URL}/")
            if res.status_code == 200:
                ai_status = "ok"
                ai_message = res.json().get("message", "AI engine running")
            else:
                ai_status = "error"
                ai_message = f"HTTP {res.status_code}"
    except Exception as e:
        ai_status = "unreachable"
        ai_message = str(e)

    # Check DB
    db_status = "ok"
    try:
        with engine.connect() as conn:
            conn.execute(models.User.__table__.select().limit(0))
    except Exception as e:
        db_status = "error"
        ai_message += f" | DB: {e}"

    return {
        "status": "ok",
        "backend": "ok",
        "database": db_status,
        "ai_engine": ai_status,
        "ai_engine_url": AI_ENGINE_URL,
        "ai_message": ai_message,
    }


@app.on_event("startup")
async def startup_event():
    """Print a friendly banner on startup + check AI engine."""
    print("\n" + "=" * 60)
    print("  🚀 CollabX Backend Starting...")
    print("=" * 60)
    print(f"  Backend:   http://127.0.0.1:8000")
    print(f"  Docs:      http://127.0.0.1:8000/docs")
    print(f"  AI Engine: {AI_ENGINE_URL}")
    print("=" * 60)

    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            res = await client.get(f"{AI_ENGINE_URL}/")
            if res.status_code == 200:
                print("  ✅ AI Engine is running")
            else:
                print(f"  ⚠️  AI Engine responded with HTTP {res.status_code}")
    except Exception:
        print("  ⚠️  AI Engine is NOT reachable")
    print("=" * 60 + "\n")