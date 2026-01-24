from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

import httpx


@dataclass
class ApiError(Exception):
    status_code: int
    message: str
    payload: Any | None = None

    def __str__(self) -> str:
        return f"{self.status_code}: {self.message}"


class ApiClient:
    def __init__(self, base_url: str, token: Optional[str] = None, timeout_s: float = 20.0) -> None:
        self.base_url = (base_url or "").rstrip("/")
        self.token = token
        self.timeout_s = float(timeout_s)

    def _url(self, path: str) -> str:
        if not path.startswith("/"):
            path = "/" + path
        return f"{self.base_url}{path}"

    def _headers(self) -> dict[str, str]:
        headers: dict[str, str] = {"Accept": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def _raise_for_status(self, resp: httpx.Response) -> None:
        if 200 <= resp.status_code < 300:
            return

        msg = resp.reason_phrase or "Request failed"
        payload: Any | None = None

        try:
            payload = resp.json()
            if isinstance(payload, dict):
                if "detail" in payload and isinstance(payload["detail"], str):
                    msg = payload["detail"]
                elif "message" in payload and isinstance(payload["message"], str):
                    msg = payload["message"]
        except Exception:
            payload = resp.text

        raise ApiError(status_code=resp.status_code, message=msg, payload=payload)

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: Any | None = None,
        data: dict[str, Any] | None = None,
        files: Any | None = None,
    ) -> Any:
        if not self.base_url:
            raise ApiError(status_code=0, message="BACKEND_URL is empty or not configured.")

        timeout = httpx.Timeout(self.timeout_s, connect=10.0)
        url = self._url(path)

        try:
            with httpx.Client(timeout=timeout) as client:
                resp = client.request(
                    method=method.upper(),
                    url=url,
                    headers=self._headers(),
                    params=params,
                    json=json,
                    data=data,
                    files=files,
                )
        except httpx.RequestError as e:
            raise ApiError(status_code=0, message=f"Network error: {e!s}") from e

        self._raise_for_status(resp)

        if resp.status_code == 204:
            return None

        content_type = resp.headers.get("content-type", "")
        if "application/json" in content_type:
            try:
                return resp.json()
            except Exception as e:
                raise ApiError(
                    status_code=resp.status_code,
                    message="Invalid JSON in response",
                    payload=resp.text,
                ) from e

        return resp.text

    # ---------- Auth ----------
    def login(self, username: str, password: str) -> dict[str, Any]:
        return self._request(
            "POST", "/auth/login", json={"username": username, "password": password}
        )

    # ---------- Customer: requests ----------
    def create_request(self, title: str, description: str, classes: list[str]) -> dict[str, Any]:
        return self._request(
            "POST",
            "/requests",
            json={"title": title, "description": description, "classes": classes},
        )

    def list_requests(self) -> list[dict[str, Any]]:
        data = self._request("GET", "/requests")
        return data if isinstance(data, list) else []

    # ---------- Uploads (MVP multipart) ----------
    def upload_files_mvp(
        self, request_id: str, packed_files: list[tuple[str, bytes, str]]
    ) -> dict[str, Any]:
        multipart: list[tuple[str, tuple[str, bytes, str]]] = []
        for fname, content, mime in packed_files:
            multipart.append(("files", (fname, content, mime)))
        return self._request("POST", f"/requests/{request_id}/uploads", files=multipart)

    def list_uploads(self, request_id: str) -> list[dict[str, Any]]:
        data = self._request("GET", f"/requests/{request_id}/uploads")
        return data if isinstance(data, list) else []

    # ---------- Uploads (presigned) ----------
    def presign_uploads(self, request_id: str, files: list[dict[str, Any]]) -> dict[str, Any]:
        return self._request(
            "POST", "/uploads/presign", json={"request_id": request_id, "files": files}
        )

    def complete_uploads(self, request_id: str, uploaded: list[dict[str, Any]]) -> dict[str, Any]:
        return self._request(
            "POST",
            "/uploads/complete",
            json={"request_id": request_id, "uploaded": uploaded},
        )

    # ---------- QC ----------
    def run_qc(self, request_id: str) -> dict[str, Any]:
        return self._request("POST", f"/requests/{request_id}/qc/run")

    def qc_results(self, request_id: str) -> list[dict[str, Any]]:
        data = self._request("GET", f"/requests/{request_id}/qc/results")
        return data if isinstance(data, list) else []

    # ---------- Labeler: tasks ----------
    def list_tasks(self) -> list[dict[str, Any]]:
        data = self._request("GET", "/tasks")
        return data if isinstance(data, list) else []

    def get_task(self, task_id: str) -> dict[str, Any]:
        data = self._request("GET", f"/tasks/{task_id}")
        return data if isinstance(data, dict) else {}

    def get_image_bytes(self, image_id: int) -> bytes:
        if not self.base_url:
            raise ApiError(status_code=0, message="BACKEND_URL is empty or not configured.")

        timeout = httpx.Timeout(self.timeout_s, connect=10.0)
        url = self._url(f"/images/{image_id}/content")

        try:
            with httpx.Client(timeout=timeout) as client:
                resp = client.get(url, headers=self._headers())
        except httpx.RequestError as e:
            raise ApiError(status_code=0, message=str(e)) from e

        if resp.status_code >= 400:
            try:
                payload = resp.json()
                msg = payload.get("detail") if isinstance(payload, dict) else str(payload)
            except Exception:
                payload = None
                msg = resp.text
            raise ApiError(status_code=resp.status_code, message=msg, payload=payload)

        return resp.content

    def save_labels(self, task_id: str, image_id: str, labels: list[str]) -> dict[str, Any]:
        return self._request(
            "POST",
            f"/tasks/{task_id}/labels",
            json={"image_id": int(image_id), "labels": labels},
        )

    def task_progress(self, task_id: str) -> dict[str, Any]:
        data = self._request("GET", f"/tasks/{task_id}/progress")
        return data if isinstance(data, dict) else {}

    def complete_task(self, task_id: str) -> dict[str, Any]:
        data = self._request("POST", f"/tasks/{task_id}/complete")
        return data if isinstance(data, dict) else {"status": "ok"}

    def export_parquet(self, request_id: str) -> dict[str, Any]:
        data = self._request("POST", f"/requests/{request_id}/export/parquet")
        return data if isinstance(data, dict) else {}

    def download_export_bytes(self, request_id: str) -> bytes:
        # Скачиваем bytes (не JSON)
        url = self._url(f"/requests/{request_id}/export/download")
        timeout = httpx.Timeout(self.timeout_s, connect=10.0)

        try:
            with httpx.Client(timeout=timeout) as client:
                resp = client.get(url, headers=self._headers())
        except httpx.RequestError as e:
            raise ApiError(status_code=0, message=f"Network error: {e!s}") from e

        if not (200 <= resp.status_code < 300):
            try:
                payload = resp.json()
                msg = payload.get("detail") or payload.get("message") or resp.text
            except Exception:
                msg = resp.text
            raise ApiError(status_code=resp.status_code, message=msg)

        return resp.content

    # ---------- Admin ----------
    def admin_list_requests(self) -> list[dict[str, Any]]:
        data = self._request("GET", "/admin/requests")
        return data if isinstance(data, list) else []

    def admin_list_tasks(self) -> list[dict[str, Any]]:
        data = self._request("GET", "/admin/tasks")
        return data if isinstance(data, list) else []

    def admin_list_users(self) -> list[dict[str, Any]]:
        data = self._request("GET", "/admin/users")
        return data if isinstance(data, list) else []

    def admin_assign_task(self, request_id: str, labeler_username: str) -> dict[str, Any]:
        return self._request(
            "POST",
            "/admin/assign",
            json={"request_id": request_id, "labeler_username": labeler_username},
        )
        # ---------- Export ----------

    def export_build_parquet(self, request_id: str) -> dict[str, Any]:
        return self._request("POST", f"/requests/{request_id}/export/parquet")

    def export_status(self, request_id: str) -> dict[str, Any]:
        data = self._request("GET", f"/requests/{request_id}/export/status")
        return data if isinstance(data, dict) else {}

    def export_download_parquet(self, request_id: str) -> bytes:
        data = self._request("GET", f"/requests/{request_id}/export/download")
        if isinstance(data, (bytes, bytearray)):
            return bytes(data)
        # если backend вдруг вернул json (ошибка) — покажем понятную ошибку
        raise ApiError(
            status_code=0, message="Expected parquet bytes, got non-bytes response", payload=data
        )
