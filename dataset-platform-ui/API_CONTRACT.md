# API Contract (UI ↔ Backend)

This document defines the minimal API contract expected by the Streamlit UI.

## Conventions
- Base URL: `BACKEND_URL` (e.g. `http://localhost:8000`)
- Auth: Bearer token in header `Authorization: Bearer <token>`
- Content-Type:
  - JSON for most endpoints
  - `multipart/form-data` for uploads (MVP)
- Error format (recommended):
  - JSON: `{ "detail": "..." }` or `{ "message": "...", "errors": [...] }`

---

## 1) Auth

### POST /auth/login
Authenticate user and return token + role.

Request (JSON):
```json
{ "username": "string", "password": "string" }
```

Response (200):
```json
{ "access_token": "string", "role": "customer|labeler|admin|universal" }
```

Errors:
- 401 invalid credentials

---

## 2) Customer: Requests

### POST /requests
Create a request.

Request (JSON):
```json
{
  "title": "string",
  "description": "string",
  "classes": ["string"]
}
```

Response (200/201):
```json
{
  "id": "string",
  "title": "string",
  "description": "string",
  "classes": ["string"],
  "status": "string",
  "created_at": "string|null"
}
```

### GET /requests
List requests for current customer (or for admin/universal, optionally all).

Response (200):
```json
[
  {
    "id": "string",
    "title": "string",
    "description": "string|null",
    "status": "string",
    "created_at": "string|null"
  }
]
```

---

## 3) Customer: Uploads (MVP)

### POST /requests/{request_id}/uploads
Upload images for a request (MVP, multipart).

Request: `multipart/form-data`
- field name: `files` (multiple files allowed)
- each file: jpg/jpeg/png

Response (200):
```json
{
  "request_id": "string",
  "uploaded": 3,
  "skipped": 0,
  "errors": []
}
```

Errors:
- 400 invalid request_id or invalid file type
- 413 payload too large
- 404 request not found

---

## 3b) Uploads (Presigned)

### POST /uploads/presign
Backend returns pre-signed URLs for direct upload to storage (S3/MinIO/etc).

Request (JSON):
```json
{
  "request_id": "string",
  "files": [
    { "filename": "string", "content_type": "string" }
  ]
}
```

Response (200):
```json
{
  "uploads": [
    {
      "filename": "string",
      "url": "string",
      "method": "PUT",
      "headers": { "Content-Type": "string" },
      "key": "string"
    }
  ]
}
```

Notes:
- UI uploads each file to `url` using `method` (UI currently supports PUT).
- `key` must be returned back to backend in `/uploads/complete`.

### POST /uploads/complete
UI notifies backend that storage uploads finished.

Request (JSON):
```json
{
  "request_id": "string",
  "uploaded": [
    { "filename": "string", "key": "string", "etag": "string|null" }
  ]
}
```

Response (200):
```json
{ "status": "ok" }
```

Errors:
- 400 invalid request_id / payload
- 404 request not found

---

## 4) QC (Duplicates + AI-generated)

### POST /requests/{request_id}/qc/run
Start QC process for a request.

Response (200):
```json
{ "request_id": "string", "status": "started" }
```

Errors:
- 404 request not found
- 409 already running (optional)

### GET /requests/{request_id}/qc/results
Return QC results.

Response (200):
```json
[
  {
    "image_id": "string",
    "duplicate_score": 0.0,
    "ai_generated_score": 0.0,
    "source_url": "string|null",
    "flags": ["string"]
  }
]
```

Notes:
- UI applies thresholds locally:
  - duplicate if `duplicate_score >= dup_thr`
  - AI if `ai_generated_score >= ai_thr`

---

## 5) Labeler: Tasks

### GET /tasks
List tasks assigned to current labeler.

Response (200):
```json
[
  {
    "id": "string",
    "request_id": "string",
    "title": "string|null",
    "request_title": "string|null",
    "status": "string",
    "images_count": 0,
    "created_at": "string|null"
  }
]
```

### GET /tasks/{task_id}
Get task details including images and classes.

Response (200):
```json
{
  "id": "string",
  "title": "string",
  "classes": ["string"],
  "images": [
    { "image_id": "string", "url": "string|null" }
  ]
}
```

Notes:
- `classes` should come from request/classes in production.

### POST /tasks/{task_id}/labels
Save labels for one image.

Request (JSON):
```json
{ "image_id": "string", "labels": ["string"] }
```

Response (200):
```json
{ "task_id": "string", "image_id": "string", "status": "saved" }
```
## Labeling progress & completion

### GET /tasks/{task_id}/progress
Response (200):
```json
{
  "task_id": "string",
  "total_images": 10,
  "labeled_images": 3
}
Response (200):
```json
{ "status": "ok", "task_id": "string" }
```

Errors:
- 404 task not found
- 400 invalid labels

---


## 6) Admin (optional for MVP)
Backend may return 501 until implemented.

### GET /admin/users
Response (200):
```json
[
  { "username": "string", "role": "customer|labeler|admin|universal", "is_active": true }
]
```

### GET /admin/requests
Response (200):
```json
[
  { "id": "string", "title": "string", "status": "string", "created_at": "string|null" }
]
```

### GET /admin/tasks
Response (200):
```json
[
  { "id": "string", "request_id": "string", "status": "string", "created_at": "string|null" }
]
```

### POST /admin/assign
Assign a request to a labeler (backend creates/assigns a task).

Request (JSON):
```json
{ "request_id": "string", "labeler_username": "string" }
```

Response (200):
```json
{ "status": "assigned", "task_id": "string|null" }
```

Notes:
- If backend prefers assigning existing tasks, it can accept `{ "task_id": "...", "labeler_username": "..." }` instead,
  but then UI/client should be updated accordingly.

### GET /requests/{request_id}/uploads
Response (200):
```json
[
  { "filename": "string", "key": "string", "etag": "string|null", "content_type": "string|null", "size_bytes": 12345, "created_at": "string|null", "preview_url": "string|null" }
]



