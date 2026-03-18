"""BudBridge global hotkey registration via pynput."""

from __future__ import annotations

import logging
import threading
from typing import Callable, Optional

log = logging.getLogger(__name__)


class HotkeyManager:
    """Register and manage a global hotkey using pynput.GlobalHotKeys."""

    def __init__(self, hotkey_str: str, callback: Callable[[], None]):
        self._hotkey_str = hotkey_str
        self._callback = callback
        self._listener: Optional[object] = None
        self._thread: Optional[threading.Thread] = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_hotkey(hotkey_str: str) -> str:
        """Convert "ctrl+shift+b" → "<ctrl>+<shift>+b" pynput format."""
        modifier_map = {
            "ctrl": "<ctrl>",
            "control": "<ctrl>",
            "shift": "<shift>",
            "alt": "<alt>",
            "win": "<cmd>",
            "super": "<cmd>",
            "cmd": "<cmd>",
        }
        parts = [p.strip().lower() for p in hotkey_str.split("+")]
        converted = []
        for part in parts:
            if part in modifier_map:
                converted.append(modifier_map[part])
            else:
                converted.append(part)
        return "+".join(converted)

    def _build_listener(self):
        try:
            from pynput import keyboard

            pynput_key = self._parse_hotkey(self._hotkey_str)
            log.debug("Registering hotkey: %s → %s", self._hotkey_str, pynput_key)

            hotkeys = {pynput_key: self._on_activate}
            return keyboard.GlobalHotKeys(hotkeys)
        except ImportError:
            log.warning("pynput not installed — global hotkey disabled.")
            return None
        except Exception as exc:
            log.error("Failed to build hotkey listener: %s", exc)
            return None

    def _on_activate(self) -> None:
        log.debug("Hotkey %s activated", self._hotkey_str)
        try:
            # Run callback in a separate thread so we don't block the hotkey listener
            t = threading.Thread(target=self._callback, daemon=True, name="HotkeyCallback")
            t.start()
        except Exception as exc:
            log.error("Hotkey callback error: %s", exc)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the hotkey listener in a background daemon thread."""
        self._listener = self._build_listener()
        if self._listener is None:
            log.error(
                "Hotkey '%s' could not be registered — hotkey is disabled. "
                "Check that pynput is installed and the hotkey string is valid.",
                self._hotkey_str,
            )
            return

        def _run():
            try:
                with self._listener:
                    self._listener.join()
            except Exception as exc:
                log.error("Hotkey listener error: %s", exc)

        self._thread = threading.Thread(target=_run, name="HotkeyListener", daemon=True)
        self._thread.start()
        log.info("Global hotkey registered: %s", self._hotkey_str)

    def stop(self) -> None:
        """Stop the hotkey listener."""
        if self._listener is not None:
            try:
                self._listener.stop()
            except Exception as exc:
                log.debug("Error stopping hotkey listener: %s", exc)
            self._listener = None
        log.debug("Hotkey listener stopped.")
