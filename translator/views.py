from django.shortcuts import render


def index(request):
    """Translator main page."""
    ctx = {
        "active_page": "translator",
        "source_text": request.POST.get("source_text", ""),
        "translated_text": "",
        "translate_error": "",
    }
    if request.method == "POST":
        source_text = request.POST.get("source_text", "")
        target_language = request.POST.get("target_language", "vi")
        source_language = request.POST.get("source_language", None)
        ctx["source_text"] = source_text
        if source_text.strip():
            from translator.services import translate_text
            result = translate_text(
                source_text,
                target_language=target_language,
                source_language=source_language,
            )
            if result.startswith("[Translation error]"):
                ctx["translate_error"] = result
                ctx["translated_text"] = ""
            else:
                ctx["translated_text"] = result
    return render(request, "translator/index.html", ctx)

