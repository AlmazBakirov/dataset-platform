import streamlit as st
from core.auth import require_role
from core.config import settings
from core.api_client import ApiClient, ApiError
from core import mock_backend
from core.ui import header

require_role(["labeler"])
header("My Tasks", "Список назначенных задач разметки.")

def client() -> ApiClient:
    return ApiClient(settings.backend_url, token=st.session_state.get("token"))

try:
    tasks = mock_backend.mock_list_tasks() if settings.use_mock else client().list_tasks()
    if not tasks:
        st.write("No tasks assigned.")
    else:
        st.dataframe(tasks, use_container_width=True)

        st.divider()
        st.subheader("Open task (no manual ID)")

        # tasks ожидается как list[dict]
        labels = []
        label_to_id = {}

        for t in tasks:
            tid = str(t.get("id", "")).strip() or str(t.get("task_id", "")).strip()
            # попробуем красиво подписать: id + статус/название (если есть)
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

except ApiError as e:
    st.error(f"Backend error ({e.status_code}): {e}")
