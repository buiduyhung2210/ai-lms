"""
Video builder service — renders slide images and assembles MP4 with gTTS narration.
"""
import os
import uuid
import textwrap
import logging
from pathlib import Path
from typing import Callable, Optional

from PIL import Image, ImageDraw, ImageFont
from gtts import gTTS
from moviepy import ImageClip, AudioFileClip, concatenate_videoclips

logger = logging.getLogger(__name__)

# Output directory (created by main.py)
OUTPUTS_DIR = Path(__file__).parent.parent / "outputs"

# Color themes for slides
THEMES = {
    "purple": {
        "bg_top": (30, 15, 60),
        "bg_bottom": (70, 20, 120),
        "accent": (180, 100, 255),
        "accent2": (120, 60, 200),
        "heading": (230, 200, 255),
        "text": (210, 190, 240),
        "bullet_dot": (180, 100, 255),
    },
    "blue": {
        "bg_top": (10, 20, 50),
        "bg_bottom": (20, 60, 120),
        "accent": (80, 160, 255),
        "accent2": (40, 100, 200),
        "heading": (200, 225, 255),
        "text": (180, 210, 245),
        "bullet_dot": (80, 160, 255),
    },
    "teal": {
        "bg_top": (5, 40, 45),
        "bg_bottom": (10, 90, 100),
        "accent": (50, 220, 200),
        "accent2": (20, 160, 150),
        "heading": (180, 245, 240),
        "text": (160, 230, 225),
        "bullet_dot": (50, 220, 200),
    },
    "orange": {
        "bg_top": (40, 20, 5),
        "bg_bottom": (100, 50, 10),
        "accent": (255, 160, 50),
        "accent2": (200, 110, 20),
        "heading": (255, 230, 180),
        "text": (245, 215, 170),
        "bullet_dot": (255, 160, 50),
    },
    "pink": {
        "bg_top": (45, 10, 40),
        "bg_bottom": (110, 20, 90),
        "accent": (255, 100, 200),
        "accent2": (200, 50, 160),
        "heading": (255, 210, 245),
        "text": (245, 190, 235),
        "bullet_dot": (255, 100, 200),
    },
}


def _get_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    """Try to get a nice system font, fallback to default."""
    candidates = []
    if bold:
        candidates = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
            "C:/Windows/Fonts/arialbd.ttf",
        ]
    else:
        candidates = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
            "C:/Windows/Fonts/arial.ttf",
        ]
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


def _draw_gradient_bg(draw: ImageDraw.Draw, width: int, height: int, top_color: tuple, bottom_color: tuple):
    """Draw a vertical gradient background."""
    for y in range(height):
        ratio = y / height
        r = int(top_color[0] + (bottom_color[0] - top_color[0]) * ratio)
        g = int(top_color[1] + (bottom_color[1] - top_color[1]) * ratio)
        b = int(top_color[2] + (bottom_color[2] - top_color[2]) * ratio)
        draw.line([(0, y), (width, y)], fill=(r, g, b))


def _draw_decorative_elements(draw: ImageDraw.Draw, width: int, height: int, theme: dict, slide_num: int):
    """Draw decorative geometric elements."""
    accent = theme["accent"]
    accent2 = theme["accent2"]

    # Top accent bar
    draw.rectangle([0, 0, width, 6], fill=accent)

    # Bottom accent bar
    draw.rectangle([0, height - 4, width, height], fill=accent2)

    # Decorative circles (subtle)
    alpha_accent = accent + (30,)
    draw.ellipse([width - 200, -100, width + 100, 200], fill=None, outline=accent, width=2)
    draw.ellipse([-100, height - 200, 200, height + 100], fill=None, outline=accent2, width=2)

    # Slide number badge
    badge_x, badge_y = width - 70, height - 55
    draw.ellipse([badge_x - 25, badge_y - 25, badge_x + 25, badge_y + 25], fill=accent2)
    num_font = _get_font(20, bold=True)
    draw.text((badge_x, badge_y), str(slide_num), font=num_font, fill=(255, 255, 255), anchor="mm")


def render_slide(slide: dict, theme: dict, lesson_title: str, total_slides: int, width: int = 1280, height: int = 720) -> Image.Image:
    """Render a single slide as a PIL Image."""
    img = Image.new("RGB", (width, height))
    draw = ImageDraw.Draw(img)

    # Background gradient
    _draw_gradient_bg(draw, width, height, theme["bg_top"], theme["bg_bottom"])

    # Decorative elements
    _draw_decorative_elements(draw, width, height, theme, slide["slide_number"])

    # Lesson title (top bar label)
    label_font = _get_font(18)
    draw.text((30, 20), lesson_title.upper(), font=label_font, fill=theme["accent"])

    # Slide type label (INTRO / TOC / CONTENT / SUMMARY)
    slide_type = slide.get("slide_type", "content").upper()
    type_font = _get_font(14)
    draw.text((30, 44), slide_type, font=type_font, fill=(*theme["accent"][:3],))

    # Chapter/section reference for content slides
    chapter_ref = slide.get("chapter_ref", "")
    section_ref = slide.get("section_ref", "")
    if chapter_ref and chapter_ref != "all" and section_ref and section_ref != "all":
        ref_font = _get_font(14)
        ref_text = f"Ch.{chapter_ref} / Sec.{section_ref}"
        draw.text((width - 200, 20), ref_text, font=ref_font, fill=theme["accent"])

    # Slide heading
    heading_font = _get_font(48, bold=True)
    emoji = slide.get("emoji", "")
    heading_text = f"{emoji}  {slide['heading']}" if emoji else slide["heading"]

    # Word wrap heading
    wrapped_heading = textwrap.fill(heading_text, width=38)
    draw.text((60, 70), wrapped_heading, font=heading_font, fill=theme["heading"])

    # Accent underline below heading
    heading_lines = wrapped_heading.count("\n") + 1
    underline_y = 70 + heading_lines * 56 + 10
    draw.rectangle([60, underline_y, 280, underline_y + 4], fill=theme["accent"])

    # Bullet points — adaptive sizing based on count
    bullets = slide.get("bullets", [])
    max_bullets = min(len(bullets), 7)  # Support up to 7 bullets for TOC slides

    # Calculate available space and adapt font/spacing
    available_height = height - underline_y - 80  # Leave room for progress bar
    if max_bullets > 5:
        bullet_font_size = 24
        line_height = 40
    else:
        bullet_font_size = 30
        line_height = 52

    bullet_font = _get_font(bullet_font_size)
    bullet_start_y = underline_y + 30

    for i, bullet in enumerate(bullets[:max_bullets]):
        y = bullet_start_y + i * line_height
        if y + line_height > height - 30:
            break  # Don't overflow past slide bottom

        # Bullet dot
        dot_x = 72
        dot_y = y + 14
        draw.ellipse([dot_x - 8, dot_y - 8, dot_x + 8, dot_y + 8], fill=theme["bullet_dot"])

        # Bullet text (wrap at ~70 chars)
        wrapped = textwrap.fill(bullet, width=70)
        first_line = wrapped.split("\n")[0]
        draw.text((100, y), first_line, font=bullet_font, fill=theme["text"])

        # If there's a second line and space allows
        if "\n" in wrapped and (y + line_height + 20 < height - 30):
            second_line = wrapped.split("\n")[1]
            draw.text((100, y + bullet_font_size + 4), second_line, font=_get_font(max(20, bullet_font_size - 4)), fill=theme["text"])

    # Progress bar at bottom
    progress = slide["slide_number"] / total_slides
    bar_y = height - 16
    draw.rectangle([0, bar_y, width, height], fill=theme["bg_bottom"])
    draw.rectangle([0, bar_y, int(width * progress), height], fill=theme["accent2"])

    return img


def build_fallback_infographic(lesson_plan: dict) -> bytes:
    """Build a Pillow-based infographic if AI image generation fails."""
    width, height = 1080, 1350  # Portrait for infographic
    theme_name = lesson_plan.get("color_theme", "purple")
    theme = THEMES.get(theme_name, THEMES["purple"])

    img = Image.new("RGB", (width, height))
    draw = ImageDraw.Draw(img)

    # Background
    _draw_gradient_bg(draw, width, height, theme["bg_top"], (theme["bg_bottom"][0] // 2, theme["bg_bottom"][1] // 2, theme["bg_bottom"][2] // 2))

    # Top accent
    draw.rectangle([0, 0, width, 8], fill=theme["accent"])

    # Title area
    draw.rectangle([0, 0, width, 180], fill=(*theme["accent2"], 200))
    title_font = _get_font(48, bold=True)
    label_font = _get_font(22)
    topic_font = _get_font(26)

    draw.text((width // 2, 60), "TRAINING INFOGRAPHIC", font=label_font, fill=theme["accent"], anchor="mm")
    draw.text((width // 2, 110), lesson_plan.get("title", "Key Concepts"), font=title_font, fill=(255, 255, 255), anchor="mm")
    draw.text((width // 2, 155), f"Topic: {lesson_plan.get('topic', '')}", font=topic_font, fill=theme["heading"], anchor="mm")

    # Slide concepts as cards
    slides = lesson_plan.get("slides", [])
    card_height = 190
    card_margin = 20
    card_start_y = 200

    for i, slide in enumerate(slides[:5]):
        card_y = card_start_y + i * (card_height + card_margin)
        # Card background
        draw.rounded_rectangle(
            [30, card_y, width - 30, card_y + card_height],
            radius=18,
            fill=(*theme["bg_top"], 220),
            outline=theme["accent"],
            width=2
        )

        # Number badge
        badge_cx = 80
        badge_cy = card_y + card_height // 2
        draw.ellipse([badge_cx - 30, badge_cy - 30, badge_cx + 30, badge_cy + 30], fill=theme["accent"])
        num_font = _get_font(28, bold=True)
        draw.text((badge_cx, badge_cy), str(i + 1), font=num_font, fill=(255, 255, 255), anchor="mm")

        # Emoji + Heading
        heading_font = _get_font(34, bold=True)
        emoji = slide.get("emoji", "📌")
        draw.text((125, card_y + 20), f"{emoji}  {slide['heading']}", font=heading_font, fill=theme["heading"])

        # Top bullet
        bullet_font = _get_font(24)
        bullets = slide.get("bullets", [])
        for j, bullet in enumerate(bullets[:2]):
            wrapped = textwrap.fill(bullet, width=60)
            first_line = wrapped.split("\n")[0]
            draw.text((135, card_y + 70 + j * 40), f"• {first_line}", font=bullet_font, fill=theme["text"])

    # Footer
    footer_font = _get_font(20)
    draw.text((width // 2, height - 30), "AI-Generated Training Material", font=footer_font, fill=theme["accent"], anchor="mm")

    import io
    buf = io.BytesIO()
    img.save(buf, format="PNG", quality=95)
    return buf.getvalue()


def build_training_video(lesson_plan: dict, progress_callback: Optional[Callable] = None) -> Path:
    """
    Build an MP4 training video from a lesson plan.
    Returns path to the generated MP4 file.
    """
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    video_id = uuid.uuid4().hex[:8]
    output_path = OUTPUTS_DIR / f"training_{video_id}.mp4"

    theme_name = lesson_plan.get("color_theme", "purple")
    theme = THEMES.get(theme_name, THEMES["purple"])
    slides = lesson_plan.get("slides", [])
    lesson_title = lesson_plan.get("title", "Training")
    total_slides = len(slides)

    if progress_callback:
        progress_callback("rendering_slides", 0, total_slides)

    # 1. Render slide images
    slide_img_paths = []
    for i, slide in enumerate(slides):
        img = render_slide(slide, theme, lesson_title, total_slides)
        img_path = OUTPUTS_DIR / f"slide_{video_id}_{i}.png"
        img.save(img_path)
        slide_img_paths.append(img_path)
        if progress_callback:
            progress_callback("rendering_slides", i + 1, total_slides)

    # 2. Generate narration audio for each slide
    if progress_callback:
        progress_callback("generating_audio", 0, total_slides)

    audio_paths = []
    for i, slide in enumerate(slides):
        narration = slide.get("narration", slide["heading"])
        audio_path = OUTPUTS_DIR / f"audio_{video_id}_{i}.mp3"
        try:
            tts = gTTS(text=narration, lang="en", slow=False)
            tts.save(str(audio_path))
        except Exception as e:
            logger.warning(f"gTTS failed for slide {i}: {e}. Using silent clip.")
            audio_path = None
        audio_paths.append(audio_path)
        if progress_callback:
            progress_callback("generating_audio", i + 1, total_slides)

    # 3. Assemble video using MoviePy
    if progress_callback:
        progress_callback("assembling_video", 0, 1)

    import numpy as np

    clips = []
    default_duration = 6  # seconds per slide if no audio

    for i, (img_path, audio_path) in enumerate(zip(slide_img_paths, audio_paths)):
        if audio_path and audio_path.exists():
            audio = AudioFileClip(str(audio_path))
            duration = audio.duration + 0.8  # small buffer
        else:
            audio = None
            duration = default_duration

        clip = ImageClip(str(img_path)).with_duration(duration)

        if audio:
            clip = clip.with_audio(audio)

        clips.append(clip)

    final = concatenate_videoclips(clips, method="compose")
    final.write_videofile(
        str(output_path),
        fps=24,
        codec="libx264",
        audio_codec="aac",
        logger=None,
    )

    # 4. Cleanup temp files
    for path in slide_img_paths:
        try:
            path.unlink()
        except Exception:
            pass
    for path in audio_paths:
        if path:
            try:
                path.unlink()
            except Exception:
                pass

    if progress_callback:
        progress_callback("assembling_video", 1, 1)

    return output_path
