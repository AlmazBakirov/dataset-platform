# dataset-platform-ui

Streamlit frontend for dataset platform (roles: customer, labeler, admin/universal).

## Run (Windows / PowerShell)

```powershell
cd C:\ML\dataset-platform-ui
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

$env:USE_MOCK="1"
$env:BACKEND_URL="http://localhost:8000"
python -m streamlit run app.py

## Config

Copy `.env.example` to `.env` (optional) and set:
- `USE_MOCK=1` to run UI without backend
- `BACKEND_URL=http://localhost:8000` for real backend
