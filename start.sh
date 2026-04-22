#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
# AI LMS — Start Script
# Usage: bash start.sh
# ─────────────────────────────────────────────────────────────
set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

echo ""
echo "  🎓  AI LMS — Document to Training Content"
echo "  ─────────────────────────────────────────"
echo ""

# Check for .env
if [ ! -f ".env" ]; then
  if [ -f ".env.example" ]; then
    cp .env.example .env
    echo "  ⚠️  Created .env from .env.example"
    echo "  👉  Please add your GEMINI_API_KEY to .env before generating content"
    echo ""
  fi
fi

# Check Python
if ! command -v python3 &>/dev/null; then
  echo "  ❌  Python 3 not found. Please install Python 3.10+"
  exit 1
fi

echo "  📦  Installing / checking Python dependencies..."
python3 -m pip install -q -r backend/requirements.txt

echo "  ✅  Dependencies ready"
echo ""
echo "  🚀  Starting Streamlit app at http://localhost:8089"
echo "  🌐  Open your browser to: http://localhost:8089"
echo ""

# Ensure port 8089 is clear (Streamlit will be told to use this port)
fuser -k 8089/tcp 2>/dev/null || true

# Run streamlit on the unusual port 8089
python3 -m streamlit run streamlit_app.py --server.port 8089 --server.address 0.0.0.0
