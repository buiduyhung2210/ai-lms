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
    generate_slide_script,
    generate_infographic_description,
    generate_infographic_image,
)
from backend.services.video_builder import build_training_video, build_fallback_infographic

# --- Constants & Config ---
OUTPUTS_DIR = Path("backend/outputs")
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

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
    st.write("### Features")
    st.markdown("""
    - 📄 PDF/DOCX Support
    - 🎬 Narrated Videos
    - 🖼️ Visual Infographics
    - 🧠 AI powered by Gemini
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
    
    if st.button("✨ Generate Training Content", use_container_width=True):
        if not api_key:
            st.error("Please provide a Gemini API Key in the sidebar.")
        else:
            try:
                # 1. Parse document
                with st.status("🚀 Processing...", expanded=True) as status:
                    status.update(label="📄 Parsing document...", state="running")
                    file_bytes = uploaded_file.read()
                    document_text = extract_text(uploaded_file.name, file_bytes)
                    
                    # 2. Analyze with Gemini
                    status.update(label="🧠 Analyzing content with AI...", state="running")
                    lesson_plan = generate_slide_script(document_text)
                    
                    # 3. Generate Infographic
                    status.update(label="🎨 Designing and generating infographic...", state="running")
                    infographic_desc = generate_infographic_description(document_text, lesson_plan)
                    image_bytes = generate_infographic_image(infographic_desc, lesson_plan)
                    
                    if not image_bytes:
                        status.update(label="🖼️ Image generation failed, building fallback...", state="running")
                        image_bytes = build_fallback_infographic(lesson_plan)
                    
                    # Store infographic
                    infographic_path = OUTPUTS_DIR / f"infographic_{uploaded_file.name}.png"
                    infographic_path.write_bytes(image_bytes)
                    
                    # 4. Build Training Video
                    status.update(label="🎬 Rendering video slides and narration...", state="running")
                    
                    # Callback for video progress
                    def progress_callback(phase, current, total):
                        status.update(label=f"🎬 {phase.replace('_', ' ').capitalize()}: {current}/{total}...", state="running")
                    
                    video_path = build_training_video(lesson_plan, progress_callback=progress_callback)
                    
                    status.update(label="✅ All materials generated successfully!", state="complete")
                
                # --- Results Display ---
                st.balloons()
                st.success("Your training package is ready!")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.subheader("🎬 Training Video")
                    st.video(str(video_path))
                    with open(video_path, "rb") as f:
                        st.download_button(
                            label="⬇️ Download MP4",
                            data=f,
                            file_name=video_path.name,
                            mime="video/mp4",
                            use_container_width=True
                        )
                
                with col2:
                    st.subheader("🖼️ Infographic")
                    st.image(image_bytes, use_column_width=True)
                    st.download_button(
                        label="⬇️ Download PNG",
                        data=image_bytes,
                        file_name=f"infographic_{uploaded_file.name}.png",
                        mime="image/png",
                        use_container_width=True
                    )
                
                # --- Lesson Outline ---
                st.markdown("---")
                st.subheader("📋 Lesson Outline")
                for slide in lesson_plan.get("slides", []):
                    with st.expander(f"Slide {slide['slide_number']}: {slide['emoji']} {slide['heading']}"):
                        st.write(f"**Narration:** {slide['narration']}")
                        st.write("**Key Points:**")
                        for bullet in slide['bullets']:
                            st.write(f"- {bullet}")
                
            except Exception as e:
                st.error(f"❌ An error occurred: {str(e)}")
                st.exception(e)

# Footer
st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: #475569;'>AI LMS • Powered by Google Gemini • Built with Streamlit</div>", 
    unsafe_allow_html=True
)
