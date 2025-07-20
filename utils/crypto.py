# utils/crypto.py

import streamlit as st
from cryptography.fernet import Fernet

# Pega a chave de criptografia do secrets
key = st.secrets["CRYPTO_KEY"].encode()
cipher = Fernet(key)

def encrypt(plain: str) -> bytes:
    return cipher.encrypt(plain.encode())

def decrypt(token: bytes) -> str:
    return cipher.decrypt(token).decode()
