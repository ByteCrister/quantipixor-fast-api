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

dotenv.load_dotenv()

# =========================
# CONFIG
# =========================
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")
API_KEY = os.getenv("API_KEY", None)

MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB
MAX_IMAGE_SIZE = 1500  # resize for performance
PORT = int(os.environ.get("PORT", 8000))

# =========================
# INIT APP
# =========================
app = FastAPI(title="BG Remover API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["POST"],
    allow_headers=["*"],
)

# =========================
# GLOBAL SESSION
# =========================
session = None

# =========================
# STARTUP: LOAD MODEL
# =========================
@app.on_event("startup")
async def load_model():
    global session
    # Force rembg to use /tmp for model cache (writable on Render)
    os.environ.setdefault("U2NET_HOME", os.path.join(os.path.dirname(__file__), ".u2net"))
    os.makedirs(os.path.join(os.path.dirname(__file__), ".u2net"), exist_ok=True)
    session = new_session(model_name="u2netp")
    print("✅ Background removal model loaded (u2netp)")

# =========================
# HEALTH CHECK
# =========================
@app.get("/health")
def health():
    return {"status": "ok", "model_loaded": session is not None}

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

    # Resize (performance boost)
    input_image.thumbnail((MAX_IMAGE_SIZE, MAX_IMAGE_SIZE))

    # Enhance contrast (better edge detection)
    enhancer = ImageEnhance.Contrast(input_image)
    input_image = enhancer.enhance(1.2)

    # Remove background – output is a PIL Image (RGBA)
    output_image = remove(
        input_image,
        session=session,
        alpha_matting=True,
        alpha_matting_foreground_threshold=240,
        alpha_matting_background_threshold=10,
        alpha_matting_erode_size=10,
    )

    # Post-process
    output_image = output_image.convert("RGBA").filter(ImageFilter.SHARPEN)

    # Save to bytes and encode as base64 data URL
    buffered = io.BytesIO()
    output_image.save(buffered, format="PNG")
    img_base64 = base64.b64encode(buffered.getvalue()).decode("utf-8")

    return f"data:image/png;base64,{img_base64}", None

# =========================
# ASYNC WRAPPER (for batch)
# =========================
async def process_file(file: UploadFile):
    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        return {"filename": file.filename, "base64": None, "error": "File too large"}
    result, error = process_image(contents)
    return {"filename": file.filename, "base64": result, "error": error}

# =========================
# ROOT ENDPOINT
# =========================
@app.get("/")
def root():
    return {"message": "API is running!"}

# =========================
# MAIN ENDPOINT
# =========================
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

# =========================
# RUN SERVER (for local testing only)
# =========================
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=PORT)
    # start -> uvicorn main:app --reload --port 8000