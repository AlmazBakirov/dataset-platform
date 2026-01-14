from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, List
import httpx

from core.config import settings

class ApiError(RuntimeError):
    def __init__(self, status_code: int, message: str, details: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.details = details

@dataclass
class LoginResponse:
    access_token: str
    role: str
    user_id: str

class ApiClient:
    def __init__(self, base_url: str, token: Optional[str] = None):
        self.base_url = base_url.rstrip("/")
        self.token = token

    def _headers(self) -> Dict[str, str]:
        h = {"Accept": "application/json"}
        if self.token:
            h["Authorization"] = f"Bearer {self.token}"
        return h

    def _request(self, method: str, path: str, **kwargs) -> Any:
        url = f"{self.base_url}{path}"
        with httpx.Client(timeout=settings.request_timeout_s) as client:
            r = client.request(method, url, headers=self._headers(), **kwargs)
        if r.status_code >= 400:
            try:
                payload = r.json()
                msg = payload.get("message") or payload.get("detail") or r.text
            except Exception:
                payload = r.text
                msg = r.text
            raise ApiError(r.status_code, msg, payload)
        if r.headers.get("content-type", "").startswith("application/json"):
            return r.json()
        return r.content

    # ---------- AUTH ----------
    def login(self, username: str, password: str) -> LoginResponse:
        payload = {"username": username, "password": password}
        data = self._request("POST", "/auth/login", json=payload)
        # ожидаемый формат: {access_token, role, user_id}
        return LoginResponse(
            access_token=data["access_token"],
            role=data["role"],
            user_id=str(data.get("user_id", "")),
        )

    def me(self) -> Dict[str, Any]:
        return self._request("GET", "/me")

    # ---------- REQUESTS / DATASETS ----------
    def list_requests(self) -> List[Dict[str, Any]]:
        return self._request("GET", "/requests")

    def create_request(self, title: str, description: str, classes: List[str]) -> Dict[str, Any]:
        payload = {"title": title, "description": description, "classes": classes}
        return self._request("POST", "/requests", json=payload)

    def get_request(self, request_id: str) -> Dict[str, Any]:
        return self._request("GET", f"/requests/{request_id}")

    # ---------- UPLOADS ----------
    def upload_files_mvp(self, request_id: str, files: List[tuple[str, bytes, str]]) -> Dict[str, Any]:
        """
        MVP-метод: отправка файлов через backend (подходит для небольших файлов).
        files: список кортежей (filename, content_bytes, mime)
        """
        multipart = []
        for name, content, mime in files:
            multipart.append(("files", (name, content, mime)))
        return self._request("POST", f"/requests/{request_id}/uploads", files=multipart)

    def get_presign(self, request_id: str, filename: str, content_type: str) -> Dict[str, Any]:
        """
        Production: backend выдаёт presigned URL для прямой загрузки в object storage.
        Ожидаем: {upload_url, object_key, headers(optional)}
        """
        payload = {"filename": filename, "content_type": content_type}
        return self._request("POST", f"/requests/{request_id}/uploads/presign", json=payload)

    def confirm_upload(self, request_id: str, object_key: str) -> Dict[str, Any]:
        payload = {"object_key": object_key}
        return self._request("POST", f"/requests/{request_id}/uploads/confirm", json=payload)

    # ---------- QC ----------
    def run_qc(self, request_id: str) -> Dict[str, Any]:
        return self._request("POST", f"/qc/run?request_id={request_id}")

    def qc_status(self, request_id: str) -> Dict[str, Any]:
        return self._request("GET", f"/qc/status?request_id={request_id}")

    def qc_results(self, request_id: str) -> List[Dict[str, Any]]:
        return self._request("GET", f"/qc/results?request_id={request_id}")

    # ---------- LABELING ----------
    def list_tasks(self) -> List[Dict[str, Any]]:
        return self._request("GET", "/tasks")

    def get_task(self, task_id: str) -> Dict[str, Any]:
        return self._request("GET", f"/tasks/{task_id}")

    def save_labels(self, task_id: str, image_id: str, labels: List[str]) -> Dict[str, Any]:
        payload = {"image_id": image_id, "labels": labels}
        return self._request("POST", f"/tasks/{task_id}/labels", json=payload)
