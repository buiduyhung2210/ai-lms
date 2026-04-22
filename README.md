# AI LMS — Document to Training Content Generator

An AI-powered learning platform that converts any document into a complete training course with a narrated video and visual infographic.

## Features

- 📄 **Upload any document** — PDF, DOCX, or TXT
- 🎬 **AI Training Video** — Narrated MP4 slideshow with 5 structured lesson slides
- 🖼️ **AI Infographic** — Visual summary image of key concepts
- 🌐 **Beautiful web UI** — Dark glassmorphism design, drag-and-drop upload, live progress
- ⚡ **Any topic** — Technology, science, business, hobbies — anything!

## Quick Start

### 1. Get a Gemini API Key (free)
Go to [https://aistudio.google.com](https://aistudio.google.com) and create an API key.

### 2. Configure
```bash
cp .env.example .env
# Edit .env and set your key:
# GEMINI_API_KEY=AIza...
```

### 3. Run
```bash
bash start.sh
```

Then open **http://localhost:8000** in your browser.

## Manual Setup

```bash
cd /home/hung/ai/ai-lms

# Install dependencies
pip install -r backend/requirements.txt

# Start server
python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

## Project Structure

```
ai-lms/
├── backend/
│   ├── main.py                    # FastAPI app entry
│   ├── routers/
│   │   └── generate.py            # Upload + generation endpoints
│   ├── services/
│   │   ├── document_parser.py     # PDF/DOCX/TXT parsing
│   │   ├── ai_service.py          # Gemini API calls
│   │   └── video_builder.py       # Slide rendering + MP4 assembly
│   └── outputs/                   # Generated videos & images
├── frontend/
│   ├── index.html                 # SPA
│   ├── style.css                  # Dark glassmorphism UI
│   └── app.js                     # Upload, SSE, results rendering
├── .env.example
├── start.sh
└── README.md
```

## How It Works

1. **Document Upload** → User uploads PDF/DOCX/TXT (max 20 MB)
2. **AI Analysis** → Gemini 2.5 Flash reads the document and creates a structured lesson plan (5 slides with headings, bullets, narration scripts)
3. **Infographic Generation** → Gemini generates a visual infographic prompt, then creates a PNG image
4. **Video Assembly**:
   - Pillow renders each slide as a 1280×720 styled image
   - gTTS converts each slide's narration to MP3 audio
   - MoviePy combines images + audio into an MP4 video
5. **Results** → Browser shows the embedded video player + infographic with download buttons

## API

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/generate` | Upload document, starts generation |
| `GET` | `/api/status/{job_id}` | SSE stream for live progress |
| `GET` | `/api/outputs/{filename}` | Download generated files |
