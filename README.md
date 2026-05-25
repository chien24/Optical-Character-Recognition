# OCR & PDF Processing Platform

Nền tảng web xây dựng bằng Django để nhận dạng văn bản từ ảnh/PDF, thao tác
tài liệu PDF, chuyển đổi định dạng và dịch văn bản trong một giao diện thống
nhất.

## Tổng Quan

Dự án tập trung vào quy trình xử lý tài liệu đầu-cuối:

- Tải lên ảnh hoặc PDF và trích xuất nội dung bằng OCR.
- Tận dụng lớp text có sẵn trong PDF; chỉ OCR các trang scan.
- Lưu lịch sử tác vụ, kết quả xử lý và tệp xuất ra.
- Cung cấp công cụ PDF, chuyển đổi tài liệu và dịch văn bản trên web.

Ứng dụng sử dụng SQLite và lưu tệp người dùng trong thư mục `media/` khi chạy
cục bộ.

## Tính Năng

| Nhóm | Khả năng hiện có |
| --- | --- |
| OCR | Nhận dạng ảnh và PDF; lựa chọn Custom PyTorch hoặc PaddleOCR/VietOCR; xuất kết quả Markdown hoặc TXT |
| PDF tools | Merge, split, extract text/image/metadata, reorder, delete pages, rotate, compress, watermark, encrypt và preview |
| Converter | Chuyển đổi giữa PDF, DOCX, TXT và Markdown theo các cặp định dạng được hỗ trợ |
| Translator | Dịch văn bản qua giao diện web hoặc JSON API, sử dụng Google Translate public endpoint |
| Tài khoản & tác vụ | Đăng ký, đăng nhập, hồ sơ, lưu file tải lên và theo dõi lịch sử OCR |

### Chuyển Đổi Định Dạng

Các cặp chuyển đổi được đăng ký trong service hiện tại:

| Đầu vào | Đầu ra hỗ trợ |
| --- | --- |
| PDF | DOCX, TXT, Markdown |
| DOCX | PDF, TXT, Markdown |
| TXT | PDF, DOCX, Markdown |
| Markdown | PDF, DOCX |

## Công Nghệ

| Thành phần | Công nghệ |
| --- | --- |
| Backend | Python, Django 5, Django REST Framework |
| Giao diện | Django Templates, CSS, JavaScript thuần |
| OCR tùy chỉnh | PyTorch, TorchVision |
| OCR tài liệu | PaddlePaddle, PaddleOCR; VietOCR khi được cài đặt |
| Xử lý PDF | PyMuPDF (`fitz`) |
| Chuyển đổi tài liệu | `python-docx`, WeasyPrint, LibreOffice |
| Dịch văn bản | Google Translate public endpoint qua `requests` |
| Lưu trữ phát triển | SQLite, Django media storage |

## Kiến Trúc Thư Mục

```text
.
|-- OCR/                 # Cấu hình Django project, URLs, WSGI/ASGI
|-- core/                # Dashboard, history, layout và static assets
|-- files/               # Quản lý tệp tải lên
|-- processing/          # Job và trạng thái xử lý
|-- ocr_engine/          # OCR pipeline, models, engine adapters và kết quả
|-- pdf_tools/           # Công cụ PDF và service xử lý
|-- converter/           # Registry và service chuyển đổi định dạng
|-- translator/          # Dịch văn bản và API
|-- users/               # Xác thực và hồ sơ người dùng
|-- media/               # Tệp runtime, không đưa vào Git
|-- manage.py
`-- requirements.txt
```

## Yêu Cầu Hệ Thống

- Python 3.10 được khuyến nghị.
- `pip` và môi trường ảo Python.
- Kết nối internet cho chức năng dịch và lần tải model PaddleOCR đầu tiên.
- LibreOffice trên `PATH` nếu sử dụng các chuyển đổi cần LibreOffice.
- Ollama là tùy chọn, chỉ cần khi bật hậu xử lý sửa văn bản OCR.

## Cài Đặt Nhanh

### 1. Tạo môi trường ảo

```powershell
git clone <repository-url>
cd Optical-Character-Recognition
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Trên macOS/Linux, kích hoạt môi trường bằng:

```bash
source .venv/bin/activate
```

### 2. Cài dependency

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Khởi tạo cơ sở dữ liệu

```bash
python manage.py migrate
python manage.py createsuperuser
```

Lệnh tạo superuser là tùy chọn nhưng hữu ích để truy cập Django Admin.

### 4. Chạy ứng dụng

```bash
python manage.py runserver
```

Truy cập:

- Dashboard: <http://127.0.0.1:8000/>
- Django Admin: <http://127.0.0.1:8000/admin/>

## Cấu Hình OCR

### Custom PyTorch

Engine tùy chỉnh yêu cầu checkpoint và vocabulary:

```text
ocr_engine/services/engines/best_model.pth
ocr_engine/services/engines/vocab.txt
```

Đường dẫn được cấu hình trong `OCR/settings.py`:

```python
OCR_MODEL_PATH = str(OCR_CHECKPOINT_DIR / 'best_model.pth')
OCR_VOCAB_PATH = str(OCR_CHECKPOINT_DIR / 'vocab.txt')
OCR_USE_GPU = None
```

Các tệp trọng số thường có dung lượng lớn và không nên commit vào repository.

### PaddleOCR / VietOCR

PaddleOCR phù hợp cho tài liệu tiếng Việt và có thể tải model trong lần chạy
đầu. Nếu VietOCR có sẵn trong môi trường, adapter có thể dùng recognizer này
trên các vùng chữ được PaddleOCR phát hiện; nếu không, PaddleOCR vẫn thực hiện
nhận dạng tích hợp.

```bash
pip install -r requirements.txt
# Tùy chọn khi cần recognizer VietOCR:
pip install vietocr
```

Khi triển khai trên môi trường không có internet, cần chuẩn bị model cache
trước khi khởi chạy OCR.

### PDF Hybrid OCR

Đối với PDF, service xử lý từng trang:

1. Trang có lớp text đủ nội dung được trích xuất trực tiếp.
2. Trang scan hoặc thiếu text được render thành ảnh rồi đưa qua OCR engine.

Có thể cấu hình thêm trong `OCR/settings.py`:

```python
OCR_PDF_RENDER_DPI = 300
OCR_PDF_TEXT_THRESHOLD = 20
```

## Cấu Hình Ứng Dụng

Cấu hình phát triển hiện được đặt trong `OCR/settings.py`.

| Setting | Mục đích |
| --- | --- |
| `OCR_USE_GPU` | Tự động/chủ động lựa chọn GPU cho OCR |
| `OCR_ENABLE_CORRECTION` | Bật hậu xử lý văn bản OCR bằng Ollama |
| `OLLAMA_URL`, `OLLAMA_MODEL` | Endpoint và model Ollama |
| `GOOGLE_TRANSLATE_FREE_URL` | Endpoint dịch văn bản |
| `GOOGLE_TRANSLATE_TIMEOUT_SECONDS` | Timeout khi gọi dịch vụ dịch |
| `LIBREOFFICE_PATH` | Đường dẫn executable `soffice` |

Trước khi triển khai production, cần chuyển `SECRET_KEY`, `DEBUG`,
`ALLOWED_HOSTS` và các thông tin nhạy cảm sang cấu hình theo môi trường.

## Các URL Chính

| Chức năng | URL | Phương thức |
| --- | --- | --- |
| Dashboard OCR | `/` | GET |
| Chạy OCR từ giao diện | `/ocr/run/` | POST |
| Kết quả OCR | `/ocr/<id>/` | GET |
| OCR upload API | `/ocr/api/upload/` | POST |
| PDF tools | `/pdf-tools/` | GET |
| Converter | `/converter/` | GET, POST |
| Translator | `/translator/` | GET, POST |
| Translator API | `/translator/api/translate/` | POST |
| Lịch sử xử lý | `/history/` | GET |
| Tài khoản | `/users/login/`, `/users/register/`, `/users/profile/` | GET, POST |

Ví dụ gọi Translator API:

```bash
curl -X POST http://127.0.0.1:8000/translator/api/translate/ \
  -H "Content-Type: application/json" \
  -d '{"source_text":"Hello","source_language":"en","target_language":"vi"}'
```

## Kiểm Thử

Chạy kiểm tra cấu hình Django và test suite:

```bash
python manage.py check
python manage.py test
```

Test riêng cho converter có thể chạy bằng:

```bash
pytest converter/tests -q
```

## Xử Lý Sự Cố

### `PaddleOCR/VietOCR engine is not available`

1. Xác nhận đang dùng đúng virtual environment.
2. Cài dependency bằng `pip install -r requirements.txt`.
3. Kiểm tra import:

```bash
python -c "import paddle; from paddleocr import PaddleOCR; print('PaddleOCR ready')"
```

4. Bảo đảm máy có mạng trong lần chạy đầu để tải model.
5. Nếu chọn pipeline có VietOCR, cài thêm `pip install vietocr`.

### Custom PyTorch không load model

Kiểm tra `best_model.pth` và `vocab.txt` đã tồn tại đúng tại thư mục engine,
đồng thời khớp với `OCR_MODEL_PATH` và `OCR_VOCAB_PATH`.

### Chuyển đổi DOCX/PDF thất bại

Cài LibreOffice và bảo đảm lệnh `soffice` có thể chạy, hoặc đặt
`LIBREOFFICE_PATH` tới executable tương ứng trong `OCR/settings.py`.

### Translator trả lỗi kết nối

Translator gọi một public endpoint của Google và có thể bị giới hạn lưu lượng
hoặc gián đoạn. Với môi trường production, nên thay thế service bằng provider
có SLA và thông tin xác thực phù hợp.

## Ghi Chú Triển Khai

- Đây là cấu hình phát triển; SQLite và Django development server không dành
  cho production.
- Tệp tải lên, tệp kết quả và model cache cần được quản lý bằng storage phù
  hợp khi triển khai thật.
- Celery và Redis đã có trong dependency để mở rộng xử lý nền, nhưng luồng web
  chính hiện chạy đồng bộ.

## License

Repository chưa khai báo giấy phép sử dụng. Hãy bổ sung tệp `LICENSE` trước
khi phân phối hoặc sử dụng trong môi trường thương mại.
README.md
Full file content failed to load
Retry
| --- | --- |
| Backend | Python, Django 5, Django REST Framework |
| Backend | Python, Django 5 |
| Giao diện | Django Templates, CSS, JavaScript thuần |

### Chuyển đổi DOCX/PDF thất bại
### Chuyển đổi dựa trên LibreOffice thất bại

Cài LibreOffice và bảo đảm lệnh `soffice` có thể chạy, hoặc đặt
`LIBREOFFICE_PATH` tới executable tương ứng trong `OCR/settings.py`.
Với các chuyển đổi cần LibreOffice, cài ứng dụng này và bảo đảm lệnh
`soffice` có thể chạy, hoặc đặt `LIBREOFFICE_PATH` tới executable tương ứng
trong `OCR/settings.py`.


```powershell
$env:DJANGO_SETTINGS_MODULE = "OCR.settings"
python -m pytest converter/tests -q
```

Trên macOS/Linux:

```bash
pytest converter/tests -q
DJANGO_SETTINGS_MODULE=OCR.settings python -m pytest converter/tests -q
```