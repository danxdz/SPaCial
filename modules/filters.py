# modules/filters.py

import streamlit as st
from utils.mongo import get_db

db = get_db()

def get_global_filters(lang):
    """
    Renders header filters (three side-by-side widgets):
      Atelier → Family → Product
    Each selection filters the next.
    Returns a dict with keys:
      atelier_id, family_id, product_id
    """

    # — language defaults
    ALL_AT  = lang("all_ateliers", "All Ateliers")
    ALL_FAM = lang("all_families",  "All Families")
    ALL_PR  = lang("all_products",  "All Products")

    # — 1) Atelier
    atelier_docs = list(db.ateliers.find({}))
    if not atelier_docs:
        st.warning(lang("no_ateliers", "No ateliers available."))
        return {"atelier_id": None, "family_id": None, "product_id": None}
    atelier_map = {a["name"]: a["_id"] for a in atelier_docs}
    atelier_opts = [ALL_AT] + list(atelier_map.keys())

    # — prepare the three-column layout
    col1, col2, col3 = st.columns([1, 1, 1])

    # — select atelier via multiselect (wheel-scrollable)
    with col1:
        sel_atel_list = st.multiselect(
            lang("select_atelier", "Atelier"),
            options=atelier_opts,
            default=[ALL_AT],
            max_selections=1,
            key="filter_atelier",
            label_visibility="collapsed"
        )
    sel_atelier = sel_atel_list[0] if sel_atel_list else ALL_AT
    atelier_id = None if sel_atelier == ALL_AT else atelier_map.get(sel_atelier)

    # — 2) Family, filtered by atelier_id
    if atelier_id:
        fam_cursor = db.families.find({"atelier_id": atelier_id})
    else:
        fam_cursor = db.families.find({})
    family_docs = list(fam_cursor)
    if not family_docs:
        st.warning(lang("no_families", "No families available."))
        return {"atelier_id": atelier_id, "family_id": None, "product_id": None}
    family_map = {f["name"]: f["_id"] for f in family_docs}
    family_opts = [ALL_FAM] + list(family_map.keys())

    with col2:
        sel_family = st.selectbox(
            lang("select_family", "Family"),
            options=family_opts,
            key="filter_family",
            label_visibility="collapsed"
        )
    family_id = None if sel_family == ALL_FAM else family_map.get(sel_family)

    # — 3) Product, filtered by family_id
    if family_id:
        prod_cursor = db.products.find({"family_id": family_id})
    else:
        prod_cursor = db.products.find({})
    product_docs = list(prod_cursor)
    if not product_docs:
        st.warning(lang("no_products", "No products available."))
        return {
            "atelier_id": atelier_id,
            "family_id": family_id,
            "product_id": None
        }
    product_map = {p["code"]: p["_id"] for p in product_docs}
    product_opts = [ALL_PR] + list(product_map.keys())

    with col3:
        sel_product = st.selectbox(
            lang("select_product", "Product"),
            options=product_opts,
            key="filter_product",
            label_visibility="collapsed"
        )
    product_id = None if sel_product == ALL_PR else product_map.get(sel_product)

    return {
        "atelier_id": atelier_id,
        "family_id":  family_id,
        "product_id": product_id
    }
