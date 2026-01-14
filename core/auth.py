import streamlit as st
from core.config import settings
from core.api_client import ApiClient, ApiError
from core import mock_backend

def get_client() -> ApiClient | None:
    token = st.session_state.get("token")
    if not token:
        return None
    return ApiClient(settings.backend_url, token=token)

def logout():
    for k in ["token", "role", "user_id"]:
        if k in st.session_state:
            del st.session_state[k]
    st.success("Вы вышли из системы.")

def require_role(roles: list[str]):
    role = st.session_state.get("role")
    token = st.session_state.get("token")
    if not token or not role:
        st.warning("Требуется вход.")
        st.stop()

    # роли, которым разрешено всё
    super_roles = {"admin", "universal"}

    if role in super_roles:
        return

    if role not in roles:
        st.error("Нет доступа для вашей роли.")
        st.stop()


def do_login(username: str, password: str):
    if settings.use_mock:
        try:
            data = mock_backend.mock_login(username, password)
        except ValueError as e:
            st.error(str(e))
            return
        st.session_state["token"] = data["access_token"]
        st.session_state["role"] = data["role"]
        st.session_state["user_id"] = data["user_id"]
        st.success(f"Вход выполнен. Роль: {data['role']}")
        st.rerun()

    client = ApiClient(settings.backend_url)
    try:
        resp = client.login(username, password)
    except ApiError as e:
        st.error(f"Ошибка входа ({e.status_code}): {e}")
        return
    st.session_state["token"] = resp.access_token
    st.session_state["role"] = resp.role
    st.session_state["user_id"] = resp.user_id
    st.success(f"Вход выполнен. Роль: {resp.role}")
    st.rerun()
