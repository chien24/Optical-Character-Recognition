from django.shortcuts import render, redirect
from django.views.decorators.http import require_http_methods
from .forms import UploadForm
from .services import FileService
from processing.services import ProcessingService


@require_http_methods(["GET", "POST"])
def upload_view(request):
	form = UploadForm(request.POST or None, request.FILES or None)
	if request.method == "POST" and form.is_valid():
		django_file = form.cleaned_data["file"]
		owner = request.user if request.user.is_authenticated else None
		uploaded = FileService.save_uploaded_file(django_file, owner=owner)
		# create an OCR job for now
		ProcessingService.create_job("ocr", input_file=uploaded, created_by=owner)
		return redirect("files:upload_success")

	return render(request, "files/upload.html", {"form": form})


def upload_success(request):
	return render(request, "files/upload_success.html")

