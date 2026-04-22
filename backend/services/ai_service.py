"""
AI service — Gemini-powered content generation.
"""
import os
import json
import base64
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def _get_client():
    from google import genai
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY not set in environment")
    return genai.Client(api_key=api_key)


def generate_slide_script(document_text: str) -> dict:
    """
    Use Gemini Flash to produce a structured lesson plan JSON from document text.
    Returns a dict with keys: title, topic, slides (list of slide dicts).
    Each slide has: heading, bullets (list[str]), narration (str), emoji (str).
    """
    client = _get_client()

    truncated = document_text[:12000]  # Stay within token budget

    prompt = f"""You are an expert instructional designer. Analyze the following document and create an engaging training lesson plan.

Return ONLY a valid JSON object (no markdown fences, no extra text) with this exact structure:
{{
  "title": "Lesson title (max 60 chars)",
  "topic": "Brief topic category (e.g. Technology, Science, Business)",
  "color_theme": "one of: purple, blue, teal, orange, pink",
  "slides": [
    {{
      "slide_number": 1,
      "heading": "Slide heading (max 50 chars)",
      "bullets": ["bullet 1", "bullet 2", "bullet 3"],
      "narration": "A 2-3 sentence narration script for this slide that a teacher would say aloud.",
      "emoji": "A single relevant emoji for this slide topic"
    }}
  ]
}}

Rules:
- Create exactly 5 slides
- Slide 1 should be an introduction/overview
- Slides 2-4 should cover key concepts from the document
- Slide 5 should be a summary/key takeaways
- Each slide should have 3-5 bullet points
- Narration should be natural, engaging, and educational
- Make it genuinely educational and accurate to the document content

Document content:
---
{truncated}
---"""

    response = client.models.generate_content(
        model="gemini-flash-latest",
        contents=prompt,
    )

    raw = response.text.strip()
    # Strip markdown code fences if present
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()
    if raw.endswith("```"):
        raw = raw[:-3].strip()

    return json.loads(raw)


def generate_infographic_description(document_text: str, lesson_plan: dict) -> str:
    """
    Use Gemini to craft a detailed infographic visual description.
    """
    client = _get_client()
    truncated = document_text[:6000]

    prompt = f"""You are a professional graphic designer and educator.
    
Based on this document and lesson plan titled "{lesson_plan.get('title', 'Training Material')}", 
write a detailed image generation prompt for a beautiful, professional educational infographic.

The infographic should:
- Have a clean, modern design with a dark or vibrant background
- Visually summarize the TOP 5 key concepts from the document
- Include icons, charts, or visual metaphors relevant to the topic
- Use a color palette that feels premium and educational
- Have clear section labels and hierarchy
- Look like something from a top consulting firm or educational platform

Write the prompt in 3-4 sentences, describing the layout, visual elements, colors, and content.
Be very specific about what visual elements should appear.

Document excerpt:
{truncated[:3000]}

Lesson title: {lesson_plan.get('title')}
Topic: {lesson_plan.get('topic')}
Key slide headings: {[s['heading'] for s in lesson_plan.get('slides', [])]}"""

    response = client.models.generate_content(
        model="gemini-flash-latest",
        contents=prompt,
    )
    return response.text.strip()


def generate_infographic_image(description: str, lesson_plan: dict) -> Optional[bytes]:
    """
    Generate an infographic PNG using Gemini image generation.
    Returns raw PNG bytes or None if generation fails.
    """
    client = _get_client()

    full_prompt = (
        f"Create a professional educational infographic poster about '{lesson_plan.get('title', 'Training')}'. "
        f"{description} "
        f"Style: modern, clean, high-contrast, suitable for corporate training. "
        f"Include the title '{lesson_plan.get('title')}' prominently at the top. "
        f"Make it visually stunning with icons and data visualization elements."
    )

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash-image",
            contents=full_prompt,
        )

        for part in response.candidates[0].content.parts:
            if part.inline_data and part.inline_data.mime_type.startswith("image/"):
                return part.inline_data.data  # raw bytes

        logger.warning("No image data returned from Gemini image generation")
        return None

    except Exception as e:
        logger.warning(f"Gemini image generation failed: {e}. Will use fallback.")
        return None
