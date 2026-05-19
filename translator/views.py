from django.shortcuts import render


def index(request):
    """Translator main page."""
    ctx = {
        "active_page": "translator",
        "source_text": request.POST.get("source_text", ""),
        "translated_text": "",
    }
    if request.method == "POST":
        source_text = request.POST.get("source_text", "")
        target_language = request.POST.get("target_language", "vi")
        ctx["source_text"] = source_text
        try:
            from translator.services import translate_text
            ctx["translated_text"] = translate_text(source_text, target_language)
        except Exception:
            ctx["translated_text"] = ""
    return render(request, "translator/index.html", ctx)
