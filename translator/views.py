import json

from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST

from translator.services import ERROR_PREFIX, translate_text


LANGUAGES = [
    ("vi", "Vietnamese"),
    ("en", "English"),
    ("zh", "Chinese"),
    ("ja", "Japanese"),
    ("ko", "Korean"),
    ("fr", "French"),
    ("de", "German"),
    ("es", "Spanish"),
    ("th", "Thai"),
]

SOURCE_LANGUAGES = [("auto", "Auto-detect"), *LANGUAGES]


def index(request):
    """Translator main page."""
    source_language = request.POST.get("source_language", "auto")
    target_language = request.POST.get("target_language", "vi")
    ctx = {
        "active_page": "translator",
        "source_text": request.POST.get("source_text", ""),
        "translated_text": "",
        "translate_error": "",
        "source_language": source_language,
        "target_language": target_language,
        "source_languages": SOURCE_LANGUAGES,
        "target_languages": LANGUAGES,
    }
    if request.method == "POST":
        source_text = request.POST.get("source_text", "")
        ctx["source_text"] = source_text
        if source_text.strip():
            result = translate_text(
                source_text,
                target_language=target_language,
                source_language=source_language,
            )
            if result.startswith(ERROR_PREFIX):
                ctx["translate_error"] = result
                ctx["translated_text"] = ""
            else:
                ctx["translated_text"] = result
    return render(request, "translator/index.html", ctx)


@require_POST
def translate_api(request):
    """Translate text for the frontend fetch workflow."""
    payload = _parse_request_payload(request)
    source_text = (payload.get("source_text") or "").strip()
    source_language = payload.get("source_language") or "auto"
    target_language = payload.get("target_language") or "vi"

    if not source_text:
        return JsonResponse(
            {"ok": False, "error": "Please enter text to translate."},
            status=400,
        )

    result = translate_text(
        source_text,
        target_language=target_language,
        source_language=source_language,
    )
    if result.startswith(ERROR_PREFIX):
        return JsonResponse({"ok": False, "error": result}, status=502)

    return JsonResponse(
        {
            "ok": True,
            "translated_text": result,
            "source_language": source_language,
            "target_language": target_language,
        }
    )


def _parse_request_payload(request):
    if (request.content_type or "").startswith("application/json"):
        try:
            return json.loads(request.body.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            return {}
    return request.POST
