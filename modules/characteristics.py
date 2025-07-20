# modules/characteristics.py

import streamlit as st
from PIL import Image, ImageDraw
from pathlib import Path
from bson import ObjectId
import json
from streamlit_drawable_canvas import st_canvas
from utils.mongo import get_db

# Initialize MongoDB connection
db = get_db()

# Ensure static folders exist
BASE     = Path(__file__).resolve().parent.parent / "static"
IMG_DIR  = BASE / "images"
JSON_DIR = BASE / "annotations"
IMG_DIR.mkdir(parents=True, exist_ok=True)
JSON_DIR.mkdir(parents=True, exist_ok=True)

# Sizes for thumbnails and full‐size previews
THUMBNAIL_WIDTH = 64
PREVIEW_WIDTH   = 480

def draw_annotation_overlay(img_path: Path, annot_path: Path) -> Image.Image:
    """
    Load base image and overlay shapes from a Streamlit-Drawable-Canvas JSON file.
    """
    base = Image.open(img_path).convert("RGBA")
    overlay = Image.new("RGBA", base.size, (255, 255, 255, 0))
    draw = ImageDraw.Draw(overlay)

    try:
        data = json.loads(annot_path.read_text(encoding="utf-8"))
        for obj in data.get("objects", []):
            t = obj.get("type")
            if t == "rect":
                x, y = obj["left"], obj["top"]
                w, h = obj["width"], obj["height"]
                draw.rectangle([x, y, x + w, y + h], outline="green", width=3)
            elif t == "circle":
                cx, cy = obj["left"], obj["top"]
                r = obj.get("radius", 10)
                draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline="green", width=3)
            elif t == "line":
                pts = obj.get("points", [])
                if len(pts) >= 2:
                    draw.line(pts, fill="green", width=3)
    except Exception:
        # If JSON invalid or missing fields, just return base image
        pass

    return Image.alpha_composite(base, overlay)

def app(lang, filters):
    """
    Characteristics management page.
    Uses three‐level scope: product → route → operation.
    Lists existing characteristics with action buttons,
    shows full‐size annotation preview on demand,
    and provides an expander form for add/edit.
    """
    # 1) Global CSS to shrink icon buttons
    st.markdown("""
    <style>
      .stButton>button {
        padding: 2px 6px !important;
        font-size: 12px !important;
        line-height: 1 !important;
      }
    </style>
    """, unsafe_allow_html=True)

    st.header(lang("characteristics", "Characteristics"))

    # 2) Scope by product → route → operation
    product_id = filters.get("product_id")
    if not product_id:
        st.info(lang("please_select_product", "Please select a product to continue."))
        return

    routes = list(db.routes.find({"product_id": product_id}))
    if not routes:
        st.info(lang("no_routes", "No routes for this product."))
        return
    route_map = {r["name"]: r["_id"] for r in routes}
    selected_route = st.selectbox(lang("select_route", "Select Route"), list(route_map.keys()))
    route_id = route_map[selected_route]

    ops = list(db.operations.find({"route_id": route_id}))
    if not ops:
        st.info(lang("no_operations", "No operations for this route."))
        return
    op_labels = [f"{o['step_number']} - {o['name']}" for o in ops]
    selected_op = st.selectbox(lang("select_operation", "Select Operation"), op_labels)
    op_id = ops[op_labels.index(selected_op)]["_id"]

    st.markdown("---")

    # 3) List existing characteristics with action icons
    chars = list(db.characteristics.find({"operation_id": op_id}))
    st.subheader(lang("existing_characteristics", "Existing Characteristics"))

    for c in chars:
        # columns: designation, unit, nominal, tol_min, tol_max, actions
        cols = st.columns([2, 1, 1, 1, 1, 0.5])
        cols[0].write(c.get("designation", ""))
        cols[1].write(c.get("unit", ""))
        cols[2].write(f"{c.get('nominal', 0):.3f}")
        cols[3].write(f"{c.get('tol_min', 0):.3f}")
        cols[4].write(f"{c.get('tol_max', 0):.3f}")

        action_col = cols[5]
        btns = action_col.columns(5, gap="small")

        # ✏️ Edit
        if btns[0].button("✏️", key=f"edit_{c['_id']}"):
            st.session_state["edit_char"] = c
            st.experimental_rerun()

        # 🗑️ Delete
        if btns[1].button("🗑️", key=f"del_{c['_id']}"):
            db.characteristics.delete_one({"_id": c["_id"]})
            st.experimental_rerun()

        # 🚫 Disable / ✅ Enable
        if c.get("active", True):
            if btns[2].button("🚫", key=f"dis_{c['_id']}"):
                db.characteristics.update_one({"_id": c["_id"]}, {"$set": {"active": False}})
                st.experimental_rerun()
        else:
            if btns[2].button("✅", key=f"en_{c['_id']}"):
                db.characteristics.update_one({"_id": c["_id"]}, {"$set": {"active": True}})
                st.experimental_rerun()

        # 👁️ Preview annotation
        if btns[3].button("👁️", key=f"view_{c['_id']}"):
            st.session_state["view_char"] = c

    st.markdown("---")

    # 4) Full‐width preview below list (if requested)
    if "view_char" in st.session_state:
        c = st.session_state["view_char"]
        img_fn  = c.get("image_path")
        ann_fn  = c.get("annotation_path")
        img_p   = IMG_DIR / img_fn   if img_fn else None
        ann_p   = JSON_DIR / ann_fn  if ann_fn else None

        if img_p and img_p.exists() and ann_p and ann_p.exists():
            over = draw_annotation_overlay(img_p, ann_p)
            st.image(
                over,
                caption=lang("annotation_preview", "Annotation Preview"),
                width=PREVIEW_WIDTH
            )
        else:
            st.error(lang("annotation_error", "Image or annotation file not found."))

        if st.button(lang("close_preview", "Close Preview")):
            del st.session_state["view_char"]

    st.markdown("---")

    # 5) Add / Edit expander form
    edit_doc = st.session_state.get("edit_char")
    is_edit  = bool(edit_doc)
    exp_label = (
        lang("edit_characteristic", "✏️ Edit Characteristic")
        if is_edit else
        lang("add_characteristic", "➕ Add New Characteristic")
    )

    with st.expander(exp_label, expanded=is_edit):
        # A) Upload + annotate
        image_file = st.file_uploader(
            lang("char_image", "Upload Base Image"),
            type=["png", "jpg", "jpeg"],
            key="char_image_uploader"
        )
        if image_file:
            pil_img = Image.open(image_file).convert("RGBA")
            mode = st.selectbox(
                lang("drawing_mode", "Drawing Mode"),
                ["rect", "circle", "line", "freedraw"],
                key="char_draw_mode"
            )
            canvas_result = st_canvas(
                background_image=pil_img,
                update_streamlit=True,
                height=pil_img.height,
                width=pil_img.width,
                drawing_mode=mode,
                stroke_width=3,
                stroke_color="#00FF00",
                fill_color="rgba(0,255,0,0.3)",
                key="char_canvas"
            )
            if canvas_result.json_data and canvas_result.json_data.get("objects"):
                st.session_state["char_annotation"] = canvas_result.json_data
                st.session_state["char_image_bytes"] = image_file.getvalue()
                st.session_state["char_image_ext"]   = Path(image_file.name).suffix

        # B) Metadata form
        defaults = edit_doc or {}
        with st.form("char_form", clear_on_submit=True):
            desig   = st.text_input(
                lang("designation", "Designation"),
                value=defaults.get("designation", "")
            )
            unit    = st.text_input(
                lang("unit", "Unit"),
                value=defaults.get("unit", "")
            )
            nominal = st.number_input(
                lang("nominal", "Nominal"),
                value=defaults.get("nominal", 0.0),
                format="%.3f"
            )
            tol_min = st.number_input(
                lang("tol_min", "Tolerance Min"),
                value=defaults.get("tol_min", 0.0),
                format="%.3f"
            )
            tol_max = st.number_input(
                lang("tol_max", "Tolerance Max"),
                value=defaults.get("tol_max", 0.0),
                format="%.3f"
            )

            submitted = st.form_submit_button(lang("save_characteristic", "Save"))
            if submitted:
                if not desig.strip():
                    st.error(lang("fill_designation", "Please fill in the Designation."))
                else:
                    doc = {
                        "operation_id": op_id,
                        "designation":  desig.strip(),
                        "unit":         unit.strip(),
                        "nominal":      nominal,
                        "tol_min":      tol_min,
                        "tol_max":      tol_max,
                        "active":       True
                    }
                    # retrieve stashed data
                    img_b = st.session_state.pop("char_image_bytes", None)
                    img_e = st.session_state.pop("char_image_ext",   None)
                    anno  = st.session_state.pop("char_annotation",  None)

                    if img_b and img_e and anno:
                        fn_img = f"{desig.strip()}_{ObjectId()}{img_e}"
                        (IMG_DIR / fn_img).write_bytes(img_b)
                        doc["image_path"] = fn_img

                        fn_json = f"{desig.strip()}_{ObjectId()}.json"
                        (JSON_DIR / fn_json).write_text(json.dumps(anno), encoding="utf-8")
                        doc["annotation_path"] = fn_json

                    if is_edit:
                        db.characteristics.update_one(
                            {"_id": edit_doc["_id"]},
                            {"$set": doc}
                        )
                        st.success(lang("char_updated", "Characteristic updated!"))
                        del st.session_state["edit_char"]
                    else:
                        db.characteristics.insert_one(doc)
                        st.success(lang("char_created", "Characteristic created!"))
                    st.experimental_rerun()
