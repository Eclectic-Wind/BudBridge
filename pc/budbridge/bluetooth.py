"""BudBridge Bluetooth backend — Win32 ctypes (primary), btcom.exe, or bleak."""

from __future__ import annotations

import ctypes
import json
import logging
import subprocess
import time
import uuid as _uuid_mod

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Win32 ctypes backend  (no subprocess, no window, instant)
# ---------------------------------------------------------------------------

class _GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", ctypes.c_ulong),
        ("Data2", ctypes.c_ushort),
        ("Data3", ctypes.c_ushort),
        ("Data4", ctypes.c_ubyte * 8),
    ]


def _make_guid(s: str) -> _GUID:
    u = _uuid_mod.UUID(s)
    return _GUID(u.time_low, u.time_mid, u.time_hi_version,
                 (ctypes.c_ubyte * 8)(*u.bytes[8:]))


class _SYSTEMTIME(ctypes.Structure):
    _fields_ = [
        ("wYear",         ctypes.c_uint16),
        ("wMonth",        ctypes.c_uint16),
        ("wDayOfWeek",    ctypes.c_uint16),
        ("wDay",          ctypes.c_uint16),
        ("wHour",         ctypes.c_uint16),
        ("wMinute",       ctypes.c_uint16),
        ("wSecond",       ctypes.c_uint16),
        ("wMilliseconds", ctypes.c_uint16),
    ]


class _BT_DEVICE_INFO(ctypes.Structure):
    # Layout matches Win32 BLUETOOTH_DEVICE_INFO (560 bytes on both 32/64-bit Windows).
    # Natural alignment: 4-byte padding after dwSize aligns Address to offset 8.
    _fields_ = [
        ("dwSize",          ctypes.c_uint32),
        ("Address",         ctypes.c_uint64),
        ("ulClassofDevice", ctypes.c_uint32),
        ("fConnected",      ctypes.c_int32),
        ("fRemembered",     ctypes.c_int32),
        ("fAuthenticated",  ctypes.c_int32),
        ("stLastSeen",      _SYSTEMTIME),
        ("stLastUsed",      _SYSTEMTIME),
        ("szName",          ctypes.c_wchar * 248),
    ]


_A2DP_SINK = "{0000110B-0000-1000-8000-00805F9B34FB}"
_HFP       = "{0000111E-0000-1000-8000-00805F9B34FB}"

_dll_cache = None


class _BT_FIND_RADIO_PARAMS(ctypes.Structure):
    _fields_ = [("dwSize", ctypes.c_uint32)]


def _dll() -> ctypes.WinDLL:
    global _dll_cache
    if _dll_cache is None:
        dll = ctypes.WinDLL("BluetoothAPIs.dll")
        dll.BluetoothSetServiceState.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(_BT_DEVICE_INFO),
            ctypes.POINTER(_GUID),
            ctypes.c_uint32,
        ]
        dll.BluetoothSetServiceState.restype = ctypes.c_uint32
        dll.BluetoothGetDeviceInfo.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(_BT_DEVICE_INFO),
        ]
        dll.BluetoothGetDeviceInfo.restype = ctypes.c_uint32
        dll.BluetoothFindFirstRadio.argtypes = [
            ctypes.POINTER(_BT_FIND_RADIO_PARAMS),
            ctypes.POINTER(ctypes.c_void_p),
        ]
        dll.BluetoothFindFirstRadio.restype = ctypes.c_void_p
        dll.BluetoothFindRadioClose.argtypes = [ctypes.c_void_p]
        dll.BluetoothFindRadioClose.restype = ctypes.c_bool
        _dll_cache = dll
    return _dll_cache


def _get_radio() -> ctypes.c_void_p:
    """Return the first available Bluetooth radio handle, or None."""
    params = _BT_FIND_RADIO_PARAMS()
    params.dwSize = ctypes.sizeof(_BT_FIND_RADIO_PARAMS)
    radio = ctypes.c_void_p()
    find_handle = _dll().BluetoothFindFirstRadio(ctypes.byref(params), ctypes.byref(radio))
    if find_handle:
        _dll().BluetoothFindRadioClose(find_handle)
        return radio
    return None


def _new_dev(mac_int: int) -> _BT_DEVICE_INFO:
    dev = _BT_DEVICE_INFO()
    dev.dwSize = ctypes.sizeof(_BT_DEVICE_INFO)
    dev.Address = mac_int
    return dev


def _populate_dev(dev: _BT_DEVICE_INFO, radio) -> None:
    """Call BluetoothGetDeviceInfo to fill fRemembered, szName, etc. before SetServiceState."""
    rc = _dll().BluetoothGetDeviceInfo(radio, ctypes.byref(dev))
    if rc != 0:
        log.warning("BluetoothGetDeviceInfo returned %d — struct may be incomplete", rc)


def _win32_connect(mac_int: int) -> None:
    radio = _get_radio()
    dev = _new_dev(mac_int)
    _populate_dev(dev, radio)

    a2dp = _make_guid(_A2DP_SINK)
    hfp  = _make_guid(_HFP)
    r1 = _dll().BluetoothSetServiceState(radio, ctypes.byref(dev), ctypes.byref(a2dp), 1)
    r2 = _dll().BluetoothSetServiceState(radio, ctypes.byref(dev), ctypes.byref(hfp),  1)
    log.info("BluetoothSetServiceState connect: A2DP=%d HFP=%d", r1, r2)
    if r1 != 0 and r2 != 0:
        raise RuntimeError(f"BluetoothSetServiceState connect failed: A2DP={r1} HFP={r2}")

    # API is asynchronous — poll up to 5 s to confirm
    for _ in range(10):
        time.sleep(0.5)
        if _win32_is_connected(mac_int):
            log.info("Bluetooth connection confirmed.")
            return
    log.warning("SetServiceState returned success but device not yet showing connected.")


def _win32_disconnect(mac_int: int) -> None:
    radio = _get_radio()
    dev = _new_dev(mac_int)
    _populate_dev(dev, radio)

    a2dp = _make_guid(_A2DP_SINK)
    hfp  = _make_guid(_HFP)
    r1 = _dll().BluetoothSetServiceState(radio, ctypes.byref(dev), ctypes.byref(a2dp), 0)
    r2 = _dll().BluetoothSetServiceState(radio, ctypes.byref(dev), ctypes.byref(hfp),  0)
    log.info("BluetoothSetServiceState disconnect: A2DP=%d HFP=%d", r1, r2)
    if r1 != 0 and r2 != 0:
        raise RuntimeError(f"BluetoothSetServiceState disconnect failed: A2DP={r1} HFP={r2}")


def _win32_is_connected(mac_int: int) -> bool:
    radio = _get_radio()
    dev = _new_dev(mac_int)
    rc = _dll().BluetoothGetDeviceInfo(radio, ctypes.byref(dev))
    return rc == 0 and bool(dev.fConnected)


# ---------------------------------------------------------------------------
# PowerShell runner (list_paired_devices only — one-time setup wizard use)
# ---------------------------------------------------------------------------


def _run_ps(script: str, timeout: int = 30) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True,
        text=True,
        timeout=timeout,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )


# ---------------------------------------------------------------------------
# btcom.exe backend
# ---------------------------------------------------------------------------

_BTCOM_PATH = "btcom"


def _btcom_connect(mac: str) -> None:
    for profile in ["-s110b", "-s111e"]:
        result = subprocess.run(
            [_BTCOM_PATH, "-b", mac, "-r", profile],
            capture_output=True, text=True, timeout=20,
        )
        if result.returncode != 0:
            log.warning("btcom connect %s failed for profile %s: %s", mac, profile, result.stderr)


def _btcom_disconnect(mac: str) -> None:
    for profile in ["-s110b", "-s111e"]:
        result = subprocess.run(
            [_BTCOM_PATH, "-b", mac, "-c", profile],
            capture_output=True, text=True, timeout=20,
        )
        if result.returncode != 0:
            log.warning("btcom disconnect %s failed for profile %s: %s", mac, profile, result.stderr)


def _btcom_is_connected(mac: str) -> bool:
    result = subprocess.run(
        [_BTCOM_PATH, "-b", mac, "-q"],
        capture_output=True, text=True, timeout=10,
    )
    return result.returncode == 0 and "connected" in result.stdout.lower()


# ---------------------------------------------------------------------------
# bleak (BLE) backend
# ---------------------------------------------------------------------------


def _bleak_connect(mac: str) -> None:
    try:
        import asyncio
        from bleak import BleakClient

        async def _do():
            async with BleakClient(mac, timeout=15.0) as client:
                if not client.is_connected:
                    raise RuntimeError(f"bleak: failed to connect to {mac}")

        asyncio.run(_do())
    except ImportError:
        raise RuntimeError("bleak is not installed. Run: pip install bleak")


def _bleak_disconnect(mac: str) -> None:
    try:
        import asyncio
        from bleak import BleakClient

        async def _do():
            async with BleakClient(mac, timeout=15.0) as client:
                await client.disconnect()

        asyncio.run(_do())
    except ImportError:
        raise RuntimeError("bleak is not installed. Run: pip install bleak")


def _bleak_is_connected(mac: str) -> bool:
    try:
        import asyncio
        from bleak import BleakClient

        holder = [False]

        async def _check():
            try:
                async with BleakClient(mac, timeout=5.0) as client:
                    holder[0] = client.is_connected
            except Exception:
                holder[0] = False

        asyncio.run(_check())
        return holder[0]
    except ImportError:
        return False


# ---------------------------------------------------------------------------
# Unified public interface
# ---------------------------------------------------------------------------


def _mac_to_int(mac: str) -> int:
    return int(mac.replace(":", "").replace("-", ""), 16)


def _resolve_mac(friendly_name: str, mac: str) -> int:
    """Return the device MAC as an integer, resolving by name if mac is empty."""
    if mac:
        return _mac_to_int(mac)
    for d in list_paired_devices():
        if friendly_name.lower() in (d["name"] or "").lower() and d["mac"]:
            return _mac_to_int(d["mac"])
    raise RuntimeError(f"Could not find MAC address for device '{friendly_name}'")


def connect(config) -> bool:
    """Connect the configured Bluetooth device. Returns True on success."""
    method = config.behavior.bt_method.lower()
    mac = config.device.bt_mac
    name = config.device.bt_friendly_name
    retry_count = config.behavior.retry_count
    retry_delay = config.behavior.retry_delay_ms / 1000.0

    for attempt in range(retry_count + 1):
        try:
            if method == "powershell":
                _win32_connect(_resolve_mac(name, mac))
            elif method == "btcom":
                _btcom_connect(mac)
            elif method == "bleak":
                _bleak_connect(mac)
            else:
                log.error("Unknown bt_method: %s", method)
                return False

            log.info("Bluetooth connected via %s (attempt %d)", method, attempt + 1)
            return True

        except Exception as exc:
            log.warning("BT connect attempt %d/%d failed: %s", attempt + 1, retry_count + 1, exc)
            if attempt < retry_count:
                time.sleep(retry_delay)

    log.error("All BT connect attempts failed.")
    return False


def disconnect(config) -> bool:
    """Disconnect the configured Bluetooth device. Returns True on success."""
    method = config.behavior.bt_method.lower()
    mac = config.device.bt_mac
    name = config.device.bt_friendly_name

    try:
        if method == "powershell":
            _win32_disconnect(_resolve_mac(name, mac))
        elif method == "btcom":
            _btcom_disconnect(mac)
        elif method == "bleak":
            _bleak_disconnect(mac)
        else:
            log.error("Unknown bt_method: %s", method)
            return False

        log.info("Bluetooth disconnected via %s", method)
        return True

    except Exception as exc:
        log.error("BT disconnect failed: %s", exc)
        return False


def is_connected(config) -> bool:
    """Return True if the configured Bluetooth device appears connected."""
    method = config.behavior.bt_method.lower()
    mac = config.device.bt_mac
    name = config.device.bt_friendly_name

    try:
        if method == "powershell":
            return _win32_is_connected(_resolve_mac(name, mac))
        elif method == "btcom":
            return _btcom_is_connected(mac)
        elif method == "bleak":
            return _bleak_is_connected(mac)
        else:
            return False
    except Exception as exc:
        log.warning("is_connected check failed: %s", exc)
        return False


def list_paired_devices() -> list:
    """Return a list of dicts with keys: name, mac, connected.

    Uses PowerShell to query PnP Bluetooth devices (setup wizard only).
    """
    script = """
Get-PnpDevice -Class Bluetooth | Select-Object FriendlyName, Status, InstanceId | ConvertTo-Json
"""
    try:
        result = _run_ps(script)
        if result.returncode != 0 or not result.stdout.strip():
            return []

        raw = json.loads(result.stdout.strip())
        if isinstance(raw, dict):
            raw = [raw]

        devices = []
        for item in raw:
            name = item.get("FriendlyName") or ""
            status = item.get("Status") or ""
            instance_id = item.get("InstanceId") or ""

            mac = ""
            parts = instance_id.upper().split("\\")
            for part in parts:
                candidate = part.replace("_", ":")
                segments = candidate.split(":")
                if len(segments) == 6 and all(len(s) == 2 for s in segments):
                    try:
                        int(candidate.replace(":", ""), 16)
                        mac = candidate
                        break
                    except ValueError:
                        pass

            devices.append({
                "name": name,
                "mac": mac,
                "connected": status.upper() == "OK",
                "instance_id": instance_id,
            })

        return devices

    except Exception as exc:
        log.warning("list_paired_devices failed: %s", exc)
        return []
