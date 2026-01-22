import json
from typing import Dict, List, Optional

import requests
import streamlit as st

API_BASE = "http://127.0.0.1:8000"


def api_headers() -> Dict[str, str]:
    token = st.session_state.get("token")
    if not token:
        return {}
    return {"Authorization": f"Bearer {token}"}


def api_post(path: str, payload: Optional[dict] = None) -> requests.Response:
    url = f"{API_BASE}{path}"
    return requests.post(url, json=payload, headers=api_headers(), timeout=30)


def api_get(path: str) -> requests.Response:
    url = f"{API_BASE}{path}"
    return requests.get(url, headers=api_headers(), timeout=30)


def fetch_image_bytes(url: str) -> bytes:
    # Важно: если /images/... требует auth — headers уже добавляем.
    r = requests.get(url, headers=api_headers(), timeout=30)
    r.raise_for_status()
    return r.content


def labels_from_selected(selected: List[str]) -> Dict[str, dict]:
    # Бекенд ожидает формат типа: {"crosswalk": {}}
    return {name: {} for name in selected}


st.set_page_config(page_title="Dataset Platform - Labeling UI", layout="wide")

st.title("Dataset Platform — Streamlit UI (Labeling MVP)")

# -----------------------
# SIDEBAR: AUTH
# -----------------------
st.sidebar.header("Auth")

if "token" not in st.session_state:
    st.session_state.token = None

with st.sidebar.form("login_form"):
    username = st.text_input("Username", value="labeler1")
    password = st.text_input("Password", type="password", value="labeler1")
    submitted = st.form_submit_button("Login")

if submitted:
    resp = api_post("/auth/login", {"username": username, "password": password})
    if resp.status_code != 200:
        st.sidebar.error(f"Login failed: {resp.status_code} {resp.text}")
    else:
        data = resp.json()
        st.session_state.token = data.get("access_token") or data.get("token")
        st.sidebar.success("Logged in")

if st.session_state.token:
    if st.sidebar.button("Logout"):
        st.session_state.token = None
        st.rerun()
else:
    st.info("Сначала залогинься (labeler1 / admin1 / universal1).")
    st.stop()

# -----------------------
# MAIN: TASKS LIST
# -----------------------
st.subheader("1) Список задач")

colA, colB = st.columns([1, 2])

with colA:
    if st.button("Обновить список задач"):
        st.session_state.pop("tasks_cache", None)

if "tasks_cache" not in st.session_state:
    r = api_get("/tasks")
    if r.status_code != 200:
        st.error(f"GET /tasks failed: {r.status_code} {r.text}")
        st.stop()
    st.session_state.tasks_cache = r.json()

tasks = st.session_state.tasks_cache

if not tasks:
    st.warning("Задач пока нет. Обычно они появляются после POST /requests/{id}/qc/run.")
    st.stop()

# Выбор task
task_options = {
    f"Task {t['id']} (request_id={t['request_id']}, status={t['status']})": t["id"] for t in tasks
}
selected_label = st.selectbox("Выбери задачу", list(task_options.keys()))
selected_task_id = task_options[selected_label]

# -----------------------
# TASK DETAIL
# -----------------------
st.subheader("2) Детали задачи")

r = api_get(f"/tasks/{selected_task_id}")
if r.status_code != 200:
    st.error(f"GET /tasks/{selected_task_id} failed: {r.status_code} {r.text}")
    st.stop()

task = r.json()

st.write(
    "**Task**:",
    task["id"],
    " | **status**:",
    task["status"],
    " | **request_id**:",
    task["request_id"],
)
classes = task.get("classes") or []
images = task.get("images") or []

st.write("**Classes**:", classes if classes else "(пусто — можно вводить вручную)")
st.write("**Images count**:", len(images))

if not images:
    st.warning("В задаче нет картинок.")
    st.stop()

# -----------------------
# LABELING UI
# -----------------------
st.subheader("3) Разметка")

# Выбор картинки из задачи
image_choices = {f"image_id={im['image_id']}": im for im in images}
image_choice_label = st.selectbox("Выбери картинку", list(image_choices.keys()))
img_obj = image_choices[image_choice_label]
image_id = img_obj["image_id"]
image_url = img_obj["url"]

left, right = st.columns([1, 1])

with left:
    st.write("**Image URL:**", image_url)
    try:
        img_bytes = fetch_image_bytes(image_url)
        st.image(img_bytes, caption=f"image_id={image_id}", use_container_width=True)
    except Exception as e:
        st.error(f"Не удалось загрузить картинку: {e}")

with right:
    st.write("**Labels**")

    # Если classes пустой — разрешим ручной ввод
    if classes:
        selected = st.multiselect("Выбери классы", options=classes, default=[])
    else:
        raw = st.text_input("Введи labels через запятую (например: crosswalk, signs)", value="")
        selected = [x.strip() for x in raw.split(",") if x.strip()]

    labels_payload = labels_from_selected(selected)

    st.code(
        json.dumps({"image_id": image_id, "labels": labels_payload}, ensure_ascii=False, indent=2),
        language="json",
    )

    if st.button("Сохранить labels (POST /tasks/{task_id}/annotations)"):
        payload = {"image_id": image_id, "labels": labels_payload}
        resp = api_post(f"/tasks/{selected_task_id}/annotations", payload)
        if resp.status_code != 200:
            st.error(f"Save failed: {resp.status_code} {resp.text}")
        else:
            st.success("Saved")
            st.json(resp.json())

    st.divider()

    if st.button("Complete task (POST /tasks/{task_id}/complete)"):
        resp = api_post(f"/tasks/{selected_task_id}/complete", {})
        if resp.status_code != 200:
            st.error(f"Complete failed: {resp.status_code} {resp.text}")
        else:
            st.success("Task completed")
            st.json(resp.json())
            # обновим кэш задач
            st.session_state.pop("tasks_cache", None)
            st.rerun()
