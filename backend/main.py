"""
AI LMS — FastAPI application entry point.
"""
import os
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from dotenv import load_dotenv

load_dotenv()

# Ensure outputs directory exists
OUTPUTS_DIR = Path(__file__).parent / "outputs"
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

FRONTEND_DIR = Path(__file__).parent.parent / "frontend"


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 AI LMS Server started")
    print(f"   Gemini key: {'✅ set' if os.getenv('GEMINI_API_KEY') else '❌ MISSING — set GEMINI_API_KEY in .env'}")
    yield
    print("👋 AI LMS Server shutting down")


app = FastAPI(
    title="AI LMS — Document to Training Content",
    description="Upload a document. Get a training video + infographic.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routes
from backend.routers.generate import router as generate_router
app.include_router(generate_router, prefix="/api")

# Frontend static files
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

    @app.get("/")
    async def serve_frontend():
        return FileResponse(str(FRONTEND_DIR / "index.html"))

    @app.get("/{path:path}")
    async def serve_frontend_catch_all(path: str):
        """Serve frontend for any non-API path."""
        file_path = FRONTEND_DIR / path
        if file_path.exists() and file_path.is_file():
            return FileResponse(str(file_path))
        return FileResponse(str(FRONTEND_DIR / "index.html"))
