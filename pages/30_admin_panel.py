import streamlit as st
from core.auth import require_role
from core.ui import header

require_role(["admin"])
header("Admin Panel", "Заглушка: позже сюда добавятся Users/Requests/Thresholds/Monitoring.")
st.write("TBD")
