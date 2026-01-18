import streamlit as st

from core import mock_backend
from core.api_client import ApiClient
from core.auth import require_role
from core.config import settings
from core.ui import header
from core.ui_helpers import api_call

require_role(["customer"])

header("Requests", "Создание заявки и просмотр списка заявок.")


def client() -> ApiClient:
    return ApiClient(settings.backend_url, token=st.session_state.get("token"))


with st.expander("Create new request", expanded=True):
    title = st.text_input("Title", placeholder="Road images: City A -> City B")
    description = st.text_area(
        "Description",
        placeholder="Требования, маршрутм, погодные условия, камера и т.д.",
    )
    classes_raw = st.text_area(
        "Classes (one per line)", placeholder="pothole\ncrosswalk\ntraffic_light"
    )
    classes = [c.strip() for c in classes_raw.splitlines() if c.strip()]

    if st.button("Create", type="primary"):

        def do_create():
            if settings.use_mock:
                return mock_backend.mock_create_request(title, description, classes)
            return client().create_request(title, description, classes)

        created = api_call(
            "Create request",
            do_create,
            spinner="Creating request...",
            show_payload=True,
        )
        if created:
            req_id = str(created.get("id", "")).strip()
            if req_id:
                st.session_state["selected_request_id"] = req_id
            st.success(f"Created request: {req_id}")
            st.rerun()


st.divider()
st.subheader("My requests")


def do_list():
    if settings.use_mock:
        return mock_backend.mock_list_requests()
    return client().list_requests()


items = api_call("Load requests", do_list, spinner="Loading requests...", show_payload=True)

if not items:
    st.write("No requests yet.")
else:
    st.dataframe(items, width="stretch")

    st.divider()
    st.subheader("Open request (no manual ID)")

    labels = []
    label_to_id = {}

    for r in items:
        rid = str(r.get("id", "")).strip()
        title = str(r.get("title", "")).strip()
        if not rid:
            continue
        label = f"{rid} — {title}" if title else rid
        labels.append(label)
        label_to_id[label] = rid

    if not labels:
        st.info("Requests exist, but no IDs found in items.")
    else:
        pre_id = str(st.session_state.get("selected_request_id", "")).strip()
        pre_index = 0
        if pre_id:
            for i, lab in enumerate(labels):
                if label_to_id[lab] == pre_id:
                    pre_index = i
                    break

        selected_label = st.selectbox("Select request", labels, index=pre_index)
        st.session_state["selected_request_id"] = label_to_id[selected_label]

        c1, c2 = st.columns(2)
        with c1:
            if st.button("Open Uploads", key="open_uploads"):
                st.switch_page("pages/11_customer_uploads.py")
        with c2:
            if st.button("Open QC Review", key="open_qc"):
                st.switch_page("pages/12_customer_qc_review.py")
