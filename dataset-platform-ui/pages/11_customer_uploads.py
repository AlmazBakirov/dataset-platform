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

upload_mode = getattr(settings, "upload_mode", "mvp")  # mvp | presigned
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

            pres = api_call(
                "Presign",
                lambda f=f, ct=content_type, sh=sha256: c.uploads_presign(
                    int(request_id), f.name, ct, sh
                ),
                spinner=f"Presigning {f.name}...",
                show_payload=False,
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

            conf = api_call(
                "Confirm",
                lambda f=f, ct=content_type, p=pres, sh=sha256: c.uploads_confirm(
                    int(request_id), f.name, ct, p["object_key"], sh
                ),
                spinner=f"Confirming {f.name}...",
                show_payload=True,
            )
            if conf:
                st.success(f"Confirmed image_id={conf.get('image_id')}")

else:
    # ✅ multipart fallback: реально загружает через backend
    if st.button("Upload (multipart via backend)", type="primary"):
        packed = []
        for f in files:
            packed.append((f.name, f.getvalue(), f.type or "application/octet-stream"))

        res = api_call(
            "Upload multipart",
            lambda: c.upload_files_mvp(str(request_id), packed),
            spinner="Uploading via backend...",
            show_payload=True,
        )
        if res is not None:
            st.success("Uploaded via backend (multipart).")

# Показать список загруженных файлов
st.divider()
if st.button("Refresh uploads list"):
    pass

uploads = api_call(
    "List uploads",
    lambda: c.list_uploads(str(request_id)),
    spinner="Loading uploads...",
    show_payload=False,
)
if uploads:
    st.write(uploads)
