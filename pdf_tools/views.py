from django.shortcuts import render


def index(request):
    """PDF Tools landing page with tool grid."""
    return render(request, "pdf_tools/index.html", {"active_page": "pdf_tools"})


def merge(request):
    """Merge PDF view placeholder."""
    return render(request, "pdf_tools/index.html", {"active_page": "pdf_tools"})


def split(request):
    """Split PDF view placeholder."""
    return render(request, "pdf_tools/index.html", {"active_page": "pdf_tools"})
