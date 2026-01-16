import streamlit as st
import pandas as pd

from core.auth import require_role
from core.config import settings
from core.api_client import ApiClient
from core import mock_backend
from core.ui import header
from core.ui_helpers import api_call

require_role(["customer", "admin", "universal"])
header("QC Review", "Duplicates + AI-generated: фильтры, сортировка, экспорт flagged.")

def client() -> ApiClient:
    return ApiClient(settings.backend_url, token=st.session_state.get("token"))

default_request_id = str(st.session_state.get("selected_request_id", "")).strip()
request_id = st.text_input("Request ID", value=default_request_id).strip()
if request_id:
    st.session_state["selected_request_id"] = request_id

c1, c2, c3, c4 = st.columns(4)
with c1:
    dup_thr = st.slider("Duplicate threshold", 0.0, 1.0, 0.85, 0.01)
with c2:
    ai_thr = st.slider("AI-generated threshold", 0.0, 1.0, 0.80, 0.01)
with c3:
    sort_by = st.selectbox("Sort by", ["duplicate_score", "ai_generated_score", "image_id"], index=0)
with c4:
    sort_desc = st.checkbox("Sort desc", value=True)

f1, f2, f3, f4 = st.columns(4)
with f1:
    only_flagged = st.checkbox("Only flagged", value=True)
with f2:
    only_duplicates = st.checkbox("Only duplicates", value=False)
with f3:
    only_ai = st.checkbox("Only AI-generated", value=False)
with f4:
    top_n = st.number_input("Top N (0 = all)", min_value=0, max_value=5000, value=200, step=50)

if st.button("Run QC", type="primary", disabled=not request_id):
    def do_run_qc():
        if settings.use_mock:
            return {"status": "mocked"}
        return client().run_qc(request_id)

    resp = api_call("Run QC", do_run_qc, spinner="Starting QC...", show_payload=True)
    if resp is not None:
        st.success("QC started (or mocked).")

if st.button("Load QC results", disabled=not request_id):
    def do_load():
        if settings.use_mock:
            return mock_backend.mock_qc_results(request_id)
        return client().qc_results(request_id)

    rows = api_call("Load QC results", do_load, spinner="Loading QC results...", show_payload=True)
    if rows is None:
        st.stop()

    df = pd.DataFrame(rows)

    if df.empty:
        st.info("No results.")
        st.stop()

    # Normalize expected columns
    if "image_id" not in df.columns:
        df["image_id"] = df.index.astype(str)
    if "duplicate_score" not in df.columns:
        df["duplicate_score"] = 0.0
    if "ai_generated_score" not in df.columns:
        df["ai_generated_score"] = 0.0

    df["is_duplicate"] = df["duplicate_score"] >= dup_thr
    df["is_ai"] = df["ai_generated_score"] >= ai_thr
    df["is_flagged"] = df["is_duplicate"] | df["is_ai"]

    total = len(df)
    flagged = int(df["is_flagged"].sum())
    dup_cnt = int(df["is_duplicate"].sum())
    ai_cnt = int(df["is_ai"].sum())

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total", total)
    m2.metric("Flagged", flagged)
    m3.metric("Duplicates", dup_cnt)
    m4.metric("AI-generated", ai_cnt)

    # Filters
    out = df.copy()

    if only_flagged:
        out = out[out["is_flagged"]]

    if only_duplicates:
        out = out[out["is_duplicate"]]

    if only_ai:
        out = out[out["is_ai"]]

    # Sort
    if sort_by in out.columns:
        out = out.sort_values(by=sort_by, ascending=not sort_desc)

    # Top N
    if top_n and top_n > 0:
        out = out.head(int(top_n))

    st.divider()
    st.subheader("QC Results")

    st.dataframe(out, use_container_width=True)

    st.divider()
    st.subheader("Export")

    # Export current view to CSV
    csv_bytes = out.to_csv(index=False).encode("utf-8")
    st.download_button(
        "Download current view as CSV",
        data=csv_bytes,
        file_name=f"qc_results_{request_id}.csv",
        mime="text/csv",
    )
