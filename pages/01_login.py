import streamlit as st
from core.auth import do_login
from core.ui import header
from core.config import settings

header("Login", "Вход по логину/паролю (UI вызывает backend auth).")

st.info(f"Backend URL: {settings.backend_url} | USE_MOCK={int(settings.use_mock)}")

username = st.text_input("Username")
password = st.text_input("Password", type="password")

if st.button("Sign in", type="primary"):
    do_login(username, password)
