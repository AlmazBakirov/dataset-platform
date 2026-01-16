import streamlit as st
from core.auth import logout

st.set_page_config(page_title="Dataset Platform UI", layout="wide")

role = st.session_state.get("role")

# Pages (Streamlit multipage via st.Page / st.navigation)
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

# Navigation structure by role
if role == "customer":
    nav_structure = {"Customer": customer_pages, "Account": [login]}
elif role == "labeler":
    nav_structure = {"Labeler": labeler_pages, "Account": [login]}
elif role in ("admin", "universal"):
    nav_structure = {
        "Admin": admin_pages,
        "Customer": customer_pages,
        "Labeler": labeler_pages,
        "Account": [login],
    }
else:
    nav_structure = {"Account": [login]}

# Default page after login
default_page = login
if role == "customer":
    default_page = customer_pages[0]   # Requests
elif role == "labeler":
    default_page = labeler_pages[0]    # My Tasks
elif role in ("admin", "universal"):
    default_page = admin_pages[0]      # Admin Panel

# Try to use Streamlit's `default` if supported; otherwise fallback
try:
    nav = st.navigation(nav_structure, default=default_page)
except TypeError:
    # Older Streamlit: no `default` kwarg. Fallback: ensure first group is the desired landing group.
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
