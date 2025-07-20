import streamlit as st
import bcrypt
from utils.mongo import get_db

def change_password_form(lang, user):
    """Password change form component"""
    with st.form("password_change", clear_on_submit=True):
        st.subheader(lang("change_password", "Change Password"))
        
        current_password = st.text_input(
            lang("current_password", "Current Password"),
            type="password"
        )
        new_password = st.text_input(
            lang("new_password", "New Password"),
            type="password"
        )
        confirm_password = st.text_input(
            lang("confirm_password", "Confirm New Password"),
            type="password"
        )
        
        if st.form_submit_button(lang("update_password", "Update Password")):
            return process_password_change(
                lang, user, 
                current_password, 
                new_password, 
                confirm_password
            )
    return False

def process_password_change(lang, user, current_password, new_password, confirm_password):
    """Process the password change request"""
    if not all([current_password, new_password, confirm_password]):
        st.error(lang("fill_all_fields", "Please fill all fields"))
        return False
        
    if new_password != confirm_password:
        st.error(lang("passwords_dont_match", "New passwords don't match"))
        return False
        
    db = get_db()
    db_user = db.users.find_one({"username": user["username"]})
    
    if not bcrypt.checkpw(
        current_password.encode(),
        db_user["password"].encode()
    ):
        st.error(lang("wrong_password", "Current password is incorrect"))
        return False
        
    new_hash = bcrypt.hashpw(
        new_password.encode(),
        bcrypt.gensalt()
    ).decode()
    
    db.users.update_one(
        {"username": user["username"]},
        {"$set": {"password": new_hash}}
    )
    
    st.success(lang("password_updated", "Password updated successfully!"))
    return True