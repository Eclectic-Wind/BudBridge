"""BudBridge mDNS/Zeroconf service advertisement and peer discovery."""

from __future__ import annotations

import concurrent.futures
import logging
import socket
from typing import Optional

log = logging.getLogger(__name__)

_SERVICE_TYPE = "_budbridge._tcp.local."
_SERVICE_NAME = "BudBridge._budbridge._tcp.local."


class DiscoveryService:
    """Advertise this PC on the LAN and optionally find the phone."""

    def __init__(self, config):
        self._config = config
        self._zeroconf = None
        self._service_info = None
        self._started = False

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _get_local_ip() -> str:
        """Best-effort: return the primary LAN IP of this machine."""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Advertise _budbridge._tcp.local. on pc_port using zeroconf."""
        try:
            from zeroconf import Zeroconf, ServiceInfo

            ip = self._get_local_ip()
            port = self._config.network.pc_port

            self._service_info = ServiceInfo(
                _SERVICE_TYPE,
                _SERVICE_NAME,
                addresses=[socket.inet_aton(ip)],
                port=port,
                properties={"version": "1.0", "app": "BudBridge", "role": "pc"},
                server="budbridge-pc.local.",
            )

            self._zeroconf = Zeroconf()
            self._zeroconf.register_service(self._service_info)
            self._started = True
            log.info("mDNS advertisement started on %s:%d", ip, port)

        except ImportError:
            log.info("zeroconf not installed — mDNS discovery disabled.")
        except Exception as exc:
            log.warning("Could not start mDNS advertisement: %s", exc)

    def stop(self) -> None:
        """Unregister the mDNS service and close zeroconf."""
        if not self._started:
            return
        try:
            if self._zeroconf and self._service_info:
                self._zeroconf.unregister_service(self._service_info)
                self._zeroconf.close()
                log.info("mDNS advertisement stopped.")
        except Exception as exc:
            log.debug("Error stopping mDNS: %s", exc)
        finally:
            self._zeroconf = None
            self._service_info = None
            self._started = False

    def scan_for_phone(self, timeout: float = 5.0) -> Optional[str]:
        """TCP-scan the local /24 subnet for the phone HTTP port.

        Works even when mDNS multicast is blocked by the router or firewall.
        Returns the first IP that has the phone port open, or None.
        """
        port = self._config.network.phone_port
        local_ip = self._get_local_ip()
        subnet = ".".join(local_ip.split(".")[:3])

        def _probe(host: str) -> Optional[str]:
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(0.5)
                    if s.connect_ex((host, port)) == 0:
                        return host
            except OSError:
                pass
            return None

        hosts = [f"{subnet}.{i}" for i in range(1, 255)]
        with concurrent.futures.ThreadPoolExecutor(max_workers=64) as pool:
            for result in concurrent.futures.as_completed(
                {pool.submit(_probe, h): h for h in hosts}, timeout=timeout
            ):
                ip = result.result()
                if ip and ip != local_ip:
                    log.info("Phone found via subnet scan at %s", ip)
                    return ip

        log.debug("Subnet scan found no phone on %s.0/24 port %d", subnet, port)
        return None

    def find_peer(self, timeout: float = 5.0) -> Optional[str]:
        """Browse for any BudBridge instance on the LAN (PC or phone).

        Returns the IP address string of the first discovered peer,
        or None if no peer was found within *timeout* seconds.
        """
        return self._browse(role_filter=None, timeout=timeout)

    def find_phone(self, timeout: float = 5.0) -> Optional[str]:
        """Browse specifically for the BudBridge Android app on the LAN.

        Returns the IP address of the phone, or None if not found.
        """
        return self._browse(role_filter="phone", timeout=timeout)

    def _browse(self, role_filter: Optional[str], timeout: float) -> Optional[str]:
        """Internal: browse for a BudBridge service, optionally filtered by role."""
        try:
            import time
            from zeroconf import Zeroconf, ServiceBrowser

            found: list[Optional[str]] = [None]

            class _Listener:
                def add_service(self, zc, svc_type, name):
                    info = zc.get_service_info(svc_type, name)
                    if not info or not info.addresses:
                        return
                    role = (info.properties.get(b"role") or b"").decode("utf-8", errors="ignore")
                    if role_filter and role != role_filter:
                        return
                    addr = socket.inet_ntoa(info.addresses[0])
                    log.debug("mDNS peer found: %s (role=%s) at %s", name, role, addr)
                    found[0] = addr

                def remove_service(self, zc, svc_type, name):
                    pass

                def update_service(self, zc, svc_type, name):
                    pass

            zc = Zeroconf()
            try:
                browser = ServiceBrowser(zc, _SERVICE_TYPE, _Listener())

                deadline = time.monotonic() + timeout
                while time.monotonic() < deadline and found[0] is None:
                    time.sleep(0.1)
            finally:
                zc.close()

            return found[0]

        except ImportError:
            log.debug("zeroconf not installed — mDNS discovery unavailable.")
            return None
        except Exception as exc:
            log.warning("find_peer error: %s", exc)
            return None
