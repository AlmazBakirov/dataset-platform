import time

import pandas as pd
import streamlit as st

from core import mock_backend
from core.api_client import ApiClient
from core.auth import require_role
from core.config import settings
from core.ui import header
from core.ui_helpers import api_call

require_role(["customer", "admin", "universal"])
header("QC Review", "Async QC: запуск → статус → авто-подгрузка результатов.")


def safe_rerun():
    try:
        st.rerun()
    except AttributeError:
        st.experimental_rerun()


def client() -> ApiClient:
    return ApiClient(settings.backend_url, token=st.session_state.get("token"))


default_request_id = str(st.session_state.get("selected_request_id", "")).strip()
request_id = st.text_input("Request ID", value=default_request_id).strip()
if request_id:
    st.session_state["selected_request_id"] = request_id

# --- Controls ---
c1, c2, c3, c4 = st.columns(4)
with c1:
    dup_thr = st.slider("Duplicate threshold", 0.0, 1.0, 0.85, 0.01)
with c2:
    ai_thr = st.slider("AI-generated threshold", 0.0, 1.0, 0.80, 0.01)
with c3:
    sort_by = st.selectbox(
        "Sort by", ["duplicate_score", "ai_generated_score", "image_id"], index=0
    )
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

st.divider()


# --- Status block (always helpful) ---
def fetch_status() -> dict:
    if not request_id:
        return {}
    if settings.use_mock:
        # мок — считаем как done
        return {"status": "done", "processed_images": 0, "total_images": 0}
    return client().qc_status(request_id)


def fetch_results() -> list[dict]:
    if settings.use_mock:
        return mock_backend.mock_qc_results(request_id)
    return client().qc_results(request_id)


status = {}
if request_id:
    status = api_call("QC status", fetch_status, spinner=None, show_payload=False) or {}

st.subheader("QC Status")
if not request_id:
    st.info("Введите Request ID или выберите Request в Customer → Requests.")
else:
    st.json(status)

st.divider()

# --- Run QC (async) ---
run_col, poll_col = st.columns([1, 2])

with run_col:
    if st.button("Run QC", type="primary", disabled=not request_id):

        def do_run_qc():
            if settings.use_mock:
                return {"status": "mocked"}
            return client().run_qc(request_id)

        resp = api_call("Run QC", do_run_qc, spinner="Starting QC...", show_payload=True)
        if resp is not None:
            # запомним qc_run_id, чтобы UI понимал, что есть активный запуск
            if isinstance(resp, dict) and "qc_run_id" in resp:
                st.session_state["last_qc_run_id"] = resp["qc_run_id"]
            st.success("QC started.")
            st.session_state["qc_autopoll"] = True
            safe_rerun()

with poll_col:
    auto = st.checkbox("Auto-poll status", value=bool(st.session_state.get("qc_autopoll", False)))
    interval = st.slider("Poll interval (sec)", 1, 10, 2)
    max_wait = st.slider("Max wait (sec)", 5, 180, 60)

    # автопуллинг: если статус queued/running -> ждём и перерисовываем
    if request_id and auto and not settings.use_mock:
        st.session_state["qc_autopoll"] = True
        started_ts = st.session_state.get("qc_poll_started_ts")
        if not started_ts:
            started_ts = time.time()
            st.session_state["qc_poll_started_ts"] = started_ts

        st.caption(
            "Polling… (страница будет авто-обновляться пока QC не станет done/failed или пока не истечёт Max wait)"
        )

        # обновим статус
        status2 = api_call("QC status", fetch_status, spinner=None, show_payload=False) or {}
        st.json(status2)

        st_status = (status2 or {}).get("status")
        if st_status in ("queued", "running"):
            if (time.time() - started_ts) >= float(max_wait):
                st.warning("Auto-poll stopped: max wait reached.")
                st.session_state["qc_autopoll"] = False
                st.session_state.pop("qc_poll_started_ts", None)
            else:
                time.sleep(float(interval))
                safe_rerun()
        else:
            # done/failed/no_runs
            st.session_state["qc_autopoll"] = False
            st.session_state.pop("qc_poll_started_ts", None)

# --- Load results (manual or auto after done) ---
st.subheader("QC Results")

load_btn = st.button("Load QC results", disabled=not request_id)
auto_load = False

if request_id and not settings.use_mock:
    st_status = (status or {}).get("status")
    if st_status == "done":
        auto_load = True

if load_btn or auto_load:
    rows = api_call(
        "Load QC results", fetch_results, spinner="Loading QC results...", show_payload=False
    )
    if rows is None:
        st.stop()

    df = pd.DataFrame(rows)
    if df.empty:
        st.info("No results yet. If QC is still running — keep polling.")
        st.stop()

    # Normalize expected columns
    if "image_id" not in df.columns:
        df["image_id"] = df.index.astype(int)
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

    st.dataframe(out, use_container_width=True)

    st.divider()
    st.subheader("Export view")

    csv_bytes = out.to_csv(index=False).encode("utf-8")
    st.download_button(
        "Download current view as CSV",
        data=csv_bytes,
        file_name=f"qc_results_{request_id}.csv",
        mime="text/csv",
    )
