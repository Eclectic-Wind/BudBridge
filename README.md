# BudBridge

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)
[![Platform: Windows](https://img.shields.io/badge/platform-Windows-blue.svg)](https://www.microsoft.com/windows)
[![Android: Native](https://img.shields.io/badge/android-Native%20App-green.svg)](https://developer.android.com/)

**One-click Bluetooth handoff for your headphones between Android and Windows PC.**

Open-source, two-part system that lets any user seamlessly transfer their Bluetooth headphones or earbuds between an Android phone and a Windows PC with a single click from either device.

---

## The Problem

You're working at your PC with your wireless headphones on. Your phone rings. You reach over, disconnect the headphones from Windows manually, wait for them to reconnect to your phone, answer the call... and then reverse the whole process when you're done.

Or you walk back to your desk, open Windows Bluetooth settings, find your headphones, click Connect, wait...

**BudBridge makes this a single keypress.**

---

## What It Does

- Press `Ctrl+Shift+B` on your PC (or click the tray icon) → headphones move from phone to PC
- Tap a widget on your phone → headphones move from PC to phone
- Everything happens automatically: BudBridge tells the other side to let go, waits the right amount of time, then connects

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         YOUR NETWORK                            │
│                                                                 │
│  ┌─────────────────────────┐     ┌────────────────────────────┐ │
│  │      Windows PC          │     │       Android Phone        │ │
│  │                          │     │                            │ │
│  │  ┌───────────────────┐  │     │  ┌──────────────────────┐  │ │
│  │  │   BudBridge.exe   │  │     │  │   BudBridge App      │  │ │
│  │  │                   │  │     │  │                       │  │ │
│  │  │  ┌─────────────┐  │  │ HTTP│  │  HTTP Server :8521   │  │ │
│  │  │  │ HTTP :8522  │◄─┼──┼─────┼──┤  BB Handle Request   │  │ │
│  │  │  └─────────────┘  │  │     │  │                       │  │ │
│  │  │                   │  │ POST│  │  BB Claim to Phone    │  │ │
│  │  │  ┌─────────────┐  │◄─┼─────┼──┤  (widget/tile)       │  │ │
│  │  │  │   Tray Icon  │  │  │     │  └──────────────────────┘  │ │
│  │  │  │   Hotkey     │  │  │     │                            │ │
│  │  │  └─────────────┘  │  │     │  ┌──────────────────────┐  │ │
│  │  └───────────────────┘  │     │  │  Bluetooth Stack      │  │ │
│  │           │              │     │  └──────────────────────┘  │ │
│  │  ┌────────▼────────┐    │     └────────────────────────────┘ │
│  │  │ Bluetooth Stack  │    │                    │               │
│  │  └─────────────────┘    │              (Bluetooth RF)        │
│  └─────────────────────────┘                    │               │
│                   │                              │               │
│                   └──────────────────────────────┘               │
│                         Headphones                              │
└─────────────────────────────────────────────────────────────────┘

Flow: Claim to PC
  PC hotkey pressed
      → BudBridge POSTs /release to phone (BudBridge app)
      → BudBridge app disconnects BT on phone
      → BudBridge waits handoff_delay_ms
      → BudBridge connects BT on PC

Flow: Claim to Phone
  Phone widget tapped
      → BudBridge app POSTs /release to PC (BudBridge server)
      → BudBridge disconnects BT on PC
      → BudBridge app waits 3 s
      → BudBridge app connects BT on phone
```

---

## Quick Start

### Requirements

- **PC:** Windows 10/11, Python 3.11+
- **Phone:** Android 8.0+
- Both devices on the same Wi-Fi network

### 5-Minute Setup

```bash
# 1. Clone the repo
git clone https://github.com/Eclectic-Wind/BudBridge.git
cd BudBridge/pc

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run BudBridge (first run launches setup wizard)
python -m budbridge.main
```

The setup wizard will:
1. List your paired Bluetooth devices — pick your headphones
2. Ask for your phone's IP address
3. Save `~/.budbridge/config.toml`

Then install the BudBridge Android app (see [Android Setup](#phone-side)) to configure your phone.

---

## Installation

### Option A: Run from source

```bash
cd budbridge/pc
pip install -r requirements.txt
python -m budbridge.main
```

### Option B: Build a standalone .exe

```bash
cd budbridge/pc

# Generate icons first
python assets/generate_icons.py

# Build single-file executable
python build.py

# Output: dist/BudBridge.exe
```

### Option C: Install as a Python package

```bash
cd budbridge/pc
pip install .
budbridge  # runs BudBridge
```

### Auto-start with Windows

1. Open BudBridge settings (tray icon → Settings)
2. Check **Start with Windows**
   — OR —
1. Press `Win+R`, type `shell:startup`
2. Create a shortcut to `BudBridge.exe` in that folder

---

## Setup Guide

### PC Side

1. Edit `~/.budbridge/config.toml` (auto-created on first run):
   ```toml
   [device]
   bt_mac = "AA:BB:CC:DD:EE:FF"         # your headphone MAC
   bt_friendly_name = "WH-1000XM5"      # as shown in Windows BT settings

   [network]
   phone_ip = "192.168.1.42"            # your phone's local IP
   phone_port = 8521                    # BudBridge Android app HTTP server port
   pc_port = 8522                       # BudBridge HTTP server port
   ```

2. Open Windows Firewall and allow inbound TCP on port 8522 (private network):
   ```powershell
   # Run as Administrator
   New-NetFirewallRule -DisplayName "BudBridge HTTP" -Direction Inbound -Protocol TCP -LocalPort 8522 -Action Allow -Profile Private
   ```

3. Start BudBridge. The tray icon appears in the system tray.

### Phone Side

1. Build and install the app from the `android/` directory using Android Studio (open the `android/` folder, let it sync, then **Build → Build APK(s)**), or sideload the APK from the Releases page.
2. Open BudBridge on your phone and tap **Settings**.
3. Enter your PC's IP address and the shared secret (if configured).
4. Tap **Test Connection** to verify it can reach the PC.
5. [Disable battery optimization](docs/battery-optimization.md) for BudBridge so the HTTP server stays alive in the background.
6. Add the **Claim to Phone** widget to your home screen.

---

## Configuration Reference

All settings live in `~/.budbridge/config.toml`.

### `[device]`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `bt_mac` | string | `"AA:BB:CC:DD:EE:FF"` | Bluetooth MAC address of your headphones |
| `bt_friendly_name` | string | `"My Headphones"` | Display name as seen in Windows BT settings (partial match OK) |

### `[network]`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `phone_ip` | string | `"192.168.1.42"` | Phone's local IP address on your network |
| `phone_port` | int | `8521` | Port the BudBridge Android app's HTTP server listens on |
| `pc_port` | int | `8522` | Port BudBridge's HTTP server listens on |
| `shared_secret` | string | `""` | If set, all requests must include `X-BudBridge-Token: <secret>` header |

### `[behavior]`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `handoff_delay_ms` | int | `2500` | Milliseconds to wait after phone releases BT before PC connects |
| `retry_count` | int | `2` | Additional BT connect attempts if first fails |
| `retry_delay_ms` | int | `2000` | Milliseconds between retry attempts |
| `bt_method` | string | `"powershell"` | BT backend: `"powershell"`, `"btcom"`, or `"bleak"` |

### `[ui]`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `hotkey` | string | `"ctrl+shift+b"` | Global hotkey to claim headphones to PC |
| `auto_start` | bool | `false` | Start BudBridge when Windows starts |
| `show_notifications` | bool | `true` | Show Windows toast notifications |

### Bluetooth Methods

| Method | Requirements | Pros | Cons |
|--------|-------------|------|------|
| `powershell` | None (built-in) | No extra tools needed | May need admin rights; re-enables device driver |
| `btcom` | [btcom.exe](https://www.bluetooth-tester.de/btcom-bluetooth-command-line-tool/) on PATH | Supports A2DP + HFP natively | External tool required |
| `bleak` | `pip install bleak` | Works with BLE devices | BLE only; not for classic BT headphones |

---

## HTTP API

Both BudBridge (PC) and the BudBridge Android app (phone) expose a small HTTP API. All responses are JSON.

### PC Endpoints (port 8522)

| Method | Path | Description | Response |
|--------|------|-------------|----------|
| `GET` | `/ping` | Health check | `{"alive": true, "app": "BudBridge", "version": "1.0"}` |
| `GET` | `/status` | Current BT connection state | `{"connected": bool, "device": "name"}` |
| `POST` | `/release` | Disconnect BT and release to phone | `{"released": bool, "was_connected": bool}` |

**Security:** Requests from IPs other than `phone_ip` and `127.0.0.1` are rejected with `403`. If `shared_secret` is set, the `X-BudBridge-Token` header is required.

**Concurrency:** If a handoff is already in progress, `/release` returns `409 Conflict`.

### Phone Endpoints (port 8521, BudBridge Android app)

| Method | Path | Description | Response |
|--------|------|-------------|----------|
| `GET` | `/ping` | Health check | `{"alive": true, "app": "BudBridge", "version": "1.0"}` |
| `GET` | `/status` | BT connection state on phone | `{"connected": bool, "device": "name"}` |
| `POST` | `/release` | Disconnect BT on phone | `{"released": true, "was_connected": bool}` |

---

## Tray Icon

| Colour | State | Meaning |
|--------|-------|---------|
| Green | Connected | Headphones on PC |
| Grey | Disconnected | Headphones not on PC |
| Yellow | Busy | Handoff in progress |
| Red | Error | Last action failed |

**Left-click** the tray icon to claim headphones to PC.

**Right-click** for the full menu:
- **Claim to PC** — move headphones from phone to PC
- **Release to Phone** — disconnect from PC (phone will reconnect on its own)
- **Settings...** — open the settings window
- **Quit** — exit BudBridge

---

## Troubleshooting

| Issue | Quick fix |
|-------|-----------|
| BudBridge app not responding | Disable battery optimization for BudBridge — see [battery-optimization.md](docs/battery-optimization.md) |
| BT won't connect after release | Increase `handoff_delay_ms` to 4000 |
| "Device not found" in PowerShell | Check `bt_friendly_name` matches Windows exactly |
| PC server unreachable from phone | Add Windows Firewall inbound rule for port 8522 |
| Hotkey not working | Check for conflicts; try running as admin |
| Phone IP keeps changing | Assign static DHCP lease in router settings |
| btcom.exe not found | Download from bluetooth-tester.de and add to PATH |

Full troubleshooting guide: [docs/troubleshooting.md](docs/troubleshooting.md)

Battery optimization guide: [docs/battery-optimization.md](docs/battery-optimization.md)

---

## Project Structure

```
BudBridge/
├── pc/
│   ├── budbridge/
│   │   ├── __init__.py        # Package metadata
│   │   ├── main.py            # Entry point, setup wizard, service orchestration
│   │   ├── tray.py            # System tray icon (pystray)
│   │   ├── server.py          # Flask HTTP server (background thread)
│   │   ├── bluetooth.py       # BT backends: PowerShell, btcom, bleak
│   │   ├── handoff.py         # Handoff state machine
│   │   ├── config.py          # TOML config load/save
│   │   ├── hotkey.py          # Global hotkey (pynput)
│   │   ├── notify.py          # Windows toast notifications (plyer)
│   │   └── discovery.py       # mDNS peer discovery (zeroconf)
│   ├── assets/
│   │   └── generate_icons.py  # Generate .ico files with Pillow
│   ├── config.toml.example    # Annotated config template
│   ├── requirements.txt       # Python dependencies
│   ├── pyproject.toml         # Package metadata and build config
│   └── build.py               # PyInstaller build script
├── android/
│   └── app/src/main/kotlin/com/budbridge/
│       ├── MainActivity.kt    # Settings UI
│       ├── BudBridgeService.kt# Foreground service + HTTP server lifecycle
│       ├── HttpServer.kt      # HTTP server (handles /ping, /status, /release)
│       ├── BluetoothHandler.kt# BT connect/disconnect via HFP hidden API
│       ├── HandoffManager.kt  # Handoff state machine
│       ├── ClaimWidget.kt     # Home screen widget
│       ├── ClaimTile.kt       # Quick Settings tile
│       ├── NsdHelper.kt       # mDNS peer discovery
│       └── Prefs.kt           # Shared preferences wrapper
├── docs/
│   ├── troubleshooting.md     # Common issues and solutions
│   └── battery-optimization.md # Per-OEM battery optimization guide
├── LICENSE                    # MIT
└── README.md                  # This file
```

---

## Dependencies

### PC (Python)

| Package | Version | Purpose |
|---------|---------|---------|
| `pystray` | >=0.19 | System tray icon |
| `Pillow` | >=10.0 | Icon generation |
| `Flask` | >=3.0 | HTTP server |
| `requests` | >=2.31 | HTTP client (call phone) |
| `pynput` | >=1.7 | Global hotkey |
| `plyer` | >=2.1 | Toast notifications |
| `toml` | >=0.10 | Config file parsing |
| `zeroconf` | >=0.131 | mDNS discovery (optional) |
| `bleak` | >=0.21 | BLE backend (optional) |

### Phone

| Requirement | Notes |
|-------------|-------|
| Android 8.0+ | API level 26 or higher |
| Bluetooth Classic | Required for HFP headphone control |

---

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Make your changes with tests where applicable
4. Run the tests: `pytest`
5. Submit a pull request with a clear description

### Development Setup

```bash
git clone https://github.com/Eclectic-Wind/BudBridge.git
cd BudBridge/pc
pip install -e ".[dev]"
pytest
```

### Areas for Contribution

- macOS support (replacing PowerShell BT backend with `blueutil`)
- iOS support (Shortcuts app integration)
- Auto-discovery of phone IP via mDNS
- Bluetooth status polling improvements
- Dark/light mode tray icons
- GUI settings improvements

---

## License

MIT License — see [LICENSE](LICENSE) for details.

Copyright (c) 2026 BudBridge Contributors
