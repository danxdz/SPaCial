

# =============================================================================
# modules/products.py
import streamlit as st
import pandas as pd
from utils.database import get_db_connection
from utils.filters import get_spc_filters



def app(lang):
    st.title(f"📦 {lang('products')}")
    
    conn = get_db_connection()
    cursor = conn.cursor()

    filters = get_spc_filters(lang)
    filter_family_id = ""
    if filters:
        if filters["family_id"]:
            filter_family_id = "WHERE family_id = "  + str(filters["family_id"])
        elif filters["product_id"]:
            filter_family_id = "WHERE product_id = " + str(filters["product_id"])

    #st.write("Selected:", filters)
    
    # Add new product
    with  st.expander(f"➕ {lang('add')} {lang('products')}"):
        # Get families for dropdown
        families_df = pd.read_sql("SELECT id, name FROM families", conn)
        
        if not families_df.empty:
            with st.form("add_product"):
                col1, col2, col3 = st.columns(3)
                with col1:
                    code = st.text_input(lang("code"))
                with col2:
                    name = st.text_input(lang("name"))
                with col3:
                    family_options = dict(zip(families_df['name'], families_df['id']))
                    selected_family = st.selectbox(lang("family"), options=list(family_options.keys()))
                
                description = st.text_area(lang("description"))
                
                if st.form_submit_button(lang("add")):
                    if code and name:
                        try:
                            family_id = family_options[selected_family]
                            cursor.execute("""INSERT INTO products (code, name, family_id, description) 
                                            VALUES (?, ?, ?, ?)""", 
                                        (code, name, family_id, description))
                            conn.commit()
                            st.success(f"Product '{name}' added!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error: {e}")
        else:
            st.warning("Please create at least one family first")
    
    # List products
    st.subheader(f"📋 {lang('products')}")
    products_df = pd.read_sql(f"""
        SELECT p.id, p.code, p.name, f.name as family_name, p.description,
               COUNT(feat.id) as feature_count
        FROM products p
        LEFT JOIN families f ON p.family_id = f.id
        LEFT JOIN features feat ON p.id = feat.product_id
        {filter_family_id}
        GROUP BY p.id, p.code, p.name, f.name, p.description
    """, conn)
    
    if not products_df.empty:
        for idx, product in products_df.iterrows():
            with st.expander(f"{product['code']} - {product['name']} ({product['feature_count']} features)"):
                col1, col2 = st.columns([3, 1])
                
                with col1:
                    st.write(f"**Family:** {product['family_name']}")
                    st.write(f"**Description:** {product['description']}")
                    
                    # Show features for this product
                    features = pd.read_sql("""
                        SELECT name, nominal, tolerance_plus, tolerance_minus, unit, measurement_type
                        FROM features WHERE product_id = ?
                    """, conn, params=(product['id'],))
                    
                    if not features.empty:
                        st.write("**Features:**")
                        st.dataframe(features, hide_index=True)
                    else:
                        st.write("No features defined for this product")
                
                with col2:
                    if st.button(f"{lang('delete')}", key=f"del_prod_{product['id']}"):
                        cursor.execute("DELETE FROM products WHERE id = ?", (product['id'],))
                        conn.commit()
                        st.rerun()
    
    conn.close()