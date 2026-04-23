"""
Document parser service — supports PDF, DOCX, and TXT.
Returns structured text with page/heading markers for downstream AI analysis.
"""
import io
import re
from pathlib import Path


def extract_text(filename: str, content: bytes) -> dict:
    """
    Extract text from uploaded file bytes, preserving structural hints.

    Returns:
        dict with keys:
            - "text": full extracted text with page/section markers
            - "hints": list of detected structural elements
              Each hint: {"type": "page"|"heading", "level": int, "title": str, "position": int}
    """
    ext = Path(filename).suffix.lower()

    if ext == ".pdf":
        return _parse_pdf(content)
    elif ext in (".docx", ".doc"):
        return _parse_docx(content)
    elif ext == ".txt":
        return _parse_txt(content)
    else:
        return _parse_txt(content)


def _parse_pdf(content: bytes) -> dict:
    """Parse PDF, inserting [PAGE N] markers and detecting heading-like lines."""
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(stream=content, filetype="pdf")
        text_parts = []
        hints = []

        for page_num, page in enumerate(doc, start=1):
            marker = f"\n[PAGE {page_num}]\n"
            position = sum(len(p) for p in text_parts)
            hints.append({
                "type": "page",
                "level": 0,
                "title": f"Page {page_num}",
                "position": position,
            })
            text_parts.append(marker)

            page_text = page.get_text()

            # Try to detect headings from font size using blocks
            try:
                blocks = page.get_text("dict", flags=0)["blocks"]
                for block in blocks:
                    if "lines" not in block:
                        continue
                    for line in block["lines"]:
                        for span in line["spans"]:
                            # Heuristic: large font or bold = heading
                            font_size = span.get("size", 12)
                            flags = span.get("flags", 0)
                            is_bold = bool(flags & 2**4)  # bit 4 = bold
                            text = span.get("text", "").strip()

                            if text and len(text) > 3 and len(text) < 120:
                                if font_size >= 16 or (font_size >= 14 and is_bold):
                                    level = 1 if font_size >= 20 else 2
                                    pos = sum(len(p) for p in text_parts)
                                    hints.append({
                                        "type": "heading",
                                        "level": level,
                                        "title": text,
                                        "position": pos,
                                    })
            except Exception:
                pass  # If dict extraction fails, we still have the plain text

            text_parts.append(page_text)

        return {
            "text": "\n\n".join(text_parts),
            "hints": hints,
        }
    except Exception as e:
        raise ValueError(f"Failed to parse PDF: {e}")


def _parse_docx(content: bytes) -> dict:
    """Parse DOCX, detecting heading styles from paragraph.style.name."""
    try:
        from docx import Document
        doc = Document(io.BytesIO(content))
        text_parts = []
        hints = []

        for para in doc.paragraphs:
            if not para.text.strip():
                continue

            position = sum(len(p) for p in text_parts)
            style_name = para.style.name if para.style else ""

            # Detect heading levels from Word styles
            if style_name.startswith("Heading"):
                try:
                    level = int(style_name.replace("Heading", "").strip())
                except ValueError:
                    level = 1
                hints.append({
                    "type": "heading",
                    "level": level,
                    "title": para.text.strip(),
                    "position": position,
                })

            text_parts.append(para.text)

        return {
            "text": "\n\n".join(text_parts),
            "hints": hints,
        }
    except Exception as e:
        raise ValueError(f"Failed to parse DOCX: {e}")


def _parse_txt(content: bytes) -> dict:
    """Parse plain text, using heuristics to detect section-like patterns."""
    text = content.decode("utf-8", errors="replace")
    hints = []

    # Heuristic: detect lines that look like headings
    # e.g., "Chapter 1: ...", "1. Introduction", "SECTION 2", all-caps lines, etc.
    heading_patterns = [
        (r'^(Chapter|CHAPTER)\s+\d+', 1),
        (r'^(Section|SECTION)\s+\d+', 2),
        (r'^\d+\.\s+[A-Z]', 2),
        (r'^\d+\.\d+\s+', 3),
        (r'^[A-Z][A-Z\s]{5,}$', 1),  # ALL CAPS lines (min 6 chars)
    ]

    for i, line in enumerate(text.split('\n')):
        stripped = line.strip()
        if not stripped:
            continue
        for pattern, level in heading_patterns:
            if re.match(pattern, stripped):
                hints.append({
                    "type": "heading",
                    "level": level,
                    "title": stripped,
                    "position": text.find(line),
                })
                break

    return {
        "text": text,
        "hints": hints,
    }
