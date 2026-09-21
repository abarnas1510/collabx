from fastapi import FastAPI
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from typing import Optional, List, Dict
import numpy as np
import csv
import re
from pathlib import Path

app = FastAPI(title="CollabX AI Engine")

print("Loading Sentence Transformer model...")
model = SentenceTransformer('all-MiniLM-L6-v2')
print("Model loaded ✅")


DATASET_PATH = Path(__file__).parent / "data" / "matching_examples.csv"
MATCHING_EXAMPLES = []
MATCHING_EMBEDDINGS = np.empty((0, 384))

CATEGORY_ALIASES = {
    "Water Resources": "Water & Resources",
    "Energy": "Energy & Electricity",
    "Environment": "Environment & Climate",
    "Rural Livelihoods": "Rural Development",
    "Disaster Management": "Public Safety",
}


def canonical_category(category: str) -> str:
    return CATEGORY_ALIASES.get(category, category)


def normalize_tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def load_matching_dataset():
    """Load labeled examples once so every report uses the same training set."""
    global MATCHING_EXAMPLES, MATCHING_EMBEDDINGS
    if not DATASET_PATH.exists():
        print(f"Matching dataset not found: {DATASET_PATH}")
        return

    with DATASET_PATH.open("r", encoding="utf-8-sig", newline="") as dataset_file:
        reader = csv.DictReader(dataset_file)
        MATCHING_EXAMPLES = [
            {
                "problem": row["citizen_problem"].strip(),
                "category": canonical_category(row["category"].strip()),
                "domain": row["university_domain"].strip(),
                "keywords": row["matching_keywords"].strip(),
            }
            for row in reader
            if row.get("citizen_problem") and row.get("category")
        ]

    example_texts = [
        f"{example['problem']}. {example['category']}. {example['domain']}. {example['keywords']}"
        for example in MATCHING_EXAMPLES
    ]
    MATCHING_EMBEDDINGS = model.encode(example_texts, normalize_embeddings=True)
    print(f"Loaded {len(MATCHING_EXAMPLES)} labeled matching examples")


load_matching_dataset()


class ExistingChallenge(BaseModel):
    id: int
    text: str
    solution_title: Optional[str] = None
    solution_university: Optional[str] = None
    solution_status: Optional[str] = None
    solution_id: Optional[int] = None
    ai_score: Optional[float] = None


class UniversityProfile(BaseModel):
    id: int
    name: str
    organization: str
    departments: Optional[str] = None


class Report(BaseModel):
    title: str
    description: str
    existing_challenges: Optional[List[ExistingChallenge]] = None
    universities: Optional[List[UniversityProfile]] = None
    category: Optional[str] = None


class SolutionScreen(BaseModel):
    challenge_title: str
    challenge_description: str
    solution_title: str
    solution_proposal: str


CATEGORIES = [
    "Infrastructure & Roads", "Water & Resources", "Energy & Electricity",
    "Healthcare", "Education", "Agriculture", "Environment & Climate",
    "Waste Management", "Transport & Mobility", "Public Safety",
    "Urban Development", "Industry & Manufacturing", "Rural Development",
    "Accessibility", "Public Administration",
]

CATEGORY_KEYWORDS: Dict[str, List[str]] = {
    "Infrastructure & Roads": ["road", "pothole", "street", "bridge", "pavement", "highway", "infrastructure"],
    "Water & Resources": ["water", "pipe", "leak", "supply", "tap", "well", "drain", "tank", "irrigation"],
    "Energy & Electricity": ["electric", "power", "light", "streetlight", "wire", "transformer", "outage", "solar"],
    "Education": ["school", "college", "student", "teacher", "education", "learning", "exam"],
    "Agriculture": ["farm", "crop", "seed", "harvest", "irrigation", "agriculture", "soil"],
    "Healthcare": ["hospital", "clinic", "doctor", "medicine", "disease", "health", "patient"],
    "Environment & Climate": ["pollution", "tree", "forest", "river", "climate", "environment", "emission"],
    "Waste Management": ["waste", "garbage", "trash", "recycling", "dump", "litter", "sanitation"],
    "Transport & Mobility": ["transport", "bus", "traffic", "vehicle", "mobility", "metro", "transit"],
    "Public Safety": ["safety", "crime", "fire", "emergency", "police", "accident", "danger"],
    "Urban Development": ["city", "urban", "town", "housing", "planning", "development"],
    "Industry & Manufacturing": ["industry", "factory", "manufacturing", "industrial", "production", "workshop"],
    "Rural Development": ["village", "rural", "farmer", "livelihood", "panchayat", "employment"],
    "Accessibility": ["wheelchair", "ramp", "blind", "disabled", "accessibility", "barrier"],
    "Public Administration": ["safety", "crime", "fire", "emergency", "police", "certificate"],
}

DEPARTMENT_CATEGORY_MAP: Dict[str, List[str]] = {
    "Civil Engineering": ["Water Resources", "Urban Development", "Environment"],
    "Environmental Engineering": ["Water Resources", "Environment"],
    "Urban Planning": ["Urban Development", "Accessibility", "Public Administration"],
    "Architecture": ["Urban Development", "Accessibility"],
    "Mechanical Engineering": ["Energy", "Agriculture", "Urban Development"],
    "Electrical Engineering": ["Energy"],
    "Energy Studies": ["Energy"],
    "Chemical Engineering": ["Water Resources", "Environment", "Energy"],
    "Materials Engineering": ["Water Resources", "Environment", "Energy"],
    "Water Resources Engineering": ["Water Resources", "Environment"],
    "Computer Science": ["Public Administration", "Accessibility", "Education", "Urban Development"],
    "Public Health": ["Healthcare", "Water Resources", "Environment"],
    "Medicine": ["Healthcare"],
    "Biomedical Engineering": ["Healthcare"],
    "Life Sciences": ["Healthcare", "Agriculture", "Environment"],
    "Agriculture": ["Agriculture", "Rural Livelihoods", "Environment"],
    "Agricultural Engineering": ["Agriculture", "Rural Livelihoods"],
    "Environmental Science": ["Environment", "Water Resources"],
    "Ecology": ["Environment"],
    "Education": ["Education"],
    "Social Sciences": ["Education", "Rural Livelihoods", "Accessibility", "Public Administration"],
    "Public Policy": ["Public Administration", "Accessibility", "Urban Development"],
    "Law": ["Public Administration", "Accessibility"],
    "Economics": ["Rural Livelihoods", "Public Administration", "Urban Development"],
    "Hydrology": ["Water Resources", "Agriculture", "Disaster Management"],
    "Disaster Management": ["Disaster Management"],
    "Agricultural Technology": ["Agriculture", "Rural Livelihoods"],
    "Agricultural Science": ["Agriculture", "Rural Livelihoods"],
    "Food Technology": ["Agriculture", "Rural Livelihoods", "Environment"],
    "Dairy Science": ["Agriculture", "Rural Livelihoods"],
    "Renewable Energy Engineering": ["Energy"],
    "Health Technology": ["Healthcare", "Accessibility"],
    "Health Informatics": ["Healthcare", "Public Administration"],
    "Computer Vision": ["Environment", "Public Administration"],
    "Transportation Engineering": ["Urban Development", "Accessibility"],
    "GIS": ["Disaster Management", "Urban Development", "Environment"],
    "IoT": ["Energy", "Environment", "Water Resources", "Agriculture"],
    "NLP": ["Public Administration", "Education", "Accessibility"],
    "Management": ["Rural Livelihoods", "Education", "Public Administration"],
    "Rural Development": ["Rural Livelihoods"],
    "Ocean Engineering": ["Disaster Management", "Rural Livelihoods"],
    "Meteorology": ["Disaster Management", "Agriculture"],
    "Mobile Computing": ["Public Administration"],
    "Assistive Technology": ["Accessibility", "Healthcare"],
}

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


def split_domains(value: str) -> List[str]:
    return [part.strip().lower() for part in re.split(r"[/,;|]", value or "") if part.strip()]


DOMAIN_EQUIVALENTS = {
    "health technology": {"health technology", "computer science", "public health", "biomedical engineering", "medicine"},
    "health informatics": {"health informatics", "computer science", "public health"},
    "computer science": {"computer science", "information systems", "mobile computing"},
    "ai": {"ai", "computer science", "data science"},
    "machine learning": {"machine learning", "computer science", "data science"},
    "iot": {"iot", "computer science", "electrical engineering", "electronics"},
    "gis": {"gis", "computer science", "civil engineering", "urban planning"},
    "transportation engineering": {"transportation engineering", "civil engineering", "urban planning"},
    "hydrology": {"hydrology", "civil engineering", "water resources engineering", "environmental engineering"},
    "agricultural technology": {"agricultural technology", "agriculture", "agricultural engineering"},
    "agricultural science": {"agricultural science", "agriculture", "agricultural engineering"},
    "food technology": {"food technology", "agricultural engineering", "agriculture"},
    "dairy science": {"dairy science", "agriculture", "food technology"},
    "renewable energy engineering": {"renewable energy engineering", "electrical engineering", "energy studies"},
    "nlp": {"nlp", "computer science", "language technology"},
    "computer vision": {"computer vision", "computer science", "environmental engineering"},
    "assistive technology": {"assistive technology", "computer science", "biomedical engineering"},
    "ocean engineering": {"ocean engineering", "civil engineering", "computer science"},
    "meteorology": {"meteorology", "agriculture", "environmental science"},
}


def domains_match(registered: str, dataset_domain: str) -> bool:
    registered_lower = registered.lower().strip()
    dataset_parts = split_domains(dataset_domain)
    for dataset_part in dataset_parts:
        if registered_lower == dataset_part:
            return True
        equivalents = DOMAIN_EQUIVALENTS.get(dataset_part, {dataset_part})
        if registered_lower in equivalents:
            return True
    return False

URGENT_WORDS = [
    "accident", "urgent", "danger", "emergency", "death", "injury",
    "fire", "flood", "disease", "outbreak", "critical", "severe",
    "children", "hospital", "immediate", "risk",
]

REPORT_STORE = []
DUPLICATE_THRESHOLD = 0.80


def verify_report(title: str, description: str):
    """Return a transparent heuristic authenticity check, not a claim of fact."""
    text = f"{title}. {description}".strip()
    lowered = text.lower()
    score = 35
    evidence = []

    if len(title.strip()) >= 8:
        score += 15
        evidence.append("specific title")
    if len(description.strip()) >= 80:
        score += 20
        evidence.append("detailed description")
    if any(word in lowered for word in ["street", "road", "village", "ward", "school", "hospital", "district"]):
        score += 15
        evidence.append("location or institution context")
    if any(word in lowered for word in ["http://", "https://", "buy now", "click here", "free money"]):
        score -= 35
        evidence.append("spam-like content")

    score = max(0, min(score, 100))
    return score, score >= 55, evidence


def classify_category(text: str):
    text_embedding = model.encode([text], normalize_embeddings=True)
    text_lower = text.lower()
    scores = {category: 0.0 for category in CATEGORIES}

    if MATCHING_EXAMPLES:
        example_sims = cosine_similarity(text_embedding, MATCHING_EMBEDDINGS)[0]
        for index, example in enumerate(MATCHING_EXAMPLES):
            overlap = len(normalize_tokens(text) & normalize_tokens(example["keywords"]))
            keyword_bonus = min(overlap * 0.035, 0.14)
            scores[example["category"]] += max(float(example_sims[index]), 0) + keyword_bonus
        counts = {category: 0 for category in CATEGORIES}
        for example in MATCHING_EXAMPLES:
            counts[example["category"]] += 1
        scores = {category: score / max(counts[category], 1) for category, score in scores.items()}

    for i, cat in enumerate(CATEGORIES):
        for kw in CATEGORY_KEYWORDS.get(cat, []):
            if kw in text_lower:
                scores[cat] += 0.08
    category = max(scores, key=scores.get)
    return category, float(scores[category])


def score_priority(text: str, description: str):
    priority = 40
    matched = []
    text_lower = text.lower()
    for word in URGENT_WORDS:
        if word in text_lower:
            priority += 5
            matched.append(word)
    if len(description) > 100:
        priority += 5
    if len(description) > 200:
        priority += 5
    return min(priority, 100), matched


def match_universities(category: str, universities: List[UniversityProfile], text: str = "") -> List[dict]:
    matching_category = {
        "Infrastructure & Roads": "Urban Development",
        "Water & Resources": "Water Resources",
        "Energy & Electricity": "Energy",
        "Environment & Climate": "Environment",
        "Waste Management": "Environment",
        "Transport & Mobility": "Urban Development",
        "Public Safety": "Disaster Management",
        "Rural Development": "Rural Livelihoods",
        "Industry & Manufacturing": "Energy",
    }.get(category, category)
    required_depts = set()
    for dept, cats in DEPARTMENT_CATEGORY_MAP.items():
        if matching_category in cats:
            required_depts.add(normalize_department(dept))

    domain_scores = {}
    if MATCHING_EXAMPLES and text:
        text_embedding = model.encode([text], normalize_embeddings=True)
        example_sims = cosine_similarity(text_embedding, MATCHING_EMBEDDINGS)[0]
        for index, example in enumerate(MATCHING_EXAMPLES):
            if example["category"] == category and float(example_sims[index]) >= 0.42:
                domain_scores[example["domain"].lower()] = max(
                    domain_scores.get(example["domain"].lower(), 0),
                    float(example_sims[index]),
                )

    matches = []
    for uni in universities:
        dept_text = uni.departments or ""
        if "|" in (uni.organization or ""):
            parts = uni.organization.split("|", 1)
            if len(parts) > 1:
                dept_text = parts[1]
        elif uni.organization:
            dept_text = uni.organization

        uni_depts = [d.strip().lower() for d in dept_text.split(",") if d.strip()]
        score = 0
        matched_depts = []
        for ud in uni_depts:
            for req in required_depts:
                if normalize_department(ud) == req:
                    score += 35
                    matched_depts.append(ud)
                    break

        if matched_depts:
            score = min(50 + (len(matched_depts) - 1) * 25, 100)
        if score > 0:
            matches.append({
                "university_id": uni.id,
                "name": uni.name,
                "organization": uni.organization,
                "match_score": score,
                "matched_departments": matched_depts,
                "reason": f"Dataset and category evidence: {', '.join(matched_depts)}",
            })

    matches.sort(key=lambda x: x["match_score"], reverse=True)
    return matches[:5]


@app.post("/process")
def process_report(report: Report):
    text = f"{report.title}. {report.description}"
    category, confidence = classify_category(text)
    if report.category in CATEGORIES:
        category = report.category
    priority, urgent_kws = score_priority(text, report.description)
    authenticity_score, is_genuine, authenticity_evidence = verify_report(report.title, report.description)
    text_embedding = model.encode([text])

    duplicate_of = None
    duplicate_score = 0.0
    if REPORT_STORE:
        past_embeddings = np.array([r["embedding"] for r in REPORT_STORE])
        sims_dup = cosine_similarity(text_embedding, past_embeddings)[0]
        best_idx = int(np.argmax(sims_dup))
        best_score = float(sims_dup[best_idx])
        if best_score > DUPLICATE_THRESHOLD:
            duplicate_of = REPORT_STORE[best_idx]["id"]
            duplicate_score = best_score

    existing_solution = None
    if report.existing_challenges:
        existing_texts = [c.text for c in report.existing_challenges]
        existing_embeddings = model.encode(existing_texts)
        sims_ex = cosine_similarity(text_embedding, existing_embeddings)[0]
        best_ex_idx = int(np.argmax(sims_ex))
        best_ex_score = float(sims_ex[best_ex_idx])
        best_ex = report.existing_challenges[best_ex_idx]
        if best_ex_score > DUPLICATE_THRESHOLD and best_ex_score > duplicate_score:
            duplicate_of = best_ex.id
            duplicate_score = best_ex_score
            if best_ex.solution_id is not None:
                existing_solution = {
                    "solution_id": best_ex.solution_id,
                    "title": best_ex.solution_title or "Untitled",
                    "university": best_ex.solution_university or "Unknown",
                    "status": best_ex.solution_status or "PENDING",
                    "ai_score": best_ex.ai_score,
                }

    matched_universities = []
    if report.universities:
        matched_universities = match_universities(category, report.universities, text)

    new_id = len(REPORT_STORE) + 1
    REPORT_STORE.append({
        "id": new_id,
        "text": text,
        "embedding": text_embedding[0].tolist(),
    })

    return {
        "category": category,
        "category_confidence": round(confidence, 3),
        "priority": priority,
        "urgent_keywords": urgent_kws,
        "is_genuine": is_genuine,
        "authenticity_score": authenticity_score,
        "authenticity_evidence": authenticity_evidence,
        "duplicate_of": duplicate_of,
        "duplicate_score": round(duplicate_score, 3),
        "existing_solution": existing_solution,
        "matched_universities": matched_universities,
    }


def infer_industry_sector(text: str) -> str:
    sector_keywords = [
        ("Agriculture", ["agriculture", "farm", "irrigation", "crop", "soil", "agri"]),
        ("Healthcare", [
            "health", "healthcare", "hospital", "clinic", "medical", "medicine",
            "medicines", "medication", "pharmacy", "pharmaceutical", "patient",
            "doctor", "nurse", "disease", "diagnosis", "treatment", "therapy",
            "wellness", "public health",
        ]),
        ("Energy & Utilities", ["energy", "solar", "power", "electricity", "renewable", "utility"]),
        ("Transport & Logistics", ["transport", "traffic", "logistics", "vehicle", "mobility", "road"]),
        ("Manufacturing", ["manufacturing", "factory", "industrial", "production", "assembly"]),
        ("Information Technology", ["software", "technology", "iot", "sensor", "data", "app", "platform"]),
        ("Education", ["education", "school", "student", "university", "learning", "classroom"]),
    ]
    text_lower = text.lower()
    ranked = sorted(
        ((sum(text_lower.count(keyword) for keyword in keywords), sector) for sector, keywords in sector_keywords),
        reverse=True,
    )
    return ranked[0][1] if ranked and ranked[0][0] else "General"


@app.post("/screen")
def screen_solution(payload: SolutionScreen):
    challenge_text = f"{payload.challenge_title}. {payload.challenge_description}"
    solution_text = f"{payload.solution_title}. {payload.solution_proposal}"
    required_industry_sector = infer_industry_sector(f"{challenge_text}. {solution_text}")
    ch_emb = model.encode([challenge_text])
    sol_emb = model.encode([solution_text])
    relevance = float(cosine_similarity(ch_emb, sol_emb)[0][0])

    tech_keywords = ["algorithm", "system", "prototype", "model", "design", "sensor",
                     "app", "platform", "iot", "ai", "data", "analysis", "test",
                     "implementation", "pilot", "budget", "timeline", "team"]
    sol_lower = solution_text.lower()
    keyword_hits = sum(1 for kw in tech_keywords if kw in sol_lower)
    length_score = min(len(payload.solution_proposal) / 500, 1.0)

    score = relevance * 50 + min(keyword_hits * 3, 30) + length_score * 20
    score = round(min(score, 100), 2)

    explanations = []
    if relevance > 0.5:
        explanations.append("Solution is highly relevant to the challenge")
    elif relevance > 0.3:
        explanations.append("Solution is moderately relevant")
    else:
        explanations.append("Solution may not address the challenge directly")

    if keyword_hits >= 5:
        explanations.append(f"Strong technical vocabulary ({keyword_hits} keywords)")
    elif keyword_hits >= 2:
        explanations.append(f"Some technical depth ({keyword_hits} keywords)")

    if length_score > 0.6:
        explanations.append("Detailed proposal with good explanation")

    return {
        "score": score,
        "explanation": " | ".join(explanations),
        "relevance": round(relevance, 3),
        "keyword_hits": keyword_hits,
        "required_industry_sector": required_industry_sector,
    }


class FindSimilarRequest(BaseModel):
    title: str
    description: str
    existing_challenges: List[ExistingChallenge]


@app.post("/find-similar")
def find_similar(payload: FindSimilarRequest):
    text = f"{payload.title}. {payload.description}"
    text_embedding = model.encode([text])
    if not payload.existing_challenges:
        return {"matches": []}
    existing_texts = [c.text for c in payload.existing_challenges]
    existing_embeddings = model.encode(existing_texts)
    sims = cosine_similarity(text_embedding, existing_embeddings)[0]
    results = []
    for i, score in enumerate(sims):
        if score > 0.60:
            c = payload.existing_challenges[i]
            results.append({
                "challenge_id": c.id,
                "score": float(score),
                "title": c.text[:80],
                "has_solution": c.solution_id is not None,
                "solution_university": c.solution_university,
            })
    results.sort(key=lambda x: x["score"], reverse=True)
    return {"matches": results[:5]}


@app.get("/")
def home():
    return {"message": "CollabX AI Engine is running 🧠"}