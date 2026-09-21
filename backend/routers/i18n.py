from fastapi import APIRouter, Query

from translation import normalize_language, translate_text

router = APIRouter(prefix="/i18n", tags=["Internationalization"])


@router.get("/translate")
def translate_content(
    text: str = Query(..., min_length=1, max_length=5000),
    language: str = Query("en"),
):
    target = normalize_language(language)
    return {
        "translation": translate_text(text, "auto", target),
        "language": target,
    }