"""Windows startup registry helpers for BudBridge."""

from __future__ import annotations

import logging
import sys
import winreg

log = logging.getLogger(__name__)

_REG_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_APP_NAME = "BudBridge"


def _exe_path() -> str:
    return sys.executable


def is_enabled() -> bool:
    """Return True if BudBridge is registered to run at startup."""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _REG_KEY) as key:
            winreg.QueryValueEx(key, _APP_NAME)
            return True
    except FileNotFoundError:
        return False
    except OSError:
        return False


def enable() -> None:
    """Add BudBridge to the Windows startup registry key."""
    path = _exe_path()
    with winreg.OpenKey(
        winreg.HKEY_CURRENT_USER, _REG_KEY, access=winreg.KEY_SET_VALUE
    ) as key:
        winreg.SetValueEx(key, _APP_NAME, 0, winreg.REG_SZ, path)
    log.info("Startup enabled: %s", path)


def disable() -> None:
    """Remove BudBridge from the Windows startup registry key."""
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, _REG_KEY, access=winreg.KEY_SET_VALUE
        ) as key:
            winreg.DeleteValue(key, _APP_NAME)
        log.info("Startup disabled.")
    except FileNotFoundError:
        pass
