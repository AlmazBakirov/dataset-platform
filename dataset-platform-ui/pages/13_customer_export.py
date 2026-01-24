import streamlit as st

from core.api_client import ApiError
from core.auth import require_role
from core.state import get_client
from core.ui_helpers import api_call

require_role(["customer"])

st.title("Export Parquet")

c = get_client()

request_id = st.session_state.get("selected_request_id")

if not request_id:
    st.warning("Сначала выберите request на странице Requests.")
    st.stop()

st.write(f"Selected request_id: **{request_id}**")


def do_status():
    return c.export_status(str(request_id))


def do_export():
    return c.export_parquet(str(request_id))


st.subheader("Status")
status = api_call(
    "Export status", do_status, spinner="Loading export status...", show_payload=False
)

if status:
    st.json(status)

st.divider()
st.subheader("Build parquet")

if st.button("Build Parquet", type="primary"):
    resp = api_call("Export parquet", do_export, spinner="Building parquet...", show_payload=True)
    if resp is not None:
        st.success("Export created.")

st.divider()
st.subheader("Download")

# Перечитаем статус (чтобы понять, готово ли)
status2 = api_call("Refresh export status", do_status, spinner="Refreshing...", show_payload=False)

can_download = bool(status2 and status2.get("status") == "done")

if st.button("Fetch file to download", disabled=not can_download):
    try:
        data = c.download_export_bytes(str(request_id))
        st.download_button(
            label="Download parquet",
            data=data,
            file_name=f"request_{request_id}.parquet",
            mime="application/octet-stream",
        )
    except ApiError as e:
        st.error(f"Download failed: {e}")
