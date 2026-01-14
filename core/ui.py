import streamlit as st

def header(title: str, subtitle: str | None = None):
    st.title(title)
    if subtitle:
        st.caption(subtitle)

def badge(label: str):
    st.markdown(f"`{label}`")

def show_kv(data: dict):
    for k, v in data.items():
        st.write(f"**{k}:** {v}")
