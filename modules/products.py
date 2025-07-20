# modules/products.py

import streamlit as st
import pandas as pd
from bson import ObjectId
from pathlib import Path
from utils.mongo import get_db

# Initialize database and static folder
db = get_db()
IMG_DIR = Path(__file__).resolve().parent.parent / "static" / "images"
IMG_DIR.mkdir(parents=True, exist_ok=True)

def app(lang, filters):
    """
    Products management page, using global filters:
      filters["atelier_id"], filters["family_id"], filters["product_id"]
    """
    st.title(lang("products", "Products"))
    st.header(lang("products_management", "Manage Products"))

    # --- 1) Build the Mongo query from filters ---
    prod_id   = filters.get("product_id")
    family_id = filters.get("family_id")

    if prod_id:
        query = {"_id": ObjectId(prod_id)}
    elif family_id:
        query = {"family_id": family_id}
    else:
        query = {}

    # --- 2) Fetch products ---
    prods = list(db.products.find(query))

    # --- 3) Prepare family lookup for display & forms ---
    all_fams = list(db.families.find({}))
    fam_map  = {f["name"]: f["_id"] for f in all_fams}
    fam_names = [lang("all_families", "All Families")] + list(fam_map.keys())

    # --- 4) Editable products table ---
    if not prods:
        st.info(lang("no_products", "No products found."))
    else:
        records = []
        for p in prods:
            fam_id   = p.get("family_id")
            fam_name = next((n for n,i in fam_map.items() if i == fam_id), "")
            records.append({
                "_id": str(p["_id"]),
                lang("product_code","Code"):        p.get("code",""),
                lang("product_name","Name"):       p.get("name",""),
                lang("product_desc","Description"):p.get("description",""),
                lang("family","Family"):           fam_name,
                lang("product_image","Image"):     p.get("image_path","")
            })
        df = pd.DataFrame(records)

        edited = st.data_editor(
            df,
            column_order=[
                lang("product_code","Code"),
                lang("product_name","Name"),
                lang("product_desc","Description"),
                lang("family","Family"),
                lang("product_image","Image")
            ],
            hide_index=True,
            use_container_width=True,
            key="prod_editor"
        )

        if st.button(lang("save_changes", "💾 Save Changes")):
            origs = df.to_dict("records")
            edits = edited.to_dict("records")
            updates = 0
            field_map = {
                lang("product_code","Code"):        "code",
                lang("product_name","Name"):        "name",
                lang("product_desc","Description"): "description",
                lang("family","Family"):            "family_id",
                lang("product_image","Image"):      "image_path"
            }
            for orig, new in zip(origs, edits):
                delta = {}
                for col_label, field in field_map.items():
                    if orig[col_label] != new[col_label]:
                        if field == "family_id":
                            delta[field] = fam_map.get(new[col_label])
                        else:
                            delta[field] = new[col_label]
                if delta:
                    db.products.update_one(
                        {"_id": ObjectId(orig["_id"])},
                        {"$set": delta}
                    )
                    updates += 1
            if updates:
                st.success(lang("products_updated", f"{updates} products updated!"))
                st.experimental_rerun()
            else:
                st.info(lang("no_changes", "No changes to save."))

    # --- 5) Change Product Image (collapsed by default) ---
    with st.expander(lang("change_image","🔄 Change Product Image"), expanded=False):
        with st.form("change_image_form", clear_on_submit=True):
            if prods:
                prod_map = {
                    p["code"]: (str(p["_id"]), p.get("image_path",""))
                    for p in prods
                }
                chosen_code = st.selectbox(
                    lang("select_product","Select Product"),
                    list(prod_map.keys()),
                    key="change_prod_select"
                )
                doc_id, curr_image = prod_map[chosen_code]

                if curr_image:
                    img_path = IMG_DIR / curr_image
                    if img_path.exists():
                        from PIL import Image
                        img = Image.open(img_path)
                        st.image(img, caption=lang("current_image","Current Image"))
                    else:
                        st.warning(lang("image_not_found","Image file not found."))

                new_file = st.file_uploader(
                    lang("upload_new_image","Upload New Image"),
                    type=["png","jpg","jpeg"],
                    key="change_image_uploader"
                )
                submitted_img = st.form_submit_button(lang("update_image","Update Image"))
                if submitted_img:
                    if new_file:
                        ext = Path(new_file.name).suffix
                        new_name = f"{chosen_code}_{ObjectId()}{ext}"
                        (IMG_DIR / new_name).write_bytes(new_file.getbuffer())
                        db.products.update_one(
                            {"_id": ObjectId(doc_id)},
                            {"$set": {"image_path": new_name}}
                        )
                        st.success(lang("image_updated","Image updated successfully!"))
                        st.experimental_rerun()
                    else:
                        st.error(lang("select_image","Please choose a new image file."))

    # --- 6) Add New Product (collapsed by default) ---
    with st.expander(lang("add_product","➕ Add New Product"), expanded=False):
        with st.form("add_prod_form", clear_on_submit=True):
            code = st.text_input(
                lang("product_code","Product Code"),
                label_visibility="visible"
            )
            name = st.text_input(
                lang("product_name","Product Name"),
                label_visibility="visible"
            )
            desc = st.text_area(
                lang("product_desc","Description"),
                label_visibility="visible"
            )

            # default to current family filter if any
            default_family = None
            if family_id:
                default_family = next((n for n,i in fam_map.items() if i==family_id), None)
            family = st.selectbox(
                lang("select_family","Select Family"),
                fam_names,
                index=fam_names.index(default_family) if default_family in fam_names else 0,
                label_visibility="visible"
            )

            image_file = st.file_uploader(
                lang("product_image","Upload Image"),
                type=["png","jpg","jpeg"],
                key="add_prod_image"
            )
            submitted = st.form_submit_button(lang("create_product","Create Product"))
            if submitted:
                if not code.strip() or not name.strip():
                    st.error(lang("fill_fields","Please fill in both Code and Name."))
                else:
                    img_fn = None
                    if image_file:
                        ext = Path(image_file.name).suffix
                        img_fn = f"{code.strip()}_{ObjectId()}{ext}"
                        (IMG_DIR / img_fn).write_bytes(image_file.getbuffer())

                    new_doc = {
                        "code": code.strip(),
                        "name": name.strip(),
                        "description": desc.strip(),
                        "family_id": fam_map.get(family) if family != lang("all_families","All Families") else None
                    }
                    if img_fn:
                        new_doc["image_path"] = img_fn

                    db.products.insert_one(new_doc)
                    st.success(lang("product_created","Product created successfully!"))
                    st.experimental_rerun()

    # --- 7) Admin-only: Add New Family ---
    if st.session_state.get("user", {}).get("role") == "admin":
        st.markdown("---")
        if st.button(lang("add_family","➕ Add New Family")):
            st.session_state["add_family"] = True

        if st.session_state.get("add_family"):
            st.subheader(lang("add_family","➕ Add New Family"))
            with st.form("family_form", clear_on_submit=True):
                family_name = st.text_input(lang("family_name","Family Name"))
                submitted = st.form_submit_button(lang("create_family","Create Family"))
                if submitted:
                    if family_name.strip():
                        db.families.insert_one({"name": family_name.strip()})
                        st.success(lang("family_created","Family created successfully!"))
                        st.experimental_rerun()
                    else:
                        st.error(lang("fill_family_name","Please fill in the Family Name."))
