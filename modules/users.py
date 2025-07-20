import streamlit as st
import pandas as pd
from utils.mongo import get_db
import bcrypt
from bson.objectid import ObjectId

def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode(), salt).decode()

def check_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())

def app(lang):
    t = lang  # translator function
    db = get_db()

    # Sidebar and headers
    st.sidebar.title(t("user_management"))
    st.sidebar.info(t("user_management_info", "This module allows you to manage users."))
    st.title(t("users"))
    st.info(t("user_management_description", "Here you can add, edit, or remove users."))

    # Add New User
    st.subheader(t("add_user", "Add New User"))
    with st.form("add_user_form"):
        new_username = st.text_input(t("username", "Username"))
        new_password = st.text_input(t("password", "Password"), type="password")
        new_role = st.selectbox(t("role", "Role"), ["user", "admin"])
        new_active = st.checkbox(t("active", "Active"), value=True)
        submitted = st.form_submit_button(t("create_user", "Create User"))
        if submitted:
            if not new_username or not new_password:
                st.error(t("require_fields", "Username and password are required."))
            else:
                hashed = hash_password(new_password)
                db.users.insert_one({
                    "username": new_username,
                    "password": hashed,
                    "role": new_role,
                    "active": new_active
                })
                st.success(t("user_created", f"User '{new_username}' created."))

    st.markdown("---")

    # Existing Users
    st.subheader(t("existing_users", "Existing Users"))
    users_cursor = db.users.find({}, {"password": 0})
    users_list = list(users_cursor)

    if not users_list:
        st.info(t("no_users", "No users found."))
        return

    df = pd.DataFrame(users_list)
    df["_id"] = df["_id"].astype(str)
    df = df.rename(columns={"_id": "id"})
    edited = st.data_editor(df, num_rows="dynamic", use_container_width=True, 
                column_order=["username","role", "active"])

    if st.button(t("save_changes", "Save Changes")):
        for _, row in edited.iterrows():
            user_id = ObjectId(row["id"])
            db.users.update_one(
                {"_id": user_id},
                {"$set": {
                    "username": row["username"],
                    "role": row["role"],
                    "active": bool(row["active"])
                }}
            )
        st.success(t("users_updated", "User changes saved."))