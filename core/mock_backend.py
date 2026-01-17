from __future__ import annotations

import itertools
import random
from typing import Any

from core.api_client import ApiError

_random = random.Random(42)

_request_counter = itertools.count(1001)
_task_counter = itertools.count(5001)

# In-memory stores
_requests: list[dict[str, Any]] = []
_tasks: list[dict[str, Any]] = []
_labels_store: dict[tuple[str, str], list[str]] = {}  # (task_id, image_id) -> labels
_uploads_store: dict[str, list[dict[str, Any]]] = {}  # request_id -> uploaded items


def _ensure_seed_data() -> None:
    if _requests:
        return

    r1 = {
        "id": "req-1001",
        "title": "Road images: City A -> City B",
        "description": "Mock request",
        "classes": ["pothole", "crosswalk", "traffic_light", "road_sign"],
        "status": "new",
    }
    r2 = {
        "id": "req-1002",
        "title": "Winter roads: City C -> City D",
        "description": "Mock request",
        "classes": ["snow", "ice", "lane_marking"],
        "status": "in_progress",
    }
    _requests.extend([r1, r2])

    t1 = {
        "id": "task-5001",
        "title": "Label req-1001",
        "status": "assigned",
        "request_id": "req-1001",
        "assignee": "labeler1",
    }
    t2 = {
        "id": "task-5002",
        "title": "Label req-1002",
        "status": "open",
        "request_id": "req-1002",
        "assignee": None,
    }
    _tasks.extend([t1, t2])


# ---------- Auth ----------
def mock_login(username: str, password: str) -> dict[str, Any]:
    users = {
        "customer1": {"password": "pass", "role": "customer"},
        "labeler1": {"password": "pass", "role": "labeler"},
        "admin1": {"password": "pass", "role": "admin"},
        "universal1": {"password": "pass", "role": "universal"},
    }

    u = users.get(username)
    if not u or u["password"] != password:
        raise ApiError(status_code=401, message="Invalid credentials (mock)")

    return {"access_token": f"mock-token-{username}", "role": u["role"]}


# ---------- Requests ----------
def mock_create_request(title: str, description: str, classes: list[str]) -> dict[str, Any]:
    _ensure_seed_data()
    rid = f"req-{next(_request_counter)}"
    req = {
        "id": rid,
        "title": title or f"Request {rid}",
        "description": description or "",
        "classes": classes or [],
        "status": "new",
    }
    _requests.append(req)
    return req


def mock_list_requests() -> list[dict[str, Any]]:
    _ensure_seed_data()
    return list(_requests)


# ---------- QC ----------
def mock_qc_results(request_id: str) -> list[dict[str, Any]]:
    _ensure_seed_data()

    # Simulate 25 images
    rows: list[dict[str, Any]] = []
    for i in range(1, 26):
        dup = _random.random()
        ai = _random.random()

        rows.append(
            {
                "request_id": request_id,
                "image_id": f"{request_id}_img_{i:03d}",
                "duplicate_score": round(dup, 4),
                "ai_generated_score": round(ai, 4),
            }
        )
    return rows


# ---------- Tasks ----------
def mock_list_tasks() -> list[dict[str, Any]]:
    _ensure_seed_data()
    return list(_tasks)


def mock_get_task(task_id: str) -> dict[str, Any]:
    _ensure_seed_data()
    t = next((x for x in _tasks if str(x.get("id")) == str(task_id)), None)
    if not t:
        raise ApiError(status_code=404, message=f"Task not found (mock): {task_id}")

    request_id = str(t.get("request_id"))
    req = next((r for r in _requests if str(r.get("id")) == request_id), None)

    classes = (req.get("classes") if req else None) or ["pothole", "crosswalk", "traffic_light", "road_sign"]

    # 10 mock images
    images = [{"image_id": f"{task_id}_img_{i:03d}", "url": None} for i in range(1, 11)]

    return {
        "id": t["id"],
        "title": t.get("title", f"Task {task_id}"),
        "status": t.get("status", "open"),
        "request_id": request_id,
        "classes": classes,
        "images": images,
    }


def mock_save_labels(task_id: str, image_id: str, labels: list[str]) -> dict[str, Any]:
    _ensure_seed_data()
    _labels_store[(str(task_id), str(image_id))] = list(labels)
    return {"status": "ok", "task_id": task_id, "image_id": image_id, "labels": labels}


# ---------- Uploads (presigned mock) ----------
def mock_presign_uploads(request_id: str, files: list[dict[str, Any]]) -> dict[str, Any]:
    # In mock we return fake URLs, but UI will NOT actually upload to them.
    uploads = []
    for f in files:
        fn = f.get("filename") or "file.bin"
        ct = f.get("content_type") or "application/octet-stream"
        uploads.append(
            {
                "filename": fn,
                "url": "https://example.com/mock-presigned-url",
                "method": "PUT",
                "headers": {"Content-Type": ct},
                "key": f"mock/{request_id}/{fn}",
            }
        )
    return {"uploads": uploads}


def mock_complete_uploads(request_id: str, uploaded: list[dict[str, Any]]) -> dict[str, Any]:
    _uploads_store[str(request_id)] = list(uploaded)
    return {"status": "ok", "request_id": request_id, "uploaded": uploaded}
