from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
import httpx
from database import get_db
import models, schemas, auth
from routers.notifications import add_notification, add_role_notifications

router = APIRouter(prefix="/solutions", tags=["Solutions"])

AI_ENGINE_URL = "http://127.0.0.1:8001"


# ---------- SUBMIT SOLUTION (university only) ----------
@router.post("/", response_model=schemas.SolutionOut, status_code=201)
async def submit_solution(
    payload: schemas.SolutionCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_role("university")),
):
    # Check challenge exists
    challenge = db.query(models.Challenge).filter(
        models.Challenge.id == payload.challenge_id
    ).first()
    if not challenge:
        raise HTTPException(status_code=404, detail="Challenge not found")

    # Check duplicate submission
    existing = db.query(models.Solution).filter(
        models.Solution.challenge_id == payload.challenge_id,
        models.Solution.university_id == current_user.id,
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="You already submitted a solution for this challenge")

    # Call AI to screen the solution
    ai_score = None
    ai_explanation = None
    ai_required_sector = None
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            res = await client.post(
                f"{AI_ENGINE_URL}/screen",
                json={
                    "challenge_title": challenge.title,
                    "challenge_description": challenge.description,
                    "solution_title": payload.title,
                    "solution_proposal": payload.proposal,
                }
            )
            if res.status_code == 200:
                data = res.json()
                ai_score = data.get("score")
                ai_explanation = data.get("explanation")
                ai_required_sector = data.get("required_industry_sector")
    except Exception as e:
        print(f"[AI Engine not reachable] {e}")

    solution = models.Solution(
        challenge_id=payload.challenge_id,
        university_id=current_user.id,
        title=payload.title,
        proposal=payload.proposal,
        ai_score=ai_score,
        ai_explanation=ai_explanation,
        status="AI_SCREENED" if ai_score is not None else "PENDING",
        required_industry_sector=payload.required_industry_sector or ai_required_sector or challenge.category,
        required_expertise=payload.required_expertise,
        required_technology=payload.required_technology,
        required_support=payload.required_support,
        budget_estimate=payload.budget_estimate,
        timeline=payload.timeline,
        team_size=payload.team_size,
        team_members=payload.team_members,
        mentor_name=payload.mentor_name,
        mentor_department=payload.mentor_department,
        mentor_designation=payload.mentor_designation,
        mentor_employee_id=payload.mentor_employee_id,
        mentor_email=str(payload.mentor_email) if payload.mentor_email else None,
        mentor_contact=payload.mentor_contact,
        project_stage=payload.project_stage or "Development",
    )
    db.add(solution)
    db.commit()
    db.refresh(solution)
    return solution


# ---------- LIST SOLUTIONS FOR A CHALLENGE ----------
@router.get("/challenge/{challenge_id}", response_model=List[schemas.SolutionOut])
def list_solutions(challenge_id: int, db: Session = Depends(get_db)):
    return db.query(models.Solution).filter(
        models.Solution.challenge_id == challenge_id
    ).order_by(models.Solution.ai_score.desc().nullslast()).all()


# ---------- MY SUBMISSIONS (university) ----------
@router.get("/mine", response_model=List[schemas.SolutionOut])
def my_solutions(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_role("university")),
):
    return db.query(models.Solution).filter(
        models.Solution.university_id == current_user.id
    ).order_by(models.Solution.created_at.desc()).all()


# ---------- EXPERT SCORE (evaluation only) ----------
@router.patch("/{solution_id}/expert-score", response_model=schemas.SolutionOut)
def expert_score(
    solution_id: int,
    score: float,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_role("expert", "admin")),
):
    solution = db.query(models.Solution).filter(
        models.Solution.id == solution_id
    ).first()
    if not solution:
        raise HTTPException(status_code=404, detail="Solution not found")

    solution.expert_score = score
    if not solution.expert_best_selected:
        solution.status = "REVIEWED"
    db.commit()
    db.refresh(solution)
    return solution


# ---------- EXPLICIT BEST-SOLUTION SELECTION (expert only) ----------
@router.patch("/{solution_id}/expert-select", response_model=schemas.SolutionOut)
def select_best_solution(
    solution_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_role("expert", "admin")),
):
    solution = db.query(models.Solution).filter(
        models.Solution.id == solution_id
    ).first()
    if not solution:
        raise HTTPException(status_code=404, detail="Solution not found")

    challenge_solutions = db.query(models.Solution).filter(
        models.Solution.challenge_id == solution.challenge_id
    ).all()
    for candidate in challenge_solutions:
        candidate.expert_best_selected = candidate.id == solution.id
        candidate.status = "EXPERT_SELECTED" if candidate.id == solution.id else "REVIEWED"
    challenge = db.query(models.Challenge).filter(models.Challenge.id == solution.challenge_id).first()
    if challenge:
        add_notification(
            db, challenge.citizen_id, "EXPERT_SELECTED", "Expert selected a solution",
            f"An expert selected {solution.title} for your reported problem.",
            challenge_id=challenge.id, solution_id=solution.id,
        )
    add_notification(
        db, solution.university_id, "EXPERT_SELECTED", "Your solution was selected",
        f"Your solution {solution.title} was selected by an expert.",
        challenge_id=solution.challenge_id, solution_id=solution.id,
    )
    add_role_notifications(
        db, ("govt", "admin"), "EXPERT_SELECTED", "Expert selected a solution",
        f"An expert selected {solution.title} for challenge #{solution.challenge_id}.",
        challenge_id=solution.challenge_id, solution_id=solution.id,
    )
    db.commit()
    db.refresh(solution)
    return solution