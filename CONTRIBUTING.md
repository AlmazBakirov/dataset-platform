# Contributing

Thanks for contributing to `dataset-platform-ui`.

## Branching
- Create a branch from `main`:
  - `feature/<short-name>` (e.g., `feature/dashboard-actions`)
  - `fix/<short-name>` (e.g., `fix/login-redirect`)
  - `chore/<short-name>` (e.g., `chore/ci-lint`)

## Local setup (Windows / PowerShell)
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -r requirements-dev.txt
