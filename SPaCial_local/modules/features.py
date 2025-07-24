

# =============================================================================
# modules/features.py
import streamlit as st
import pandas as pd
from utils.database import get_db_connection


def app(lang):
    st.title(f"⚙️ {lang('features')}")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Add new feature
    with st.expander(f"➕ {lang('add')} Feature"):
            
        
        # Get products for dropdown
        products_df = pd.read_sql("SELECT id, code, name FROM products", conn)
        
        if not products_df.empty:
            with st.form("add_feature"):
                # Product selection
                product_options = dict(zip([f"{row['code']} - {row['name']}" for _, row in products_df.iterrows()], 
                                        products_df['id']))
                selected_product = st.selectbox("Product", options=list(product_options.keys()))
                
                col1, col2 = st.columns(2)
                with col1:
                    name = st.text_input(lang("name"))
                    description = st.text_input(lang("description"))
                    unit = st.text_input(lang("unit"), value="mm")
                
                with col2:
                    nominal = st.number_input(lang("nominal"), format="%.3f")
                    tolerance_plus = st.number_input("Tolerance +", format="%.3f", value=0.1)
                    tolerance_minus = st.number_input("Tolerance -", format="%.3f", value=-0.1)
                
                measurement_type = st.selectbox("Measurement Type", 
                                            ["dimension", "surface", "geometric", "optical", "temporal", "other"])
                
                if st.form_submit_button(lang("add")):
                    if name and selected_product:
                        try:
                            product_id = product_options[selected_product]
                            cursor.execute("""INSERT INTO features 
                                            (product_id, name, description, nominal, tolerance_plus, tolerance_minus, unit, measurement_type) 
                                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""", 
                                        (product_id, name, description, nominal, tolerance_plus, tolerance_minus, unit, measurement_type))
                            conn.commit()
                            st.success(f"Feature '{name}' added!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error: {e}")
        else:
            st.warning("Please create at least one product first")
    
    # List features
    st.subheader("📋 Features")
    features_df = pd.read_sql("""
        SELECT f.id, f.name, f.description, f.nominal, f.tolerance_plus, f.tolerance_minus, 
               f.unit, f.measurement_type, p.code as product_code, p.name as product_name
        FROM features f
        JOIN products p ON f.product_id = p.id
        ORDER BY p.code, f.name
    """, conn)
    
    if not features_df.empty:
        # Group by product
        for product_code in features_df['product_code'].unique():
            product_features = features_df[features_df['product_code'] == product_code]
            
            with st.expander(f"Product: {product_code} ({len(product_features)} features)"):
                for idx, feature in product_features.iterrows():
                    col1, col2 = st.columns([4, 1])
                    
                    with col1:
                        st.write(f"**{feature['name']}** - {feature['description']}")
                        st.write(f"Nominal: {feature['nominal']} {feature['unit']} "
                               f"(+{feature['tolerance_plus']}, {feature['tolerance_minus']})")
                        st.write(f"Type: {feature['measurement_type']}")
                    
                    with col2:
                        if st.button("Delete", key=f"del_feat_{feature['id']}"):
                            cursor.execute("DELETE FROM features WHERE id = ?", (feature['id'],))
                            conn.commit()
                            st.rerun()
    
    conn.close()