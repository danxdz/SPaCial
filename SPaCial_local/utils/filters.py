import streamlit as st
from utils.database import get_db_connection

def get_spc_filters(lang):
    """
    Renders filters: Family → Product
    Returns: dict with family_id, product_id
    """

    # Language labels
    ALL_FAM = lang("all_families", "All Families")
    ALL_PROD = lang("all_products", "All Products")

    conn = get_db_connection()
    cursor = conn.cursor()

    # — Get Families
    cursor.execute("SELECT id, name FROM families ORDER BY name")
    fam_rows = cursor.fetchall()
    if not fam_rows:
        st.warning(lang("no_families", "No families available."))
        return {"family_id": None, "product_id": None}
    
    family_map = {name: fid for fid, name in fam_rows}
    family_opts = [ALL_FAM] + list(family_map.keys())

    col1, col2 = st.columns([1, 1])

    with col1:
        sel_family = st.selectbox(
            lang("select_family", "Family"),
            options=family_opts,
            key="filter_family",
            label_visibility="collapsed"
        )
    family_id = None if sel_family == ALL_FAM else family_map[sel_family]

    # — Get Products
    if family_id:
        cursor.execute("SELECT id, code FROM products WHERE family_id = ? ORDER BY code", (family_id,))
    else:
        cursor.execute("SELECT id, code FROM products ORDER BY code")
    prod_rows = cursor.fetchall()

    if not prod_rows:
        st.warning(lang("no_products", "No products available."))
        return {"family_id": family_id, "product_id": None}

    product_map = {code: pid for pid, code in prod_rows}
    product_opts = [ALL_PROD] + list(product_map.keys())

    with col2:
        sel_product = st.selectbox(
            lang("select_product", "Product"),
            options=product_opts,
            key="filter_product",
            label_visibility="collapsed"
        )
    product_id = None if sel_product == ALL_PROD else product_map[sel_product]

    conn.close()

    return {
        "family_id": family_id,
        "product_id": product_id
    }
