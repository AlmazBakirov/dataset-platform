import streamlit as st

from core import mock_backend
from core.api_client import ApiClient, ApiError
from core.auth import require_role
from core.config import settings
from core.ui import header
from core.ui_helpers import api_call

require_role(["admin", "universal"])
header(
    "Admin Panel",
    "MVP: просмотр Requests/Tasks + быстрые переходы без ручного копирования ID.",
)


def client() -> ApiClient:
    return ApiClient(settings.backend_url, token=st.session_state.get("token"))


# --------------------------
# Data loaders (with fallback)
# --------------------------
def load_requests():
    if settings.use_mock:
        return mock_backend.mock_list_requests()

    try:
        return client().admin_list_requests()
    except ApiError as e:
        # If admin endpoints not implemented yet, fallback
        if e.status_code in (404, 405, 501):
            return client().list_requests()
        raise


def load_tasks():
    if settings.use_mock:
        return mock_backend.mock_list_tasks()

    try:
        return client().admin_list_tasks()
    except ApiError as e:
        if e.status_code in (404, 405, 501):
            return client().list_tasks()
        raise


# --------------------------
# UI helpers
# --------------------------
def apply_filters(
    rows: list[dict],
    search: str,
    status_filter: list[str],
    id_key_candidates: list[str],
    title_key_candidates: list[str],
) -> list[dict]:
    s = (search or "").strip().lower()

    def get_first(d: dict, keys: list[str]) -> str:
        for k in keys:
            v = d.get(k)
            if v is not None and str(v).strip():
                return str(v)
        return ""

    out = rows

    if status_filter:
        out = [r for r in out if str(r.get("status", "")).strip() in status_filter]

    if s:
        filtered = []
        for r in out:
            rid = get_first(r, id_key_candidates)
            title = get_first(r, title_key_candidates)
            blob = f"{rid} {title} {str(r.get('status', ''))}".lower()
            if s in blob:
                filtered.append(r)
        out = filtered

    return out


def make_select_labels(
    rows: list[dict], id_keys: list[str], title_keys: list[str]
) -> tuple[list[str], dict[str, str]]:
    labels: list[str] = []
    label_to_id: dict[str, str] = {}

    for r in rows:
        rid = ""
        for k in id_keys:
            rid = str(r.get(k, "")).strip()
            if rid:
                break
        if not rid:
            continue

        title = ""
        for k in title_keys:
            title = str(r.get(k, "")).strip()
            if title:
                break

        status = str(r.get("status", "")).strip()
        meta = " | ".join([x for x in [title, status] if x])
        label = f"{rid} — {meta}" if meta else rid

        labels.append(label)
        label_to_id[label] = rid

    return labels, label_to_id


# --------------------------
# Top metrics
# --------------------------
colA, colB, colC = st.columns(3)
with colA:
    st.write("**Role**")
    st.write(st.session_state.get("role", "—"))
with colB:
    st.write("**Backend**")
    st.write("MOCK" if settings.use_mock else settings.backend_url)
with colC:
    if st.button("Refresh", type="secondary"):
        st.rerun()

st.divider()

tabs = st.tabs(["Requests", "Tasks", "Users (TBD)", "Thresholds (TBD)"])

# ==========================
# Requests tab
# ==========================
with tabs[0]:
    st.subheader("Requests")

    req_search = st.text_input("Search (id/title/status)", key="admin_req_search")
    # Load requests once per render
    req_items = (
        api_call(
            "Load requests",
            load_requests,
            spinner="Loading requests...",
            show_payload=True,
        )
        or []
    )
    # Status filter options
    req_statuses = sorted(
        {str(r.get("status", "")).strip() for r in req_items if str(r.get("status", "")).strip()}
    )
    req_status_filter = st.multiselect("Status filter", req_statuses, key="admin_req_status_filter")

    req_filtered = apply_filters(
        req_items,
        req_search,
        req_status_filter,
        id_key_candidates=["id", "request_id"],
        title_key_candidates=["title", "request_title"],
    )

    if not req_filtered:
        st.info("No requests found (after filters).")
    else:
        st.dataframe(req_filtered, width="stretch")

        st.divider()
        st.subheader("Open request (no manual ID)")

        labels, label_to_id = make_select_labels(
            req_filtered,
            id_keys=["id", "request_id"],
            title_keys=["title", "request_title"],
        )

        if not labels:
            st.info("Requests exist, but no ID field found.")
        else:
            pre_id = str(st.session_state.get("selected_request_id", "")).strip()
            pre_index = 0
            if pre_id:
                for i, lab in enumerate(labels):
                    if label_to_id[lab] == pre_id:
                        pre_index = i
                        break

            selected_label = st.selectbox(
                "Select request", labels, index=pre_index, key="admin_req_select"
            )
            selected_request_id = label_to_id[selected_label]
            st.session_state["selected_request_id"] = selected_request_id

            c1, c2, c3 = st.columns([1, 1, 2])
            with c1:
                if st.button("Open Uploads", type="primary", key="admin_open_uploads"):
                    st.switch_page("pages/11_customer_uploads.py")
            with c2:
                if st.button("Open QC Review", type="primary", key="admin_open_qc"):
                    st.switch_page("pages/12_customer_qc_review.py")
            with c3:
                if st.checkbox("Show selected JSON", key="admin_req_show_json"):
                    # show full row for selected id
                    row = next(
                        (
                            r
                            for r in req_items
                            if str(r.get("id", r.get("request_id", ""))).strip()
                            == selected_request_id
                        ),
                        None,
                    )
                    if row:
                        st.json(row)

            st.divider()
            st.subheader("Assign (MVP)")

            labeler_username = st.text_input(
                "Assign to labeler (username)",
                placeholder="labeler1",
                key="admin_assign_labeler_username",
            ).strip()

            if st.button(
                "Assign task to labeler",
                type="secondary",
                disabled=not labeler_username,
                key="admin_assign_btn",
            ):

                def do_assign():
                    if settings.use_mock:
                        # optional mock; if not implemented, return a stub
                        return {
                            "status": "mocked",
                            "request_id": selected_request_id,
                            "labeler_username": labeler_username,
                        }
                    return client().admin_assign_task(selected_request_id, labeler_username)

                resp = api_call("Assign", do_assign, spinner="Assigning...", show_payload=True)
                if resp is not None:
                    st.success("Assign request to labeler: done (or mocked).")


# ==========================
# Tasks tab
# ==========================
with tabs[1]:
    st.subheader("Tasks")

    task_search = st.text_input("Search (id/title/status)", key="admin_task_search")
    task_items = (
        api_call("Load tasks", load_tasks, spinner="Loading tasks...", show_payload=True) or []
    )
    task_statuses = sorted(
        {str(t.get("status", "")).strip() for t in task_items if str(t.get("status", "")).strip()}
    )
    task_status_filter = st.multiselect(
        "Status filter", task_statuses, key="admin_task_status_filter"
    )

    task_filtered = apply_filters(
        task_items,
        task_search,
        task_status_filter,
        id_key_candidates=["id", "task_id"],
        title_key_candidates=["title", "request_title"],
    )

    if not task_filtered:
        st.info("No tasks found (after filters).")
    else:
        st.dataframe(task_filtered, width="stretch")

        st.divider()
        st.subheader("Open task (no manual ID)")

        labels, label_to_id = make_select_labels(
            task_filtered,
            id_keys=["id", "task_id"],
            title_keys=["title", "request_title"],
        )

        if not labels:
            st.info("Tasks exist, but no task ID field found.")
        else:
            pre_id = str(st.session_state.get("selected_task_id", "")).strip()
            pre_index = 0
            if pre_id:
                for i, lab in enumerate(labels):
                    if label_to_id[lab] == pre_id:
                        pre_index = i
                        break

            selected_label = st.selectbox(
                "Select task", labels, index=pre_index, key="admin_task_select"
            )
            selected_task_id = label_to_id[selected_label]
            st.session_state["selected_task_id"] = selected_task_id

            # If task has request_id, store it too (nice for QC/Uploads)
            selected_task_row = None
            for t in task_items:
                tid = str(t.get("id", "")).strip() or str(t.get("task_id", "")).strip()
                if tid == selected_task_id:
                    selected_task_row = t
                    break
            if selected_task_row:
                rid = selected_task_row.get("request_id")
                if rid:
                    st.session_state["selected_request_id"] = str(rid)

            c1, c2 = st.columns([1, 2])
            with c1:
                if st.button("Open Annotate", type="primary", key="admin_open_annotate"):
                    st.switch_page("pages/21_labeler_annotate.py")
            with c2:
                if (
                    st.checkbox("Show selected JSON", key="admin_task_show_json")
                    and selected_task_row
                ):
                    st.json(selected_task_row)

# ==========================
# Users / Thresholds placeholders
# ==========================
with tabs[2]:
    st.subheader("Users (TBD)")
    st.info(
        "Пока нет эндпоинта. Как только backend добавит /admin/users — подключим сюда список пользователей и роли."
    )

with tabs[3]:
    st.subheader("Thresholds (TBD)")
    st.info(
        "Пороговые значения QC (duplicate/AI) лучше хранить в backend + выдавать через /admin/settings. UI подключим после реализации."
    )
