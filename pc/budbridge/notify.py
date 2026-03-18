"""BudBridge notifications — Windows toast messages via plyer."""

from __future__ import annotations

import logging

log = logging.getLogger(__name__)

_APP_NAME = "BudBridge"


def notify(title: str, message: str, enabled: bool = True) -> None:
    """Show a Windows toast notification.

    Falls back silently if plyer is unavailable or notifications are disabled.
    """
    if not enabled:
        return
    try:
        from plyer import notification

        notification.notify(
            title=title,
            message=message,
            app_name=_APP_NAME,
            timeout=4,
        )
    except Exception as exc:
        log.debug("Notification suppressed: %s", exc)


# ---------------------------------------------------------------------------
# Pre-defined helpers
# ---------------------------------------------------------------------------


def notify_connected(device_name: str, enabled: bool = True) -> None:
    notify(
        "BudBridge — Connected",
        f"{device_name} is now connected to this PC.",
        enabled,
    )


def notify_released(device_name: str, enabled: bool = True) -> None:
    notify(
        "BudBridge — Released",
        f"{device_name} has been released back to your phone.",
        enabled,
    )


def notify_phone_unreachable(enabled: bool = True) -> None:
    notify(
        "BudBridge — Phone Unreachable",
        "Could not reach your phone. If your headphones are still connected to it, "
        "disconnect them manually first.",
        enabled,
    )


def notify_bt_failed(device_name: str, enabled: bool = True) -> None:
    notify(
        "BudBridge — Bluetooth Error",
        f"Failed to connect {device_name}. Check the device and try again.",
        enabled,
    )


def notify_handoff_failed(reason: str, enabled: bool = True) -> None:
    notify(
        "BudBridge — Handoff Failed",
        f"Handoff error: {reason}",
        enabled,
    )
