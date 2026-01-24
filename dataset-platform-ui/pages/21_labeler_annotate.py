import streamlit as st

from core import mock_backend
from core.api_client import ApiClient, ApiError
from core.auth import require_role
from core.config import settings
from core.ui import header
from core.ui_helpers import api_call

require_role(["labeler", "admin", "universal"])
header("Annotate", "MVP: классификация. Прогресс + Finish task (UI-ready).")


def client() -> ApiClient:
    return ApiClient(
        settings.backend_url,
        token=st.session_state.get("token"),
        timeout_s=settings.request_timeout_s,
    )


default_task_id = str(st.session_state.get("selected_task_id", "")).strip()
task_id = st.text_input(
    "Task ID", value=default_task_id, placeholder="Выберите задачу в My Tasks"
).strip()

if task_id:
    st.session_state["selected_task_id"] = task_id
else:
    st.info("Сначала выберите задачу на странице **My Tasks** и нажмите **Annotate**.")
    if st.button("Back to My Tasks"):
        st.switch_page("pages/20_labeler_tasks.py")
    st.stop()


def do_get_task():
    return mock_backend.mock_get_task(task_id) if settings.use_mock else client().get_task(task_id)


task = api_call("Load task", do_get_task, spinner="Loading task...", show_payload=True)
if not task:
    st.stop()

st.subheader(task.get("title", "Task"))

images = task.get("images", [])
if not images:
    st.warning("No images in task.")
    st.stop()

classes = (
    task.get("classes")
    or st.session_state.get("cached_classes")
    or ["pothole", "crosswalk", "traffic_light", "road_sign"]
)
st.session_state["cached_classes"] = classes


# ---- Progress ----
def do_progress():
    if settings.use_mock:
        return mock_backend.mock_task_progress(task_id)
    try:
        return client().task_progress(task_id)
    except ApiError as e:
        # backend not implemented yet: compute local fallback using images and no remote labels
        if e.status_code in (404, 405, 501):
            return {
                "task_id": task_id,
                "total_images": len(images),
                "labeled_images": 0,
            }
        raise


progress = (
    api_call("Load progress", do_progress, spinner="Loading progress...", show_payload=False) or {}
)
total_images = int(progress.get("total_images") or len(images))
labeled_images = int(progress.get("labeled_images") or 0)

m1, m2, m3 = st.columns(3)
m1.metric("Total images", total_images)
m2.metric("Labeled", labeled_images)
m3.metric("Remaining", max(total_images - labeled_images, 0))

# ---- Image index persisted ----
idx_key = f"img_idx_{task_id}"
if idx_key not in st.session_state:
    st.session_state[idx_key] = 0

idx = st.number_input(
    "Image index",
    min_value=0,
    max_value=len(images) - 1,
    value=int(st.session_state[idx_key]),
    step=1,
)

st.session_state[idx_key] = int(idx)

img = images[int(idx)]
image_id = str(img.get("image_id", "")).strip()
if not image_id:
    st.error("Image record missing image_id.")
    st.stop()

st.write(f"Image: **{image_id}**")

# --- IMAGE PREVIEW (mock vs real) ---

if settings.use_mock:
    # В mock-режиме показываем url (если mock его даёт)
    if img.get("url"):
        st.image(img["url"], use_container_width=True)
    else:
        st.info("Mock: нет URL для изображения.")
else:
    # В real-режиме НЕ используем url напрямую (он 401 в браузере).
    # Мы качаем байты по image_id с токеном и показываем их.
    try:
        content = client().get_image_bytes(int(image_id))
        st.image(content, width=900)
    except ApiError as e:
        st.error(f"Failed to load image bytes: {e}")
        st.write("Debug url:", img.get("url", ""))
        st.write("Token present:", bool(st.session_state.get("token")))


labels_key = f"labels_{task_id}_{image_id}"
auto_next_key = f"auto_next_{task_id}"  # чтобы checkbox не сбрасывался при каждом rerun

cL, cR = st.columns([3, 1], vertical_alignment="bottom")

with cL:
    selected = st.multiselect("Labels", options=classes, key=labels_key)
    auto_next = st.checkbox("Auto-next after Save", value=True, key=auto_next_key)

with cR:
    save_disabled = len(selected) == 0

    def do_save():
        if settings.use_mock:
            return mock_backend.mock_save_labels(task_id, image_id, list(selected))
        return client().save_labels(task_id, image_id, list(selected))

    save_clicked = st.button(
        "Save labels",
        type="primary",
        disabled=save_disabled,
        key=f"save_{task_id}_{image_id}",
        use_container_width=True,
    )

if save_clicked:
    resp = api_call("Save labels", do_save, spinner="Saving...", show_payload=True)
    if resp is not None:
        st.success("Saved.")

        # refresh progress (сервер)
        api_call(
            "Refresh progress",
            do_progress,
            spinner="Refreshing progress...",
            show_payload=False,
        )

        # auto-next
        if auto_next and int(idx) < len(images) - 1:
            st.session_state[idx_key] = int(idx) + 1

        # всегда перерисовываем, чтобы метрики/Finish обновились
        st.rerun()


# ---- Finish task ----
def do_finish():
    if settings.use_mock:
        return mock_backend.mock_complete_task(task_id)
    return client().complete_task(task_id)


c1, c2, c3 = st.columns([1, 1, 2])
with c1:
    if st.button("Back to My Tasks", key="back_tasks"):
        st.switch_page("pages/20_labeler_tasks.py")
with c2:
    if st.button("Next image", disabled=(int(idx) >= len(images) - 1), key="next_img"):
        st.session_state[idx_key] = int(idx) + 1
        st.rerun()
with c3:
    finish_disabled = labeled_images < total_images

    if st.button(
        "Finish task",
        type="secondary",
        disabled=finish_disabled,
        key="finish_task",
    ):
        resp = api_call("Complete task", do_finish, spinner="Completing task...", show_payload=True)
        if resp is not None:
            st.success("Task completed.")
            st.switch_page("pages/20_labeler_tasks.py")

st.caption("Finish task активируется, когда labeled_images == total_images (по progress).")
