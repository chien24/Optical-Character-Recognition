# OCR & PDF Processing Platform

This repository contains a Django-based platform for document OCR, PDF processing, file conversion, and translation workflows.

Key capabilities

- OCR images and PDFs using the custom PyTorch model (ResNetEncoder)
- Export OCR results to Markdown, TXT, JSON, or searchable PDF
- PDF editing: merge, split, rotate, crop, watermark, add text/image
- File conversion: DOCX/TXT/Markdown/Image → PDF
- Translation pipeline using Google Translate's free endpoint and export
- User accounts and job management

This README provides a high-level project overview and quick setup instructions. Detailed architecture and development workflows are under the `docs/` directory.

--

## Main Features

- OCR processing (images, PDFs) with export to Markdown
- PDF processing tools (merge/split/rotate/crop/watermark)
- File conversion and PDF generation
- Text translation pipeline with backend API, live frontend updates, and export
- Basic user authentication and job orchestration

## Tech Stack

- Backend: Django
- API: Django REST Framework (planned)
- OCR: Custom PyTorch model (ResNetEncoder) loaded via `ocr_engine` service
- PDF processing: PyMuPDF
- File conversion: WeasyPrint, python-docx, LibreOffice (optional)
- Frontend: Django templates with Custom Vanilla CSS (Design System)

## Project Structure (high level)

- `OCR/` — Django project configuration (settings, urls)
- `apps/` / top-level apps: `files`, `ocr_engine`, `processing`, `pdf_tools`, `converter`, `translator`, `users`, `core`, `api`
- `docs/` — architecture and workflow markdown files
- `templates/` — Django templates per app
- `static/` — CSS/JS/images
- `requirements.txt` — Python dependencies

## Installation (local development)

1. Clone the repository

```bash
git clone <repo-url>
cd OCR_APP
```

2. Create and activate a Conda environment

```bash
conda create -n ocr python=3.10
conda activate ocr
```

3. Install dependencies

```bash
pip install -r OCR/requirements.txt
```

4. Add environment variables

Create a `.env` file in the project root with at least:

```env
SECRET_KEY=your-secret-key
DEBUG=True
DATABASE_URL=sqlite:///db.sqlite3
# Optional
EMAIL_HOST=smtp.example.com
```

5. Setup OCR Model Checkpoints

Place your trained PyTorch `.pth` and `vocab.txt` files inside the configured checkpoints directory before starting the server:

```bash
mkdir -p OCR/ocr_engine/services/engines/
# Move your best_model.pth and vocab.txt into this directory
```

6. Run migrations and start the server

```bash
python OCR/manage.py makemigrations
python OCR/manage.py migrate
python OCR/manage.py createsuperuser
python OCR/manage.py runserver
```

7. Open `http://127.0.0.1:8000/`

## Environment variables

The project reads configuration from environment variables. Key variables:

- `SECRET_KEY` — Django secret key
- `DEBUG` — `True`/`False`
- `DATABASE_URL` — database connection string

- `GOOGLE_TRANSLATE_FREE_URL` - optional override for the translator endpoint
- `GOOGLE_TRANSLATE_TIMEOUT_SECONDS` - optional timeout for translation requests

Use `python-dotenv` or a process manager to load `.env` in development.

## Translation module

The translator app is available at `/translator/`.

- Backend service: `translator/services.py`
- Page view and JSON API: `translator/views.py`
- API endpoint: `POST /translator/api/translate/`
- Frontend template: `translator/templates/translator/index.html`

Translation now uses Google Translate's free public endpoint:

```text
https://translate.googleapis.com/translate_a/single
```

No Google Cloud API key or service account is required. The frontend sends text,
source language, and target language to the Django backend with `fetch`; the
backend calls Google Translate and returns JSON to update the translation panel.
The original form POST flow is still kept as a fallback.

Example JSON request:

```json
{
  "source_text": "Hello",
  "source_language": "en",
  "target_language": "vi"
}
```

Example JSON response:

```json
{
  "ok": true,
  "translated_text": "Xin chao",
  "source_language": "en",
  "target_language": "vi"
}
```

Because this is a free public Google endpoint, it may be rate-limited by Google
under heavier usage. For production-grade translation, replace the service layer
with an official paid provider.

## Development workflow

- Follow `docs/DEVELOPMENT_WORKFLOW.md` for branch, PR, and testing guidelines.
- Use `docs/SETUP_GUIDE.md` for environment setup and local services.

## Future plans

- Background task queue: Celery + Redis for async OCR and PDF operations
- Improved OCR engine integrations (PaddleOCR GPU support)
- REST API endpoints for programmatic access
- CI pipelines and automated tests

## Documentation

All architecture decisions and feature documentation live in the `docs/` folder. Read `docs/PROJECT_OVERVIEW.md` and `docs/DJANGO_ARCHITECTURE.md` first.

--

If you need a tailored setup (Docker, cloud deployment, GPU support), I can add Dockerfiles and deployment scripts.

---
