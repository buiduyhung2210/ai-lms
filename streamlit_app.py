import streamlit as st
import os
import base64
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import backend services
from backend.services.document_parser import extract_text
from backend.services.ai_service import (
    classify_document,
    detect_structure,
    summarize_sections,
    generate_lesson_plan,
    generate_infographic_description,
    generate_infographic_image,
)
from backend.services.video_builder import build_training_video, build_fallback_infographic

# --- Constants & Config ---
OUTPUTS_DIR = Path("backend/outputs")
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

# Subject options for the dropdown
SUBJECT_OPTIONS = [
    "Auto-detect",
    "Mathematics",
    "Computer Science / IT",
    "Physics",
    "Chemistry",
    "Biology / Life Sciences",
    "Engineering",
    "Business / Management",
    "Economics / Finance",
    "Law",
    "Medicine / Healthcare",
    "History",
    "Literature / Language",
    "Psychology",
    "Other",
]

# --- Page Config & Styling ---
st.set_page_config(
    page_title="AI LMS — Document to Training Content",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS for glassmorphism-like feel in Streamlit
st.markdown("""
<style>
    .stApp {
        background-color: #080b14;
        color: #f1f5f9;
    }
    .main .block-container {
        padding-top: 2rem;
    }
    [data-testid="stSidebar"] {
        background-color: rgba(15, 20, 40, 0.7);
        backdrop-filter: blur(10px);
        border-right: 1px solid rgba(255,255,255,0.1);
    }
    .stButton>button {
        background: linear-gradient(135deg, #7c3aed 0%, #06b6d4 100%);
        border: none;
        color: white;
        font-weight: 600;
        transition: all 0.2s;
    }
    .stButton>button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 15px rgba(124,58,237,0.4);
    }
    .stHeader {
        font-family: 'Space Grotesk', sans-serif;
    }
    .card {
        background: rgba(255,255,255,0.05);
        border-radius: 12px;
        padding: 20px;
        border: 1px solid rgba(255,255,255,0.1);
        margin-bottom: 20px;
    }
    .analysis-badge {
        display: inline-block;
        background: rgba(124,58,237,0.2);
        border: 1px solid rgba(124,58,237,0.4);
        border-radius: 8px;
        padding: 4px 12px;
        margin: 2px 4px;
        font-size: 0.85em;
    }
</style>
""", unsafe_allow_html=True)

# --- Sidebar ---
with st.sidebar:
    st.title("AI LMS")
    st.subheader("Document → Training")
    
    st.markdown("---")
    
    # API Key Handling
    api_key = st.text_input(
        "Gemini API Key", 
        type="password", 
        value=os.getenv("GEMINI_API_KEY", ""),
        help="Get a free key at aistudio.google.com"
    )
    if api_key:
        os.environ["GEMINI_API_KEY"] = api_key
    
    st.markdown("---")
    
    # Subject type selector
    st.write("### Document Settings")
    subject_hint = st.selectbox(
        "Subject Type",
        options=SUBJECT_OPTIONS,
        index=0,
        help="Select the subject area or leave on Auto-detect for AI classification."
    )
    
    st.markdown("---")
    st.write("### Features")
    st.markdown("""
    - PDF/DOCX Support
    - Narrated Videos
    - Visual Infographics
    - AI powered by Gemini
    """)

# --- Main UI ---
st.title("AI Training Content Generator")
st.markdown("Turn any document into a narrated training video and infographic in minutes.")

# File uploader
uploaded_file = st.file_uploader(
    "Upload your document", 
    type=["pdf", "docx", "txt"],
    help="Support for PDF, Word documents, and text files up to 20MB."
)

if uploaded_file is not None:
    # File details
    file_details = {"FileName": uploaded_file.name, "FileType": uploaded_file.type, "FileSize": uploaded_file.size}
    
    if st.button("Generate Training Content", use_container_width=True):
        if not api_key:
            st.error("Please provide a Gemini API Key in the sidebar.")
        else:
            try:
                with st.status("Processing...", expanded=True) as status:
                    
                    # ── Stage 0: Parse Document ──
                    status.update(label="Stage 0/4 — Parsing document...", state="running")
                    file_bytes = uploaded_file.read()
                    parsed = extract_text(uploaded_file.name, file_bytes)
                    document_text = parsed["text"]
                    doc_hints = parsed["hints"]
                    
                    heading_count = len([h for h in doc_hints if h["type"] == "heading"])
                    page_count = len([h for h in doc_hints if h["type"] == "page"])
                    status.update(
                        label=f"Stage 0/4 — Parsed: {len(document_text):,} chars, {page_count} pages, {heading_count} headings detected",
                        state="running"
                    )
                    
                    # ── Stage 1: Classify Document ──
                    status.update(label="Stage 1/4 — Classifying document type...", state="running")
                    classification = classify_document(document_text, subject_hint)
                    status.update(
                        label=f"Stage 1/4 — Classified: {classification.get('subject', '?')} / {classification.get('sub_field', '?')} ({classification.get('difficulty_level', '?')})",
                        state="running"
                    )
                    
                    # ── Stage 2: Detect Structure ──
                    status.update(label="Stage 2/4 — Detecting chapters & sections...", state="running")
                    structure = detect_structure(document_text, classification, doc_hints)
                    status.update(
                        label=f"Stage 2/4 — Found {structure.get('total_chapters', 0)} chapters, {structure.get('total_sections', 0)} sections",
                        state="running"
                    )
                    
                    # ── Stage 3: Summarize Sections ──
                    status.update(label="Stage 3/4 — Summarizing key ideas per section...", state="running")
                    section_summaries = summarize_sections(document_text, structure, classification)
                    total_ideas = sum(len(s.get("key_ideas", [])) for s in section_summaries.get("sections", []))
                    status.update(
                        label=f"Stage 3/4 — Extracted {total_ideas} key ideas across {len(section_summaries.get('sections', []))} sections",
                        state="running"
                    )
                    
                    # ── Stage 4: Generate Lesson Plan ──
                    status.update(label="Stage 4/4 — Generating lesson plan...", state="running")
                    lesson_plan = generate_lesson_plan(classification, structure, section_summaries, document_text)
                    slide_count = len(lesson_plan.get("slides", []))
                    status.update(
                        label=f"Stage 4/4 — Created {slide_count}-slide lesson plan",
                        state="running"
                    )
                    
                    # ── Generate Infographic ──
                    status.update(label="Designing and generating infographic...", state="running")
                    infographic_desc = generate_infographic_description(document_text, lesson_plan)
                    image_bytes = generate_infographic_image(infographic_desc, lesson_plan)
                    
                    if not image_bytes:
                        status.update(label="Image generation failed, building fallback...", state="running")
                        image_bytes = build_fallback_infographic(lesson_plan)
                    
                    # Store infographic
                    infographic_path = OUTPUTS_DIR / f"infographic_{uploaded_file.name}.png"
                    infographic_path.write_bytes(image_bytes)
                    
                    # ── Build Training Video ──
                    status.update(label="Rendering video slides and narration...", state="running")
                    
                    def progress_callback(phase, current, total):
                        status.update(label=f"{phase.replace('_', ' ').capitalize()}: {current}/{total}...", state="running")
                    
                    video_path = build_training_video(lesson_plan, progress_callback=progress_callback)
                    
                    status.update(label="All materials generated successfully!", state="complete")
                
                # --- Document Analysis Display ---
                st.success("Your training package is ready!")
                
                with st.expander("Document Analysis", expanded=True):
                    col_a, col_b, col_c = st.columns(3)
                    
                    with col_a:
                        st.metric("Subject", classification.get("subject", "—"))
                        st.caption(f"Sub-field: {classification.get('sub_field', '—')}")
                    
                    with col_b:
                        st.metric("Difficulty", classification.get("difficulty_level", "—").capitalize())
                        st.caption(f"Content type: {classification.get('content_type', '—')}")
                    
                    with col_c:
                        st.metric("Structure", f"{structure.get('total_chapters', 0)} ch / {structure.get('total_sections', 0)} sec")
                        st.caption(f"Teaching: {classification.get('teaching_approach', '—')}")
                    
                    # Chapter/Section breakdown
                    st.markdown("---")
                    st.write("**Document Structure:**")
                    for ch in structure.get("structure", []):
                        st.write(f"**Chapter {ch.get('chapter', '?')}: {ch.get('chapter_title', 'Untitled')}**")
                        for sec in ch.get("sections", []):
                            # Find matching summary
                            summary_match = next(
                                (s for s in section_summaries.get("sections", []) 
                                 if s.get("section_id") == sec.get("section_number")),
                                None
                            )
                            ideas_count = len(summary_match.get("key_ideas", [])) if summary_match else 0
                            st.write(f"  - {sec.get('section_number', '?')}. {sec.get('section_title', '')} — {ideas_count} key ideas")
                
                # --- Results Display ---
                st.markdown("---")
                col1, col2 = st.columns(2)
                
                with col1:
                    st.subheader("Training Video")
                    st.video(str(video_path))
                    with open(video_path, "rb") as f:
                        st.download_button(
                            label="Download MP4",
                            data=f,
                            file_name=video_path.name,
                            mime="video/mp4",
                            use_container_width=True
                        )
                
                with col2:
                    st.subheader("Infographic")
                    st.image(image_bytes, use_column_width=True)
                    st.download_button(
                        label="Download PNG",
                        data=image_bytes,
                        file_name=f"infographic_{uploaded_file.name}.png",
                        mime="image/png",
                        use_container_width=True
                    )
                
                # --- Lesson Outline ---
                st.markdown("---")
                st.subheader("Lesson Outline")
                for slide in lesson_plan.get("slides", []):
                    slide_type = slide.get("slide_type", "content")
                    type_label = f"[{slide_type.upper()}]"
                    with st.expander(f"Slide {slide['slide_number']} {type_label}: {slide.get('emoji', '')} {slide['heading']}"):
                        if slide.get("chapter_ref") and slide["chapter_ref"] != "all":
                            st.caption(f"Chapter: {slide['chapter_ref']} | Section: {slide.get('section_ref', '—')}")
                        st.write(f"**Narration:** {slide['narration']}")
                        st.write("**Key Points:**")
                        for bullet in slide['bullets']:
                            st.write(f"- {bullet}")
                
            except Exception as e:
                st.error(f"An error occurred: {str(e)}")
                st.exception(e)

# Footer
st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: #475569;'>AI LMS • Powered by Google Gemini • Built with Streamlit</div>", 
    unsafe_allow_html=True
)
