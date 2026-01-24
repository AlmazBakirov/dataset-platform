import streamlit as st

from core.api_client import ApiClient
from core.auth import require_role
from core.config import settings
from core.ui import header
from core.ui_helpers import api_call

require_role(["customer", "admin", "universal"])

header("Export", "Экспорт финального датасета в Parquet (build/status/download).")


def client() -> ApiClient:
    return ApiClient(settings.backend_url, token=st.session_state.get("token"))


# --- Автоподстановка request_id из session_state ---
selected_request_id = str(st.session_state.get("selected_request_id", "")).strip()

if not selected_request_id:
    st.warning("Request не выбран. Перейдите в Customer → Requests и выберите заявку.")
    if st.button("Go to Requests", type="primary"):
        st.switch_page("pages/10_customer_requests.py")
    st.stop()

st.text_input("Selected request_id", value=selected_request_id, disabled=True)

st.info(
    "Важно: если backend настроен строго, export может вернуть 409 (Conflict), "
    "если разметка (labels) отсутствует для части изображений."
)

st.divider()

# --- Actions ---
c1, c2, c3 = st.columns(3)

with c1:
    if st.button("Build parquet", type="primary", key="build_parquet"):

        def do_build():
            return client().export_build_parquet(selected_request_id)

        resp = api_call(
            "Build parquet",
            do_build,
            spinner="Building parquet...",
            show_payload=True,
        )
        if resp is not None:
            st.success("Export job started / parquet built.")

with c2:
    if st.button("Refresh status", key="refresh_status"):

        def do_status():
            return client().export_status(selected_request_id)

        status = api_call(
            "Load export status",
            do_status,
            spinner="Loading status...",
            show_payload=True,
        )
        if status is not None:
            st.session_state["export_status_cache"] = status

with c3:
    # Скачивание — делаем отдельной кнопкой, чтобы не путать со статусом
    if st.button("Prepare download", key="prepare_download"):

        def do_download():
            return client().export_download_parquet(selected_request_id)

        content = api_call(
            "Download parquet",
            do_download,
            spinner="Downloading parquet...",
            show_payload=False,
        )
        if content:
            st.session_state["export_download_bytes"] = content
            st.success("Parquet downloaded into UI memory. Use Download button below.")

st.divider()

# --- Status view ---
status = st.session_state.get("export_status_cache")
if status:
    st.subheader("Export status")
    st.json(status)
else:
    st.caption("Нажмите Refresh status, чтобы увидеть состояние экспорта.")

# --- Download button (actual file download in browser) ---
data = st.session_state.get("export_download_bytes")
if data:
    file_name = f"request_{selected_request_id}.parquet"
    st.download_button(
        label="Download parquet",
        data=data,
        file_name=file_name,
        mime="application/octet-stream",
        type="secondary",
        key="download_parquet_btn",
    )
else:
    st.caption(
        "Нажмите Prepare download, чтобы загрузить parquet байты и активировать Download кнопку."
    )
