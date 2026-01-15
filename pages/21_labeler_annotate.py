import streamlit as st
from core.auth import require_role
from core.config import settings
from core.api_client import ApiClient, ApiError
from core import mock_backend
from core.ui import header

require_role(["labeler"])
header("Annotate", "MVP: классификация (выбор классов). Для bbox позже добавляется canvas-компонент.")


def client() -> ApiClient:
    return ApiClient(settings.backend_url, token=st.session_state.get("token"))

default_task_id = str(st.session_state.get("selected_task_id", "")).strip()

task_id = st.text_input("Task ID", value=default_task_id).strip()

if task_id:
    st.session_state["selected_task_id"] = task_id
else:
    st.stop()


try:
    task = mock_backend.mock_get_task(task_id) if settings.use_mock else client().get_task(task_id)
except ApiError as e:
    st.error(f"Backend error ({e.status_code}): {e}")
    st.stop()

st.subheader(task.get("title", "Task"))

images = task.get("images", [])
if not images:
    st.write("No images in task.")
    st.stop()

# В реальном проекте классы должны приходить из backend (из request/classes)
classes = st.session_state.get("cached_classes") or ["pothole", "crosswalk", "traffic_light", "road_sign"]

idx = st.number_input("Image index", min_value=0, max_value=len(images)-1, value=0, step=1)
img = images[int(idx)]

st.write(f"Image: **{img['image_id']}**")
if img.get("url"):
    st.image(img["url"], use_container_width=True)
else:
    st.info("Mock: нет URL. В проде backend должен отдавать ссылку на превью/объект в storage.")

selected = st.multiselect("Labels", options=classes)

if st.button("Save labels", type="primary"):
    try:
        if settings.use_mock:
            resp = mock_backend.mock_save_labels(task_id, img["image_id"], selected)
        else:
            resp = client().save_labels(task_id, img["image_id"], selected)
        st.success("Saved.")
        st.json(resp)
    except ApiError as e:
        st.error(f"Backend error ({e.status_code}): {e}")
