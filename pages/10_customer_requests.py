import streamlit as st
from core.auth import require_role
from core.config import settings
from core.api_client import ApiClient, ApiError
from core import mock_backend
from core.ui import header

require_role(["customer"])

header("Requests", "Создание заявки и просмотр списка заявок.")

def client() -> ApiClient:
    return ApiClient(settings.backend_url, token=st.session_state.get("token"))

with st.expander("Create new request", expanded=True):
    title = st.text_input("Title", placeholder="Road images: City A -> City B")
    description = st.text_area("Description", placeholder="Требования, маршрутм, погодные условия, камера и т.д.")
    classes_raw = st.text_area("Classes (one per line)", placeholder="pothole\ncrosswalk\ntraffic_light")
    classes = [c.strip() for c in classes_raw.splitlines() if c.strip()]

    if st.button("Create", type="primary"):
        try:
            if settings.use_mock:
                created = mock_backend.mock_create_request(title, description, classes)
            else:
                created = client().create_request(title, description, classes)
            st.success(f"Created request: {created.get('id')}")
            st.rerun()
        except ApiError as e:
            st.error(f"Backend error ({e.status_code}): {e}")

st.divider()
st.subheader("My requests")

try:
    if settings.use_mock:
        items = mock_backend.mock_list_requests()
    else:
        items = client().list_requests()
    if not items:
        st.write("No requests yet.")
    else:
        st.dataframe(items, use_container_width=True)
except ApiError as e:
    st.error(f"Backend error ({e.status_code}): {e}")
