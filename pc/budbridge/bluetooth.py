"""BudBridge Bluetooth backend — PowerShell, btcom.exe, or bleak."""

from __future__ import annotations

import json
import logging
import re
import subprocess
import time
from typing import Optional

log = logging.getLogger(__name__)


def _ps_escape_name(name: str) -> str:
    """Sanitize a device name for safe interpolation into a PowerShell -like pattern.

    Removes characters that could break the enclosing script structure, then
    escapes PowerShell wildcard metacharacters so the name matches literally.
    """
    # Strip characters that could escape the enclosing double-quoted string or script block
    safe = re.sub(r'["`${}()|;&]', "", name)
    # Escape -like wildcards to prevent unintended glob expansion
    safe = safe.replace("[", "`[").replace("]", "`]").replace("*", "`*").replace("?", "`?")
    return safe


# ---------------------------------------------------------------------------
# PowerShell backend
# ---------------------------------------------------------------------------


def _run_ps(script: str, timeout: int = 30) -> subprocess.CompletedProcess:
    """Run a PowerShell script and return the CompletedProcess."""
    return subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True,
        text=True,
        timeout=timeout,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )


_WINRT_HELPER = r"""
Add-Type -AssemblyName System.Runtime.WindowsRuntime | Out-Null

$asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() |
    Where-Object {
        $_.Name -eq 'AsTask' -and
        $_.GetParameters().Count -eq 1 -and
        $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1'
    })[0]

function Await($WinRtTask, $ResultType) {
    $spec = $asTaskGeneric.MakeGenericMethod($ResultType)
    $task = $spec.Invoke($null, @($WinRtTask))
    $task.Wait(-1) | Out-Null
    $task.Result
}

[void][Windows.Devices.Bluetooth.BluetoothDevice,Windows.Devices.Bluetooth,ContentType=WindowsRuntime]
[void][Windows.Devices.Enumeration.DevicePairingResult,Windows.Devices.Enumeration,ContentType=WindowsRuntime]
"""


def _mac_to_int(mac: str) -> int:
    return int(mac.replace(":", "").replace("-", ""), 16)


def _powershell_connect(friendly_name: str, mac: str = "") -> None:
    """Connect a Bluetooth device using the WinRT Bluetooth API (no admin required)."""
    if mac:
        mac_int = _mac_to_int(mac)
        script = _WINRT_HELPER + f"""
$device = Await ([Windows.Devices.Bluetooth.BluetoothDevice]::FromBluetoothAddressAsync({mac_int})) `
    ([Windows.Devices.Bluetooth.BluetoothDevice])
if ($null -eq $device) {{ Write-Error "Device not found by MAC"; exit 1 }}
$access = Await ($device.RequestAccessAsync()) ([Windows.Devices.Bluetooth.BluetoothAccessStatus])
if ($access -ne [Windows.Devices.Bluetooth.BluetoothAccessStatus]::Allowed) {{
    Write-Error "Access denied: $access"; exit 1
}}
Write-Output "ok"
"""
    else:
        safe_name = _ps_escape_name(friendly_name)
        script = _WINRT_HELPER + f"""
$selector = [Windows.Devices.Bluetooth.BluetoothDevice]::GetDeviceSelectorFromPairingState($true)
$devices  = Await ([Windows.Devices.Enumeration.DeviceInformation]::FindAllAsync($selector)) `
    ([Windows.Devices.Enumeration.DeviceInformationCollection])
$info = $devices | Where-Object {{ $_.Name -like "*{safe_name}*" }} | Select-Object -First 1
if ($null -eq $info) {{ Write-Error "Device not found"; exit 1 }}
$device = Await ([Windows.Devices.Bluetooth.BluetoothDevice]::FromIdAsync($info.Id)) `
    ([Windows.Devices.Bluetooth.BluetoothDevice])
$access = Await ($device.RequestAccessAsync()) ([Windows.Devices.Bluetooth.BluetoothAccessStatus])
if ($access -ne [Windows.Devices.Bluetooth.BluetoothAccessStatus]::Allowed) {{
    Write-Error "Access denied: $access"; exit 1
}}
Write-Output "ok"
"""
    result = _run_ps(script)
    if result.returncode != 0 or "ok" not in result.stdout.lower():
        raise RuntimeError(
            f"PowerShell connect failed (rc={result.returncode}): {result.stderr.strip()}"
        )


def _powershell_disconnect(friendly_name: str, mac: str = "") -> None:
    """Disconnect a Bluetooth device by disposing the WinRT device object."""
    if mac:
        mac_int = _mac_to_int(mac)
        script = _WINRT_HELPER + f"""
$device = Await ([Windows.Devices.Bluetooth.BluetoothDevice]::FromBluetoothAddressAsync({mac_int})) `
    ([Windows.Devices.Bluetooth.BluetoothDevice])
if ($null -eq $device) {{ Write-Error "Device not found by MAC"; exit 1 }}
$device.Dispose()
Write-Output "ok"
"""
    else:
        safe_name = _ps_escape_name(friendly_name)
        script = _WINRT_HELPER + f"""
$selector = [Windows.Devices.Bluetooth.BluetoothDevice]::GetDeviceSelectorFromPairingState($true)
$devices  = Await ([Windows.Devices.Enumeration.DeviceInformation]::FindAllAsync($selector)) `
    ([Windows.Devices.Enumeration.DeviceInformationCollection])
$info = $devices | Where-Object {{ $_.Name -like "*{safe_name}*" }} | Select-Object -First 1
if ($null -eq $info) {{ Write-Error "Device not found"; exit 1 }}
$device = Await ([Windows.Devices.Bluetooth.BluetoothDevice]::FromIdAsync($info.Id)) `
    ([Windows.Devices.Bluetooth.BluetoothDevice])
$device.Dispose()
Write-Output "ok"
"""
    result = _run_ps(script)
    if result.returncode != 0 or "ok" not in result.stdout.lower():
        raise RuntimeError(
            f"PowerShell disconnect failed (rc={result.returncode}): {result.stderr.strip()}"
        )


def _powershell_is_connected(friendly_name: str, mac: str = "") -> bool:
    """Return True if the device is paired and currently connected."""
    if mac:
        mac_int = _mac_to_int(mac)
        script = _WINRT_HELPER + f"""
$device = Await ([Windows.Devices.Bluetooth.BluetoothDevice]::FromBluetoothAddressAsync({mac_int})) `
    ([Windows.Devices.Bluetooth.BluetoothDevice])
if ($null -ne $device -and $device.ConnectionStatus -eq [Windows.Devices.Bluetooth.BluetoothConnectionStatus]::Connected) {{
    Write-Output "true"
}} else {{
    Write-Output "false"
}}
"""
    else:
        safe_name = _ps_escape_name(friendly_name)
        script = _WINRT_HELPER + f"""
$selector = [Windows.Devices.Bluetooth.BluetoothDevice]::GetDeviceSelectorFromPairingState($true)
$devices  = Await ([Windows.Devices.Enumeration.DeviceInformation]::FindAllAsync($selector)) `
    ([Windows.Devices.Enumeration.DeviceInformationCollection])
$info = $devices | Where-Object {{ $_.Name -like "*{safe_name}*" }} | Select-Object -First 1
if ($null -eq $info) {{ Write-Output "false"; exit 0 }}
$device = Await ([Windows.Devices.Bluetooth.BluetoothDevice]::FromIdAsync($info.Id)) `
    ([Windows.Devices.Bluetooth.BluetoothDevice])
if ($null -ne $device -and $device.ConnectionStatus -eq [Windows.Devices.Bluetooth.BluetoothConnectionStatus]::Connected) {{
    Write-Output "true"
}} else {{
    Write-Output "false"
}}
"""
    result = _run_ps(script)
    return result.stdout.strip().lower() == "true"


# ---------------------------------------------------------------------------
# btcom.exe backend
# ---------------------------------------------------------------------------

_BTCOM_PATH = "btcom"  # must be on PATH or full path set here


def _btcom_connect(mac: str) -> None:
    """Connect A2DP and HFP profiles via btcom.exe."""
    for profile in ["-s110b", "-s111e"]:
        result = subprocess.run(
            [_BTCOM_PATH, "-b", mac, "-r", profile],
            capture_output=True,
            text=True,
            timeout=20,
        )
        if result.returncode != 0:
            log.warning("btcom connect %s failed for profile %s: %s", mac, profile, result.stderr)


def _btcom_disconnect(mac: str) -> None:
    """Disconnect A2DP and HFP profiles via btcom.exe."""
    for profile in ["-s110b", "-s111e"]:
        result = subprocess.run(
            [_BTCOM_PATH, "-b", mac, "-c", profile],
            capture_output=True,
            text=True,
            timeout=20,
        )
        if result.returncode != 0:
            log.warning("btcom disconnect %s failed for profile %s: %s", mac, profile, result.stderr)


def _btcom_is_connected(mac: str) -> bool:
    """Check A2DP connection status via btcom.exe."""
    result = subprocess.run(
        [_BTCOM_PATH, "-b", mac, "-q"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    return result.returncode == 0 and "connected" in result.stdout.lower()


# ---------------------------------------------------------------------------
# bleak (BLE) backend
# ---------------------------------------------------------------------------


def _bleak_connect(mac: str) -> None:
    try:
        import asyncio
        from bleak import BleakClient

        async def _do_connect():
            async with BleakClient(mac, timeout=15.0) as client:
                if not client.is_connected:
                    raise RuntimeError(f"bleak: failed to connect to {mac}")

        asyncio.run(_do_connect())
    except ImportError:
        raise RuntimeError("bleak is not installed. Run: pip install bleak")


def _bleak_disconnect(mac: str) -> None:
    try:
        import asyncio
        from bleak import BleakClient

        async def _do_disconnect():
            async with BleakClient(mac, timeout=15.0) as client:
                await client.disconnect()

        asyncio.run(_do_disconnect())
    except ImportError:
        raise RuntimeError("bleak is not installed. Run: pip install bleak")


def _bleak_is_connected(mac: str) -> bool:
    try:
        import asyncio
        from bleak import BleakClient

        result_holder = [False]

        async def _check():
            try:
                async with BleakClient(mac, timeout=5.0) as client:
                    result_holder[0] = client.is_connected
            except Exception:
                result_holder[0] = False

        asyncio.run(_check())
        return result_holder[0]
    except ImportError:
        return False


# ---------------------------------------------------------------------------
# Unified public interface
# ---------------------------------------------------------------------------


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
                _powershell_connect(name, mac)
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
            _powershell_disconnect(name, mac)
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
            return _powershell_is_connected(name, mac)
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

    Uses PowerShell to query PnP Bluetooth devices.
    """
    script = """
Get-PnpDevice -Class Bluetooth | Select-Object FriendlyName, Status, InstanceId | ConvertTo-Json
"""
    try:
        result = _run_ps(script)
        if result.returncode != 0 or not result.stdout.strip():
            return []

        raw = json.loads(result.stdout.strip())
        # PowerShell returns a single object (not list) when only one device
        if isinstance(raw, dict):
            raw = [raw]

        devices = []
        for item in raw:
            name = item.get("FriendlyName") or ""
            status = item.get("Status") or ""
            instance_id = item.get("InstanceId") or ""

            # Extract MAC from InstanceId, e.g. BTHENUM\...\AA_BB_CC_DD_EE_FF
            mac = ""
            parts = instance_id.upper().split("\\")
            for part in parts:
                # Look for a segment that looks like a MAC (12 hex chars with underscores)
                candidate = part.replace("_", ":")
                segments = candidate.split(":")
                if len(segments) == 6 and all(len(s) == 2 for s in segments):
                    try:
                        int(candidate.replace(":", ""), 16)
                        mac = candidate
                        break
                    except ValueError:
                        pass

            devices.append(
                {
                    "name": name,
                    "mac": mac,
                    "connected": status.upper() == "OK",
                    "instance_id": instance_id,
                }
            )

        return devices

    except Exception as exc:
        log.warning("list_paired_devices failed: %s", exc)
        return []
