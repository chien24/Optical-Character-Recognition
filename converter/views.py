from django.shortcuts import render


def convert(request):
    """File Converter main page."""
    ctx = {"active_page": "converter"}
    if request.method == "POST":
        # Conversion logic handled by services layer
        pass
    return render(request, "converter/index.html", ctx)
