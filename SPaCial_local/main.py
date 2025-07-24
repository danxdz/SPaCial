# main.py
import streamlit as st
from utils.auth import check_login
from utils.lang import init_language
from utils.database import initialize_db
from modules import dashboard, families, products, gammas, measurements, users, features

# Initialize database
initialize_db()

st.set_page_config(
    page_title="SPaCial - SMART production control", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize language and auth
lang = init_language()
user_session = check_login()

if user_session:
    st.sidebar.title(f"{lang('welcome')}, {user_session['username']}")
    
    menu = st.sidebar.radio(lang("navigate"), [
        lang("home"),
        lang("families"),
        lang("products"),
        lang("features"),
        lang("gammas"),
        lang("measurements"),
        lang("users") if user_session["role"] == "admin" else ""
    ])

    # Route to modules
    if menu == lang("home"):
        dashboard.app(lang)
    elif menu == lang("families"):
        families.app(lang)
    elif menu == lang("products"):
        products.app(lang)
    elif menu == lang("features"):
        features.app(lang)
    elif menu == lang("gammas"):
        gammas.app(lang)
    elif menu == lang("measurements"):
        measurements.app(lang)
    elif menu == lang("users") and user_session["role"] == "admin":
        users.app(lang)
    else:
        st.warning(lang("access_denied"))
else:
    st.stop()