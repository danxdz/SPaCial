import streamlit as st
from utils.mongo import get_db
from modules.filters import get_global_filters

def app(lang, filters):
    """Families management page with filters and family list."""
    st.title(lang("families"))
    st.header(lang("families_management"))

    # Get database
    db = get_db()

    # Get families
    families = list(db.families.find({}))
    if not families:
        st.info(lang("no_families", "No families found."))
        return
    # Display families
    for family in families:
        st.markdown(f"**{family['name']}**: {family.get('description', lang('no_description', 'No description available.'))}")

    data = len(families)
    cols = st.columns(len(families))
    for i in families:
        with cols[i]:
            st.markdown(f"""
                <div style='
                    border:1px solid #ccc;
                    border-radius:8px;
                    padding:15px;
                    text-align:center;
                    background:white;
                    height:120px;
                    box-shadow:2px 2px 6px rgba(0,0,0,0.1);
                    cursor:pointer;
                '>
                    <h3></h3>
                    <div style='font-size:24px;font-weight:bold;margin:10px;'>
                        {len(families)}
                    </div>
                </div>
            """, unsafe_allow_html=True)
            
            if st.button(lang("view_details", "View Details"), key=f"btn_{families['name']}", use_container_width=True):
                st.session_state['selected_view'] = families['name']
