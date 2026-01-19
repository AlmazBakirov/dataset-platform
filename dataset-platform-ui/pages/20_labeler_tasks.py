import streamlit as st

from core import mock_backend
from core.api_client import ApiClient
from core.auth import require_role
from core.config import settings
from core.ui import header
from core.ui_helpers import api_call

require_role(["labeler"])
header("My Tasks", "Список назначенных задач разметки.")


def client() -> ApiClient:
    return ApiClient(settings.backend_url, token=st.session_state.get("token"))


def do_list_tasks():
    return mock_backend.mock_list_tasks() if settings.use_mock else client().list_tasks()


tasks = api_call("Load tasks", do_list_tasks, spinner="Loading tasks...", show_payload=True)

if not tasks:
    st.write("No tasks assigned.")
else:
    st.dataframe(tasks, width="stretch")

    st.divider()
    st.subheader("Open task (no manual ID)")

    labels = []
    label_to_id = {}

    for t in tasks:
        tid = str(t.get("id", "")).strip() or str(t.get("task_id", "")).strip()
        status = str(t.get("status", "")).strip()
        title = str(t.get("title", "")).strip() or str(t.get("request_title", "")).strip()

        if not tid:
            continue

        meta = " | ".join([x for x in [title, status] if x])
        label = f"{tid} — {meta}" if meta else tid

        labels.append(label)
        label_to_id[label] = tid

    if not labels:
        st.info("Tasks exist, but no task id found in items.")
    else:
        pre_id = str(st.session_state.get("selected_task_id", "")).strip()
        pre_index = 0
        if pre_id:
            for i, lab in enumerate(labels):
                if label_to_id[lab] == pre_id:
                    pre_index = i
                    break

        selected_label = st.selectbox("Select task", labels, index=pre_index)
        st.session_state["selected_task_id"] = label_to_id[selected_label]

        if st.button("Annotate", type="primary"):
            st.switch_page("pages/21_labeler_annotate.py")
