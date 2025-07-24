

# =============================================================================
# modules/families.py
import streamlit as st
import pandas as pd
from utils.database import get_db_connection

def app(lang):
    st.title(f"🏷️ {lang('families')}")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    

    
    # Add new family
    with st.expander(f"➕ {lang('add')} {lang('family')}"):
        with st.form("add_family"):
            col1, col2 = st.columns(2)
            with col1:
                name = st.text_input(lang("name"))
            with col2:
                description = st.text_input(lang("description"))
            
            if st.form_submit_button(lang("add")):
                if name:
                    try:
                        cursor.execute("INSERT INTO families (name, description) VALUES (?, ?)", 
                                    (name, description))
                        conn.commit()
                        st.success(f"Family '{name}' added!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")
    
    # List families
    st.subheader(f"📋 {lang('families')}")
    families_df = pd.read_sql("SELECT id, name, description FROM families", conn)
    
    if not families_df.empty:
        for idx, family in families_df.iterrows():
            with st.expander(f"{family['name']} - {family['description']}"):
                col1, col2 = st.columns([3, 1])
                with col1:
                    # Show products in this family
                    products = pd.read_sql("""
                        SELECT code, name FROM products WHERE family_id = ?
                    """, conn, params=(family['id'],))
                    
                    if not products.empty:
                        st.write("**Products:**")
                        for _, prod in products.iterrows():
                            st.write(f"• {prod['code']} - {prod['name']}")
                    else:
                        st.write("No products in this family")
                
                with col2:
                    if st.button(f"{lang('delete')}", key=f"del_fam_{family['id']}"):
                        cursor.execute("DELETE FROM families WHERE id = ?", (family['id'],))
                        conn.commit()
                        st.rerun()
    
    conn.close()