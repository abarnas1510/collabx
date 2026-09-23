from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os
import uvicorn

from database import engine, Base
from sqlalchemy import inspect, text
import models  # noqa — needed so tables get created

from routers import users, challenges, solutions, matching, collaboration, notifications, government, i18n
from ai_model import model_status

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
    is_postgresql = engine.dialect.name == "postgresql"
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
        "expert_best_selected": "BOOLEAN NOT NULL DEFAULT FALSE" if is_postgresql else "BOOLEAN NOT NULL DEFAULT 0",
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
    is_postgresql = engine.dialect.name == "postgresql"
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
        "government_reviewed_at": "TIMESTAMP" if is_postgresql else "DATETIME",
    }.items():
        if column_name not in existing_workspace_columns:
            connection.execute(text(f"ALTER TABLE collaboration_workspaces ADD COLUMN {column_name} {column_type}"))

with engine.begin() as connection:
    existing_notification_columns = {column["name"] for column in inspect(engine).get_columns("notifications")}
    if "workspace_id" not in existing_notification_columns:
        connection.execute(text("ALTER TABLE notifications ADD COLUMN workspace_id INTEGER"))

app = FastAPI(
    title="CollabX API",
    description="Connecting citizens, universities, government, industry, and experts to create public impact.",
    version="1.0.0",
)

configured_cors_origins = os.getenv(
    "CORS_ORIGINS",
    "https://abarnas1510.github.io,http://localhost:5500,http://127.0.0.1:5500",
)
cors_origins = [origin.strip().rstrip("/") for origin in configured_cors_origins.split(",") if origin.strip()]
production_frontend_origin = "https://abarnas1510.github.io"
if production_frontend_origin not in cors_origins:
    cors_origins.append(production_frontend_origin)

# CORS — allow only configured frontend origins in production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Accept", "Authorization", "Content-Type", "Origin", "X-Requested-With"],
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
    """Return backend, database, and in-process model readiness."""
    db_status = "ok"
    db_message = ""
    try:
        with engine.connect() as conn:
            conn.execute(models.User.__table__.select().limit(0))
    except Exception as e:
        db_status = "error"
        db_message = str(e)

    return {
        "status": "ok" if db_status == "ok" else "error",
        "backend": "ok",
        "database": db_status,
        "ai_model": model_status(),
        "database_message": db_message,
    }


@app.on_event("startup")
async def startup_event():
    """Print a startup banner without loading AI resources."""
    print("\n" + "=" * 60)
    print("  🚀 CollabX Backend Starting...")
    print("=" * 60)
    print("  Backend:   configured by the hosting service")
    print("  Docs:      /docs")
    print(f"  AI Model:  {model_status()['name']}")
    print("=" * 60)
    print("=" * 60 + "\n")


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
        reload=os.getenv("RELOAD", "false").lower() == "true",
    )