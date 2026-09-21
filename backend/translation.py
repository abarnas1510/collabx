from functools import lru_cache
import json
from urllib.parse import quote
from urllib.request import Request, urlopen


LANGUAGE_CODES = {
    "en": "en", "hi": "hi", "ta": "ta", "te": "te", "bn": "bn",
    "mr": "mr", "gu": "gu", "kn": "kn", "ml": "ml", "pa": "pa",
    "or": "or", "as": "as", "ur": "ur",
}


def normalize_language(language: str | None) -> str:
    value = (language or "en").lower().replace("_", "-").split("-")[0]
    if value == "auto":
        return "auto"
    return LANGUAGE_CODES.get(value, "en")


@lru_cache(maxsize=512)
def translate_text(text: str, source_language: str | None, target_language: str | None) -> str:
    if not text:
        return text

    source = normalize_language(source_language)
    target = normalize_language(target_language)
    if source == target:
        return text

    url = (
        "https://translate.googleapis.com/translate_a/single?client=gtx"
        f"&sl={source}&tl={target}&dt=t&q={quote(text)}"
    )
    try:
        request = Request(url, headers={"User-Agent": "CollabX/1.0"})
        with urlopen(request, timeout=8) as response:
            payload = json.loads(response.read().decode("utf-8"))
        translated = "".join(part[0] for part in payload[0] if part and part[0])
        return translated or text
    except Exception:
        return text


def translated_fields(title: str, description: str, source_language: str | None, target_language: str | None) -> dict:
    return {
        "title": translate_text(title, source_language, target_language),
        "description": translate_text(description, source_language, target_language),
    }
