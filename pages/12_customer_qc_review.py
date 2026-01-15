import streamlit as st
import pandas as pd
from core.auth import require_role
from core.config import settings
from core.api_client import ApiClient, ApiError
from core import mock_backend
from core.ui import header

require_role(["customer"])
header("QC Review", "Проверка на плагиат/дубликаты + AI-generated. Отображаем результаты, фильтруем по порогам.")

def client() -> ApiClient:
    return ApiClient(settings.backend_url, token=st.session_state.get("token"))

default_request_id = str(st.session_state.get("selected_request_id", "")).strip()

request_id = st.text_input("Request ID", value=default_request_id).strip()

if request_id:
    st.session_state["selected_request_id"] = request_id


col1, col2 = st.columns(2)
with col1:
    dup_thr = st.slider("Duplicate threshold", 0.0, 1.0, 0.85, 0.01)
with col2:
    ai_thr = st.slider("AI-generated threshold", 0.0, 1.0, 0.80, 0.01)

if st.button("Run QC", type="primary", disabled=not request_id):
    try:
        if not settings.use_mock:
            client().run_qc(request_id)
        st.success("QC started (or mocked).")
    except ApiError as e:
        st.error(f"Backend error ({e.status_code}): {e}")

if st.button("Load QC results", disabled=not request_id):
    try:
        if settings.use_mock:
            rows = mock_backend.mock_qc_results(request_id)
        else:
            rows = client().qc_results(request_id)

        df = pd.DataFrame(rows)
        if df.empty:
            st.write("No results.")
        else:
            df["is_duplicate"] = df["duplicate_score"] >= dup_thr
            df["is_ai"] = df["ai_generated_score"] >= ai_thr

            only_flagged = st.checkbox("Show only flagged", value=True)
            if only_flagged:
                df = df[df["is_duplicate"] | df["is_ai"]]

            st.dataframe(df, use_container_width=True)

    except ApiError as e:
        st.error(f"Backend error ({e.status_code}): {e}")
