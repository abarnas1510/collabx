from datetime import datetime
import os
from typing import Optional
import json

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from database import get_db
import auth
import models
from routers.notifications import add_notification, add_role_notifications

router = APIRouter(tags=["Industry Collaboration"])


def log_activity(db, workspace_id, actor_id, event_type, message):
    db.add(models.WorkspaceActivity(
        workspace_id=workspace_id,
        actor_id=actor_id,
        event_type=event_type,
        message=message,
    ))


def infer_required_sector(solution, challenge) -> str:
    stored_sector = (solution.required_industry_sector or "").strip()
    if stored_sector and stored_sector.lower() not in {"general", "other"}:
        return stored_sector
    text = " ".join([
        solution.title or "",
        solution.proposal or "",
        challenge.title if challenge else "",
        challenge.description if challenge else "",
        challenge.category if challenge else "",
    ]).lower()
    if any(term in text for term in [
        "health", "healthcare", "medical", "medicine", "medication", "pharmacy",
        "hospital", "clinic", "patient", "doctor", "disease", "diagnosis", "treatment",
    ]):
        return "Healthcare"
    return stored_sector or (challenge.category if challenge else "General")


def sector_match(industry_sector: Optional[str], required_sector: Optional[str]) -> bool:
    if not industry_sector or not required_sector:
        return False
    left = industry_sector.strip().lower()
    right = required_sector.strip().lower()
    aliases = {
        "health": {"health", "healthcare", "medical", "medicine", "public health"},
        "healthcare": {"health", "healthcare", "medical", "medicine", "public health"},
        "medical": {"health", "healthcare", "medical", "medicine", "public health"},
        "medicine": {"health", "healthcare", "medical", "medicine", "public health"},
        "public health": {"health", "healthcare", "medical", "medicine", "public health"},
        "information technology": {"information technology", "it", "computer science"},
        "energy & utilities": {"energy & utilities", "energy", "renewable energy"},
        "transport & logistics": {"transport & logistics", "transportation", "logistics"},
    }
    left_values = aliases.get(left, {left})
    right_values = aliases.get(right, {right})
    return bool(left_values & right_values)


def project_payload(solution, challenge, university, industry, partnership=None):
    try:
        team_members = json.loads(solution.team_members or "[]")
    except (TypeError, json.JSONDecodeError):
        team_members = []
    return {
        "solution_id": solution.id,
        "challenge_id": challenge.id,
        "project_title": solution.title,
        "problem_statement": challenge.description,
        "category": challenge.category,
        "subcategory": challenge.title,
        "university": university.organization or university.name,
        "university_id": university.id,
        "student_team": university.name,
        "faculty_mentor": "University proposal team",
        "solution_summary": solution.proposal,
        "required_industry_sector": infer_required_sector(solution, challenge),
        "required_expertise": solution.required_expertise or "Domain expertise",
        "required_technology": solution.required_technology or "Technology support",
        "required_support": solution.required_support or "Technical mentoring",
        "budget_estimate": solution.budget_estimate,
        "timeline": solution.timeline,
        "team_size": solution.team_size,
        "project_stage": solution.project_stage or "Development",
        "match_status": "Sector Match",
        "match_score": 94,
        "partnership_status": partnership.status if partnership else None,
        "team_members": team_members,
        "faculty_mentor": {
            "name": solution.mentor_name or "University proposal team",
            "department": solution.mentor_department,
            "designation": solution.mentor_designation,
            "employee_id": solution.mentor_employee_id,
            "email": solution.mentor_email,
            "contact": solution.mentor_contact,
        },
        "solution_details": {
            "title": solution.title,
            "proposal": solution.proposal,
            "technology": solution.required_technology,
            "budget": solution.budget_estimate,
            "timeline": solution.timeline,
            "stage": solution.project_stage,
        },
        "industry_details": {
            "name": industry.name,
            "organization": industry.organization,
            "sector": industry.primary_sector,
            "mentor": industry.expertise or industry.support,
        },
    }


@router.get("/industry/matches")
def industry_matches(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_role("industry")),
):
    solutions = db.query(models.Solution).filter(
        models.Solution.status == "EXPERT_SELECTED",
        models.Solution.expert_best_selected.is_(True),
    ).order_by(models.Solution.created_at.desc()).all()
    results = []
    for solution in solutions:
        challenge = db.query(models.Challenge).filter(models.Challenge.id == solution.challenge_id).first()
        university = db.query(models.User).filter(models.User.id == solution.university_id).first()
        if not challenge or not university or not sector_match(
            current_user.primary_sector, infer_required_sector(solution, challenge)
        ):
            continue
        partnership = db.query(models.IndustryPartnership).filter(
            models.IndustryPartnership.solution_id == solution.id,
            models.IndustryPartnership.industry_id == current_user.id,
        ).first()
        results.append(project_payload(solution, challenge, university, current_user, partnership))
    return results


def workspace_member(workspace, current_user, db):
    solution = db.query(models.Solution).filter(models.Solution.id == workspace.solution_id).first()
    if not solution:
        return None
    if current_user.role not in {"govt", "admin"} and current_user.id not in (workspace.industry_id, solution.university_id):
        raise HTTPException(status_code=403, detail="You are not part of this workspace")
    return solution


@router.get("/workspaces/mine")
def my_workspaces(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    workspaces = db.query(models.CollaborationWorkspace).order_by(
        models.CollaborationWorkspace.created_at.desc()
    ).all()
    result = []
    for workspace in workspaces:
        solution = db.query(models.Solution).filter(models.Solution.id == workspace.solution_id).first()
        challenge = db.query(models.Challenge).filter(models.Challenge.id == workspace.challenge_id).first()
        industry = db.query(models.User).filter(models.User.id == workspace.industry_id).first()
        if not solution or not challenge or not industry:
            continue
        if current_user.id not in (workspace.industry_id, solution.university_id):
            continue
        university = db.query(models.User).filter(models.User.id == solution.university_id).first()
        result.append({
            "workspace_id": workspace.id,
            "project_name": solution.title,
            "university": university.organization or university.name,
            "industry": industry.organization or industry.name,
            "progress": workspace.progress,
            "stage": workspace.stage,
        })
    return result


@router.post("/industry/solutions/{solution_id}/partner")
def partner_with_project(
    solution_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_role("industry")),
):
    solution = db.query(models.Solution).filter(
        models.Solution.id == solution_id,
        models.Solution.status == "EXPERT_SELECTED",
        models.Solution.expert_best_selected.is_(True),
    ).first()
    if not solution:
        raise HTTPException(status_code=404, detail="Expert-selected proposal not found")
    challenge = db.query(models.Challenge).filter(models.Challenge.id == solution.challenge_id).first()
    if not sector_match(current_user.primary_sector, infer_required_sector(solution, challenge)):
        raise HTTPException(status_code=403, detail="This proposal does not match your primary sector")
    partnership = db.query(models.IndustryPartnership).filter(
        models.IndustryPartnership.solution_id == solution_id,
        models.IndustryPartnership.industry_id == current_user.id,
    ).first()
    if not partnership:
        partnership = models.IndustryPartnership(
            solution_id=solution_id, industry_id=current_user.id, status="PARTNER_SELECTED"
        )
        db.add(partnership)
    else:
        partnership.status = "PARTNER_SELECTED"
    challenge = db.query(models.Challenge).filter(models.Challenge.id == solution.challenge_id).first()
    add_notification(
        db, solution.university_id, "INDUSTRY_SELECTED", "Industry selected your solution",
        f"An industry partner selected {solution.title} for collaboration.",
        challenge_id=solution.challenge_id, solution_id=solution.id,
    )
    if challenge:
        add_notification(
            db, challenge.citizen_id, "INDUSTRY_SELECTED", "Industry selected a solution",
            f"An industry partner selected {solution.title} for your reported problem.",
            challenge_id=challenge.id, solution_id=solution.id,
        )
    add_role_notifications(
        db, ("govt", "admin"), "INDUSTRY_SELECTED", "Industry selected a solution",
        f"An industry partner selected {solution.title} for challenge #{solution.challenge_id}.",
        challenge_id=solution.challenge_id, solution_id=solution.id,
    )
    db.commit()
    return {"solution_id": solution_id, "status": partnership.status, "can_create_workspace": True}


@router.post("/industry/solutions/{solution_id}/workspace")
def create_workspace(
    solution_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_role("industry")),
):
    partnership = db.query(models.IndustryPartnership).filter(
        models.IndustryPartnership.solution_id == solution_id,
        models.IndustryPartnership.industry_id == current_user.id,
        models.IndustryPartnership.status == "PARTNER_SELECTED",
    ).first()
    if not partnership:
        raise HTTPException(status_code=409, detail="Select Partner with Project before creating a workspace")
    solution = db.query(models.Solution).filter(models.Solution.id == solution_id).first()
    existing = db.query(models.CollaborationWorkspace).filter(
        models.CollaborationWorkspace.solution_id == solution_id,
        models.CollaborationWorkspace.industry_id == current_user.id,
    ).first()
    if existing:
        return {"workspace_id": existing.id, "status": "already_exists"}
    workspace = models.CollaborationWorkspace(
        challenge_id=solution.challenge_id,
        solution_id=solution.id,
        industry_id=current_user.id,
        stage=solution.project_stage or "Development",
        progress=0,
    )
    db.add(workspace)
    db.flush()
    log_activity(db, workspace.id, current_user.id, "WORKSPACE_CREATED", "Workspace created")
    db.commit()
    db.refresh(workspace)
    return {"workspace_id": workspace.id, "status": "created"}


@router.get("/workspaces/{workspace_id}")
def get_workspace(
    workspace_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    workspace = db.query(models.CollaborationWorkspace).filter(
        models.CollaborationWorkspace.id == workspace_id
    ).first()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    solution = db.query(models.Solution).filter(models.Solution.id == workspace.solution_id).first()
    challenge = db.query(models.Challenge).filter(models.Challenge.id == workspace.challenge_id).first()
    university = db.query(models.User).filter(models.User.id == solution.university_id).first()
    industry = db.query(models.User).filter(models.User.id == workspace.industry_id).first()
    workspace_member(workspace, current_user, db)
    messages = db.query(models.WorkspaceMessage).filter(models.WorkspaceMessage.workspace_id == workspace_id).all()
    tasks = db.query(models.WorkspaceTask).filter(models.WorkspaceTask.workspace_id == workspace_id).all()
    documents = db.query(models.WorkspaceDocument).filter(models.WorkspaceDocument.workspace_id == workspace_id).all()
    activities = db.query(models.WorkspaceActivity).filter(
        models.WorkspaceActivity.workspace_id == workspace_id
    ).order_by(models.WorkspaceActivity.created_at.desc()).limit(50).all()
    return {
        "workspace_id": workspace.id,
        "project": project_payload(solution, challenge, university, industry),
        "industry": industry.organization or industry.name,
        "faculty_mentor": project_payload(solution, challenge, university, industry)["faculty_mentor"],
        "stage": workspace.stage,
        "progress": workspace.progress,
        "prototype": {
            "status": workspace.prototype_status or "DEVELOPMENT",
            "file_url": workspace.prototype_file_url,
            "file_name": workspace.prototype_file_name,
            "feedback": workspace.prototype_feedback,
        },
        "government_review": {
            "status": workspace.government_review_status or "PENDING",
            "reason": workspace.government_review_reason,
            "comment": workspace.government_review_comment,
            "reviewed_at": workspace.government_reviewed_at,
        },
        "overview": {"problem": challenge.description, "solution": solution.proposal, "objectives": solution.required_support, "expected_impact": "Community impact through implementation"},
        "messages": [{"id": m.id, "sender_id": m.sender_id, "message": m.message, "parent_id": m.parent_id, "created_at": m.created_at} for m in messages],
        "tasks": [{"id": t.id, "title": t.title, "assigned_to": t.assigned_to, "due_date": t.due_date, "status": t.status, "progress": t.progress, "feedback": t.feedback} for t in tasks],
        "documents": [{"id": d.id, "filename": d.filename, "file_url": d.file_url, "created_at": d.created_at} for d in documents],
        "activities": [{"id": a.id, "actor_id": a.actor_id, "event_type": a.event_type, "message": a.message, "created_at": a.created_at} for a in activities],
        "timeline": ["Expert Selected", "Industry Matched", "Partner Selected", "Workspace Created"],
        "notifications": ["Workspace created"],
    }


@router.patch("/workspaces/{workspace_id}")
def update_workspace(
    workspace_id: int,
    progress: Optional[int] = Form(None),
    stage: Optional[str] = Form(None),
    prototype_status: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    workspace = db.query(models.CollaborationWorkspace).filter(
        models.CollaborationWorkspace.id == workspace_id
    ).first()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    workspace_member(workspace, current_user, db)

    if progress is not None:
        workspace.progress = max(0, min(100, int(progress)))
    if stage is not None:
        cleaned = stage.strip()
        allowed = ["Development", "Prototype", "Pilot", "Citizen Feedback", "Impact"]
        if cleaned not in allowed:
            raise HTTPException(status_code=400, detail="Invalid workspace stage")
        workspace.stage = cleaned
    if prototype_status is not None:
        workspace.prototype_status = prototype_status.strip()

    log_activity(
        db, workspace_id, current_user.id, "WORKSPACE_UPDATED",
        f"Updated workspace progress to {workspace.progress}% and stage to {workspace.stage}"
    )
    db.commit()
    db.refresh(workspace)
    return {
        "workspace_id": workspace.id,
        "stage": workspace.stage,
        "progress": workspace.progress,
        "prototype_status": workspace.prototype_status,
    }


@router.post("/workspaces/{workspace_id}/prototype")
def upload_prototype(
    workspace_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    workspace = db.query(models.CollaborationWorkspace).filter(models.CollaborationWorkspace.id == workspace_id).first()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    workspace_member(workspace, current_user, db)
    if current_user.role != "university":
        raise HTTPException(status_code=403, detail="Only the university team can upload a prototype")
    import os
    upload_dir = "uploads/workspaces/prototypes"
    os.makedirs(upload_dir, exist_ok=True)
    safe_name = f"{workspace_id}_{int(datetime.utcnow().timestamp())}_{file.filename}"
    path = os.path.join(upload_dir, safe_name)
    with open(path, "wb") as output:
        output.write(file.file.read())
    workspace.prototype_file_url = path
    workspace.prototype_file_name = file.filename
    workspace.prototype_status = "PROTOTYPE_UPLOADED"
    workspace.prototype_updated_by = current_user.id
    log_activity(db, workspace_id, current_user.id, "PROTOTYPE_UPLOADED", f"Prototype uploaded: {file.filename}")
    db.commit()
    return {"status": workspace.prototype_status, "file_url": path, "file_name": file.filename}


@router.post("/workspaces/{workspace_id}/prototype/start")
def start_prototype(
    workspace_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    workspace = db.query(models.CollaborationWorkspace).filter(models.CollaborationWorkspace.id == workspace_id).first()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    workspace_member(workspace, current_user, db)
    if current_user.role != "university":
        raise HTTPException(status_code=403, detail="Only the university team can start a prototype")
    if workspace.prototype_status == "DEVELOPMENT":
        workspace.prototype_status = "PROTOTYPE_STARTED"
        workspace.prototype_updated_by = current_user.id
        log_activity(db, workspace_id, current_user.id, "PROTOTYPE_STARTED", "Prototype development started")
        db.commit()
    return {"status": workspace.prototype_status}


@router.post("/workspaces/{workspace_id}/prototype/feedback")
def prototype_feedback(
    workspace_id: int,
    feedback: str = Form(...),
    request_changes: bool = Form(False),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    workspace = db.query(models.CollaborationWorkspace).filter(models.CollaborationWorkspace.id == workspace_id).first()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    workspace_member(workspace, current_user, db)
    if current_user.role != "industry":
        raise HTTPException(status_code=403, detail="Only the industry partner can review a prototype")
    workspace.prototype_feedback = feedback.strip()
    workspace.prototype_status = "CHANGES_REQUESTED" if request_changes else "INDUSTRY_REVIEW"
    workspace.prototype_updated_by = current_user.id
    log_activity(db, workspace_id, current_user.id, workspace.prototype_status, feedback.strip())
    db.commit()
    return {"status": workspace.prototype_status, "feedback": workspace.prototype_feedback}


@router.post("/workspaces/{workspace_id}/prototype/approve")
def approve_prototype(
    workspace_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    workspace = db.query(models.CollaborationWorkspace).filter(models.CollaborationWorkspace.id == workspace_id).first()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    workspace_member(workspace, current_user, db)
    if current_user.role != "industry":
        raise HTTPException(status_code=403, detail="Only the industry partner can approve a prototype")
    workspace.prototype_status = "GOVERNMENT_REVIEW_PENDING"
    workspace.government_review_status = "PENDING"
    workspace.prototype_updated_by = current_user.id
    log_activity(db, workspace_id, current_user.id, "GOVERNMENT_REVIEW_PENDING", "Prototype approved by industry and sent to government review")
    add_role_notifications(
        db, ("govt", "admin"), "GOVERNMENT_REVIEW_PENDING", "Prototype ready for government review",
        f"Industry approved {workspace.prototype_file_name or 'the prototype'} for government review.",
        challenge_id=workspace.challenge_id, solution_id=workspace.solution_id,
        workspace_id=workspace.id,
    )
    db.commit()
    return {"status": workspace.prototype_status}


@router.post("/workspaces/{workspace_id}/messages")
def send_message(
    workspace_id: int,
    message: str = Form(...),
    parent_id: Optional[int] = Form(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    workspace = db.query(models.CollaborationWorkspace).filter(models.CollaborationWorkspace.id == workspace_id).first()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    workspace_member(workspace, current_user, db)
    if parent_id:
        parent = db.query(models.WorkspaceMessage).filter(
            models.WorkspaceMessage.id == parent_id,
            models.WorkspaceMessage.workspace_id == workspace_id,
        ).first()
        if not parent:
            raise HTTPException(status_code=404, detail="Reply target not found")
    item = models.WorkspaceMessage(workspace_id=workspace_id, sender_id=current_user.id, message=message, parent_id=parent_id)
    db.add(item)
    log_activity(db, workspace_id, current_user.id, "REPLY" if parent_id else "MESSAGE", "Replied in team chat" if parent_id else "Posted a team chat message")
    db.commit()
    db.refresh(item)
    return {"id": item.id, "message": item.message, "sender_id": item.sender_id, "created_at": item.created_at}


@router.patch("/workspaces/{workspace_id}/messages/{message_id}")
def update_message(
    workspace_id: int,
    message_id: int,
    message: str = Form(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    workspace = db.query(models.CollaborationWorkspace).filter(models.CollaborationWorkspace.id == workspace_id).first()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    workspace_member(workspace, current_user, db)
    item = db.query(models.WorkspaceMessage).filter(
        models.WorkspaceMessage.id == message_id,
        models.WorkspaceMessage.workspace_id == workspace_id,
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="Message not found")
    if item.sender_id != current_user.id:
        raise HTTPException(status_code=403, detail="You can only edit your own messages")
    cleaned_message = message.strip()
    if not cleaned_message:
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    item.message = cleaned_message
    log_activity(db, workspace_id, current_user.id, "MESSAGE_UPDATED", "Updated a team chat message")
    db.commit()
    db.refresh(item)
    return {"id": item.id, "message": item.message, "sender_id": item.sender_id, "created_at": item.created_at}


@router.delete("/workspaces/{workspace_id}/messages/{message_id}")
def delete_message(
    workspace_id: int,
    message_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    workspace = db.query(models.CollaborationWorkspace).filter(models.CollaborationWorkspace.id == workspace_id).first()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    workspace_member(workspace, current_user, db)
    item = db.query(models.WorkspaceMessage).filter(
        models.WorkspaceMessage.id == message_id,
        models.WorkspaceMessage.workspace_id == workspace_id,
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="Message not found")
    if item.sender_id != current_user.id:
        raise HTTPException(status_code=403, detail="You can only delete your own messages")
    db.delete(item)
    log_activity(db, workspace_id, current_user.id, "MESSAGE_DELETED", "Deleted a team chat message")
    db.commit()
    return {"deleted": True, "message_id": message_id}


@router.post("/workspaces/{workspace_id}/tasks")
def create_task(
    workspace_id: int,
    title: str = Form(...),
    assigned_to: Optional[str] = Form(None),
    due_date: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    workspace = db.query(models.CollaborationWorkspace).filter(models.CollaborationWorkspace.id == workspace_id).first()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    workspace_member(workspace, current_user, db)
    task = models.WorkspaceTask(workspace_id=workspace_id, title=title, assigned_to=assigned_to, due_date=due_date)
    db.add(task)
    log_activity(db, workspace_id, current_user.id, "TASK_CREATED", f"Created task: {title}")
    db.commit()
    db.refresh(task)
    return {"id": task.id, "title": task.title, "status": task.status}


@router.patch("/workspaces/{workspace_id}/tasks/{task_id}")
def update_task(
    workspace_id: int,
    task_id: int,
    title: Optional[str] = Form(None),
    assigned_to: Optional[str] = Form(None),
    due_date: Optional[str] = Form(None),
    status: Optional[str] = Form(None),
    progress: Optional[int] = Form(None),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    workspace = db.query(models.CollaborationWorkspace).filter(models.CollaborationWorkspace.id == workspace_id).first()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    workspace_member(workspace, current_user, db)
    task = db.query(models.WorkspaceTask).filter(
        models.WorkspaceTask.id == task_id,
        models.WorkspaceTask.workspace_id == workspace_id,
    ).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if title is not None: task.title = title.strip()
    if assigned_to is not None: task.assigned_to = assigned_to.strip() or None
    if due_date is not None: task.due_date = due_date.strip() or None
    if status is not None:
        normalized = status.upper()
        if normalized not in {"NOT_STARTED", "IN_PROGRESS", "DONE", "COMPLETED"}:
            raise HTTPException(status_code=400, detail="Invalid task status")
        task.status = normalized
    if progress is not None: task.progress = max(0, min(100, progress))
    log_activity(db, workspace_id, current_user.id, "TASK_UPDATED", f"Updated task: {task.title}")
    db.commit()
    db.refresh(task)
    return {"id": task.id, "title": task.title, "assigned_to": task.assigned_to, "due_date": task.due_date, "status": task.status, "progress": task.progress}


@router.delete("/workspaces/{workspace_id}/tasks/{task_id}")
def delete_task(
    workspace_id: int,
    task_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    workspace = db.query(models.CollaborationWorkspace).filter(models.CollaborationWorkspace.id == workspace_id).first()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    workspace_member(workspace, current_user, db)
    task = db.query(models.WorkspaceTask).filter(
        models.WorkspaceTask.id == task_id,
        models.WorkspaceTask.workspace_id == workspace_id,
    ).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    title = task.title
    db.delete(task)
    log_activity(db, workspace_id, current_user.id, "TASK_DELETED", f"Deleted task: {title}")
    db.commit()
    return {"deleted": True, "task_id": task_id}


@router.post("/workspaces/{workspace_id}/documents")
def upload_document(
    workspace_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    workspace = db.query(models.CollaborationWorkspace).filter(models.CollaborationWorkspace.id == workspace_id).first()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    workspace_member(workspace, current_user, db)
    upload_dir = "uploads/workspaces"
    import os
    os.makedirs(upload_dir, exist_ok=True)
    safe_name = f"{workspace_id}_{int(datetime.utcnow().timestamp())}_{file.filename}"
    path = os.path.join(upload_dir, safe_name)
    with open(path, "wb") as output:
        output.write(file.file.read())
    document = models.WorkspaceDocument(workspace_id=workspace_id, uploaded_by=current_user.id, filename=file.filename, file_url=path)
    db.add(document)
    log_activity(db, workspace_id, current_user.id, "DOCUMENT_UPLOADED", f"Uploaded document: {file.filename}")
    db.commit()
    db.refresh(document)
    return {"id": document.id, "filename": document.filename, "file_url": document.file_url}


@router.delete("/workspaces/{workspace_id}/documents/{document_id}")
def delete_document(
    workspace_id: int,
    document_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    workspace = db.query(models.CollaborationWorkspace).filter(models.CollaborationWorkspace.id == workspace_id).first()
    if not workspace:
        raise HTTPException(status_code=404, detail="Workspace not found")
    workspace_member(workspace, current_user, db)

    document = db.query(models.WorkspaceDocument).filter(
        models.WorkspaceDocument.id == document_id,
        models.WorkspaceDocument.workspace_id == workspace_id,
    ).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    try:
        if document.file_url and os.path.exists(document.file_url):
            os.remove(document.file_url)
    except OSError:
        pass

    db.delete(document)
    log_activity(db, workspace_id, current_user.id, "DOCUMENT_DELETED", f"Deleted document: {document.filename}")
    db.commit()
    return {"deleted": True, "document_id": document_id}
