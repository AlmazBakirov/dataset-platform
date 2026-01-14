from __future__ import annotations
from typing import Any, Dict, List
from dataclasses import dataclass
import uuid
import random

@dataclass
class MockUser:
    username: str
    password: str
    role: str

USERS = [
    MockUser("customer1", "pass", "customer"),
    MockUser("labeler1", "pass", "labeler"),
    MockUser("admin1", "pass", "admin"),
    MockUser("Nurdaulet", "best777", "universal"),
    MockUser("Aslan", "best777", "universal"),
    MockUser("Rasul", "best777", "universal"),
    MockUser("Almazito", "Study91!@", "universal"),
]

_requests: List[Dict[str, Any]] = []
_tasks: List[Dict[str, Any]] = []

def mock_login(username: str, password: str) -> Dict[str, Any]:
    u = next((x for x in USERS if x.username == username and x.password == password), None)
    if not u:
        raise ValueError("Invalid credentials")
    return {"access_token": f"mock-{uuid.uuid4()}", "role": u.role, "user_id": username}

def mock_list_requests() -> List[Dict[str, Any]]:
    return _requests

def mock_create_request(title: str, description: str, classes: List[str]) -> Dict[str, Any]:
    rid = str(uuid.uuid4())
    req = {"id": rid, "title": title, "description": description, "classes": classes, "status": "NEW"}
    _requests.append(req)
    # создадим фиктивную задачу для разметчика
    _tasks.append({
        "id": str(uuid.uuid4()),
        "request_id": rid,
        "title": f"Labeling: {title}",
        "images": [{"image_id": f"img_{i}", "url": None} for i in range(1, 6)],
        "status": "ASSIGNED"
    })
    return req

def mock_qc_results(request_id: str) -> List[Dict[str, Any]]:
    res = []
    for i in range(1, 16):
        res.append({
            "image_id": f"img_{i}",
            "filename": f"img_{i}.jpg",
            "duplicate_score": round(random.random(), 3),
            "ai_generated_score": round(random.random(), 3),
            "flags": [f for f in [
                "DUPLICATE" if random.random() > 0.8 else None,
                "AI_SUSPECT" if random.random() > 0.8 else None,
            ] if f],
        })
    return res

def mock_list_tasks() -> List[Dict[str, Any]]:
    return [{"id": t["id"], "title": t["title"], "status": t["status"], "request_id": t["request_id"]} for t in _tasks]

def mock_get_task(task_id: str) -> Dict[str, Any]:
    t = next(x for x in _tasks if x["id"] == task_id)
    return t

def mock_save_labels(task_id: str, image_id: str, labels: List[str]) -> Dict[str, Any]:
    return {"ok": True, "task_id": task_id, "image_id": image_id, "labels": labels}
