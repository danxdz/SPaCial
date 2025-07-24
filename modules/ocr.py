import streamlit as st
from PIL import Image
from streamlit_cropper import st_cropper
from . import ocr_engine

def app(lang, filters=None):
    st.subheader(lang("ocr_module_title", "OCR Text Extraction"))

    # Upload ou colar imagem
    uploaded_file = st.file_uploader(lang("upload_image", "Upload an image"), type=["png", "jpg", "jpeg"])
    img = None

    if uploaded_file:
        img = Image.open(uploaded_file)
    elif "image" in st.session_state:
        img = st.session_state["image"]

    if not img:
        st.info(lang("waiting_image", "Please upload or paste an image to begin."))
        return

    st.markdown("### 1. Select Region of Interest (ROI)")
    cropped_img = st_cropper(img, realtime_update=True, box_color='#0000FF', aspect_ratio=None)

    st.markdown("### 2. Choose OCR Engines")
    engines = st.multiselect(
        lang("select_engines", "Select OCR Engines"),
        options=["tesseract", "easyocr", "trocr", "donut"],
        default=["tesseract", "easyocr"]
    )

    if st.button(lang("run_ocr", "Run OCR")):
        with st.spinner(lang("running_ocr", "Running OCR…")):
            results = ocr_engine.run_all(cropped_img)

        st.markdown("### 🔎 OCR Results")
        for engine in engines:
            if engine in results:
                st.markdown(f"**{engine.upper()}**")
                st.code("\n".join(results[engine]), language="text")
