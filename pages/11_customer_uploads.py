import streamlit as st
from core.auth import require_role
from core.config import settings
from core.api_client import ApiClient, ApiError
from core.ui import header

require_role(["customer"])
header("Uploads", "MVP: загрузка небольших файлов через backend. Для продакшена лучше presigned upload.")

def client() -> ApiClient:
    return ApiClient(settings.backend_url, token=st.session_state.get("token"))

request_id = st.text_input("Request ID", placeholder="Вставьте ID заявки из Requests")

files = st.file_uploader("Select images", type=["jpg","jpeg","png"], accept_multiple_files=True)

if st.button("Upload", type="primary", disabled=not(request_id and files)):
    try:
        packed = []
        for f in files:
            packed.append((f.name, f.getvalue(), f.type or "application/octet-stream"))
        resp = client().upload_files_mvp(request_id, packed)
        st.success("Uploaded.")
        st.json(resp)
    except ApiError as e:
        st.error(f"Backend error ({e.status_code}): {e}")
