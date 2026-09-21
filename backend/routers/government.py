from datetime import datetime

from fastapi import APIRouter, Depends, Form, HTTPException
from sqlalchemy.orm import Session

from database import get_db
import auth
import models
from routers.notifications import add_notification

router = APIRouter(prefix="/government", tags=["Government Review"])


def review_payload(workspace, solution, challenge, university, industry):
    return {
        "workspace_id": workspace.id,
        "solution_id": solution.id,
        "challenge_id": challenge.id,
        "project_title": solution.title,
        "problem": challenge.description,
        "solution": solution.proposal,
        "university": university.organization or university.name,
        "industry": industry.organization or industry.name,
        "prototype": {
            "status": workspace.prototype_status or "DEVELOPMENT",
            "file_url": workspace.prototype_file_url,
            "file_name": workspace.prototype_file_name,
            "feedback": workspace.prototype_feedback,
        },
        "review": {
            "status": workspace.government_review_status or "PENDING",
            "reason": workspace.government_review_reason,
            "comment": workspace.government_review_comment,
            "reviewed_at": workspace.government_reviewed_at,
        },
    }


def get_review_context(db, workspace_id):
    workspace = db.query(models.CollaborationWorkspace).filter(
        models.CollaborationWorkspace.id == workspace_id
    ).first()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    solution = db.query(models.Solution).filter(models.Solution.id == workspace.solution_id).first()
    challenge = db.query(models.Challenge).filter(models.Challenge.id == workspace.challenge_id).first()
    if not solution or not challenge:
        raise HTTPException(status_code=409, detail="Workspace project data is incomplete")
    university = db.query(models.User).filter(models.User.id == solution.university_id).first()
    industry = db.query(models.User).filter(models.User.id == workspace.industry_id).first()
    if not university or not industry:
        raise HTTPException(status_code=409, detail="Workspace member data is incomplete")
    return workspace, solution, challenge, university, industry


@router.get("/reviews")
def government_reviews(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_role("govt", "admin")),
):
    workspaces = db.query(models.CollaborationWorkspace).order_by(
        models.CollaborationWorkspace.created_at.desc()
    ).all()
    results = []
    for workspace in workspaces:
        context = get_review_context(db, workspace.id)
        if workspace.prototype_file_url or workspace.government_review_status != "PENDING":
            results.append(review_payload(*context))
    return results


@router.get("/workspaces/{workspace_id}/problem")
def government_problem_context(
    workspace_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_role("govt", "admin")),
):
    workspace, solution, challenge, university, industry = get_review_context(db, workspace_id)
    return {
        "workspace_id": workspace.id,
        "problem": {
            "id": challenge.id,
            "title": challenge.title,
            "description": challenge.description,
            "status": challenge.status,
        },
        "solution": {
            "id": solution.id,
            "title": solution.title,
            "proposal": solution.proposal,
            "status": solution.status,
            "university": university.organization or university.name,
        },
        "industry": {
            "name": industry.organization or industry.name,
            "sector": industry.primary_sector,
        },
        "collaboration": {
            "stage": workspace.stage,
            "progress": workspace.progress,
            "status": workspace.government_review_status or "PENDING",
        },
        "prototype": {
            "status": workspace.prototype_status or "DEVELOPMENT",
            "file_url": workspace.prototype_file_url,
            "file_name": workspace.prototype_file_name,
        },
        "industry_feedback": workspace.prototype_feedback,
    }


@router.post("/workspaces/{workspace_id}/review")
def review_workspace(
    workspace_id: int,
    action: str = Form(...),
    reason: str = Form(""),
    comment: str = Form(""),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_role("govt", "admin")),
):
    workspace, solution, challenge, university, industry = get_review_context(db, workspace_id)
    action = action.strip().lower()
    reason = reason.strip()
    comment = comment.strip()
    if action not in {"approve", "changes", "reject", "comment"}:
        raise HTTPException(status_code=400, detail="Invalid review action")
    if action in {"changes", "reject"} and not reason:
        raise HTTPException(status_code=400, detail="A reason is required")
    if action == "comment" and not comment:
        raise HTTPException(status_code=400, detail="A comment is required")

    title = "Government review update"
    message = comment or reason
    if action == "approve":
        workspace.government_review_status = "APPROVED_FOR_PILOT"
        workspace.government_review_reason = None
        workspace.prototype_status = "GOVERNMENT_APPROVED"
        workspace.stage = "Pilot"
        solution.status = "PILOT"
        challenge.status = "PILOT"
        title = "Prototype approved for pilot"
        message = f"Government approved {solution.title} for pilot deployment."
        event_type = "GOVERNMENT_APPROVED"
    elif action == "changes":
        workspace.government_review_status = "CHANGES_REQUESTED"
        workspace.government_review_reason = reason
        workspace.prototype_status = "GOVERNMENT_CHANGES_REQUESTED"
        title = "Government requested prototype changes"
        message = f"Changes requested for {solution.title}: {reason}"
        event_type = "GOVERNMENT_CHANGES_REQUESTED"
    elif action == "reject":
        workspace.government_review_status = "REJECTED"
        workspace.government_review_reason = reason
        workspace.prototype_status = "GOVERNMENT_REJECTED"
        title = "Prototype rejected by government"
        message = f"Government rejected {solution.title}: {reason}"
        event_type = "GOVERNMENT_REJECTED"
    else:
        workspace.government_review_comment = comment
        title = "Government added a workspace comment"
        event_type = "GOVERNMENT_COMMENT"

    if action != "comment":
        workspace.government_reviewed_by = current_user.id
        workspace.government_reviewed_at = datetime.utcnow()
    db.add(models.WorkspaceActivity(
        workspace_id=workspace.id,
        actor_id=current_user.id,
        event_type=event_type,
        message=message,
    ))
    for recipient_id in {university.id, industry.id}:
        add_notification(
            db, recipient_id, event_type, title, message,
            challenge_id=challenge.id, solution_id=solution.id,
            workspace_id=workspace.id,
        )
    db.commit()
    db.refresh(workspace)
    return review_payload(workspace, solution, challenge, university, industry)