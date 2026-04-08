# QuantiPixor Fast API

A high-performance microservice for automated image background removal. Built with **FastAPI** and powered by the **rembg** machine learning library, it provides a robust pipeline for cleaning up product photos, portraits, and other images via a simple REST API.

---

## Table of Contents

- [Features](#features)
- [Tech Stack](#tech-stack)
- [Architecture](#architecture)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Installation](#installation)
  - [Configuration](#configuration)
- [Usage](#usage)
  - [Running the Server](#running-the-server)
  - [API Reference](#api-reference)
- [Error Handling](#error-handling)
- [Deployment](#deployment)
  - [Docker](#docker)
  - [Production Hardening](#production-hardening)
  - [Deployment Checklist](#deployment-checklist)
- [Project Structure](#project-structure)
- [License](#license)

---

## Features

- **Batch Processing** — Upload multiple images in a single request; all are processed concurrently via `asyncio.gather`.
- **Pre-loaded ML Model** — The `isnet-general-use` model is loaded once at startup, eliminating per-request overhead.
- **Image Enhancement** — Automatic contrast boosting and post-process sharpening for cleaner results.
- **Built-in Security** — CORS origin validation and optional Bearer token authentication.
- **Graceful Error Handling** — Per-file errors are returned inline; a single bad file never fails the entire batch.
- **Base64 Output** — Processed images are returned as `data:image/png;base64,...` strings, ready for direct use in frontends.

---

## Tech Stack

| Library | Role |
| :--- | :--- |
| [FastAPI](https://fastapi.tiangolo.com/) | Async web framework, routing, and request validation |
| [uvicorn](https://www.uvicorn.org/) | ASGI server |
| [rembg](https://github.com/danielgatis/rembg) | Background removal using the ISNet/U2Net ONNX models |
| [Pillow](https://python-pillow.org/) | Image resizing, enhancement, and format conversion |
| [onnxruntime](https://onnxruntime.ai/) | ML model inference backend for rembg |
| [python-dotenv](https://github.com/theskumar/python-dotenv) | Environment variable management via `.env` files |

---

## Architecture

```mermaid
graph TD
    A["Client POST /remove-bg"] --> B["CORSMiddleware"]
    B --> C["verify_request()"]
    C --> D["remove_bg() endpoint"]
    D --> E["asyncio.gather()"]
    E --> F1["process_file(file_1)"]
    E --> F2["process_file(file_2)"]
    E --> FN["process_file(file_n)"]
    F1 --> G["process_image()"]
    F2 --> G
    FN --> G
    G --> H["PIL: Open, Resize, Enhance"]
    H --> I["rembg.remove() with alpha matting"]
    I --> J["Sharpen + Base64 Encode"]
    J --> K["JSON Response"]
```

---

## Getting Started

### Prerequisites

- **Python 3.8+**
- **pip** (Python package manager)
- ~150 MB disk space for the `isnet-general-use` model (auto-downloaded on first run to `~/.u2net/`)

### Installation

```bash
# Clone the repository
git clone https://github.com/ByteCrister/quantipixor-fast-api.git
cd quantipixor-fast-api

# (Recommended) Create and activate a virtual environment
python -m venv venv
source venv/bin/activate   # Linux/macOS
venv\Scripts\activate      # Windows

# Install dependencies
pip install -r requirements.txt
```

### Configuration

Create a `.env` file in the project root (it is git-ignored by default):

```env
ALLOWED_ORIGINS=https://your-app.com,http://localhost:3000
API_KEY=your_secure_random_token_here
```

#### Environment Variables

| Variable | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `ALLOWED_ORIGINS` | Comma-separated string | `http://localhost:3000` | Origins permitted by CORS and the origin check |
| `API_KEY` | String \| _unset_ | `None` | Bearer token for `Authorization` header. If unset, API key auth is disabled |

#### Hardcoded Constants

| Constant | Value | Description |
| :--- | :--- | :--- |
| `MAX_FILE_SIZE` | 5 MB | Maximum allowed size per uploaded file |
| `MAX_IMAGE_SIZE` | 1500 px | Max dimension (width/height) — images are thumbnailed to this limit |

---

## Usage

### Running the Server

**Development (with auto-reload):**

```bash
uvicorn main:app --reload
```

**Production:**

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

The interactive API docs are available at `http://localhost:8000/docs` (Swagger UI).

### API Reference

#### `POST /remove-bg`

Remove backgrounds from one or more images.

**Headers:**

| Header | Required | Description |
| :--- | :--- | :--- |
| `Origin` | Yes | Must match an entry in `ALLOWED_ORIGINS` |
| `Authorization` | Conditional | `Bearer <API_KEY>` — required only if `API_KEY` is configured |

**Request Body:** `multipart/form-data`

| Field | Type | Description |
| :--- | :--- | :--- |
| `files` | `List[UploadFile]` | One or more image files (JPEG, PNG, WebP, etc.) |

**Example (cURL):**

```bash
curl -X POST http://localhost:8000/remove-bg \
  -H "Origin: http://localhost:3000" \
  -H "Authorization: Bearer your_secure_random_token_here" \
  -F "files=@photo1.jpg" \
  -F "files=@photo2.png"
```

**Example (Python):**

```python
import requests

url = "http://localhost:8000/remove-bg"
headers = {
    "Origin": "http://localhost:3000",
    "Authorization": "Bearer your_secure_random_token_here",
}
files = [
    ("files", ("photo1.jpg", open("photo1.jpg", "rb"), "image/jpeg")),
    ("files", ("photo2.png", open("photo2.png", "rb"), "image/png")),
]

response = requests.post(url, headers=headers, files=files)
print(response.json())
```

**Success Response (`200 OK`):**

```json
{
  "results": [
    {
      "filename": "photo1.jpg",
      "base64": "data:image/png;base64,iVBORw0KGgo...",
      "error": null
    },
    {
      "filename": "photo2.png",
      "base64": "data:image/png;base64,iVBORw0KGgo...",
      "error": null
    }
  ]
}
```

---

## Error Handling

The service uses a **two-tier** error model:

### HTTP-Level Errors (request rejected)

| Status | Detail | Cause |
| :--- | :--- | :--- |
| `400` | `"No files provided"` | Empty file list in the request body |
| `401` | `"Invalid API key"` | Missing or incorrect `Authorization` header |
| `403` | `"Origin not allowed"` | `Origin` header not in `ALLOWED_ORIGINS` |

### Per-File Inline Errors (request succeeds with `200 OK`)

A failing file does **not** fail the entire batch. Errors are returned inline:

```json
{
  "results": [
    {
      "filename": "valid.png",
      "base64": "data:image/png;base64,...",
      "error": null
    },
    {
      "filename": "huge_image.jpg",
      "base64": null,
      "error": "File too large"
    },
    {
      "filename": "document.pdf",
      "base64": null,
      "error": "Unsupported image format"
    }
  ]
}
```

---

## Deployment

### Docker

The application binds to `0.0.0.0` and is container-ready out of the box.

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .

# Pre-download the model during build
RUN python -c "from rembg import new_session; new_session(model_name='isnet-general-use')"

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

```bash
docker build -t quantipixor-api .
docker run -d -p 8000:8000 \
  -e ALLOWED_ORIGINS="https://your-app.com" \
  -e API_KEY="your_secure_random_token_here" \
  quantipixor-api
```

### Production Hardening

1. **API Key** — Use a high-entropy secret. Rotate periodically by updating the environment variable and restarting the service.
2. **Origins** — Never use `*`. Explicitly list only the domains that should access the API.
3. **Workers** — Use `--workers N` (e.g., `N = 2 * CPU_CORES + 1`) for multi-process concurrency.
4. **Reverse Proxy** — Place behind Nginx or a cloud load balancer for TLS termination and rate limiting.
5. **Secrets Injection** — In production, prefer platform-native secrets (Kubernetes Secrets, AWS Parameter Store, etc.) over `.env` files.

### Deployment Checklist

| Category | Item |
| :--- | :--- |
| **Network** | Port 8000 open in firewall / security group |
| **Storage** | ~150 MB disk for model cache (`~/.u2net/`) |
| **Security** | `API_KEY` set to a strong secret |
| **Security** | `ALLOWED_ORIGINS` set to production domain(s) only |
| **Performance** | Monitor CPU — `rembg` inference is CPU-intensive |
| **Reliability** | Health check endpoint or process supervisor configured |

---

## Project Structure

```
quantipixor-fast-api/
├── main.py             # Application entry point (FastAPI app, routes, processing logic)
├── requirements.txt    # Python dependencies
├── .env                # Environment variables (git-ignored)
└── .gitignore          # Version control exclusions
```

---

## License

This project is maintained by [ByteCrister](https://github.com/ByteCrister). See the repository for license details.