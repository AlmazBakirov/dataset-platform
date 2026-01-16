import streamlit as st
from core.config import settings
from core.api_client import ApiClient, ApiError
from core.ui import header
from core.ui_helpers import api_call
from core import mock_backend

header("Login", "Вход в систему по роли (customer / labeler / admin / universal).")

def client() -> ApiClient:
    return ApiClient(settings.backend_url, token=None)

# If already logged in
if st.session_state.get("token") and st.session_state.get("role"):
    st.success(f"Logged in as: {st.session_state['role']}")
    if st.button("Logout"):
        st.session_state.pop("token", None)
        st.session_state.pop("role", None)
        st.session_state.pop("selected_request_id", None)
        st.session_state.pop("selected_task_id", None)
        st.rerun()
    st.stop()

username = st.text_input("Username", placeholder="customer1 / labeler1 / admin1 / universal1")
password = st.text_input("Password", type="password", placeholder="pass")

if st.button("Login", type="primary", disabled=not (username and password)):
    def do_login():
        if settings.use_mock:
            # Требуется mock_backend.mock_login(username, password)
            return mock_backend.mock_login(username, password)
        return client().login(username, password)

    data = api_call("Login", do_login, spinner="Logging in...", show_payload=True)
    if not data:
        st.stop()

    token = data.get("access_token") or data.get("token")
    role = data.get("role")

    if not token or not role:
        st.error("Login response missing 'access_token' or 'role'.")
        st.json(data)
        st.stop()

    st.session_state["token"] = token
    st.session_state["role"] = role

    # Important: do NOT st.switch_page here.
    # We rerun so app.py rebuilds navigation with the new role.
    st.rerun()
