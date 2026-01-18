import streamlit as st
import httpx

from core.auth import require_role
from core.config import settings
from core.ui import header

# Доступен всем залогиненным ролям
require_role(["customer", "labeler", "admin", "universal"])

header("Dashboard", "Главная страница: статус backend, режимы, быстрые переходы.")

role = str(st.session_state.get("role", "") or "")
token = st.session_state.get("token")
selected_request_id = str(st.session_state.get("selected_request_id", "") or "").strip()
selected_task_id = str(st.session_state.get("selected_task_id", "") or "").strip()

c1, c2, c3, c4 = st.columns(4)
c1.metric("Role", role or "-")
c2.metric("USE_MOCK", "1" if settings.use_mock else "0")
c3.metric("UPLOAD_MODE", getattr(settings, "upload_mode", "mvp"))
c4.metric("Timeout (s)", str(getattr(settings, "request_timeout_s", 20)))

st.divider()

st.subheader("Backend status")
st.write(f"BACKEND_URL: `{settings.backend_url}`")

def try_health() -> tuple[bool, str]:
    """
    Try a few common endpoints. Backend may implement one of them.
    """
    base = (settings.backend_url or "").rstrip("/")
    if not base:
        return (False, "BACKEND_URL is empty")

    timeout = httpx.Timeout(float(getattr(settings, "request_timeout_s", 20)), connect=10.0)

    endpoints = ["/health", "/_health", "/api/health", "/docs"]
    last_err = None

    for ep in endpoints:
        url = base + ep
        try:
            r = httpx.get(url, timeout=timeout, headers={"Accept": "application/json"})
            if 200 <= r.status_code < 300:
                # if JSON - show short info
                ct = r.headers.get("content-type", "")
                if "application/json" in ct:
                    try:
                        data = r.json()
                        return (True, f"{ep} OK (json): {data}")
                    except Exception:
                        return (True, f"{ep} OK (json parse failed)")
                return (True, f"{ep} OK (status {r.status_code})")
            else:
                last_err = f"{ep} returned {r.status_code}"
        except Exception as e:
            last_err = f"{ep} error: {e!s}"

    return (False, last_err or "No health endpoint responded")

ok, msg = try_health()
if ok:
    st.success(msg)
else:
    st.warning(f"Backend health not confirmed: {msg}")
    st.caption("Это нормально на ранней стадии. Когда backend добавит /health, здесь будет зелёный статус.")

st.divider()

st.subheader("Quick actions")

# Customer block
if role in ("customer", "admin", "universal"):
    st.markdown("### Customer")
    cc1, cc2, cc3 = st.columns(3)
    with cc1:
        if st.button("Requests", use_container_width=True):
            st.switch_page("pages/10_customer_requests.py")
    with cc2:
        if st.button("Uploads", use_container_width=True):
            st.switch_page("pages/11_customer_uploads.py")
    with cc3:
        if st.button("QC Review", use_container_width=True):
            st.switch_page("pages/12_customer_qc_review.py")

    if selected_request_id:
        st.info(f"Selected request_id: **{selected_request_id}**")
    else:
        st.caption("selected_request_id ещё не выбран. Откройте Requests и выберите заявку.")

# Labeler block
if role in ("labeler", "admin", "universal"):
    st.markdown("### Labeler")
    lc1, lc2 = st.columns(2)
    with lc1:
        if st.button("My Tasks", use_container_width=True):
            st.switch_page("pages/20_labeler_tasks.py")
    with lc2:
        if st.button("Annotate", use_container_width=True):
            st.switch_page("pages/21_labeler_annotate.py")

    if selected_task_id:
        st.info(f"Selected task_id: **{selected_task_id}**")
    else:
        st.caption("selected_task_id ещё не выбран. Откройте My Tasks и выберите задачу.")

# Admin block
if role in ("admin", "universal"):
    st.markdown("### Admin")
    if st.button("Admin Panel", use_container_width=True):
        st.switch_page("pages/30_admin_panel.py")

st.divider()
st.subheader("Session details (debug)")
st.json(
    {
        "role": role,
        "token_present": bool(token),
        "selected_request_id": selected_request_id,
        "selected_task_id": selected_task_id,
        "backend_url": settings.backend_url,
        "use_mock": settings.use_mock,
        "upload_mode": getattr(settings, "upload_mode", "mvp"),
    }
)
