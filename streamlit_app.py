import streamlit as st
import os
import base64
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

import sys
from pathlib import Path
# Add the current directory to sys.path to ensure 'backend' is recognized
sys.path.append(str(Path(__file__).parent))

try:
    # Import backend services
    from backend.services.document_parser import extract_text
    from backend.services.ai_service import (
        classify_document,
        detect_structure,
        summarize_sections,
        generate_lesson_plan,
        generate_infographic_descriptions,
        generate_infographic_images,
    )
    from backend.services.video_builder import build_training_video, build_fallback_infographic
except Exception as e:
    import traceback
    st.error("Error importing backend services:")
    st.code(traceback.format_exc())
    st.stop()

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
                    
                    # ── Generate Infographics ──
                    status.update(label="Designing and generating infographics...", state="running")
                    infographic_descs = generate_infographic_descriptions(document_text, lesson_plan)
                    images_list = generate_infographic_images(infographic_descs, lesson_plan)
                    
                    if not images_list:
                        status.update(label="Image generation failed, building fallback...", state="running")
                        fallback = build_fallback_infographic(lesson_plan)
                        images_list = [fallback]
                    
                    # Store infographics
                    infographic_paths = []
                    for i, image_bytes in enumerate(images_list):
                        inf_path = OUTPUTS_DIR / f"infographic_{uploaded_file.name}_{i}.png"
                        inf_path.write_bytes(image_bytes)
                        infographic_paths.append(inf_path)
                    
                    # ── Build Training Video ──
                    status.update(label="Rendering video slides and narration...", state="running")
                    
                    def progress_callback(phase, current, total):
                        status.update(label=f"{phase.replace('_', ' ').capitalize()}: {current}/{total}...", state="running")
                    
                    video_path = build_training_video(lesson_plan, progress_callback=progress_callback)
                    
                    status.update(label="All materials generated successfully!", state="complete")
                
                # --- Document Analysis Display ---
                st.success("Your training package is ready!")
                
                with st.expander("🔍 Document Analysis & Structural Map", expanded=True):
                    col_a, col_b, col_c = st.columns(3)
                    
                    with col_a:
                        st.markdown(f"""
                        <div class="card">
                            <h3 style='margin:0; font-size:0.9em; color:#94a3b8;'>SUBJECT</h3>
                            <div style='font-size:1.5em; font-weight:700;'>{classification.get("subject", "—")}</div>
                            <div style='font-size:0.8em; color:#7c3aed;'>{classification.get('sub_field', '—')}</div>
                        </div>
                        """, unsafe_allow_html=True)
                    
                    with col_b:
                        st.markdown(f"""
                        <div class="card">
                            <h3 style='margin:0; font-size:0.9em; color:#94a3b8;'>DIFFICULTY</h3>
                            <div style='font-size:1.5em; font-weight:700;'>{classification.get("difficulty_level", "—").capitalize()}</div>
                            <div style='font-size:0.8em; color:#06b6d4;'>{classification.get('content_type', '—')}</div>
                        </div>
                        """, unsafe_allow_html=True)
                    
                    with col_c:
                        st.markdown(f"""
                        <div class="card">
                            <h3 style='margin:0; font-size:0.9em; color:#94a3b8;'>STRUCTURE</h3>
                            <div style='font-size:1.5em; font-weight:700;'>{structure.get('total_chapters', 0)} Ch / {structure.get('total_sections', 0)} Sec</div>
                            <div style='font-size:0.8em; color:#10b981;'>{classification.get('teaching_approach', '—')} Approach</div>
                        </div>
                        """, unsafe_allow_html=True)
                    
                    # Chapter/Section breakdown
                    st.markdown("### 🗺️ Content Roadmap")
                    for ch in structure.get("structure", []):
                        with st.container():
                            st.markdown(f"""
                            <div style='border-left: 3px solid #7c3aed; padding-left: 15px; margin: 15px 0;'>
                                <div style='font-weight:700; color:#f1f5f9;'>Chapter {ch.get('chapter', '?')}: {ch.get('chapter_title', 'Untitled')}</div>
                            </div>
                            """, unsafe_allow_html=True)
                            
                            cols = st.columns([1, 11])
                            with cols[1]:
                                for sec in ch.get("sections", []):
                                    summary_match = next(
                                        (s for s in section_summaries.get("sections", []) 
                                         if s.get("section_id") == sec.get("section_number")),
                                        None
                                    )
                                    ideas_count = len(summary_match.get("key_ideas", [])) if summary_match else 0
                                    st.markdown(f"""
                                    <div style='font-size:0.9em; padding: 5px 0; border-bottom: 1px solid rgba(255,255,255,0.05);'>
                                        <span style='color:#7c3aed; font-weight:600;'>{sec.get('section_number', '?')}</span> 
                                        {sec.get('section_title', '')} 
                                        <span style='color:#64748b; font-size:0.8em;'>({ideas_count} key ideas)</span>
                                    </div>
                                    """, unsafe_allow_html=True)
                
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
                    st.subheader("🖼️ Visual Infographics")
                    st.caption("Use the tabs below to switch between a standard preview and a high-resolution Zoom Mode.")
                    
                    # Display multiple infographics if available
                    for i, img_bytes in enumerate(images_list):
                        tab1, tab2 = st.tabs([f"Preview {i+1}", f"🔍 Zoom Mode {i+1}"])
                        
                        with tab1:
                            st.markdown(f"""
                            <div style='background: rgba(255,255,255,0.03); border-radius: 10px; padding: 10px; border: 1px solid rgba(255,255,255,0.1);'>
                                <div style='font-size:0.8em; color:#94a3b8; margin-bottom:10px;'>PART {i+1} PREVIEW</div>
                            </div>
                            """, unsafe_allow_html=True)
                            st.image(img_bytes, use_column_width=True)
                        
                        with tab2:
                            st.markdown(f"""
                            <div style='background: rgba(255,255,255,0.03); border-radius: 10px; padding: 10px; border: 1px solid rgba(255,255,255,0.1);'>
                                <div style='font-size:0.8em; color:#94a3b8; margin-bottom:10px;'>PART {i+1} HIGH-RES PAN & ZOOM</div>
                                <div style='height: 600px; overflow: scroll; border: 1px solid rgba(255,255,255,0.2); border-radius: 8px;'>
                                    <img src="data:image/png;base64,{base64.b64encode(img_bytes).decode()}" style="width: 200%; max-width: none;">
                                </div>
                                <p style='font-size: 0.8em; color: #64748b; margin-top: 10px;'>Tip: Scroll horizontally and vertically to explore details.</p>
                            </div>
                            """, unsafe_allow_html=True)
                            
                        st.download_button(
                            label=f"Download Part {i+1} (PNG)",
                            data=img_bytes,
                            file_name=f"infographic_{uploaded_file.name}_{i}.png",
                            mime="image/png",
                            key=f"dl_infographic_{i}",
                            use_container_width=True
                        )
                        st.markdown("<br>", unsafe_allow_html=True)
                
                # --- Lesson Outline ---
                st.markdown("---")
                st.markdown("---")
                st.subheader("📚 Detailed Lesson Plan")
                
                for slide in lesson_plan.get("slides", []):
                    slide_type = slide.get("slide_type", "content")
                    type_colors = {
                        "intro": "#7c3aed",
                        "toc": "#06b6d4",
                        "content": "#10b981",
                        "summary": "#f59e0b"
                    }
                    border_color = type_colors.get(slide_type, "#64748b")
                    
                    with st.container():
                        st.markdown(f"""
                        <div style='background: rgba(15, 23, 42, 0.4); border-left: 5px solid {border_color}; border-radius: 8px; padding: 20px; margin-bottom: 20px;'>
                            <div style='display:flex; justify-content:space-between; align-items:center; margin-bottom:15px;'>
                                <span style='font-weight:800; font-size:1.1em; color:{border_color};'>{slide_type.upper()}</span>
                                <span style='color:#64748b; font-size:0.9em;'>Slide {slide['slide_number']}</span>
                            </div>
                            <h2 style='margin-top:0; font-size:1.4em; color:#f1f5f9;'>{slide['heading']}</h2>
                            <div style='color:#94a3b8; font-size:0.85em; margin-bottom:15px;'>
                                Chapter: {slide.get('chapter_ref', 'all')} | Section: {slide.get('section_ref', '—')}
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        col_text, col_narr = st.columns([1, 1])
                        
                        with col_text:
                            st.markdown("#### **Key Points**")
                            for bullet in slide['bullets']:
                                if isinstance(bullet, dict):
                                    b_text = bullet.get("text", "")
                                    b_example = bullet.get("example")
                                    st.markdown(f"- {b_text}")
                                    if b_example:
                                        st.code(b_example)
                                else:
                                    st.markdown(f"- {bullet}")
                                    
                        with col_narr:
                            st.markdown("#### **Narration Script**")
                            st.info(slide['narration'])
                        
                        st.markdown("<div style='height:30px'></div>", unsafe_allow_html=True)
                
            except Exception as e:
                st.error(f"An error occurred: {str(e)}")
                st.exception(e)

# Footer
st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: #475569;'>AI LMS • Powered by Google Gemini • Built with Streamlit</div>", 
    unsafe_allow_html=True
)
