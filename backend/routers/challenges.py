from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from sqlalchemy.orm import Session
from typing import List, Optional
import os, shutil, httpx, time, json
from database import get_db
import models, schemas, auth
from translation import normalize_language, translated_fields
from routers.notifications import add_notification, add_role_notifications

router = APIRouter(prefix="/challenges", tags=["Challenges"])

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

AI_ENGINE_URL = "http://127.0.0.1:8001"

FALLBACK_CATEGORY_KEYWORDS = {
    "Infrastructure & Roads": ["road", "pothole", "street", "pavement", "highway", "bridge", "infrastructure"],
    "Water & Resources": ["water", "pipe", "leak", "supply", "tap", "well", "drain", "tank"],
    "Energy & Electricity": ["electric", "power", "light", "streetlight", "wire", "transformer", "outage"],
    "Healthcare": ["hospital", "clinic", "doctor", "medicine", "disease", "health", "patient"],
    "Education": ["school", "college", "student", "teacher", "education", "exam"],
    "Agriculture": ["farm", "crop", "seed", "harvest", "irrigation", "agriculture", "soil"],
    "Environment & Climate": ["pollution", "tree", "forest", "river", "climate", "environment", "emission"],
    "Waste Management": ["waste", "garbage", "trash", "recycling", "dump", "litter", "sanitation"],
    "Transport & Mobility": ["transport", "bus", "traffic", "vehicle", "mobility", "metro", "transit"],
    "Public Safety": ["safety", "crime", "fire", "emergency", "police", "accident", "danger"],
    "Accessibility": ["wheelchair", "ramp", "blind", "disabled", "accessibility", "barrier"],
    "Urban Development": ["city", "urban", "town", "housing", "planning", "development"],
    "Industry & Manufacturing": ["industry", "factory", "manufacturing", "industrial", "production", "workshop"],
    "Rural Development": ["village", "rural", "farmer", "livelihood", "panchayat", "employment"],
    "Public Administration": ["safety", "crime", "fire", "emergency", "police", "certificate"],
}


def fallback_category(title: str, description: str) -> str:
    text = f"{title} {description}".lower()
    scores = {
        category: sum(text.count(keyword) for keyword in keywords)
        for category, keywords in FALLBACK_CATEGORY_KEYWORDS.items()
    }
    category, score = max(scores.items(), key=lambda item: item[1])
    return category if score else "General"


def fallback_university_matches(category: str, universities: list) -> list:
    from routers.matching import MIN_MATCH_SCORE, parse_university_departments, score_university_for_category

    matches = []
    for university in universities:
        score, departments = score_university_for_category(
            parse_university_departments(university.organization), category
        )
        if score < MIN_MATCH_SCORE:
            continue
        matches.append({
            "university_id": university.id,
            "name": university.name,
            "organization": university.organization,
            "match_score": score,
            "matched_departments": departments,
            "reason": f"Category and department match: {', '.join(departments)}",
        })
    return sorted(matches, key=lambda item: item["match_score"], reverse=True)[:5]


def fallback_verification(title: str, description: str) -> tuple[bool, int, list[str]]:
    text = f"{title}. {description}".strip().lower()
    score = 35
    evidence = []
    if len(title.strip()) >= 8:
        score += 15
        evidence.append("specific title")
    if len(description.strip()) >= 80:
        score += 20
        evidence.append("detailed description")
    if any(word in text for word in ("street", "road", "village", "ward", "school", "hospital", "district")):
        score += 15
        evidence.append("location or institution context")
    if any(word in text for word in ("http://", "https://", "buy now", "click here", "free money")):
        score -= 35
        evidence.append("spam-like content")
    score = max(0, min(score, 100))
    return score >= 55, score, evidence


# ---------- CREATE CHALLENGE (GUEST + DUPLICATE + UNIVERSITY MATCHING) ----------
@router.post("/", response_model=schemas.ChallengeOut, status_code=201)
async def create_challenge(
    title: str = Form(...),
    description: str = Form(...),
    source_language: str = Form("en"),
    latitude: Optional[float] = Form(None),
    longitude: Optional[float] = Form(None),
    guest: Optional[str] = Form(None),
    submitter_name: Optional[str] = Form(None),
    category: Optional[str] = Form(None),
    file: Optional[List[UploadFile]] = File(None),
    db: Session = Depends(get_db),
    current_user: Optional[models.User] = Depends(auth.get_optional_user),
):
    # ---------- AUTH RESOLUTION ----------
    is_guest = (current_user is None) or (guest == "true")
    citizen_id = None if is_guest else current_user.id
    display_name = (
        submitter_name if is_guest
        else (getattr(current_user, "name", None) or "Citizen")
    )
    print(f"[Challenge Submit] guest={is_guest} citizen_id={citizen_id} name={display_name}")

    # ---------- SAVE UPLOADED FILES ----------
    file_urls: List[str] = []
    if file:
        for f in file:
            if not f or not f.filename:
                continue
            safe_name = f"{citizen_id or 'guest'}_{int(time.time() * 1000)}_{f.filename}"
            file_path = os.path.join(UPLOAD_DIR, safe_name)
            try:
                with open(file_path, "wb") as buffer:
                    shutil.copyfileobj(f.file, buffer)
                file_urls.append(file_path)
            except Exception as e:
                print(f"[File Save Error] {e}")
    file_url = ",".join(file_urls) if file_urls else None

    # ---------- BUILD EXISTING CHALLENGES CONTEXT FOR AI ----------
    existing = db.query(models.Challenge).order_by(
        models.Challenge.created_at.desc()
    ).limit(50).all()

    existing_payload = []
    for ch in existing:
        best_sol = db.query(models.Solution).filter(
            models.Solution.challenge_id == ch.id
        ).order_by(models.Solution.ai_score.desc().nullslast()).first()

        uni_name = None
        if best_sol:
            uni = db.query(models.User).filter(
                models.User.id == best_sol.university_id
            ).first()
            uni_name = uni.name if uni else "Unknown University"

        existing_payload.append({
            "id": ch.id,
            "text": f"{ch.title}. {ch.description}",
            "solution_id": best_sol.id if best_sol else None,
            "solution_title": best_sol.title if best_sol else None,
            "solution_university": uni_name,
            "solution_status": best_sol.status if best_sol else None,
            "ai_score": best_sol.ai_score if best_sol else None,
        })

    # ---------- BUILD UNIVERSITY CONTEXT FOR AI ----------
    universities = db.query(models.User).filter(
        models.User.role == "university"
    ).all()

    universities_payload = []
    for uni in universities:
        universities_payload.append({
            "id": uni.id,
            "name": uni.name,
            "organization": uni.organization or "",
            "departments": uni.organization.split("|", 1)[1].strip() if "|" in (uni.organization or "") else uni.organization or "",
        })

    # ---------- CALL AI ENGINE ----------
    priority: int = 50
    duplicate_of: Optional[int] = None
    existing_solution = None
    matched_universities = []
    is_genuine = None
    authenticity_score = None
    authenticity_evidence = []

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            res = await client.post(
                f"{AI_ENGINE_URL}/process",
                json={
                    "title": title,
                    "description": description,
                    "category": category,
                    "existing_challenges": existing_payload,
                    "universities": universities_payload,
                }
            )
            if res.status_code == 200:
                ai_data = res.json()
                category = category or ai_data.get("category")
                priority = ai_data.get("priority", 50)
                duplicate_of = ai_data.get("duplicate_of")
                existing_solution = ai_data.get("existing_solution")
                matched_universities = ai_data.get("matched_universities", [])
                is_genuine = ai_data.get("is_genuine")
                authenticity_score = ai_data.get("authenticity_score")
                authenticity_evidence = ai_data.get("authenticity_evidence", [])
            else:
                print(f"[AI Engine] Non-200: {res.status_code}")
    except Exception as e:
        print(f"[AI Engine not reachable] {e}")

    # Keep quick reports in the same university flow when the AI service is unavailable.
    if not category:
        category = fallback_category(title, description)
    if not matched_universities:
        matched_universities = fallback_university_matches(category, universities)
    if is_genuine is None or authenticity_score is None:
        is_genuine, authenticity_score, authenticity_evidence = fallback_verification(title, description)

    # ---------- CREATE CHALLENGE ROW ----------
    challenge = models.Challenge(
        citizen_id=citizen_id,
        title=title,
        description=description,
        source_language=normalize_language(source_language),
        latitude=latitude,
        longitude=longitude,
        category=category,
        priority_score=priority,
        image_url=file_url,
        duplicate_of=duplicate_of,
        status="AI_PROCESSED" if category else "SUBMITTED",
        is_genuine=is_genuine,
        authenticity_score=authenticity_score,
        authenticity_evidence=json.dumps(authenticity_evidence),
        matched_universities=json.dumps(matched_universities),
    )
    if hasattr(challenge, "submitter_name"):
        challenge.submitter_name = display_name

    db.add(challenge)
    db.commit()
    db.refresh(challenge)

    for match in matched_universities:
        university_id = match.get("university_id") if isinstance(match, dict) else None
        add_notification(
            db, university_id, "ASSIGNED", "New problem assigned",
            f"{challenge.title} was matched to your university for a possible solution.",
            challenge_id=challenge.id,
        )
    if matched_universities:
        add_notification(
            db, challenge.citizen_id, "ASSIGNED", "Problem assigned",
            f"Your problem {challenge.title} was assigned to relevant university teams.",
            challenge_id=challenge.id,
        )
    db.commit()

    print(f"[Challenge Created] id={challenge.id} category={category} "
          f"dup_of={duplicate_of} matched_unis={len(matched_universities)}")
    return challenge


# ---------- LIST ALL CHALLENGES (PUBLIC) ----------
@router.get("/", response_model=List[schemas.ChallengeOut])
def list_challenges(
    status: Optional[str] = None,
    category: Optional[str] = None,
    db: Session = Depends(get_db),
):
    query = db.query(models.Challenge)
    if status:
        query = query.filter(models.Challenge.status == status)
    if category:
        query = query.filter(models.Challenge.category == category)
    return query.order_by(models.Challenge.priority_score.desc()).all()


# ---------- MY CHALLENGES (logged-in only) ----------
@router.get("/mine", response_model=List[schemas.ChallengeOut])
def my_challenges(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    return db.query(models.Challenge).filter(
        models.Challenge.citizen_id == current_user.id
    ).order_by(models.Challenge.created_at.desc()).all()


# ---------- CHECK IF DELETABLE (frontend pre-check) ----------
@router.get("/{challenge_id}/can-delete")
def can_delete_challenge(
    challenge_id: int,
    db: Session = Depends(get_db),
    current_user: Optional[models.User] = Depends(auth.get_optional_user),
):
    if not current_user:
        return {
            "can_delete": False,
            "reason": "not_logged_in",
            "message": "Login as the original reporter to delete this report.",
        }

    challenge = db.query(models.Challenge).filter(
        models.Challenge.id == challenge_id
    ).first()

    if not challenge:
        return {"can_delete": False, "reason": "not_found", "message": "Challenge not found."}

    is_admin = current_user.role in ("admin", "govt")
    is_owner = challenge.citizen_id == current_user.id

    if not is_admin and not is_owner:
        return {
            "can_delete": False,
            "reason": "not_owner",
            "message": "You can only delete your own reports.",
        }

    solution_count = db.query(models.Solution).filter(
        models.Solution.challenge_id == challenge_id
    ).count()

    if solution_count > 0 and not is_admin:
        return {
            "can_delete": False,
            "reason": "locked",
            "solution_count": solution_count,
            "message": f"Cannot delete — {solution_count} university solution(s) already submitted. Report is locked.",
        }

    return {"can_delete": True, "reason": "ok", "message": "You can delete this report."}


# ---------- WORKFLOW PROGRESS (PUBLIC) ----------
@router.get("/{challenge_id}/progress")
def challenge_progress(challenge_id: int, db: Session = Depends(get_db)):
    challenge = db.query(models.Challenge).filter(
        models.Challenge.id == challenge_id
    ).first()
    if not challenge:
        raise HTTPException(status_code=404, detail="Challenge not found")

    solutions = db.query(models.Solution).filter(
        models.Solution.challenge_id == challenge_id
    ).all()
    selected = [
        solution for solution in solutions
        if solution.expert_best_selected or solution.status == "EXPERT_SELECTED"
    ]
    workspaces = db.query(models.CollaborationWorkspace).filter(
        models.CollaborationWorkspace.challenge_id == challenge_id
    ).all()
    partnerships = db.query(models.IndustryPartnership).filter(
        models.IndustryPartnership.solution_id.in_([solution.id for solution in selected])
    ).all() if selected else []

    if challenge.status == "DEPLOYED" or any(
        workspace.stage.lower() in {"completed", "deployed"} or workspace.progress >= 100
        for workspace in workspaces
    ):
        current_stage = 6
    elif challenge.status == "PILOT" or any(
        workspace.stage.lower() == "pilot" for workspace in workspaces
    ):
        current_stage = 5
    elif challenge.status == "IN_PROGRESS" or selected or partnerships or workspaces:
        current_stage = 4
    elif solutions:
        current_stage = 3
    elif challenge.status == "PUBLISHED":
        current_stage = 2
    elif challenge.status == "AI_PROCESSED":
        current_stage = 1
    else:
        current_stage = 0

    return {
        "challenge_id": challenge_id,
        "current_stage": current_stage,
        "completed_stages": list(range(current_stage)),
        "solution_count": len(solutions),
        "selected_solution_count": len(selected),
        "partnership_count": len(partnerships),
        "workspace_count": len(workspaces),
    }


# ---------- DELETE CHALLENGE (citizen only, before solutions) ----------
@router.delete("/{challenge_id}", status_code=200)
def delete_challenge(
    challenge_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user),
):
    challenge = db.query(models.Challenge).filter(
        models.Challenge.id == challenge_id
    ).first()

    if not challenge:
        raise HTTPException(status_code=404, detail="Challenge not found")

    is_admin = current_user.role in ("admin", "govt")
    is_owner = challenge.citizen_id == current_user.id

    if not is_admin and not is_owner:
        raise HTTPException(status_code=403, detail="You can only delete your own reports.")

    solution_count = db.query(models.Solution).filter(
        models.Solution.challenge_id == challenge_id
    ).count()

    if solution_count > 0 and not is_admin:
        raise HTTPException(
            status_code=423,
            detail=f"This report cannot be deleted because {solution_count} university solution(s) have already been submitted. The report is now locked.",
        )

    if solution_count > 0 and is_admin:
        db.query(models.Solution).filter(
            models.Solution.challenge_id == challenge_id
        ).delete()

    if challenge.image_url:
        for path in challenge.image_url.split(","):
            path = path.strip()
            if path and os.path.exists(path):
                try:
                    os.remove(path)
                except Exception as e:
                    print(f"[File Delete Warning] {path}: {e}")

    db.delete(challenge)
    db.commit()

    print(f"[Challenge Deleted] id={challenge_id} by user={current_user.id} (role={current_user.role})")

    return {
        "deleted": True,
        "challenge_id": challenge_id,
        "message": "Report deleted successfully.",
    }


# ---------- GET ONE CHALLENGE (WITH DUPLICATE INFO + MATCHED UNIVERSITIES) ----------
@router.get("/{challenge_id}")
def get_challenge(
    challenge_id: int,
    language: Optional[str] = Query("en"),
    db: Session = Depends(get_db),
):
    challenge = db.query(models.Challenge).filter(
        models.Challenge.id == challenge_id
    ).first()
    if not challenge:
        raise HTTPException(status_code=404, detail="Challenge not found")

    original = None
    existing_solution = None
    if challenge.duplicate_of:
        original = db.query(models.Challenge).filter(
            models.Challenge.id == challenge.duplicate_of
        ).first()

        if original:
            best_sol = db.query(models.Solution).filter(
                models.Solution.challenge_id == original.id
            ).order_by(models.Solution.ai_score.desc().nullslast()).first()

            if best_sol:
                uni = db.query(models.User).filter(
                    models.User.id == best_sol.university_id
                ).first()
                existing_solution = {
                    "solution_id": best_sol.id,
                    "title": best_sol.title,
                    "proposal": best_sol.proposal,
                    "university_name": uni.name if uni else "Unknown University",
                    "organization": uni.organization if uni else None,
                    "status": best_sol.status,
                    "ai_score": best_sol.ai_score,
                }

    # Match universities for this challenge
    from routers.matching import parse_university_departments, score_university_for_category
    universities = db.query(models.User).filter(models.User.role == "university").all()
    matched = []
    for uni in universities:
        uni_depts = parse_university_departments(uni.organization)
        score, matched_depts = score_university_for_category(uni_depts, challenge.category or "")
        if score > 0:
            matched.append({
                "university_id": uni.id,
                "name": uni.name,
                "organization": uni.organization,
                "match_score": score,
                "matched_departments": matched_depts,
            })
    matched.sort(key=lambda x: x["match_score"], reverse=True)

    translated = translated_fields(challenge.title, challenge.description, challenge.source_language, language)
    return {
        "id": challenge.id,
        "citizen_id": challenge.citizen_id,
        "submitter_name": getattr(challenge, "submitter_name", None),
        "title": translated["title"],
        "description": translated["description"],
        "original_title": challenge.title,
        "original_description": challenge.description,
        "source_language": challenge.source_language,
        "translated_language": normalize_language(language),
        "category": challenge.category,
        "priority_score": challenge.priority_score,
        "latitude": challenge.latitude,
        "longitude": challenge.longitude,
        "voice_url": challenge.voice_url,
        "image_url": challenge.image_url,
        "status": challenge.status,
        "duplicate_of": challenge.duplicate_of,
        "created_at": challenge.created_at,
        "original_challenge": {
            "id": original.id,
            "title": original.title,
            "status": original.status,
        } if original else None,
        "existing_solution": existing_solution,
        "is_genuine": challenge.is_genuine,
        "authenticity_score": challenge.authenticity_score,
        "authenticity_evidence": challenge.authenticity_evidence,
        "matched_universities": matched[:5],
    }


# ---------- PUBLISH CHALLENGE (govt/admin only) ----------
@router.patch("/{challenge_id}/publish", response_model=schemas.ChallengeOut)
def publish_challenge(
    challenge_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_role("govt", "admin")),
):
    challenge = db.query(models.Challenge).filter(
        models.Challenge.id == challenge_id
    ).first()
    if not challenge:
        raise HTTPException(status_code=404, detail="Challenge not found")

    challenge.status = "PUBLISHED"
    db.commit()
    db.refresh(challenge)
    return challenge