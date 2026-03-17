"""BudBridge — entry point."""

from __future__ import annotations

import logging
import sys
import threading
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Logging setup — do this before importing local modules
# ---------------------------------------------------------------------------

_LOG_DIR = Path.home() / ".budbridge"
_LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(_LOG_DIR / "budbridge.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Local imports
# ---------------------------------------------------------------------------

from budbridge.config import load as load_config, save as save_config, BudBridgeConfig
from budbridge.handoff import HandoffManager
from budbridge.hotkey import HotkeyManager
from budbridge.server import start_server, stop_server
from budbridge.tray import TrayApp
from budbridge.discovery import DiscoveryService
from budbridge import bluetooth


# ---------------------------------------------------------------------------
# Setup wizard
# ---------------------------------------------------------------------------

def run_setup_wizard(config: BudBridgeConfig) -> None:
    """Minimal tkinter first-run wizard: pick BT device → enter phone IP → save."""
    import tkinter as tk
    from tkinter import ttk, messagebox
    import requests

    root = tk.Tk()
    root.title("BudBridge — First-Time Setup")
    root.resizable(False, False)

    notebook = ttk.Notebook(root)
    notebook.pack(fill="both", expand=True, padx=16, pady=16)

    # ------------------------------------------------------------------
    # Step 1: Bluetooth device
    # ------------------------------------------------------------------
    frame1 = ttk.Frame(notebook, padding=16)
    notebook.add(frame1, text="Step 1 — Bluetooth Device")

    ttk.Label(
        frame1,
        text="Select your headphones from the list of paired Bluetooth devices.",
    ).pack(anchor="w")

    listbox_frame = ttk.Frame(frame1)
    listbox_frame.pack(fill="both", expand=True, pady=8)

    scrollbar = ttk.Scrollbar(listbox_frame, orient="vertical")
    listbox = tk.Listbox(listbox_frame, height=8, width=50, yscrollcommand=scrollbar.set)
    scrollbar.config(command=listbox.yview)
    scrollbar.pack(side="right", fill="y")
    listbox.pack(side="left", fill="both", expand=True)

    devices = []

    def _populate_devices():
        listbox.delete(0, "end")
        listbox.insert("end", "Scanning…")
        devices.clear()
        refresh_btn.config(state="disabled")

        def _run():
            try:
                devs = bluetooth.list_paired_devices()
            except Exception as exc:
                devs = []
                root.after(0, lambda: listbox.delete(0, "end") or listbox.insert("end", f"Error: {exc}"))
                root.after(0, lambda: refresh_btn.config(state="normal"))
                return

            def _update():
                listbox.delete(0, "end")
                devices.clear()
                for d in devs:
                    status = "Connected" if d["connected"] else "Paired"
                    label = f"{d['name']}  [{d.get('mac', 'N/A')}]  — {status}"
                    listbox.insert("end", label)
                    devices.append(d)
                refresh_btn.config(state="normal")

            root.after(0, _update)

        threading.Thread(target=_run, daemon=True).start()

    refresh_btn = ttk.Button(frame1, text="Refresh Device List", command=_populate_devices)
    refresh_btn.pack(anchor="w")
    _populate_devices()

    # Manual fallback
    ttk.Separator(frame1).pack(fill="x", pady=8)
    ttk.Label(frame1, text="Or enter manually:").pack(anchor="w")
    manual_frame = ttk.Frame(frame1)
    manual_frame.pack(fill="x", pady=4)
    ttk.Label(manual_frame, text="MAC:").pack(side="left")
    mac_var = tk.StringVar(value=config.device.bt_mac)
    ttk.Entry(manual_frame, textvariable=mac_var, width=20).pack(side="left", padx=4)
    ttk.Label(manual_frame, text="Name:").pack(side="left")
    name_var = tk.StringVar(value=config.device.bt_friendly_name)
    ttk.Entry(manual_frame, textvariable=name_var, width=22).pack(side="left", padx=4)

    def _on_select(_event=None):
        sel = listbox.curselection()
        if sel and devices:
            d = devices[sel[0]]
            mac_var.set(d.get("mac", ""))
            name_var.set(d.get("name", ""))

    listbox.bind("<<ListboxSelect>>", _on_select)

    # ------------------------------------------------------------------
    # Step 2: Phone discovery (automatic)
    # ------------------------------------------------------------------
    frame2 = ttk.Frame(notebook, padding=16)
    notebook.add(frame2, text="Step 2 — Find Phone")

    ttk.Label(
        frame2,
        text=(
            "BudBridge will automatically find your phone over WiFi.\n\n"
            "Make sure the BudBridge app is running on your phone and\n"
            "both devices are on the same WiFi network.\n\n"
            "Click 'Search Now' to scan, or skip — discovery happens\n"
            "automatically in the background at handoff time."
        ),
        justify="left",
    ).pack(anchor="w", pady=(0, 12))

    search_result_var = tk.StringVar(value="")
    ttk.Label(frame2, textvariable=search_result_var, foreground="grey").pack(anchor="w", pady=4)

    def _search_phone():
        search_result_var.set("Searching for phone (5 s)…")
        root.update()
        from budbridge.discovery import DiscoveryService
        ds = DiscoveryService(config)
        ip = ds.find_phone(timeout=5.0)
        if ip:
            config.network.phone_ip = ip
            search_result_var.set(f"Found phone at {ip}!")
        else:
            search_result_var.set("Phone not found. Make sure the BudBridge app is open on your phone.")

    ttk.Button(frame2, text="Search Now", command=_search_phone).pack(anchor="w")

    # Advanced override (collapsed)
    ttk.Separator(frame2).pack(fill="x", pady=12)
    ttk.Label(frame2, text="Advanced — manual IP override (optional):").pack(anchor="w")
    net_frame = ttk.Frame(frame2)
    net_frame.pack(fill="x", pady=4)
    ttk.Label(net_frame, text="Phone IP:").grid(row=0, column=0, sticky="w")
    phone_ip_var = tk.StringVar(value=config.network.phone_ip)
    ttk.Entry(net_frame, textvariable=phone_ip_var, width=18).grid(row=0, column=1, padx=4)
    ttk.Label(net_frame, text="PC Port:").grid(row=1, column=0, sticky="w", pady=4)
    pc_port_var = tk.StringVar(value=str(config.network.pc_port))
    ttk.Entry(net_frame, textvariable=pc_port_var, width=8).grid(row=1, column=1, sticky="w", padx=4)

    # ------------------------------------------------------------------
    # Step 3: Save
    # ------------------------------------------------------------------
    frame3 = ttk.Frame(notebook, padding=16)
    notebook.add(frame3, text="Step 3 — Save")

    ttk.Label(
        frame3,
        text="Review your settings and click Save to finish setup.",
    ).pack(anchor="w", pady=(0, 8))

    summary_var = tk.StringVar()
    ttk.Label(frame3, textvariable=summary_var, justify="left").pack(anchor="w")

    def _update_summary(_event=None):
        ip_display = phone_ip_var.get() or "(auto-discover via mDNS)"
        summary_var.set(
            f"BT Name:  {name_var.get()}\n"
            f"BT MAC:   {mac_var.get()}\n"
            f"Phone IP: {ip_display}\n"
            f"PC Port:  {pc_port_var.get()}"
        )

    notebook.bind("<<NotebookTabChanged>>", _update_summary)

    def _save():
        config.device.bt_mac = mac_var.get().strip()
        config.device.bt_friendly_name = name_var.get().strip()
        config.network.phone_ip = phone_ip_var.get().strip()
        try:
            config.network.pc_port = int(pc_port_var.get())
        except ValueError:
            messagebox.showerror("Invalid", "PC Port must be an integer.")
            return
        save_config(config)
        messagebox.showinfo("Done", "Configuration saved! BudBridge will now start.")
        root.destroy()

    ttk.Button(frame3, text="Save & Start", command=_save).pack(pady=8)

    root.mainloop()


# ---------------------------------------------------------------------------
# Status polling
# ---------------------------------------------------------------------------

def start_status_poll(config: BudBridgeConfig, tray: TrayApp, handoff: "HandoffManager") -> None:
    """Poll BT connection status every 30 s and update the tray icon."""

    def _poll():
        while True:
            time.sleep(30)
            try:
                if handoff.in_progress:
                    continue
                connected = bluetooth.is_connected(config)
                tray.set_state("connected" if connected else "disconnected")
            except Exception as exc:
                log.debug("Status poll error: %s", exc)

    t = threading.Thread(target=_poll, name="StatusPoll", daemon=True)
    t.start()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    log.info("BudBridge starting…")

    config = load_config()
    log.info("Config loaded from %s", config._config_path)

    if not config.is_configured():
        log.info("First run — launching setup wizard.")
        run_setup_wizard(config)
        # Reload after wizard
        config = load_config()
        if not config.is_configured():
            log.warning("Setup wizard closed without saving. Running with defaults.")

    handoff = HandoffManager(config)
    tray = TrayApp(config, handoff)
    hotkey = HotkeyManager(config.ui.hotkey, handoff.claim_to_pc)
    discovery = DiscoveryService(config)

    # Wire callbacks
    handoff.on_state_change = tray.set_state
    handoff.set_discovery(discovery)

    # Start background services
    start_server(config, handoff.release_from_phone_request)
    hotkey.start()
    discovery.start()

    # Status polling
    start_status_poll(config, tray, handoff)

    log.info("All services started. Entering tray loop.")

    # Blocking tray loop
    try:
        tray.run()
    except KeyboardInterrupt:
        log.info("KeyboardInterrupt — shutting down.")
    finally:
        log.info("BudBridge shutting down…")
        hotkey.stop()
        discovery.stop()
        stop_server()
        log.info("BudBridge stopped.")


if __name__ == "__main__":
    main()
