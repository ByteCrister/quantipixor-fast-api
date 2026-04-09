# api/index.py
from main import app  # import existing FastAPI app

# Vercel expects a callable named 'app'
handler = app