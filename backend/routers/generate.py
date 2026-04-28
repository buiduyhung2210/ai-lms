"""
Generate router — handles document upload and content generation.
"""
import asyncio
import json
import uuid
import base64
import logging
import os
from pathlib import Path
from typing import Dict, Any, Optional

from fastapi import APIRouter, File, Form, UploadFile, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse, FileResponse

from backend.services.document_parser import extract_text
from backend.services.ai_service import (
    generate_lesson_plan,
    generate_infographic_descriptions,
    generate_infographic_images,
)
from backend.services.video_builder import build_training_video, build_fallback_infographic

logger = logging.getLogger(__name__)
router = APIRouter()

# In-memory job store {job_id: {"status": str, "progress": dict, "result": dict, "error": str}}
JOBS: Dict[str, Dict[str, Any]] = {}

OUTPUTS_DIR = Path(__file__).parent.parent / "outputs"


@router.post("/generate")
async def start_generation(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    api_key: Optional[str] = Form(None),
):
    """Accept a document upload, kick off async generation pipeline."""
    # Validate file type
    allowed_exts = {".pdf", ".docx", ".doc", ".txt"}
    filename = file.filename or "upload.txt"
    ext = Path(filename).suffix.lower()
    if ext not in allowed_exts:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Allowed: {', '.join(allowed_exts)}"
        )

    content = await file.read()
    if len(content) > 20 * 1024 * 1024:  # 20 MB limit
        raise HTTPException(status_code=400, detail="File too large. Max 20 MB.")

    job_id = uuid.uuid4().hex
    JOBS[job_id] = {
        "status": "queued",
        "step": "Queued",
        "progress": 0,
        "result": None,
        "error": None,
    }

    background_tasks.add_task(_run_pipeline, job_id, filename, content, api_key)

    return {"job_id": job_id}


@router.get("/status/{job_id}")
async def stream_status(job_id: str):
    """SSE endpoint — streams job progress updates."""
    if job_id not in JOBS:
        raise HTTPException(status_code=404, detail="Job not found")

    async def event_generator():
        while True:
            job = JOBS.get(job_id, {})
            data = json.dumps({
                "status": job.get("status"),
                "step": job.get("step"),
                "progress": job.get("progress", 0),
                "result": job.get("result"),
                "error": job.get("error"),
            })
            yield f"data: {data}\n\n"

            if job.get("status") in ("done", "error"):
                break
            await asyncio.sleep(0.8)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        }
    )


@router.get("/outputs/{filename}")
async def serve_output(filename: str):
    """Serve generated video/image files."""
    path = OUTPUTS_DIR / filename
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    # Security: only allow files within outputs dir
    if OUTPUTS_DIR not in path.parents and path.parent != OUTPUTS_DIR:
        raise HTTPException(status_code=403)
    return FileResponse(str(path))


# ─── Pipeline ───────────────────────────────────────────────────────────────

async def _run_pipeline(job_id: str, filename: str, content: bytes, api_key: Optional[str] = None):
    """Background task: full generation pipeline."""
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

    # If user provided API key via UI, use it (override env for this call)
    if api_key:
        os.environ["GEMINI_API_KEY"] = api_key

    def update(step: str, progress: int):
        JOBS[job_id]["step"] = step
        JOBS[job_id]["progress"] = progress
        JOBS[job_id]["status"] = "running"

    try:
        # Step 1: Parse document
        update("📄 Parsing document...", 5)
        loop = asyncio.get_event_loop()
        document_text = await loop.run_in_executor(None, extract_text, filename, content)

        if not document_text.strip():
            raise ValueError("Document appears to be empty or could not be parsed.")

        # Step 2: Analyze with Gemini
        update("🧠 Analyzing content with AI...", 15)
        # Using full pipeline explicitly for more control
        from backend.services.ai_service import classify_document, detect_structure, summarize_sections
        classification = await loop.run_in_executor(None, classify_document, document_text)
        structure = await loop.run_in_executor(None, detect_structure, document_text, classification)
        summaries = await loop.run_in_executor(None, summarize_sections, document_text, structure, classification)
        lesson_plan = await loop.run_in_executor(None, generate_lesson_plan, classification, structure, summaries, document_text)

        # Step 3: Generate infographic prompts
        update("🎨 Designing infographics...", 35)
        infographic_descs = await loop.run_in_executor(
            None, generate_infographic_descriptions, document_text, lesson_plan
        )

        # Step 4: Generate infographic images
        update("🖼️ Generating infographic images...", 45)
        images_list = await loop.run_in_executor(
            None, generate_infographic_images, infographic_descs, lesson_plan
        )

        if not images_list:
            update("🖼️ Building infographic (fallback renderer)...", 50)
            fallback = await loop.run_in_executor(
                None, build_fallback_infographic, lesson_plan
            )
            images_list = [fallback]

        # Save infographics
        infographic_urls = []
        infographic_b64s = []
        for i, image_bytes in enumerate(images_list):
            inf_id = uuid.uuid4().hex[:6]
            inf_filename = f"infographic_{inf_id}_{i}.png"
            inf_path = OUTPUTS_DIR / inf_filename
            inf_path.write_bytes(image_bytes)
            infographic_urls.append(f"/api/outputs/{inf_filename}")
            infographic_b64s.append(base64.b64encode(image_bytes).decode())

        # Step 5: Build training video
        update("🎬 Rendering training video slides...", 55)

        def _build_video():
            def progress_cb(phase: str, current: int, total: int):
                if phase == "rendering_slides":
                    pct = 55 + int((current / max(total, 1)) * 20)
                    update(f"🎬 Rendering slide {current}/{total}...", pct)
                elif phase == "generating_audio":
                    pct = 75 + int((current / max(total, 1)) * 15)
                    update(f"🔊 Generating narration {current}/{total}...", pct)
                elif phase == "assembling_video":
                    update("🎞️ Assembling final video...", 92)
            return build_training_video(lesson_plan, progress_callback=progress_cb)

        video_path = await loop.run_in_executor(None, _build_video)

        # Step 6: Done
        update("✅ Complete!", 100)
        JOBS[job_id]["status"] = "done"
        JOBS[job_id]["result"] = {
            "lesson_title": lesson_plan.get("title"),
            "topic": lesson_plan.get("topic"),
            "video_url": f"/api/outputs/{video_path.name}",
            "infographic_urls": infographic_urls,
            "infographic_base64s": infographic_b64s,
            "slides": lesson_plan.get("slides", []),
        }

    except Exception as e:
        logger.exception(f"Pipeline failed for job {job_id}")
        JOBS[job_id]["status"] = "error"
        JOBS[job_id]["error"] = str(e)
        JOBS[job_id]["step"] = "❌ Error"
