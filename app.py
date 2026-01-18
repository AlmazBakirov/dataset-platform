import streamlit as st

from core.auth import logout

st.set_page_config(page_title="Dataset Platform UI", layout="wide")

role = st.session_state.get("role")

# Pages
login = st.Page("pages/01_login.py", title="Login", icon="🔐")
dashboard = st.Page("pages/02_dashboard.py", title="Dashboard", icon="📊")

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

# Navigation structure by role
if role == "customer":
    nav_structure = {
        "Home": [dashboard],
        "Customer": customer_pages,
        "Account": [login],
    }
elif role == "labeler":
    nav_structure = {
        "Home": [dashboard],
        "Labeler": labeler_pages,
        "Account": [login],
    }
elif role in ("admin", "universal"):
    nav_structure = {
        "Home": [dashboard],
        "Customer": customer_pages,
        "Labeler": labeler_pages,
        "Admin": admin_pages,
        "Account": [login],
    }
else:
    nav_structure = {
        "Login": [login],
    }

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
