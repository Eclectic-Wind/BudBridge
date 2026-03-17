"""BudBridge handoff orchestration — coordinates phone↔PC Bluetooth hand-over."""

from __future__ import annotations

import logging
import threading
import time
from typing import Callable, Optional

import requests

from budbridge import bluetooth
from budbridge.discovery import DiscoveryService

log = logging.getLogger(__name__)

# State constants
STATE_IDLE = "idle"
STATE_RELEASING = "releasing"
STATE_WAITING = "waiting"
STATE_CONNECTING = "connecting"
STATE_CONNECTED = "connected"
STATE_DISCONNECTED = "disconnected"
STATE_ERROR = "error"


class HandoffManager:
    """Orchestrate Bluetooth handoff between phone and PC."""

    def __init__(self, config):
        self._config = config
        self._lock = threading.Lock()
        self._in_progress = False
        self._discovery: Optional[DiscoveryService] = None

        # Public callback — set by caller after construction
        self.on_state_change: Optional[Callable[[str], None]] = None

    def set_discovery(self, discovery: DiscoveryService) -> None:
        """Inject the DiscoveryService so handoff can resolve phone IP via mDNS."""
        self._discovery = discovery

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _emit(self, state: str) -> None:
        log.debug("HandoffManager state → %s", state)
        if self.on_state_change:
            try:
                self.on_state_change(state)
            except Exception as exc:
                log.warning("on_state_change callback raised: %s", exc)

    def _resolve_phone_ip(self) -> Optional[str]:
        """Return phone IP: use stored if set, otherwise discover via mDNS and cache it."""
        ip = self._config.network.phone_ip
        if ip:
            return ip
        if self._discovery:
            log.info("Phone IP unknown — scanning via mDNS…")
            found = self._discovery.find_phone(timeout=5.0)
            if found:
                log.info("Phone found at %s — caching for this session.", found)
                self._config.network.phone_ip = found
                return found
        return None

    def _phone_url(self, path: str) -> Optional[str]:
        ip = self._resolve_phone_ip()
        if not ip:
            return None
        return f"http://{ip}:{self._config.network.phone_port}{path}"

    def _phone_headers(self) -> dict:
        secret = self._config.network.shared_secret
        if secret:
            return {"X-BudBridge-Token": secret}
        return {}

    def _tell_phone_release(self) -> bool:
        """POST /release to the phone's BudBridge app. Returns True on success."""
        url = self._phone_url("/release")
        if not url:
            log.warning("Phone IP not known and mDNS discovery found nothing — proceeding anyway.")
            return False
        try:
            resp = requests.post(
                url,
                headers=self._phone_headers(),
                timeout=8,
            )
            if resp.status_code == 200:
                log.info("Phone acknowledged release.")
                return True
            log.warning("Phone /release returned HTTP %d", resp.status_code)
            return False
        except requests.exceptions.ConnectionError:
            log.warning("Cannot reach phone at %s — proceeding anyway.", url)
            # Clear cached IP so next attempt re-discovers
            self._config.network.phone_ip = ""
            return False
        except requests.exceptions.Timeout:
            log.warning("Phone /release timed out — proceeding anyway.")
            return False
        except Exception as exc:
            log.warning("Unexpected error contacting phone: %s", exc)
            return False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def claim_to_pc(self) -> None:
        """Full handoff: tell phone to release → wait → connect BT on PC.

        Runs in the calling thread (typically the hotkey thread); it will
        acquire the lock so only one handoff runs at a time.
        """
        if not self._lock.acquire(blocking=False):
            log.info("claim_to_pc: handoff already in progress, ignoring.")
            return

        self._in_progress = True
        try:
            cfg = self._config

            self._emit(STATE_RELEASING)
            phone_ok = self._tell_phone_release()
            if not phone_ok:
                from budbridge.notify import notify_phone_unreachable
                notify_phone_unreachable(cfg.ui.show_notifications)

            # Wait for phone to release BT
            self._emit(STATE_WAITING)
            delay = cfg.behavior.handoff_delay_ms / 1000.0
            log.debug("Waiting %.1f s for phone to release BT…", delay)
            time.sleep(delay)

            # Attempt BT connect
            self._emit(STATE_CONNECTING)
            success = bluetooth.connect(cfg)

            if success:
                self._emit(STATE_CONNECTED)
                from budbridge.notify import notify_connected
                notify_connected(cfg.device.bt_friendly_name, cfg.ui.show_notifications)
            else:
                self._emit(STATE_ERROR)
                from budbridge.notify import notify_bt_failed
                notify_bt_failed(cfg.device.bt_friendly_name, cfg.ui.show_notifications)

        except Exception as exc:
            log.error("claim_to_pc raised: %s", exc)
            self._emit(STATE_ERROR)
            from budbridge.notify import notify_handoff_failed
            notify_handoff_failed(str(exc), self._config.ui.show_notifications)
        finally:
            self._in_progress = False
            self._lock.release()

    def release_to_phone(self) -> None:
        """Disconnect BT on PC side only; phone will reconnect on its own.

        Runs in the calling thread.
        """
        if not self._lock.acquire(blocking=False):
            log.info("release_to_phone: handoff already in progress, ignoring.")
            return

        self._in_progress = True
        try:
            cfg = self._config
            self._emit(STATE_RELEASING)
            success = bluetooth.disconnect(cfg)

            if success:
                self._emit(STATE_DISCONNECTED)
                from budbridge.notify import notify_released
                notify_released(cfg.device.bt_friendly_name, cfg.ui.show_notifications)
            else:
                self._emit(STATE_ERROR)
                from budbridge.notify import notify_bt_failed
                notify_bt_failed(cfg.device.bt_friendly_name, cfg.ui.show_notifications)

        except Exception as exc:
            log.error("release_to_phone raised: %s", exc)
            self._emit(STATE_ERROR)
        finally:
            self._in_progress = False
            self._lock.release()

    def release_from_phone_request(self) -> Optional[dict]:
        """Called by the HTTP server when the phone sends POST /release.

        Returns a dict to be JSON-serialised, or None if a handoff is
        already in progress (server will return 409).
        """
        if not self._lock.acquire(blocking=False):
            log.info("release_from_phone_request: busy — returning None (409).")
            return None

        self._in_progress = True
        try:
            cfg = self._config
            was_connected = bluetooth.is_connected(cfg)

            self._emit(STATE_RELEASING)
            success = bluetooth.disconnect(cfg)

            if success:
                self._emit(STATE_DISCONNECTED)
                from budbridge.notify import notify_released
                notify_released(cfg.device.bt_friendly_name, cfg.ui.show_notifications)
            else:
                self._emit(STATE_ERROR)

            return {"released": success, "was_connected": was_connected}

        except Exception as exc:
            log.error("release_from_phone_request raised: %s", exc)
            self._emit(STATE_ERROR)
            return {"released": False, "was_connected": False, "error": str(exc)}
        finally:
            self._in_progress = False
            self._lock.release()

    @property
    def in_progress(self) -> bool:
        # The lock is held for the entire duration of any handoff operation,
        # so locked() is the authoritative signal that work is in flight.
        return self._lock.locked()
