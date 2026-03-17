# BudBridge — Troubleshooting Guide

This document covers the most common issues encountered when setting up and using BudBridge.

---

## 1. Tasker HTTP Server Not Responding

**Symptom:** BudBridge on PC reports "Could not reach phone" or `curl http://<phone-ip>:8521/ping` times out.

### Check 1: Profile is active

1. Open Tasker on your phone
2. Go to the **Profiles** tab
3. Confirm **BB HTTP Server** has a green indicator (active)
4. If it shows grey/disabled, tap it to enable

### Check 2: Battery optimization

This is the #1 cause of Tasker dying in the background.

1. Go to **Settings → Apps → Tasker → Battery**
2. Set to **Unrestricted** (not "Optimized")
3. Also check **Settings → Battery → Background App Refresh** (OEM-specific)
4. See [`battery-optimization.md`](battery-optimization.md) for per-manufacturer steps

### Check 3: Android Wi-Fi restrictions

Some Android versions block apps from opening server ports unless Wi-Fi is active and connected.

1. Ensure your phone is connected to the **same Wi-Fi network** as your PC
2. Disable **Wi-Fi power saving** in Android Settings or your router settings

### Check 4: Port conflict

1. In Tasker's BB HTTP Server profile, confirm the port is `8521`
2. Check no other app is using port 8521 (uncommon on Android)

### Check 5: Firewall on phone

Some security apps (ESET, Bitdefender Mobile) may block inbound connections.

1. Temporarily disable your mobile security app
2. Test again; if it works, add a Tasker exception

---

## 2. Bluetooth Won't Connect After Release

**Symptom:** BudBridge says "Connected" but no audio, or Windows shows the device as connected but headphones give no sound.

### Check 1: Handoff delay too short

The phone may still be holding the BT connection when PC tries to connect.

1. Open `~/.budbridge/config.toml`
2. Increase `handoff_delay_ms`:
   ```toml
   [behavior]
   handoff_delay_ms = 4000   # try 4 seconds
   ```
3. Restart BudBridge

### Check 2: Device in wrong state

Some headphones stay in "connecting" state. Power-cycle them:

1. Release the device from the phone manually
2. Turn headphones off, then on
3. Try the handoff again

### Check 3: bt_method mismatch

The PowerShell method uses `Enable-PnpDevice` which re-enables the BT driver stack but doesn't always trigger an A2DP profile connection.

1. Try `bt_method = "btcom"` if you have btcom.exe
2. Download btcom from: https://www.bluetooth-tester.de/btcom-bluetooth-command-line-tool/
3. Place `btcom.exe` in your PATH or in the BudBridge directory

### Check 4: Run BudBridge as Administrator

`Enable-PnpDevice` requires elevated privileges on some Windows configurations.

1. Right-click `BudBridge.exe` → **Run as administrator**
2. Or create a scheduled task that runs at login with highest privileges

### Check 5: Windows Audio not switching

Even when BT connects, Windows may not switch the default audio device.

1. Go to **Settings → System → Sound → More sound settings**
2. Set your headphones as the **Default Device** and **Default Communications Device**
3. Or use `SoundSwitch` app for automatic audio device switching

---

## 3. Windows Firewall Blocking the PC Server

**Symptom:** Tasker cannot reach the PC's BudBridge server (`http://<pc-ip>:8522/release` fails).

### Add a Firewall Inbound Rule

1. Open **Windows Defender Firewall with Advanced Security**
   (Search "Windows Firewall" → Advanced Settings)
2. Click **Inbound Rules** → **New Rule…**
3. Rule Type: **Port**
4. Protocol: **TCP**, Specific local ports: `8522`
5. Action: **Allow the connection**
6. Profile: Check **Private** (uncheck Public and Domain)
7. Name: `BudBridge HTTP`
8. Click **Finish**

### Quick PowerShell method (run as Administrator)

```powershell
New-NetFirewallRule -DisplayName "BudBridge HTTP" -Direction Inbound -Protocol TCP -LocalPort 8522 -Action Allow -Profile Private
```

### Verify the rule is active

```powershell
Get-NetFirewallRule -DisplayName "BudBridge HTTP"
```

---

## 4. "Device Not Found" in PowerShell

**Symptom:** BudBridge log shows `PowerShell connect failed` or `Get-PnpDevice returns no results`.

### Check 1: Friendly name spelling

The friendly name in `config.toml` must match (partially) how Windows sees the device.

1. Open **Device Manager** → expand **Bluetooth**
2. Find your headphones and note the **exact display name**
3. Update `bt_friendly_name` in config.toml — even a partial match works:
   ```toml
   bt_friendly_name = "WH-1000"   # matches "WH-1000XM5"
   ```

### Check 2: Device class

Some headphones appear under a different PnP class.

Run in PowerShell:
```powershell
Get-PnpDevice | Where-Object { $_.FriendlyName -like "*<your device name>*" } | Select-Object FriendlyName, Class, Status
```

If the class is not "Bluetooth", the PowerShell script needs adjustment.

### Check 3: Multiple devices with same name

If you have two devices matching the name pattern, only the first is used.

1. Use the MAC address method instead: switch to `bt_method = "btcom"`
2. Or make the friendly name more specific

### Check 4: Device not paired in Windows

1. Go to **Settings → Bluetooth & devices**
2. Ensure your headphones are listed as "Paired" (not just "Connected")
3. If missing, pair them manually, then test BudBridge

---

## 5. btcom.exe Not Found

**Symptom:** `BT connect attempt failed: [WinError 2] The system cannot find the file specified`

### Solution

1. Download btcom from: https://www.bluetooth-tester.de/btcom-bluetooth-command-line-tool/
2. Extract `btcom.exe` to one of these locations:
   - The BudBridge installation directory (same folder as `BudBridge.exe`)
   - A folder on your system PATH (e.g., `C:\Windows\System32` or `C:\tools\`)
3. Verify it works: open Command Prompt and run `btcom` — you should see usage help
4. Restart BudBridge

### Alternative: Switch to PowerShell method

If btcom won't work, switch back:
```toml
[behavior]
bt_method = "powershell"
```

---

## 6. Phone IP Keeps Changing

**Symptom:** BudBridge can't reach the phone after a router restart or reconnect.

### Solution A: Assign a static DHCP lease (recommended)

1. Log into your router's admin interface (usually http://192.168.1.1)
2. Find **DHCP Reservations** or **Static Leases**
3. Find your phone's MAC address in the connected devices list
4. Assign it a fixed IP (e.g., `192.168.1.100`)
5. Save and restart the router
6. Update `phone_ip` in `~/.budbridge/config.toml`

### Solution B: Use mDNS discovery

If zeroconf is installed on both sides, BudBridge can discover the phone automatically.

1. Install `zeroconf` on the PC: `pip install zeroconf`
2. Leave `phone_ip` as is — the discovery service will try to find the phone via mDNS

### Solution C: Use the BudBridge tray → Settings

1. Right-click the BudBridge tray icon
2. Click **Settings…**
3. Update the Phone IP field
4. Click **Save**

---

## 7. Hotkey Not Working

**Symptom:** Pressing `Ctrl+Shift+B` (or your configured hotkey) does nothing.

### Check 1: Confirm pynput is installed

```bash
pip show pynput
```

If missing: `pip install pynput`

### Check 2: Hotkey conflict

Another application may be capturing the same key combination.

1. Try a different hotkey in config.toml:
   ```toml
   [ui]
   hotkey = "ctrl+alt+h"
   ```
2. Restart BudBridge

### Check 3: Run as administrator

Some games and full-screen apps require the hotkey listener to run with elevated privileges.

1. Right-click `BudBridge.exe` → **Run as administrator**

### Check 4: Check the BudBridge log

```
~/.budbridge/budbridge.log
```

Look for lines like:
```
[INFO] Global hotkey registered: ctrl+shift+b
```
or error lines indicating failure.

### Check 5: Hotkey format

Valid format examples:
- `ctrl+shift+b`
- `ctrl+alt+f12`
- `win+shift+h`

Do NOT include spaces: `ctrl + shift + b` will fail. Use lowercase.

---

## General Log Inspection

BudBridge writes a log to:
```
C:\Users\<you>\.budbridge\budbridge.log
```

To watch it in real time (PowerShell):
```powershell
Get-Content "$env:USERPROFILE\.budbridge\budbridge.log" -Wait -Tail 50
```

---

## Getting Help

If your issue isn't covered here, open an issue on GitHub:
https://github.com/yourusername/budbridge/issues

Please include:
1. Your `config.toml` (redact the shared_secret)
2. The last 50 lines of `budbridge.log`
3. Windows version and headphone model
4. Whether you're using PowerShell, btcom, or bleak method
