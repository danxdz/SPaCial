

# =============================================================================
# utils/auth.py
import streamlit as st
from utils.database import get_db_connection, hash_password

def authenticate_user(username, password):
    """Authenticate user credentials"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("""SELECT id, username, role, active 
                     FROM users 
                     WHERE username=? AND password=? AND active=1""", 
                  (username, hash_password(password)))
    
    user = cursor.fetchone()
    conn.close()
    
    if user:
        return {
            "id": user[0],
            "username": user[1], 
            "role": user[2]
        }
    return None

def check_login():
    """Check if user is logged in, show login form if not"""
    if "user" not in st.session_state:
        st.title("🔐 SPaCial Login")
        
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submit = st.form_submit_button("Login")
            
            if submit:
                user = authenticate_user(username, password)
                if user:
                    st.session_state.user = user
                    st.success("Login successful!")
                    st.rerun()
                else:
                    st.error("Invalid credentials")
        
        st.info("Demo: admin / admin")
        return None
    
    return st.session_state.user
