import streamlit as st
import httpx

from core.auth import require_role
from core.config import settings
from core.api_client import ApiClient
from core.ui import header
from core.ui_helpers import api_call
from core import mock_backend

require_role(["customer", "admin", "universal"])
header("Uploads", "mvp: multipart через backend. presigned: presign -> storage PUT -> complete (готово под прод).")

def client() -> ApiClient:
    return ApiClient(settings.backend_url, token=st.session_state.get("token"), timeout_s=settings.request_timeout_s)

default_request_id = str(st.session_state.get("selected_request_id", "")).strip()

request_id = st.text_input(
    "Request ID",
    value=default_request_id,
    placeholder="ID заявки из Requests",
).strip()

if request_id:
    st.session_state["selected_request_id"] = request_id

files = st.file_uploader("Select images", type=["jpg", "jpeg", "png"], accept_multiple_files=True)

# Default from config, but allow override in UI (useful for testing)
mode_default = getattr(settings, "upload_mode", "mvp")
upload_mode = st.selectbox("Upload mode", ["mvp", "presigned"], index=0 if mode_default != "presigned" else 1)

st.caption("mvp = backend принимает файлы; presigned = UI грузит в storage по URL, затем сообщает backend complete.")

def do_upload_mvp():
    packed = []
    for f in files:
        packed.append((f.name, f.getvalue(), f.type or "application/octet-stream"))
    return client().upload_files_mvp(request_id, packed)

def do_upload_presigned():
    presign_payload = [{"filename": f.name, "content_type": (f.type or "application/octet-stream")} for f in files]

    # 1) presign
    if settings.use_mock:
        presigned = mock_backend.mock_presign_uploads(request_id, presign_payload)
    else:
        presigned = client().presign_uploads(request_id, presign_payload)

    uploads = presigned.get("uploads") or []
    if not uploads:
        raise RuntimeError("Presign returned empty uploads list")

    rec_by_name = {u.get("filename"): u for u in uploads if u.get("filename")}

    # In mock mode we do NOT perform real PUT requests (URLs are fake)
    if settings.use_mock:
        uploaded_report = []
        for f in files:
            rec = rec_by_name.get(f.name)
            if not rec:
                raise RuntimeError(f"No presigned entry for file: {f.name}")
            uploaded_report.append({"filename": f.name, "key": rec.get("key") or f.name, "etag": None})
        return mock_backend.mock_complete_uploads(request_id, uploaded_report)

    # 2) upload each file to storage (PUT)
    uploaded_report = []
    progress = st.progress(0)
    total = len(files)

    timeout = httpx.Timeout(120.0, connect=10.0)
    with httpx.Client(timeout=timeout, follow_redirects=True) as h:
        for i, f in enumerate(files, start=1):
            rec = rec_by_name.get(f.name)
            if not rec:
                raise RuntimeError(f"No presigned entry for file: {f.name}")

            url = rec.get("url")
            method = (rec.get("method") or "PUT").upper()
            headers = rec.get("headers") or {}

            if not url:
                raise RuntimeError(f"Presigned entry missing url for file: {f.name}")
            if method != "PUT":
                raise RuntimeError(f"Only PUT presigned is supported in UI now. Got method={method}")

            content = f.getvalue()
            resp = h.put(url, content=content, headers=headers)

            if resp.status_code < 200 or resp.status_code >= 300:
                text = (resp.text or "")[:200]
                raise RuntimeError(f"Storage upload failed for {f.name}: {resp.status_code} {text}")

            etag = resp.headers.get("ETag") or resp.headers.get("etag")
            uploaded_report.append(
                {
                    "filename": f.name,
                    "key": rec.get("key") or rec.get("object_key") or f.name,
                    "etag": etag,
                }
            )

            progress.progress(int(i * 100 / total))

    # 3) complete
    return client().complete_uploads(request_id, uploaded_report)

disabled = not (request_id and files)

if st.button("Upload", type="primary", disabled=disabled):
    if upload_mode == "mvp":
        resp = api_call("Upload files (MVP)", do_upload_mvp, spinner="Uploading via backend...", show_payload=True)
    else:
        resp = api_call("Upload files (Presigned)", do_upload_presigned, spinner="Uploading (presigned)...", show_payload=True)

    if resp is not None:
        st.success("Upload completed.")
        st.json(resp)
