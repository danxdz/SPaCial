# =============================================================================
# modules/users.py
import streamlit as st
import pandas as pd
from utils.database import get_db_connection, hash_password



# modules/users.py
def app(lang, user_session=None):
    # Verificação de segurança
    if user_session and user_session["role"] != "admin":
        st.error(lang("access_denied"))
        return
        
    st.title(f"👥 {lang('users')}")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Add new user
    st.subheader(f"➕ {lang('add')} {lang('user')}")
    with st.form("add_user"):
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            username = st.text_input(lang("username"))
        with col2:
            password = st.text_input(lang("password"), type="password")
        with col3:
            role = st.selectbox(lang("role"), ["user", "admin"])
        with col4:
            active = st.checkbox(lang("active"), value=True)
        
        if st.form_submit_button(lang("add")):
            if username and password:
                try:
                    hashed_pw = hash_password(password)
                    cursor.execute("""INSERT INTO users (username, password, role, active) 
                                    VALUES (?, ?, ?, ?)""", 
                                 (username, hashed_pw, role, 1 if active else 0))
                    conn.commit()
                    st.success(f"User '{username}' added!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")
    
    # List users
    st.subheader(f"📋 {lang('users')}")
    users_df = pd.read_sql("SELECT id, username, role, active FROM users", conn)
    
    if not users_df.empty:
        for idx, user in users_df.iterrows():
            col1, col2, col3, col4, col5 = st.columns([2, 2, 2, 1, 1])
            with col1:
                st.text(user['username'])
            with col2:
                st.text(user['role'])
            with col3:
                st.text("Active" if user['active'] else "Inactive")
            with col4:
                if st.button("Toggle", key=f"toggle_{user['id']}"):
                    new_status = 0 if user['active'] else 1
                    cursor.execute("UPDATE users SET active = ? WHERE id = ?", (new_status, user['id']))
                    conn.commit()
                    st.rerun()
            with col5:
                if user['username'] != 'admin':  # Protect admin user
                    if st.button("Delete", key=f"delete_{user['id']}"):
                        cursor.execute("DELETE FROM users WHERE id = ?", (user['id'],))
                        conn.commit()
                        st.rerun()
    
    conn.close()