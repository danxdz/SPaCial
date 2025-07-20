import streamlit as st
from typing import Dict, Callable, Any
from utils.lang import init_language
from utils.auth import login_form, cookies
from utils.mongo import initialize_mongo_if_needed
from utils.password_manager import change_password_form
from modules.filters import get_global_filters
from modules import (
    dashboard, families, products,
    routes, measurements, users,
    characteristics
)

def initialize_app() -> tuple:
    """Initialize core app components and return (lang, user)"""
    try:
        # 0) Initialize MongoDB
        initialize_mongo_if_needed()

        # 1) Restore user from URL params
        params = st.experimental_get_query_params()
        if "user" in params and "role" in params and "user" not in st.session_state:
            st.session_state["user"] = {
                "username": params["user"][0],
                "role": params["role"][0]
            }

        # 2) Configure page
        st.set_page_config(
            page_title="SPaCial",
            layout="wide",
            initial_sidebar_state="expanded"
        )

        # 3) Initialize language
        lang = init_language()
        st.session_state["translator"] = lang

        return lang, st.session_state.get("user")

    except Exception as e:
        st.error(f"Critical initialization error: {str(e)}")
        st.stop()

def render_header(lang, user):
    """Render app header with login"""
    col_title, col_login = st.columns([7, 3], gap="small")
    with col_title:
        st.title("SPaCial – Smart Production Control")
    with col_login:
        if user:
            # Add user menu with password change
            with st.expander(f"👤 {user['username']}", expanded=False):
                if change_password_form(lang, user):
                    st.experimental_rerun()
                st.markdown("---")
                if st.button(lang("logout", "Logout")):
                    st.session_state.clear()
                    if cookies.ready():
                        cookies["user"] = None
                        cookies.save()
                    st.experimental_rerun()
        else:
            login_form(lang)

    # Greet user
    st.markdown(
        f"{lang('welcome')}, {user['username'] if user else lang('guest','Guest')}"
    )

def get_navigation(lang, user) -> str:
    """Setup sidebar navigation and return selected menu"""
    options = [
        lang("home"),
        lang("families"),
        lang("products"),
        lang("routes"),
        lang("characteristics"),
        lang("measurements")
    ]
    
    if user and user["role"] == "admin":
        options.append(lang("users"))

    return st.sidebar.radio(lang("navigate"), options)

def main():
    # Initialize app
    lang, user = initialize_app()

    # Render header
    render_header(lang, user)

    # Setup navigation
    menu = get_navigation(lang, user)

    # Save cookies
    if cookies.ready():
        cookies.save()

    # Setup filters
    filters = (
        {} if menu == lang("home")
        else get_global_filters(lang)
    )

    # Show dashboard description if on home
    if menu == lang("home"):
        st.sidebar.markdown(
            lang("dashboard_description", "Dashboard description…")
        )

    # Route to modules
    modules: Dict[str, Callable] = {
        lang("home"): dashboard.app,
        lang("families"): families.app,
        lang("products"): products.app,
        lang("routes"): routes.app,
        lang("characteristics"): characteristics.app,
        lang("measurements"): measurements.app,
        lang("users"): users.app
    }

    try:
        if menu in modules:
            if menu == lang("users") and user and user["role"] == "admin":
                modules[menu](lang)
            elif menu != lang("users"):
                modules[menu](lang, filters)
            else:
                st.warning(lang("access_denied"))
        else:
            st.error(lang("invalid_page"))
    except Exception as e:
        st.error(f"Error loading module: {str(e)}")

if __name__ == "__main__":
    main()