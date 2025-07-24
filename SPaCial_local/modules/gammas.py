# =============================================================================
# modules/gammas.py
import streamlit as st
import pandas as pd
from utils.database import get_db_connection
from datetime import datetime


def app(lang, user_session=None):

    st.title(f"🎯 {lang('gammas')}")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Add new gamma
    st.subheader(f"➕ {lang('add')} Control Gamma")
    
    # Get products for dropdown
    products_df = pd.read_sql("SELECT id, code, name FROM products", conn)
    
    if not products_df.empty:
        with st.form("add_gamma"):
            product_options = dict(zip([f"{row['code']} - {row['name']}" for _, row in products_df.iterrows()], 
                                     products_df['id']))
            selected_product = st.selectbox("Product", options=list(product_options.keys()))
            
            col1, col2 = st.columns(2)
            with col1:
                name = st.text_input(lang("name"))
            with col2:
                description = st.text_input(lang("description"))
            
            if st.form_submit_button(lang("add")):
                if name and selected_product:
                    try:
                        product_id = product_options[selected_product]
                        cursor.execute("""INSERT INTO gammas (product_id, name, description, created_date) 
                                        VALUES (?, ?, ?, ?)""", 
                                     (product_id, name, description, datetime.now().isoformat()))
                        conn.commit()
                        st.success(f"Gamma '{name}' created!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")
    
    # List and configure gammas
    st.subheader("📋 Control Gammas")
    gammas_df = pd.read_sql("""
        SELECT g.id, g.name, g.description, g.active, p.code as product_code, p.name as product_name,
               COUNT(gf.id) as feature_count
        FROM gammas g
        JOIN products p ON g.product_id = p.id
        LEFT JOIN gamma_features gf ON g.id = gf.gamma_id
        GROUP BY g.id, g.name, g.description, g.active, p.code, p.name
    """, conn)
    
    if not gammas_df.empty:
        for idx, gamma in gammas_df.iterrows():
            with st.expander(f"{gamma['name']} - {gamma['product_code']} ({gamma['feature_count']} features configured)"):
                col1, col2 = st.columns([3, 1])
                
                with col1:
                    st.write(f"**Product:** {gamma['product_code']} - {gamma['product_name']}")
                    st.write(f"**Description:** {gamma['description']}")
                    st.write(f"**Status:** {'Active' if gamma['active'] else 'Inactive'}")
                    
                    # Configure features for this gamma
                    st.subheader("Configure Features")
                    
                    # Get available features for this product
                    available_features = pd.read_sql("""
                        SELECT f.id, f.name, f.nominal, f.unit
                        FROM features f
                        JOIN products p ON f.product_id = p.id
                        JOIN gammas g ON p.id = g.product_id
                        WHERE g.id = ?
                    """, conn, params=(gamma['id'],))
                    
                    # Get already configured features
                    configured_features = pd.read_sql("""
                        SELECT gf.feature_id, f.name, gf.target, gf.usl, gf.lsl
                        FROM gamma_features gf
                        JOIN features f ON gf.feature_id = f.id
                        WHERE gf.gamma_id = ?
                    """, conn, params=(gamma['id'],))
                    
                    if not available_features.empty:
                        # Show configured features
                        if not configured_features.empty:
                            st.write("**Configured Features:**")
                            for _, cf in configured_features.iterrows():
                                subcol1, subcol2 = st.columns([3, 1])
                                with subcol1:
                                    st.write(f"• {cf['name']} - Target: {cf['target']}, USL: {cf['usl']}, LSL: {cf['lsl']}")
                                with subcol2:
                                    if st.button("Remove", key=f"remove_feat_{gamma['id']}_{cf['feature_id']}"):
                                        cursor.execute("DELETE FROM gamma_features WHERE gamma_id = ? AND feature_id = ?", 
                                                     (gamma['id'], cf['feature_id']))
                                        conn.commit()
                                        st.rerun()
                        
                        # Add new feature to gamma
                        st.write("**Add Feature to Gamma:**")
                        
                        # Get features not yet configured
                        configured_ids = configured_features['feature_id'].tolist() if not configured_features.empty else []
                        unconfigured = available_features[~available_features['id'].isin(configured_ids)]
                        
                        if not unconfigured.empty:
                            with st.form(f"add_feature_gamma_{gamma['id']}"):
                                feature_options = dict(zip(unconfigured['name'], unconfigured['id']))
                                selected_feature = st.selectbox("Feature", options=list(feature_options.keys()))
                                
                                subcol1, subcol2, subcol3 = st.columns(3)
                                with subcol1:
                                    target = st.number_input("Target", format="%.3f")
                                with subcol2:
                                    usl = st.number_input("USL", format="%.3f")
                                with subcol3:
                                    lsl = st.number_input("LSL", format="%.3f")
                                
                                if st.form_submit_button("Add Feature"):
                                    feature_id = feature_options[selected_feature]
                                    cursor.execute("""INSERT INTO gamma_features (gamma_id, feature_id, target, usl, lsl) 
                                                    VALUES (?, ?, ?, ?, ?)""", 
                                                 (gamma['id'], feature_id, target, usl, lsl))
                                    conn.commit()
                                    st.success("Feature added to gamma!")
                                    st.rerun()
                        else:
                            st.info("All available features are already configured for this gamma")
                    else:
                        st.warning("No features available for this product")
                
                with col2:
                    # Toggle active status
                    if st.button("Toggle Active", key=f"toggle_gamma_{gamma['id']}"):
                        new_status = 0 if gamma['active'] else 1
                        cursor.execute("UPDATE gammas SET active = ? WHERE id = ?", (new_status, gamma['id']))
                        conn.commit()
                        st.rerun()
                    
                    # Delete gamma
                    if st.button("Delete", key=f"del_gamma_{gamma['id']}"):
                        cursor.execute("DELETE FROM gammas WHERE id = ?", (gamma['id'],))
                        conn.commit()
                        st.rerun()
    
    conn.close()
