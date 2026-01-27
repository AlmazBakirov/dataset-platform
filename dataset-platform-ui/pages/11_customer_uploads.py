import streamlit as st

from core.api_client import ApiClient, ApiError
from core.auth import require_role
from core.config import settings
from core.ui import header
from core.ui_helpers import api_call

require_role(["customer", "admin", "universal"])
header("Uploads", "Загрузка изображений в заявку (multipart или presigned).")

c = ApiClient(settings.backend_url, token=st.session_state.get("token"))

request_id = st.session_state.get("selected_request_id")
if not request_id:
    st.warning("Сначала выберите Request в Customer → Requests.")
    if st.button("Go to Requests", type="primary"):
        st.switch_page("pages/10_customer_requests.py")
    st.stop()

st.text_input("Selected request_id", value=str(request_id), disabled=True)

upload_mode = getattr(
    settings, "upload_mode", "multipart"
)  # если у вас есть это поле в UI settings
st.caption(f"UPLOAD_MODE = {upload_mode}")

files = st.file_uploader("Select images", type=["jpg", "jpeg", "png"], accept_multiple_files=True)

if not files:
    st.stop()

if upload_mode == "presigned":
    if st.button("Upload (presigned)", type="primary"):
        for f in files:
            data = f.getvalue()
            content_type = f.type or "application/octet-stream"
            sha256 = ApiClient.sha256_bytes(data)

            def do_presign(
                f=f,
                content_type=content_type,
                sha256=sha256,
            ):  # Fix function definitions to bind loop variables properly  # Fix function definitions to bind loop variables properly
                return c.uploads_presign(int(request_id), f.name, content_type, sha256)

            pres = api_call(
                "Presign", do_presign, spinner=f"Presigning {f.name}...", show_payload=False
            )
            if not pres:
                continue

            # PUT напрямую в MinIO
            try:
                ApiClient.put_presigned(pres["upload_url"], data, content_type)
                st.success(f"Uploaded to S3: {f.name}")
            except ApiError as e:
                st.error(f"Presigned upload failed for {f.name}: {e}")
                continue

            def do_confirm(
                f=f,
                content_type=content_type,
                pres=pres,
                sha256=sha256,
            ):  # Fix function definitions to bind loop variables properly  # Fix function definitions to bind loop variables properly
                return c.uploads_confirm(
                    int(request_id), f.name, content_type, pres["object_key"], sha256
                )

            conf = api_call(
                "Confirm", do_confirm, spinner=f"Confirming {f.name}...", show_payload=True
            )
            if conf:
                st.success(f"Confirmed image_id={conf.get('image_id')}")

else:
    st.info(
        "multipart режим оставлен как fallback. Если хотите — я дам финальный код и для multipart страницы."
    )
