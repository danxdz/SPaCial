# utils/auth.py

import streamlit as st
import bcrypt
import json
from streamlit_cookies_manager import EncryptedCookieManager
from utils.mongo import get_db

# Pull this secret from .streamlit/secrets.toml
cookie_secret = st.secrets["COOKIE_PASSWORD"]

# Initialize cookie manager
cookies = EncryptedCookieManager(prefix="spacial_", password=cookie_secret)

def check_user_credentials(username: str, plain_password: str):
    db = get_db()
    user = db.users.find_one({"username": username, "active": True})
    if user and bcrypt.checkpw(plain_password.encode(), user["password"].encode()):
        return user
    return None

def login_form(lang):
    t = lang
    # Add custom CSS for login button
    st.markdown("""
        <style>
        div[data-testid="stButton"] button {
            min-width: fit-content;
            width: auto;
            padding-left: 15px;
            padding-right: 15px;
        }
        </style>
    """, unsafe_allow_html=True)
    # Try to restore user session from cookie (only if cookies are ready)
    if "user" not in st.session_state and cookies.ready():
        raw = cookies.get("user")
        if raw:
            st.session_state["user"] = json.loads(raw)

    # If logged in, show only logout button
    if "user" in st.session_state:
        if st.button(t("logout", "Logout")):
            st.session_state.clear()
            if cookies.ready():
                cookies["user"] = None
                cookies.save()
            st.experimental_rerun()
        return  # Stop here if logged in

    # Show login form
    col1, col2, col3 = st.columns([3, 3, 5], gap="small")
    username = col1.text_input(
        label=t("username", "Username"),
        placeholder=t("username", "Username"),
        key="login_user",
        label_visibility="collapsed"
    )
    password = col2.text_input(
        label=t("password", "Password"),
        placeholder=t("password", "Password"),
        type="password",
        key="login_pass",
        label_visibility="collapsed"
    )
    if col3.button(t("login", "Login"), use_container_width=False):
        user = check_user_credentials(username, password)
        if user:
            st.session_state["user"] = {
                "username": user["username"],
                "role": user["role"]
            }
            if cookies.ready():
                cookies["user"] = json.dumps(st.session_state["user"])
                cookies.save()
            st.experimental_rerun()
        else:
            st.error(t("invalid_credentials", "Invalid credentials."))

    # Save cookies once if ready
    if cookies.ready():
        cookies.save()
