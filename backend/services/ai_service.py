# -*- coding: utf-8 -*-
"""
AI service -- Multi-stage Gemini-powered content generation pipeline.

Pipeline stages:
  1. classify_document()     - detect subject type, difficulty, content style
  2. detect_structure()      - find chapters & sections in the document
  3. summarize_sections()    - extract key ideas per section
  4. generate_lesson_plan()  - produce a rich, context-aware lesson plan
"""
import os
import json
import base64
import logging
from typing import Optional
import time
from google import genai
from google.genai.errors import APIError

logger = logging.getLogger(__name__)


def _get_client():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY not set in environment")
    return genai.Client(api_key=api_key)


def _call_gemini(prompt: str, max_chars: int = 0) -> str:
    """Helper to call Gemini and return raw text response."""
    client = _get_client()
    response = client.models.generate_content(
        model="gemini-flash-latest",
        contents=prompt,
    )
    return response.text.strip()


def _parse_json_response(raw: str) -> dict:
    """Strip markdown fences and parse JSON from Gemini response."""
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    if text.endswith("```"):
        text = text[:-3].strip()
    return json.loads(text)


# ---------------------------------------------------------------------------
# Stage 1: Document Classification
# ---------------------------------------------------------------------------

def classify_document(document_text: str, user_subject_hint: str = "Auto-detect") -> dict:
    """
    Classify the document's subject, difficulty, and content style.

    Args:
        document_text: Full extracted text from the document.
        user_subject_hint: Optional user-provided subject type override.

    Returns:
        dict with keys: subject, sub_field, difficulty_level, content_type, language_style
    """
    # Use first ~4000 chars for classification (enough to understand the topic)
    sample = document_text[:4000]

    hint_instruction = ""
    if user_subject_hint and user_subject_hint != "Auto-detect":
        hint_instruction = f'\nThe user has indicated this document is about "{user_subject_hint}". Use this as a strong hint but refine the sub_field based on the actual content.'

    prompt = f"""You are an expert document analyst. Analyze the following document excerpt and classify it.
{hint_instruction}

Return ONLY a valid JSON object (no markdown fences, no extra text) with this exact structure:
{{
  "subject": "Main subject area (e.g., Mathematics, Computer Science, Biology, Business, Law, Literature, Medicine, Engineering, Physics, Chemistry, History, Economics)",
  "sub_field": "Specific sub-field (e.g., Linear Algebra, Web Development, Organic Chemistry, Contract Law)",
  "difficulty_level": "One of: elementary, intermediate, undergraduate, graduate, professional",
  "content_type": "One of: textbook, tutorial, research_paper, report, manual, lecture_notes, article",
  "language_style": "One of: academic, technical, conversational, formal, simplified",
  "teaching_approach": "Recommended approach: one of: conceptual, procedural, example_driven, case_study, problem_solving"
}}

Document excerpt:
---
{sample}
---"""

    raw = _call_gemini(prompt)
    result = _parse_json_response(raw)
    logger.info(f"Document classified: {result.get('subject')} / {result.get('sub_field')}")
    return result


# ---------------------------------------------------------------------------
# Stage 2: Structure Detection
# ---------------------------------------------------------------------------

def detect_structure(document_text: str, classification: dict, hints: list = None) -> dict:
    """
    Detect the chapter/section structure of the document.

    Args:
        document_text: Full extracted text.
        classification: Output from classify_document().
        hints: Structural hints from document parser (page markers, headings).

    Returns:
        dict with keys: total_chapters, total_sections, structure (list of chapters with sections)
    """
    # Use up to ~100,000 chars to capture full document structure (Gemini can handle this easily)
    truncated = document_text[:100000]

    # Build context about detected hints
    hint_context = ""
    if hints:
        heading_hints = [h for h in hints if h["type"] == "heading"]
        if heading_hints:
            hint_list = "\n".join(
                f"  - Level {h['level']}: \"{h['title']}\"" for h in heading_hints[:50]
            )
            hint_context = f"""
The document parser detected these potential headings:
{hint_list}
Use these as strong signals for section boundaries, but also look for additional sections the parser may have missed.
"""

    subject = classification.get("subject", "General")
    content_type = classification.get("content_type", "document")

    # Subject-specific detection guidance
    subject_guidance = _get_subject_guidance(subject)

    prompt = f"""You are an expert document structure analyst specializing in {subject} {content_type}s.

Analyze the following document and identify its chapter/section structure.
{hint_context}
{subject_guidance}

Return ONLY a valid JSON object (no markdown fences, no extra text) with this structure:
{{
  "total_chapters": <number>,
  "total_sections": <number>,
  "structure": [
    {{
      "chapter": 1,
      "chapter_title": "Chapter title or main topic area",
      "sections": [
        {{
          "section_number": "1.1",
          "section_title": "Section title",
          "content_preview": "First 100-150 characters of this section's content"
        }}
      ]
    }}
  ]
}}

Rules:
- Identify ALL chapters/major divisions in the document
- Each chapter should have at least 1 section
- If no clear chapter divisions exist, treat the whole document as 1 chapter with multiple sections
- Section titles should be descriptive and meaningful
- Maximum 20 sections total (group small subsections)

Document content:
---
{truncated}
---"""

    raw = _call_gemini(prompt)
    result = _parse_json_response(raw)
    logger.info(f"Structure detected: {result.get('total_chapters')} chapters, {result.get('total_sections')} sections")
    return result


def _get_subject_guidance(subject: str) -> str:
    """Return subject-specific guidance for structure detection."""
    guidance_map = {
        "Mathematics": """For mathematics content, look for:
- Definitions, Theorems, Proofs, Lemmas, Corollaries as section markers
- Problem sets and worked examples as subsections
- Mathematical notation and formula blocks""",

        "Computer Science": """For CS/IT content, look for:
- Code blocks, algorithms, and implementation sections
- API documentation patterns (classes, methods, modules)
- Architecture descriptions, design patterns, system components""",

        "Science": """For science content, look for:
- Abstract, Introduction, Methods, Results, Discussion structure
- Experimental procedures and data sections
- Hypotheses, theories, and evidence blocks""",

        "Business": """For business content, look for:
- Executive summary, analysis sections, recommendations
- Case studies, financial data sections, strategy frameworks
- Market analysis, competitor sections, action plans""",

        "Law": """For legal content, look for:
- Articles, clauses, and statutory sections
- Case citations and legal precedent discussions
- Arguments, counter-arguments, and rulings""",

        "Medicine": """For medical content, look for:
- Clinical findings, diagnosis, treatment sections
- Patient case presentations, lab results
- Drug information, dosage, contraindications""",
    }

    for key, guidance in guidance_map.items():
        if key.lower() in subject.lower():
            return guidance

    return "Look for natural topic boundaries, numbered sections, and clear thematic shifts."


# ---------------------------------------------------------------------------
# Stage 3: Section Summarization
# ---------------------------------------------------------------------------

def summarize_sections(document_text: str, structure: dict, classification: dict) -> dict:
    """
    Summarize key ideas for each section detected in the document.
    Batches multiple sections per API call for efficiency.

    Args:
        document_text: Full extracted text.
        structure: Output from detect_structure().
        classification: Output from classify_document().

    Returns:
        dict with key "sections" containing list of section summaries.
    """
    subject = classification.get("subject", "General")
    teaching_approach = classification.get("teaching_approach", "conceptual")

    # Collect all sections
    all_sections = []
    for chapter in structure.get("structure", []):
        for section in chapter.get("sections", []):
            all_sections.append({
                "chapter_title": chapter.get("chapter_title", ""),
                "section_number": section.get("section_number", ""),
                "section_title": section.get("section_title", ""),
                "content_preview": section.get("content_preview", ""),
            })

    if not all_sections:
        return {"sections": []}

    # Build section list for the prompt
    section_list = "\n".join(
        f"  {s['section_number']}. {s['section_title']} (from chapter: {s['chapter_title']})"
        for s in all_sections
    )

    # Use up to ~100,000 chars for summarization
    truncated = document_text[:100000]

    prompt = f"""You are an expert {subject} educator using a {teaching_approach} teaching approach.

The document has the following sections:
{section_list}

For EACH section, extract the key ideas and important terms from the document content below.

Return ONLY a valid JSON object (no markdown fences, no extra text) with this structure:
{{
  "sections": [
    {{
      "section_id": "1.1",
      "title": "Section title",
      "key_ideas": [
        {{
          "idea": "First key idea — must include specific facts from the text.",
          "example": "VERBATIM code block, CLI command, or formula. Return null if no concrete example exists. DO NOT rephrase the idea as an example."
        }}
      ],
      "important_terms": ["term1", "term2", "term3"],
      "complexity": "introductory | intermediate | advanced"
    }}
  ]
}}

Rules:
- Extract 4-6 key ideas per section.
- CRITICAL: NO ABSTRACTION. If the text provides a specific code snippet (e.g. a full C function or loop), a CLI command (e.g. `chmod 755`), or a formula, you MUST INCLUDE IT VERBATIM.
- DO NOT summarize code. Capture the entire relevant block.
- Do NOT write generic summaries like "This section discusses terminal commands." Instead write: "Use `ls -la` to view all files including hidden ones."
- Key ideas should be informative enough to stand alone as a learning point.
- For {subject}: focus on {_get_focus_area(subject)}
- Important terms should be domain-specific vocabulary.
- Complexity should reflect the difficulty of THAT section.
- If a section contains exercises, include the specific questions or problems.

Document content:
---
{truncated}
---"""

    raw = _call_gemini(prompt)
    result = _parse_json_response(raw)
    logger.info(f"Summarized {len(result.get('sections', []))} sections")
    return result


def _get_focus_area(subject: str) -> str:
    """Return what to focus on per subject."""
    focus = {
        "Mathematics": "formulas, theorems, proofs, and step-by-step problem-solving methods",
        "Computer Science": "exact CLI commands, verbatim code snippets, algorithms, data structures, and syntax examples",
        "DevSecOps": "specific CLI commands, configuration snippets (e.g. YAML, JSON), pipeline stages, and security tool usage",
        "DevOps": "specific CLI commands, configuration snippets (e.g. YAML, JSON), pipeline stages, and security tool usage",
        "Science": "hypotheses, experimental evidence, causal relationships, and scientific laws",
        "Business": "strategies, frameworks, metrics, and actionable recommendations",
        "Law": "legal principles, precedents, statutory interpretations, and procedural rules",
        "Medicine": "clinical findings, treatment protocols, drug mechanisms, and diagnostic criteria",
        "Engineering": "design principles, calculations, standards compliance, and safety factors",
        "Physics": "physical laws, equations, experimental results, and real-world applications",
        "Chemistry": "reactions, molecular structures, equilibria, and synthesis pathways",
        "History": "events, causes, consequences, key figures, and primary source evidence",
        "Economics": "models, market dynamics, policy implications, and empirical data",
    }
    for key, val in focus.items():
        if key.lower() in subject.lower():
            return val
    return "core concepts, definitions, relationships, and practical applications"


# ---------------------------------------------------------------------------
# Stage 4: Lesson Plan Generation (replaces old generate_slide_script)
# ---------------------------------------------------------------------------

def generate_lesson_plan(
    classification: dict,
    structure: dict,
    section_summaries: dict,
    document_text: str,
) -> dict:
    """
    Generate a rich, context-aware lesson plan using all upstream analysis.

    Args:
        classification: Output from classify_document().
        structure: Output from detect_structure().
        section_summaries: Output from summarize_sections().
        document_text: Original text (used for additional context if needed).

    Returns:
        dict with keys: title, topic, subject, color_theme, slides
    """
    subject = classification.get("subject", "General")
    sub_field = classification.get("sub_field", "")
    difficulty = classification.get("difficulty_level", "intermediate")
    teaching_approach = classification.get("teaching_approach", "conceptual")
    content_type = classification.get("content_type", "document")

    # Calculate dynamic slide count: 1 intro + 1 per section (max 10) + 1 TOC + 1 summary
    total_sections = structure.get("total_sections", 3)
    content_slides = min(total_sections, 10)
    total_slides = 1 + 1 + content_slides + 1  # intro + TOC + content + summary
    total_slides = max(5, min(total_slides, 15))  # clamp to 5-15

    # Build section context
    sections_context = ""
    for sec in section_summaries.get("sections", []):
        ideas_list = []
        for idea_obj in sec.get("key_ideas", []):
            if isinstance(idea_obj, dict):
                idea_text = idea_obj.get("idea", "")
                example_text = idea_obj.get("example")
                if example_text:
                    ideas_list.append(f"- {idea_text} (Example: {example_text})")
                else:
                    ideas_list.append(f"- {idea_text}")
            else:
                ideas_list.append(f"- {idea_obj}")
        
        ideas = "\n    ".join(ideas_list)
        terms = ", ".join(sec.get("important_terms", []))
        sections_context += f"""
  Section {sec.get('section_id', '?')}: {sec.get('title', 'Untitled')} [{sec.get('complexity', 'intermediate')}]
    Key ideas:
    {ideas}
    Terms: {terms}
"""

    # Build chapter structure overview
    chapters_overview = ""
    for ch in structure.get("structure", []):
        sec_titles = ", ".join(s.get("section_title", "") for s in ch.get("sections", []))
        chapters_overview += f"  Chapter {ch.get('chapter', '?')}: {ch.get('chapter_title', '')} — Sections: {sec_titles}\n"

    prompt = f"""You are an expert instructional designer specializing in {subject} ({sub_field}).
You are creating training content for a {difficulty}-level audience from a {content_type}.
Use a {teaching_approach} teaching approach.

DOCUMENT ANALYSIS:
Subject: {subject} / {sub_field}
Difficulty: {difficulty}
Content type: {content_type}

CHAPTER STRUCTURE:
{chapters_overview}

SECTION SUMMARIES:
{sections_context}

Create an engaging training lesson plan with EXACTLY {total_slides} slides.

Return ONLY a valid JSON object (no markdown fences, no extra text) with this exact structure:
{{
  "title": "Lesson title (max 60 chars)",
  "topic": "{subject} — {sub_field}",
  "subject": "{subject}",
  "difficulty": "{difficulty}",
  "color_theme": "one of: purple, blue, teal, orange, pink",
  "total_chapters_covered": {structure.get('total_chapters', 1)},
  "total_sections_covered": {total_sections},
  "slides": [
    {{
      "slide_number": 1,
      "slide_type": "one of: intro, toc, content, summary",
      "chapter_ref": "Which chapter this slide covers (or 'all' for intro/toc/summary)",
      "section_ref": "Which section ID this slide covers (or 'all')",
      "heading": "Slide heading (max 50 chars)",
      "bullets": [
        {{
          "text": "The main point to display on the slide",
          "example": "Verbatim code snippet, command, or logic block. Return null if no concrete example exists. DO NOT rephrase the bullet text."
        }}
      ],
      "narration": "A 2-3 sentence narration script for this slide that a teacher would say aloud."
    }}
  ]
}}

Slide layout rules:
- Slide 1: type "intro" — A high-impact opening. Set the stage, hook the audience, and state 3 clear learning objectives.
- Slide 2: type "toc" — A clear roadmap of the journey ahead.
- Slides 3 to {total_slides - 1}: type "content" — One slide per major section.
- Slide {total_slides}: type "summary" — Synthesis of key takeaways and a "Call to Action" or "Next Steps".
- CRITICAL: NO EMPTY SLIDES. Every slide MUST have at least 3 bullet points and a full narration script.
- CRITICAL: NO VAGUE CONTENT. Each bullet point MUST contain a concrete fact, a specific step, an exact CLI command (e.g., `kubectl get pods`), or a technical detail from the section summaries.
- If the subject is technical or DevSecOps, you MUST include the exact commands, code snippets, or configuration examples in the bullets.
- DO NOT say "Learn how to manage files". DO say "Manage files using the `mv` and `cp` commands."
- Each content slide should have 3-5 bullet points.
- Narration should be authoritative yet engaging, professional, and explain the "WHY" behind the technical details.
- For {subject}: {_get_narration_style(subject)}
- Reference specific terms and ideas from the section summaries.
- If a slide is about "Exercises", include the actual questions in the bullets."""

    raw = _call_gemini(prompt)
    result = _parse_json_response(raw)

    # Inject analysis metadata into the result
    result["classification"] = classification
    result["structure_summary"] = {
        "total_chapters": structure.get("total_chapters", 0),
        "total_sections": structure.get("total_sections", 0),
    }

    logger.info(f"Lesson plan generated: {len(result.get('slides', []))} slides for {subject}")
    return result


def _get_narration_style(subject: str) -> str:
    """Return narration style guidance per subject."""
    styles = {
        "Mathematics": "walk through formulas step by step, explain WHY each step works, use analogies for abstract concepts",
        "Computer Science": "use real-world analogies for algorithms, explain code logic in plain English, mention practical use cases",
        "Science": "connect to real-world phenomena, explain cause-and-effect clearly, reference experiments",
        "Business": "use industry examples, mention real companies/cases, focus on actionable insights",
        "Law": "cite specific legal principles, use case references, explain implications clearly",
        "Medicine": "use patient-centered language, explain clinical relevance, connect symptoms to mechanisms",
    }
    for key, style in styles.items():
        if key.lower() in subject.lower():
            return style
    return "be clear and engaging, use examples, connect concepts to real-world applications"


# ---------------------------------------------------------------------------
# Legacy wrapper (for backward compatibility)
# ---------------------------------------------------------------------------

def generate_slide_script(document_text: str) -> dict:
    """
    Legacy wrapper — runs the full 4-stage pipeline.
    Kept for backward compatibility with existing code.
    """
    classification = classify_document(document_text)
    structure = detect_structure(document_text, classification)
    summaries = summarize_sections(document_text, structure, classification)
    return generate_lesson_plan(classification, structure, summaries, document_text)


# ---------------------------------------------------------------------------
# Infographic functions (unchanged)
# ---------------------------------------------------------------------------

def generate_infographic_descriptions(document_text: str, lesson_plan: dict) -> list[str]:
    """
    Use Gemini to craft multiple detailed infographic visual descriptions, 
    one for each major division in the content.
    """
    client = _get_client()
    truncated = document_text[:10000]

    subject = lesson_plan.get("subject", lesson_plan.get("topic", "Training"))
    slides = lesson_plan.get("slides", [])
    
    # Group slides by chapter for per-chapter infographics
    chapters = []
    current_chapter = None
    for slide in slides:
        c_ref = slide.get("chapter_ref")
        if c_ref and c_ref != "all" and c_ref != current_chapter:
            chapters.append(c_ref)
            current_chapter = c_ref
            
    if not chapters:
        chapters = ["Overview"]

    prompt = f"""You are a professional graphic designer and master educator specializing in {subject}.
    
Based on this document and lesson plan titled "{lesson_plan.get('title', 'Training Material')}", 
write a series of HIGH-FIDELITY image generation prompts for professional educational infographics.

We need one infographic for each of these chapters/sections: {chapters}

The infographics MUST:
- Look like a premium "Internet-Pro" asset (e.g., from a top-tier tech blog or professional textbook).
- Incorporate REALISTIC photographic elements (e.g. professional stock photos of hardware, people in a lab, or urban environments).
- Use DETAILED technical diagrams (e.g. 3D exploded views, high-fidelity flowcharts, or system architectures).
- Have a clean, modern design with a dark or vibrant background.
- Visually summarize the key concepts of THAT SPECIFIC chapter using icons and data visualization.
- Use a color palette that feels premium (e.g. deep teals, electric purples, or slate blues).

Return ONLY a valid JSON array of strings (the prompts), no markdown fences.
Example: ["A professional high-fidelity infographic showing a 3D cutaway of a server rack with realistic lighting, combined with a technical network architecture diagram, deep blue theme..."]

Document excerpt:
{truncated[:4000]}

Lesson title: {lesson_plan.get('title')}
Topic: {lesson_plan.get('topic')}
"""

    raw = _call_gemini(prompt)
    try:
        descriptions = _parse_json_response(raw)
        if isinstance(descriptions, list):
            return descriptions
        return [raw]
    except:
        return [raw]


def generate_infographic_images(descriptions: list[str], lesson_plan: dict) -> list[bytes]:
    """
    Generate infographic PNGs using Gemini image generation.
    Simplified to handle quota better.
    """
    client = _get_client()
    images = []

    # Use all descriptions (up to a reasonable limit to avoid 429s)
    if not descriptions:
        return []
        
    for desc in descriptions[:3]:  # Limit to 3 parts to be safe with quota
        full_prompt = (
            f"Create a professional high-fidelity educational infographic poster about '{lesson_plan.get('title', 'Training')}'. "
            f"{desc} "
            f"Style: clean, modern, minimalist, high-contrast. "
            f"IMPORTANT: NO GARBLED TEXT. Use simple icons and clear symbols. Avoid complex text labels inside the image. "
            f"Focus on visual metaphors and stunning technical layouts."
        )

        try:
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=full_prompt,
            )

            for part in response.candidates[0].content.parts:
                if part.inline_data and part.inline_data.mime_type.startswith("image/"):
                    images.append(part.inline_data.data)
                    break
            
            # Small delay to avoid 429
            time.sleep(1)
        except Exception as e:
            logger.warning(f"Infographic generation part failed: {e}")
                
    return images


# --- Legacy Aliases for backward compatibility ---
def generate_infographic_description(document_text: str, lesson_plan: dict) -> str:
    """Legacy singular wrapper."""
    descs = generate_infographic_descriptions(document_text, lesson_plan)
    return descs[0] if descs else ""

def generate_infographic_image(description: str, lesson_plan: dict) -> Optional[bytes]:
    """Legacy singular wrapper."""
    imgs = generate_infographic_images([description], lesson_plan)
    return imgs[0] if imgs else None

