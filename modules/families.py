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