import httpx
import streamlit as st

from core import mock_backend
from core.api_client import ApiClient
from core.auth import require_role
from core.config import settings
from core.ui import header
from core.ui_helpers import api_call

require_role(["customer", "admin", "universal"])
header(
    "Uploads",
    "mvp: multipart через backend. presigned: presign -> storage PUT -> complete. + статус/галерея.",
)


def client() -> ApiClient:
    return ApiClient(
        settings.backend_url,
        token=st.session_state.get("token"),
        timeout_s=settings.request_timeout_s,
    )


default_request_id = str(st.session_state.get("selected_request_id", "")).strip()
request_id = st.text_input(
    "Request ID", value=default_request_id, placeholder="ID заявки из Requests"
).strip()
if request_id:
    st.session_state["selected_request_id"] = request_id

files = st.file_uploader("Select images", type=["jpg", "jpeg", "png"], accept_multiple_files=True)

# Default from config, but allow override in UI (useful for testing)
mode_default = getattr(settings, "upload_mode", "mvp")
upload_mode = st.selectbox(
    "Upload mode", ["mvp", "presigned"], index=0 if mode_default != "presigned" else 1
)

st.caption(
    "mvp = backend принимает файлы; presigned = UI грузит в storage по URL, затем сообщает backend complete."
)


def do_upload_mvp():
    packed = []
    for f in files:
        packed.append((f.name, f.getvalue(), f.type or "application/octet-stream"))

    if settings.use_mock:
        return mock_backend.mock_upload_files_mvp(request_id, packed)

    return client().upload_files_mvp(request_id, packed)


def do_upload_presigned():
    presign_payload = [
        {"filename": f.name, "content_type": (f.type or "application/octet-stream")} for f in files
    ]

    # 1) presign
    if settings.use_mock:
        presigned = mock_backend.mock_presign_uploads(request_id, presign_payload)
    else:
        presigned = client().presign_uploads(request_id, presign_payload)

    uploads = presigned.get("uploads") or []
    if not uploads:
        raise RuntimeError("Presign returned empty uploads list")

    rec_by_name = {u.get("filename"): u for u in uploads if u.get("filename")}

    # Mock: не делаем PUT, только complete
    if settings.use_mock:
        uploaded_report = []
        for f in files:
            rec = rec_by_name.get(f.name)
            if not rec:
                raise RuntimeError(f"No presigned entry for file: {f.name}")
            uploaded_report.append(
                {"filename": f.name, "key": rec.get("key") or f.name, "etag": None}
            )
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
                raise RuntimeError(
                    f"Only PUT presigned is supported in UI now. Got method={method}"
                )

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


def do_list_uploads():
    if settings.use_mock:
        return mock_backend.mock_list_uploads(request_id)
    return client().list_uploads(request_id)


def do_run_qc():
    if settings.use_mock:
        return {"status": "mocked"}
    return client().run_qc(request_id)


st.divider()

col1, col2, col3, col4 = st.columns([1, 1, 1, 2])

with col1:
    disabled_upload = not (request_id and files)
    if st.button("Upload", type="primary", disabled=disabled_upload):
        if upload_mode == "mvp":
            resp = api_call(
                "Upload files (MVP)",
                do_upload_mvp,
                spinner="Uploading via backend...",
                show_payload=True,
            )
        else:
            resp = api_call(
                "Upload files (Presigned)",
                do_upload_presigned,
                spinner="Uploading (presigned)...",
                show_payload=True,
            )

        if resp is not None:
            st.success("Upload completed.")
            st.json(resp)

with col2:
    if st.button("Load uploads", disabled=not request_id):
        rows = api_call(
            "List uploads",
            do_list_uploads,
            spinner="Loading uploads...",
            show_payload=True,
        )
        if rows is not None:
            st.session_state["uploads_cache"] = rows

with col3:
    if st.button("Run QC", disabled=not request_id):
        resp = api_call("Run QC", do_run_qc, spinner="Starting QC...", show_payload=True)
        if resp is not None:
            st.success("QC started (or mocked).")

with col4:
    if st.button("Open QC Review", disabled=not request_id):
        st.switch_page("pages/12_customer_qc_review.py")

st.divider()
st.subheader("Uploads status")

rows = st.session_state.get("uploads_cache")
if not rows and request_id and st.checkbox("Auto-load uploads", value=True):
    rows = api_call(
        "List uploads", do_list_uploads, spinner="Loading uploads...", show_payload=True
    )
    if rows is not None:
        st.session_state["uploads_cache"] = rows

if not rows:
    st.info("No uploads loaded yet.")
else:
    # Show count
    st.metric("Uploaded files", len(rows))

    # Table view
    st.dataframe(rows, use_container_width=True)

    # Optional gallery if preview_url exists (backend can provide thumbnail URLs later)
    previewable = [r for r in rows if r.get("preview_url")]
    if previewable and st.checkbox("Show gallery previews", value=False):
        st.caption("Preview URLs are optional; backend/storage should provide them.")
        cols = st.columns(4)
        for i, r in enumerate(previewable):
            with cols[i % 4]:
                st.image(
                    r["preview_url"],
                    caption=r.get("filename") or r.get("key"),
                    use_container_width=True,
                )
