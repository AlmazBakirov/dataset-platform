from __future__ import annotations

import hashlib
import traceback
from typing import Any, Callable, Optional, TypeVar

import httpx
import streamlit as st

from core.api_client import ApiError

T = TypeVar("T")


def _stable_key(prefix: str, label: str) -> str:
    h = hashlib.md5(label.encode("utf-8")).hexdigest()[:10]
    return f"{prefix}_{h}"


def _toast(msg: str) -> None:
    # st.toast exists in newer Streamlit; keep compatibility
    try:
        if hasattr(st, "toast"):
            st.toast(msg)
    except Exception:
        pass


def _render_error_hints(status_code: int, message: str) -> None:
    # Practical, role-focused hints
    if status_code == 0:
        st.caption(
            "Проверьте BACKEND_URL, доступность backend и VPN/Firewall. Попробуйте увеличить REQUEST_TIMEOUT_S."
        )
    elif status_code == 401:
        st.caption(
            "Похоже, сессия истекла или токен неверный. Нажмите Logout и залогиньтесь снова."
        )
    elif status_code == 403:
        st.caption("Доступ запрещён для вашей роли. Проверьте роль/права в backend.")
    elif status_code == 404:
        st.caption(
            "Endpoint не найден. Вероятно, backend ещё не реализовал этот маршрут (это нормально на ранней стадии)."
        )
    elif status_code == 422:
        st.caption(
            "Ошибка валидации данных. Проверьте payload (поля, типы, обязательные значения)."
        )
    elif status_code >= 500:
        st.caption("Ошибка backend. Проверьте логи backend сервиса.")
    else:
        # Generic hint for other errors
        if "timeout" in (message or "").lower():
            st.caption("Возможен таймаут. Попробуйте увеличить REQUEST_TIMEOUT_S и проверьте сеть.")


def _render_debug(label: str, payload: Any | None, exc: BaseException) -> None:
    with st.expander("Details (debug)", expanded=False):
        st.code(traceback.format_exc())
        if payload is not None:
            st.write("Payload:")
            try:
                st.json(payload)
            except Exception:
                st.write(payload)


def api_call(
    label: str,
    fn: Callable[[], T],
    *,
    spinner: str | None = None,
    show_payload: bool = False,
    success_toast: bool = False,
    retry_button: bool = True,
    key: str | None = None,
) -> Optional[T]:
    """
    Unified wrapper for backend calls:
    - normalizes ApiError/httpx errors
    - shows consistent error blocks + hints
    - optional payload preview
    - optional Retry button
    Returns result or None if failed.
    """

    run_key = key or _stable_key("api", label)
    retry_key = _stable_key("retry", f"{run_key}:{label}")

    try:
        if spinner:
            with st.spinner(spinner):
                result = fn()
        else:
            result = fn()

        if show_payload and result is not None:
            with st.expander(f"{label} — response", expanded=False):
                try:
                    st.json(result)  # works for dict/list
                except Exception:
                    st.write(result)

        if success_toast:
            _toast(f"{label}: OK")

        return result

    except ApiError as e:
        st.error(f"{label}: Backend error ({e.status_code}) — {e.message}")
        _render_error_hints(e.status_code, e.message)
        _render_debug(label, e.payload, e)

    except httpx.TimeoutException as e:
        st.error(f"{label}: Timeout — запрос занял слишком много времени.")
        _render_error_hints(0, "timeout")
        _render_debug(label, None, e)

    except httpx.RequestError as e:
        st.error(f"{label}: Network error — {e!s}")
        _render_error_hints(0, str(e))
        _render_debug(label, None, e)

    except Exception as e:
        st.error(f"{label}: Unexpected error — {e!s}")
        _render_debug(label, None, e)

    # Retry UX
    if retry_button:
        if st.button("Retry", key=retry_key):
            st.rerun()

    return None
