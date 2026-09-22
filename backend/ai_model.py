import csv
import os
import re
from threading import Lock
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

MODEL_NAME = os.getenv("MODEL_NAME", "sentence-transformers/all-MiniLM-L6-v2")

model: Optional[Any] = None

def get_model() -> Any:
    global model
    if model is None:
        from sentence_transformers import SentenceTransformer

        print(f"Loading Sentence Transformer model: {MODEL_NAME}")
        model = SentenceTransformer(MODEL_NAME)
        print("Sentence Transformer model loaded")
    return model

DATASET_PATH = Path(__file__).resolve().parent.parent / "ai-engine" / "data" / "matching_examples.csv"
MATCHING_EXAMPLES: list[dict] = []
MATCHING_EMBEDDINGS = np.empty((0, 384))
_matching_dataset_loaded = False
_matching_dataset_lock = Lock()

CATEGORIES = [
    "Infrastructure & Roads", "Water & Resources", "Energy & Electricity",
    "Healthcare", "Education", "Agriculture", "Environment & Climate",
    "Waste Management", "Transport & Mobility", "Public Safety",
    "Urban Development", "Industry & Manufacturing", "Rural Development",
    "Accessibility", "Public Administration",
]

CATEGORY_ALIASES = {
    "Water Resources": "Water & Resources",
    "Energy": "Energy & Electricity",
    "Environment": "Environment & Climate",
    "Rural Livelihoods": "Rural Development",
    "Disaster Management": "Public Safety",
}

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

URGENT_WORDS = [
    "accident", "urgent", "danger", "emergency", "death", "injury",
    "fire", "flood", "disease", "outbreak", "critical", "severe",
    "children", "hospital", "immediate", "risk",
]
DUPLICATE_THRESHOLD = 0.80
REPORT_STORE: list[dict] = []


def normalize_tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def normalize_department(value: str) -> str:
    normalized = " ".join((value or "").lower().replace("&", "and").split())
    return DEPARTMENT_ALIASES.get(normalized, normalized)


def load_matching_dataset() -> None:
    global MATCHING_EXAMPLES, MATCHING_EMBEDDINGS, _matching_dataset_loaded
    if _matching_dataset_loaded:
        return
    with _matching_dataset_lock:
        if _matching_dataset_loaded:
            return
        if not DATASET_PATH.exists():
            print(f"Matching dataset not found: {DATASET_PATH}")
            _matching_dataset_loaded = True
            return
        with DATASET_PATH.open("r", encoding="utf-8-sig", newline="") as dataset_file:
            reader = csv.DictReader(dataset_file)
            MATCHING_EXAMPLES = [
                {
                    "problem": row["citizen_problem"].strip(),
                    "category": CATEGORY_ALIASES.get(row["category"].strip(), row["category"].strip()),
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
        if example_texts:
            MATCHING_EMBEDDINGS = get_model().encode(example_texts, normalize_embeddings=True)
            del example_texts
        _matching_dataset_loaded = True
        print(f"Loaded {len(MATCHING_EXAMPLES)} labeled matching examples")





def classify_category(text: str) -> tuple[str, float]:
    load_matching_dataset()
    text_embedding = get_model().encode([text], normalize_embeddings=True)
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
    del text_embedding
    for category in CATEGORIES:
        for keyword in CATEGORY_KEYWORDS.get(category, []):
            if keyword in text_lower:
                scores[category] += 0.08
    category = max(scores, key=scores.get)
    return category, float(scores[category])


def score_priority(text: str, description: str) -> tuple[int, list[str]]:
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


def match_universities(category: str, universities: List[dict], text: str = "") -> List[dict]:
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
    for department, categories in DEPARTMENT_CATEGORY_MAP.items():
        if matching_category in categories:
            required_depts.add(normalize_department(department))

    matches = []
    for university in universities:
        department_text = university.get("departments") or ""
        if "|" in (university.get("organization") or ""):
            department_text = university["organization"].split("|", 1)[1]
        elif university.get("organization"):
            department_text = university["organization"]
        departments = [item.strip().lower() for item in department_text.split(",") if item.strip()]
        matched_departments = [
            department for department in departments
            if any(normalize_department(department) == required for required in required_depts)
        ]
        if matched_departments:
            score = min(50 + (len(matched_departments) - 1) * 25, 100)
            matches.append({
                "university_id": university["id"],
                "name": university["name"],
                "organization": university["organization"],
                "match_score": score,
                "matched_departments": matched_departments,
                "reason": f"Dataset and category evidence: {', '.join(matched_departments)}",
            })
    matches.sort(key=lambda item: item["match_score"], reverse=True)
    return matches[:5]


def verify_report(title: str, description: str) -> tuple[int, bool, list[str]]:
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


def process_report(payload: dict) -> dict:
    title = payload["title"]
    description = payload["description"]
    text = f"{title}. {description}"
    category, confidence = classify_category(text)
    if payload.get("category") in CATEGORIES:
        category = payload["category"]
    priority, urgent_keywords = score_priority(text, description)
    authenticity_score, is_genuine, authenticity_evidence = verify_report(title, description)
    text_embedding = get_model().encode([text])

    duplicate_of = None
    duplicate_score = 0.0
    if REPORT_STORE:
        past_embeddings = np.array([item["embedding"] for item in REPORT_STORE])
        similarities = cosine_similarity(text_embedding, past_embeddings)[0]
        best_index = int(np.argmax(similarities))
        best_score = float(similarities[best_index])
        if best_score > DUPLICATE_THRESHOLD:
            duplicate_of = REPORT_STORE[best_index]["id"]
            duplicate_score = best_score
        del past_embeddings

    existing_solution = None
    existing_challenges = payload.get("existing_challenges") or []
    if existing_challenges:
        existing_embeddings = get_model().encode([item["text"] for item in existing_challenges])
        similarities = cosine_similarity(text_embedding, existing_embeddings)[0]
        best_index = int(np.argmax(similarities))
        best_score = float(similarities[best_index])
        best = existing_challenges[best_index]
        if best_score > DUPLICATE_THRESHOLD and best_score > duplicate_score:
            duplicate_of = best["id"]
            duplicate_score = best_score
            if best.get("solution_id") is not None:
                existing_solution = {
                    "solution_id": best["solution_id"],
                    "title": best.get("solution_title") or "Untitled",
                    "university": best.get("solution_university") or "Unknown",
                    "status": best.get("solution_status") or "PENDING",
                    "ai_score": best.get("ai_score"),
                }
        del existing_embeddings

    universities = payload.get("universities") or []
    matched_universities = match_universities(category, universities, text)
    REPORT_STORE.append({"id": len(REPORT_STORE) + 1, "text": text, "embedding": text_embedding[0].tolist()})
    del text_embedding
    return {
        "category": category,
        "category_confidence": round(confidence, 3),
        "priority": priority,
        "urgent_keywords": urgent_keywords,
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
        ("Healthcare", ["health", "healthcare", "hospital", "clinic", "medical", "medicine", "medicines", "medication", "pharmacy", "pharmaceutical", "patient", "doctor", "nurse", "disease", "diagnosis", "treatment", "therapy", "wellness", "public health"]),
        ("Energy & Utilities", ["energy", "solar", "power", "electricity", "renewable", "utility"]),
        ("Transport & Logistics", ["transport", "traffic", "logistics", "vehicle", "mobility", "road"]),
        ("Manufacturing", ["manufacturing", "factory", "industrial", "production", "assembly"]),
        ("Information Technology", ["software", "technology", "iot", "sensor", "data", "app", "platform"]),
        ("Education", ["education", "school", "student", "university", "learning", "classroom"]),
    ]
    lowered = text.lower()
    ranked = sorted(((sum(lowered.count(keyword) for keyword in keywords), sector) for sector, keywords in sector_keywords), reverse=True)
    return ranked[0][1] if ranked and ranked[0][0] else "General"


def screen_solution(payload: dict) -> dict:
    challenge_text = f"{payload['challenge_title']}. {payload['challenge_description']}"
    solution_text = f"{payload['solution_title']}. {payload['solution_proposal']}"
    required_industry_sector = infer_industry_sector(f"{challenge_text}. {solution_text}")
    challenge_embedding = get_model().encode([challenge_text])
    solution_embedding = get_model().encode([solution_text])
    relevance = float(cosine_similarity(challenge_embedding, solution_embedding)[0][0])
    del challenge_embedding, solution_embedding
    technical_keywords = ["algorithm", "system", "prototype", "model", "design", "sensor", "app", "platform", "iot", "ai", "data", "analysis", "test", "implementation", "pilot", "budget", "timeline", "team"]
    lowered = solution_text.lower()
    keyword_hits = sum(1 for keyword in technical_keywords if keyword in lowered)
    length_score = min(len(payload["solution_proposal"]) / 500, 1.0)
    score = round(min(relevance * 50 + min(keyword_hits * 3, 30) + length_score * 20, 100), 2)
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


def model_status() -> dict:
    return {"loaded": model is not None, "name": MODEL_NAME, "embedding_dimension": model.get_embedding_dimension()if model is not None else 384,}
