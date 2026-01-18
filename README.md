# dataset-platform-ui

Streamlit frontend for dataset platform (roles: customer, labeler, admin/universal).

This repo contains UI only. Backend, DB, QC (Google Lens / embeddings), and AI-generated detection are handled by a separate service.

---

## Features (MVP)

### Roles
- **customer**: create requests, upload images, run QC, review QC results
- **labeler**: view assigned tasks, annotate images (multi-label), progress + finish task (UI-ready)
- **admin/universal**: access all customer + labeler pages (admin panel placeholder)

### UX improvements already implemented
- No manual `request_id` copy/paste: selection stored in `st.session_state["selected_request_id"]`
- No manual `task_id` copy/paste: selection stored in `st.session_state["selected_task_id"]`
- Unified API error handling (`api_call`) + retry + debug details
- Global banner when backend is offline / misconfigured (shown via `header()` on all pages)
- Dashboard page with backend status + quick navigation

---

## Quick start (Windows / PowerShell)

### 1) Clone
```powershell
git clone git@github.com:AlmazBakirov/dataset-platform-ui.git
cd dataset-platform-ui
