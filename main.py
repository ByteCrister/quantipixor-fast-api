# main.py (modified for Vercel)

import os
import io
import base64
from typing import List
from fastapi import FastAPI, UploadFile, File, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from rembg import remove, new_session
from PIL import Image, ImageEnhance, ImageFilter
import dotenv
import asyncio
import shutil

dotenv.load_dotenv()

# =========================
# CONFIG
# =========================
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")
API_KEY = os.getenv("API_KEY", None)

MAX_FILE_SIZE = 5 * 1024 * 1024
MAX_IMAGE_SIZE = 800

app = FastAPI(title="BG Remover API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["POST"],
    allow_headers=["*"],
)

# =========================
# LAZY MODEL LOADER (Vercel-friendly)
# =========================
_session = None

def get_session():
    global _session
    if _session is None:
        cache_dir = "/tmp/.u2net"
        os.makedirs(cache_dir, exist_ok=True)
        
        # Path to model that was downloaded during build
        bundled_model_dir = os.path.join(os.path.dirname(__file__), ".u2net")
        bundled_model_path = os.path.join(bundled_model_dir, "u2netp.onnx")
        target_path = os.path.join(cache_dir, "u2netp.onnx")
        
        if os.path.exists(bundled_model_path) and not os.path.exists(target_path):
            print("📦 Copying model from build output to /tmp")
            shutil.copy2(bundled_model_path, target_path)
        
        os.environ["U2NET_HOME"] = cache_dir
        _session = new_session(model_name="u2netp")
        print("✅ Model loaded")
    return _session

# =========================
# HEALTH CHECK
# =========================
@app.get("/health")
def health():
    return {"status": "ok", "model_loaded": _session is not None}

# =========================
# SECURITY CHECK
# =========================
def verify_request(request: Request):
    origin = request.headers.get("origin")
    if origin not in ALLOWED_ORIGINS:
        raise HTTPException(status_code=403, detail="Origin not allowed")
    if API_KEY:
        auth = request.headers.get("Authorization")
        if not auth or auth != f"Bearer {API_KEY}":
            raise HTTPException(status_code=401, detail="Invalid API key")

# =========================
# IMAGE PROCESSING
# =========================
def process_image(contents: bytes):
    try:
        input_image = Image.open(io.BytesIO(contents)).convert("RGB")
    except Exception:
        return None, "Unsupported image format"
    
    input_image.thumbnail((MAX_IMAGE_SIZE, MAX_IMAGE_SIZE))

    enhancer = ImageEnhance.Contrast(input_image)
    input_image = enhancer.enhance(1.2)

    # Use lazy-loaded session
    output_image = remove(
        input_image,
        session=get_session(),
        alpha_matting=False,
        alpha_matting_foreground_threshold=240,
        alpha_matting_background_threshold=10,
        alpha_matting_erode_size=10,
    )

    output_image = output_image.convert("RGBA").filter(ImageFilter.SHARPEN)

    buffered = io.BytesIO()
    output_image.save(buffered, format="PNG")
    img_base64 = base64.b64encode(buffered.getvalue()).decode("utf-8")

    return f"data:image/png;base64,{img_base64}", None

async def process_file(file: UploadFile):
    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        return {"filename": file.filename, "base64": None, "error": "File too large"}
    result, error = process_image(contents)
    return {"filename": file.filename, "base64": result, "error": error}

@app.get("/")
def root():
    return {"message": "API is running on Vercel!"}

@app.post("/remove-bg")
async def remove_bg(
    request: Request,
    files: List[UploadFile] = File(...),
):
    verify_request(request)
    if not files:
        raise HTTPException(status_code=400, detail="No files provided")
    results = await asyncio.gather(*[process_file(f) for f in files])
    return {"results": results}