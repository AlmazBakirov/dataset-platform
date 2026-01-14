import streamlit as st
from core.auth import logout
from core.ui import header

st.set_page_config(page_title="Dataset Platform UI", layout="wide")

role = st.session_state.get("role")

# Страницы (Streamlit современный multipage: st.Page / st.navigation) :contentReference[oaicite:3]{index=3}
login = st.Page("pages/01_login.py", title="Login", icon="🔐")

customer_pages = [
    st.Page("pages/10_customer_requests.py", title="Requests", icon="📄"),
    st.Page("pages/11_customer_uploads.py", title="Uploads", icon="⬆️"),
    st.Page("pages/12_customer_qc_review.py", title="QC Review", icon="✅"),
]

labeler_pages = [
    st.Page("pages/20_labeler_tasks.py", title="My Tasks", icon="🧾"),
    st.Page("pages/21_labeler_annotate.py", title="Annotate", icon="🏷️"),
]

admin_pages = [
    st.Page("pages/30_admin_panel.py", title="Admin Panel", icon="⚙️"),
]

pages = [login]
nav_structure = {"Login": [login]}

if role == "customer":
    nav_structure = {"Customer": customer_pages, "Account": [login]}
elif role == "labeler":
    nav_structure = {"Labeler": labeler_pages, "Account": [login]}
elif role in ("admin", "universal"):
    nav_structure = {
        "Customer": customer_pages,
        "Labeler": labeler_pages,
        "Admin": admin_pages,
        "Account": [login],
    }
else:
    nav_structure = {"Login": [login]}


nav = st.navigation(nav_structure)
nav.run()

with st.sidebar:
    st.divider()
    if st.session_state.get("token"):
        st.write(f"Role: **{st.session_state.get('role')}**")
        if st.button("Logout"):
            logout()
            st.rerun()
    st.caption("Frontend: Streamlit UI; логика и безопасность — в backend.")
