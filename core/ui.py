from __future__ import annotations

from typing import Optional, Tuple

import streamlit as st
import httpx

from core.config import settings


@st.cache_data(ttl=20, show_spinner=False)
def _backend_probe(base_url: str, timeout_s: float) -> Tuple[bool, str, str]:
    """
    Returns: (ok, info, details)
    - ok: backend reachable
    - info: short status string
    - details: more detailed error
    """
    base = (base_url or "").strip().rstrip("/")
    if not base:
        return (False, "BACKEND_URL is empty", "Set BACKEND_URL in env (.env)")

    timeout = httpx.Timeout(float(timeout_s), connect=5.0)
    endpoints = ["/health", "/_health", "/api/health", "/docs"]

    last_err = ""
    for ep in endpoints:
        url = base + ep
        try:
            r = httpx.get(url, timeout=timeout, follow_redirects=True, headers={"Accept": "application/json"})
            if 200 <= r.status_code < 300:
                return (True, f"Backend OK ({ep})", f"{url} -> {r.status_code}")
            last_err = f"{url} -> {r.status_code}"
        except Exception as e:
            last_err = f"{url} -> {e!s}"

    return (False, "Backend is not reachable", last_err)


def backend_banner(*, show_dashboard_button: bool = True) -> None:
    """
    Global banner shown on every page (via header()).
    - If USE_MOCK=1: show info
    - Else: warn if BACKEND_URL misconfigured or backend offline
    """
    # Small debug line (collapsed) to help the team quickly understand env
    if settings.use_mock:
        st.info(
            f"Mock mode enabled (USE_MOCK=1). BACKEND_URL={settings.backend_url} | UPLOAD_MODE={getattr(settings, 'upload_mode', 'mvp')}"
        )
        return

    ok, info, details = _backend_probe(settings.backend_url, getattr(settings, "request_timeout_s", 20))

    if ok:
        # Keep it lightweight; show only if you want.
        # You can comment this out if you prefer silent success.
        st.success(f"{info}. {details}")
        return

    # Not ok -> banner
    st.warning(
        f"{info}. BACKEND_URL={settings.backend_url}. Details: {details}"
    )
    st.caption(
        "Если backend ещё не поднят — это нормально. "
        "Если должен быть доступен: проверьте BACKEND_URL, сеть/VPN/Firewall и REQUEST_TIMEOUT_S."
    )

    # Optional “Open Dashboard” button (only useful if user is logged in and the page exists in nav)
    if show_dashboard_button and st.session_state.get("token"):
        c1, c2 = st.columns([1, 3])
        with c1:
            if st.button("Open Dashboard", use_container_width=True):
                st.switch_page("pages/02_dashboard.py")
        with c2:
            st.caption("Dashboard показывает backend status и быстрые переходы.")


def header(title: str, subtitle: Optional[str] = None) -> None:
    """
    Standard header used across pages.
    Also renders the global backend banner.
    """
    backend_banner(show_dashboard_button=True)

    st.title(title)
    if subtitle:
        st.caption(subtitle)
