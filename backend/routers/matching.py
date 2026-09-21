from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
import json
from database import get_db
import models, schemas, auth
from translation import normalize_language, translate_text

router = APIRouter(prefix="/matching", tags=["Matching"])


# ============================================================
# DEPARTMENT → CATEGORY MAP
# ============================================================
DEPARTMENT_CATEGORY_MAP = {
    "Civil Engineering": ["Infrastructure & Roads", "Water & Resources", "Urban Development", "Environment & Climate"],
    "Environmental Engineering": ["Water & Resources", "Environment & Climate", "Waste Management"],
    "Urban Planning": ["Infrastructure & Roads", "Urban Development", "Accessibility", "Public Administration"],
    "Architecture": ["Infrastructure & Roads", "Urban Development", "Accessibility"],
    "Mechanical Engineering": ["Energy & Electricity", "Agriculture", "Industry & Manufacturing"],
    "Electrical Engineering": ["Energy & Electricity"],
    "Energy Studies": ["Energy & Electricity"],
    "Chemical Engineering": ["Water & Resources", "Environment & Climate", "Energy & Electricity", "Industry & Manufacturing"],
    "Materials Engineering": ["Infrastructure & Roads", "Energy & Electricity", "Industry & Manufacturing"],
    "Water Resources Engineering": ["Water & Resources", "Environment & Climate"],
    "Computer Science": ["Public Administration", "Accessibility", "Education", "Urban Development", "Transport & Mobility", "Healthcare"],
    "Public Health": ["Healthcare", "Water & Resources", "Environment & Climate"],
    "Medicine": ["Healthcare"],
    "Biomedical Engineering": ["Healthcare"],
    "Life Sciences": ["Healthcare", "Agriculture", "Environment & Climate"],
    "Agriculture": ["Agriculture", "Rural Development", "Environment & Climate"],
    "Agricultural Engineering": ["Agriculture", "Rural Development"],
    "Environmental Science": ["Environment & Climate", "Water & Resources"],
    "Ecology": ["Environment"],
    "Education": ["Education"],
    "Social Sciences": ["Education", "Rural Development", "Accessibility", "Public Administration"],
    "Public Policy": ["Public Administration", "Accessibility", "Urban Development", "Rural Development"],
    "Law": ["Public Administration", "Accessibility", "Public Safety"],
    "Economics": ["Rural Development", "Public Administration", "Urban Development", "Industry & Manufacturing"],
    "Hydrology": ["Water & Resources", "Agriculture"],
    "Disaster Management": ["Public Safety", "Infrastructure & Roads"],
    "Agricultural Technology": ["Agriculture", "Rural Development"],
    "Agricultural Science": ["Agriculture", "Rural Development"],
    "Food Technology": ["Agriculture", "Rural Development", "Waste Management", "Industry & Manufacturing"],
    "Dairy Science": ["Agriculture", "Rural Development"],
    "Renewable Energy Engineering": ["Energy & Electricity"],
    "Health Technology": ["Healthcare", "Accessibility"],
    "Health Informatics": ["Healthcare", "Public Administration"],
    "Computer Vision": ["Environment & Climate", "Public Safety", "Public Administration"],
    "Transportation Engineering": ["Infrastructure & Roads", "Transport & Mobility", "Accessibility"],
    "GIS": ["Public Safety", "Urban Development", "Environment & Climate", "Rural Development"],
    "IoT": ["Energy & Electricity", "Environment & Climate", "Water & Resources", "Agriculture", "Industry & Manufacturing"],
    "NLP": ["Public Administration", "Education", "Accessibility"],
    "Management": ["Rural Development", "Education", "Public Administration", "Industry & Manufacturing"],
    "Rural Development": ["Rural Development"],
    "Ocean Engineering": ["Public Safety", "Rural Development"],
    "Meteorology": ["Public Safety", "Agriculture", "Environment & Climate"],
    "Mobile Computing": ["Public Administration", "Transport & Mobility"],
    "Assistive Technology": ["Accessibility", "Healthcare"],
    "Manufacturing": ["Industry & Manufacturing"],
    "Public Safety": ["Public Safety"],
    "Waste Management": ["Waste Management", "Environment & Climate"],
}

# Include close and slight matches so universities can review relevant challenges.
MIN_MATCH_SCORE = 25

DEPARTMENT_ALIASES = {
    "ece": "computer science",
    "computer science and engineering": "computer science",
    "information technology": "computer science",
    "agricultural economics": "economics",
    "agricultural tech": "agricultural technology",
    "education technology": "education",
    "edtech": "education",
}


def normalize_department(value: str) -> str:
    normalized = " ".join((value or "").lower().replace("&", "and").split())
    return DEPARTMENT_ALIASES.get(normalized, normalized)


# ============================================================
# HELPER: PARSE UNIVERSITY DEPARTMENTS
# ============================================================
def parse_university_departments(organization: str) -> List[str]:
    """
    Parses a university's organization string into a list of lowercase departments.

    Expected format from register.html:
        "IIT Delhi | Civil Engineering, Computer Science, Environmental Engineering"

    Falls back gracefully if format is different.
    """
    if not organization:
        return []

    if "|" in organization:
        _, depts_str = organization.split("|", 1)
        return [normalize_department(d) for d in depts_str.split(",") if d.strip()]

    # Fallback — treat whole string as one department
    return [normalize_department(organization)]


# ============================================================
# HELPER: SCORE UNIVERSITY FOR CATEGORY
# ============================================================
def score_university_for_category(uni_depts: List[str], category: str) -> tuple[int, List[str]]:
    """
    Returns (score, matched_depts).

    - "General" category → NO match (score 0)
    - Other categories → 50 points per matched department, capped at 100
    """
    # "General" and other unmapped categories should never match
    if not category or category == "General":
        return 0, []

    # Find which departments are relevant for this category
    required_depts = set()
    for dept, cats in DEPARTMENT_CATEGORY_MAP.items():
        if category in cats:
            required_depts.add(normalize_department(dept))

    if not required_depts:
        # No department in our map covers this category
        return 0, []

    # Check which of the university's departments match
    matched = []
    for ud in uni_depts:
        normalized_ud = normalize_department(ud)
        if normalized_ud in required_depts:
            matched.append(ud)

    # Score: 50 points per match, capped at 100
    score = min(len(matched) * 50, 100)
    return score, matched


# ============================================================
# GET MATCHED UNIVERSITIES FOR A CHALLENGE
# ============================================================
@router.get("/challenge/{challenge_id}")
def match_universities(challenge_id: int, db: Session = Depends(get_db)):
    """
    Returns a ranked list of universities best suited for a given challenge,
    based on their registered departments. Close and slight matches are retained.
    """
    challenge = db.query(models.Challenge).filter(
        models.Challenge.id == challenge_id
    ).first()
    if not challenge:
        raise HTTPException(status_code=404, detail="Challenge not found")

    category = challenge.category or "General"

    universities = db.query(models.User).filter(
        models.User.role == "university"
    ).all()

    matches = []
    for uni in universities:
        uni_depts = parse_university_departments(uni.organization)
        score, matched_depts = score_university_for_category(uni_depts, category)
        # Small bonus for proven track record (max +10)
        past_solutions = db.query(models.Solution).filter(
            models.Solution.university_id == uni.id
        ).count()
        score += min(past_solutions * 3, 10)
        score = min(score, 100)

        # ⭐ Only include real matches
        if score < MIN_MATCH_SCORE:
            continue

        matches.append({
            "university_id": uni.id,
            "name": uni.name,
            "organization": uni.organization,
            "departments": uni_depts,
            "matched_departments": matched_depts,
            "past_solutions": past_solutions,
            "match_score": score,
        })

    matches.sort(key=lambda x: x["match_score"], reverse=True)
    return {
        "challenge_id": challenge_id,
        "category": category,
        "matched_universities": matches,
    }


# ============================================================
# RECOMMENDED CHALLENGES FOR A UNIVERSITY
# ============================================================
@router.get("/university/recommended")
def recommended_for_university(
    language: Optional[str] = Query("en"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.require_role("university")),
):
    """
    Returns challenges matched to the logged-in university based on its departments.
    Close and slight matches are retained when a department is relevant.
    """
    uni_depts = parse_university_departments(current_user.organization)

    # Get all open challenges
    challenges = db.query(models.Challenge).filter(
        models.Challenge.status.in_(["PUBLISHED", "AI_PROCESSED", "SUBMITTED"])
    ).all()

    recommendations = []
    for ch in challenges:
        category = ch.category or "General"
        score, matched = score_university_for_category(uni_depts, category)

        # ⭐ Skip anything that isn't a real category match
        if score < MIN_MATCH_SCORE:
            continue

        # Small priority bonus (max +10) — applied only AFTER the match check
        priority_bonus = min(ch.priority_score // 10, 10)
        final_score = min(score + priority_bonus, 100)

        recommendations.append({
            "challenge_id": ch.id,
            "title": translate_text(ch.title, ch.source_language, language),
            "original_title": ch.title,
            "source_language": ch.source_language,
            "translated_language": normalize_language(language),
            "category": category,
            "priority_score": ch.priority_score,
            "match_score": final_score,
            "matched_departments": matched,
            "is_genuine": ch.is_genuine,
            "authenticity_score": ch.authenticity_score,
        })

    recommendations.sort(key=lambda x: x["match_score"], reverse=True)
    return recommendations[:10]


# ============================================================
# PLATFORM STATS (admin/govt)
# ============================================================
@router.get("/stats")
def platform_stats(db: Session = Depends(get_db)):
    return {
        "total_challenges": db.query(models.Challenge).count(),
        "published_challenges": db.query(models.Challenge).filter(
            models.Challenge.status == "PUBLISHED"
        ).count(),
        "total_solutions": db.query(models.Solution).count(),
        "selected_solutions": db.query(models.Solution).filter(
            models.Solution.status == "SELECTED"
        ).count(),
        "total_users": db.query(models.User).count(),
        "universities": db.query(models.User).filter(
            models.User.role == "university"
        ).count(),
        "industries": db.query(models.User).filter(
            models.User.role == "industry"
        ).count(),
        "citizens": db.query(models.User).filter(
            models.User.role == "citizen"
        ).count(),
        "experts": db.query(models.User).filter(
            models.User.role == "expert"
        ).count(),
        "government": db.query(models.User).filter(
            models.User.role == "govt"
        ).count(),
        "admins": db.query(models.User).filter(
            models.User.role == "admin"
        ).count(),
    }