import streamlit as st
from core.auth import require_role
from core.config import settings
from core.api_client import ApiClient, ApiError
from core import mock_backend
from core.ui import header

require_role(["labeler"])
header("My Tasks", "Список назначенных задач разметки.")

def client() -> ApiClient:
    return ApiClient(settings.backend_url, token=st.session_state.get("token"))

try:
    tasks = mock_backend.mock_list_tasks() if settings.use_mock else client().list_tasks()
    if not tasks:
        st.write("No tasks assigned.")
    else:
        st.dataframe(tasks, use_container_width=True)
        st.info("Откройте страницу Annotate и вставьте task_id.")
except ApiError as e:
    st.error(f"Backend error ({e.status_code}): {e}")
