from __future__ import annotations

import asyncio

import openai._base_client as openai_base_client

_PATCHED = False


def _has_httpx_state(client: object) -> bool:
    """
    Check if the given client has an HTTPX state.

    Args:
        client (object): The client object to check.

    Returns:
        bool: True if the client has an HTTPX state, False otherwise.
    """
    return getattr(client, "_state", None) is not None


def apply_openai_httpx_compat() -> None:
    """Apply compatibility patches for OpenAI HTTPX clients."""
    global _PATCHED
    if _PATCHED:
        return

    def _safe_sync_del(self) -> None:
        """Safely delete a synchronous HTTPX client."""
        if not _has_httpx_state(self):
            return

        try:
            if self.is_closed:
                return
            self.close()
        except Exception:
            pass

    def _safe_async_del(self) -> None:
        """Safely delete an asynchronous HTTPX client."""
        if not _has_httpx_state(self):
            return

        try:
            if self.is_closed:
                return
        except Exception:
            return

        try:
            asyncio.get_running_loop().create_task(self.aclose())
        except Exception:
            pass

    openai_base_client.SyncHttpxClientWrapper.__del__ = _safe_sync_del
    openai_base_client.AsyncHttpxClientWrapper.__del__ = _safe_async_del
    _PATCHED = True
