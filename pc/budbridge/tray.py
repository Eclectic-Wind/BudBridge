"""BudBridge system tray icon — pystray integration with Pillow-generated icons."""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Optional, Callable

log = logging.getLogger(__name__)

# Icon state colours (RGBA)
_COLOURS = {
    "connected": (34, 197, 94, 255),      # green
    "disconnected": (156, 163, 175, 255),  # grey
    "busy": (234, 179, 8, 255),            # yellow
    "error": (239, 68, 68, 255),           # red
}

_ASSETS_DIR = Path(__file__).parent.parent / "assets"
_ICON_FILES = {
    "connected": "budbridge_connected.ico",
    "disconnected": "budbridge.ico",
    "busy": "budbridge_busy.ico",
    "error": "budbridge_error.ico",
}


# ---------------------------------------------------------------------------
# Icon generation helpers
# ---------------------------------------------------------------------------

def _draw_icon(colour: tuple, size: int = 64):
    """Create a PIL Image with a coloured circle and headphone silhouette."""
    from PIL import Image, ImageDraw

    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Background circle
    margin = 2
    draw.ellipse(
        [margin, margin, size - margin, size - margin],
        fill=colour,
    )

    # Simple headphone shape (white)
    c = size // 2
    r_outer = int(size * 0.30)
    r_inner = int(size * 0.15)
    lw = max(2, size // 16)
    white = (255, 255, 255, 230)

    # Arc (headband)
    arc_margin = c - r_outer
    draw.arc(
        [arc_margin, arc_margin, c + r_outer, c + r_outer],
        start=200,
        end=340,
        fill=white,
        width=lw,
    )

    # Left ear cup
    lx = c - r_outer
    draw.ellipse(
        [lx - lw * 2, c - lw * 2, lx + lw * 2, c + lw * 2],
        fill=white,
    )

    # Right ear cup
    rx = c + r_outer
    draw.ellipse(
        [rx - lw * 2, c - lw * 2, rx + lw * 2, c + lw * 2],
        fill=white,
    )

    return img


def _load_or_generate_icon(state: str):
    """Return a PIL Image for *state*, loading from file or generating on-the-fly."""
    from PIL import Image

    ico_path = _ASSETS_DIR / _ICON_FILES.get(state, "budbridge.ico")
    if ico_path.exists():
        try:
            return Image.open(ico_path).convert("RGBA")
        except Exception as exc:
            log.debug("Could not open icon %s: %s", ico_path, exc)

    colour = _COLOURS.get(state, _COLOURS["disconnected"])
    return _draw_icon(colour)


# ---------------------------------------------------------------------------
# TrayApp
# ---------------------------------------------------------------------------

_TOOLTIP_TEMPLATES = {
    "connected":        "BudBridge — {device} connected to PC",
    "disconnected":     "BudBridge — {device} on phone",
    "busy_claiming":    "BudBridge — Claiming {device} to PC…",
    "busy_releasing":   "BudBridge — Releasing {device} to phone…",
    "busy":             "BudBridge — Handoff in progress…",
    "error":            "BudBridge — Connection failed (click to retry)",
}


class TrayApp:
    """System tray application powered by pystray."""

    def __init__(self, config, handoff_manager):
        self._config = config
        self._handoff = handoff_manager
        self._icon = None
        self._state = "disconnected"
        self._settings_open = False
        self._wizard_open = False
        self._wizard_fn: Optional[Callable] = None
        self._on_quit: Optional[Callable] = None

    def set_wizard_callback(self, fn: Callable) -> None:
        self._wizard_fn = fn

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_menu(self):
        import pystray

        from budbridge import startup

        return pystray.Menu(
            pystray.MenuItem(
                "Claim to PC",
                self._action_claim,
                default=True,
                visible=True,
            ),
            pystray.MenuItem(
                "Release to Phone",
                self._action_release,
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "Run at startup",
                self._action_toggle_startup,
                checked=lambda item: startup.is_enabled(),
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "Setup Wizard…",
                self._action_wizard,
            ),
            pystray.MenuItem(
                "Settings…",
                self._action_settings,
            ),
            pystray.MenuItem(
                "Quit",
                self._action_quit,
            ),
        )

    def _make_tooltip(self) -> str:
        device = self._config.device.bt_friendly_name
        template = _TOOLTIP_TEMPLATES.get(self._state, "BudBridge")
        return template.format(device=device)

    # ------------------------------------------------------------------
    # Menu actions
    # ------------------------------------------------------------------

    def _action_claim(self, icon=None, item=None) -> None:
        t = threading.Thread(
            target=self._handoff.claim_to_pc, name="ClaimToPC", daemon=True
        )
        t.start()

    def _action_release(self, icon=None, item=None) -> None:
        t = threading.Thread(
            target=self._handoff.release_to_phone, name="ReleaseToPhone", daemon=True
        )
        t.start()

    def _action_wizard(self, icon=None, item=None) -> None:
        if self._wizard_open or self._wizard_fn is None:
            return
        self._wizard_open = True
        def _run():
            try:
                self._wizard_fn()
            except Exception as exc:
                log.error("Setup wizard error: %s", exc)
            finally:
                self._wizard_open = False
        threading.Thread(target=_run, name="SetupWizard", daemon=True).start()

    def _action_settings(self, icon=None, item=None) -> None:
        if self._settings_open:
            return
        t = threading.Thread(target=self._open_settings_window, name="Settings", daemon=True)
        t.start()

    def _action_toggle_startup(self, icon=None, item=None) -> None:
        from budbridge import startup
        try:
            if startup.is_enabled():
                startup.disable()
            else:
                startup.enable()
        except Exception as exc:
            log.error("Failed to toggle startup: %s", exc)

    def _action_quit(self, icon=None, item=None) -> None:
        if self._icon:
            self._icon.stop()

    def _open_settings_window(self) -> None:
        """Open a minimal tkinter settings/status window."""
        self._settings_open = True
        try:
            import tkinter as tk
            from tkinter import ttk, messagebox
            from budbridge.config import save as save_config, is_valid_mac

            cfg = self._config
            root = tk.Tk()
            root.title("BudBridge Settings")
            root.resizable(False, False)

            frame = ttk.Frame(root, padding=16)
            frame.grid(row=0, column=0, sticky="nsew")

            # Device section
            ttk.Label(frame, text="Device", font=("TkDefaultFont", 10, "bold")).grid(
                row=0, column=0, columnspan=2, sticky="w", pady=(0, 4)
            )

            ttk.Label(frame, text="BT MAC:").grid(row=1, column=0, sticky="w")
            mac_var = tk.StringVar(value=cfg.device.bt_mac)
            ttk.Entry(frame, textvariable=mac_var, width=20).grid(row=1, column=1, sticky="ew")

            ttk.Label(frame, text="Friendly Name:").grid(row=2, column=0, sticky="w")
            name_var = tk.StringVar(value=cfg.device.bt_friendly_name)
            ttk.Entry(frame, textvariable=name_var, width=24).grid(row=2, column=1, sticky="ew")

            ttk.Separator(frame).grid(row=3, column=0, columnspan=2, sticky="ew", pady=8)

            # Network section
            ttk.Label(frame, text="Network", font=("TkDefaultFont", 10, "bold")).grid(
                row=4, column=0, columnspan=2, sticky="w", pady=(0, 4)
            )

            ttk.Label(frame, text="Phone IP:").grid(row=5, column=0, sticky="w")
            phone_ip_var = tk.StringVar(value=cfg.network.phone_ip)
            ttk.Entry(frame, textvariable=phone_ip_var, width=18).grid(row=5, column=1, sticky="ew")

            ttk.Label(frame, text="Phone Port:").grid(row=6, column=0, sticky="w")
            phone_port_var = tk.StringVar(value=str(cfg.network.phone_port))
            ttk.Entry(frame, textvariable=phone_port_var, width=8).grid(row=6, column=1, sticky="w")

            ttk.Label(frame, text="PC Port:").grid(row=7, column=0, sticky="w")
            pc_port_var = tk.StringVar(value=str(cfg.network.pc_port))
            ttk.Entry(frame, textvariable=pc_port_var, width=8).grid(row=7, column=1, sticky="w")

            ttk.Separator(frame).grid(row=8, column=0, columnspan=2, sticky="ew", pady=8)

            # Behavior
            ttk.Label(frame, text="Behavior", font=("TkDefaultFont", 10, "bold")).grid(
                row=9, column=0, columnspan=2, sticky="w", pady=(0, 4)
            )

            ttk.Label(frame, text="BT Method:").grid(row=10, column=0, sticky="w")
            method_var = tk.StringVar(value=cfg.behavior.bt_method)
            method_frame = ttk.Frame(frame)
            method_frame.grid(row=10, column=1, sticky="w")
            ttk.Combobox(
                method_frame,
                textvariable=method_var,
                values=["powershell", "btcom", "bleak"],
                state="readonly",
                width=14,
            ).pack(side="left")
            ttk.Label(method_frame, text=" (restart required)", foreground="grey").pack(side="left")

            ttk.Label(frame, text="Hotkey:").grid(row=11, column=0, sticky="w")
            hotkey_var = tk.StringVar(value=cfg.ui.hotkey)
            hotkey_frame = ttk.Frame(frame)
            hotkey_frame.grid(row=11, column=1, sticky="w")
            ttk.Entry(hotkey_frame, textvariable=hotkey_var, width=16).pack(side="left")
            ttk.Label(hotkey_frame, text=" (restart required)", foreground="grey").pack(side="left")

            show_notif_var = tk.BooleanVar(value=cfg.ui.show_notifications)
            ttk.Checkbutton(
                frame, text="Show notifications", variable=show_notif_var
            ).grid(row=12, column=0, columnspan=2, sticky="w")

            ttk.Separator(frame).grid(row=13, column=0, columnspan=2, sticky="ew", pady=8)

            def _save():
                mac = mac_var.get().strip()
                if mac and not is_valid_mac(mac):
                    messagebox.showerror("Invalid", "Bluetooth MAC must be in the format AA:BB:CC:DD:EE:FF.")
                    return
                cfg.device.bt_mac = mac
                cfg.device.bt_friendly_name = name_var.get().strip()
                cfg.network.phone_ip = phone_ip_var.get().strip()
                try:
                    phone_port = int(phone_port_var.get())
                    pc_port = int(pc_port_var.get())
                    if not (1 <= phone_port <= 65535) or not (1 <= pc_port <= 65535):
                        raise ValueError
                    cfg.network.phone_port = phone_port
                    cfg.network.pc_port = pc_port
                except ValueError:
                    messagebox.showerror("Invalid", "Ports must be integers between 1 and 65535.")
                    return
                cfg.behavior.bt_method = method_var.get()
                cfg.ui.hotkey = hotkey_var.get().strip()
                cfg.ui.show_notifications = show_notif_var.get()
                save_config(cfg)
                messagebox.showinfo("Saved", "Settings saved. Restart BudBridge for changes to take effect.")
                root.destroy()

            btn_frame = ttk.Frame(frame)
            btn_frame.grid(row=14, column=0, columnspan=2, sticky="e")
            ttk.Button(btn_frame, text="Save", command=_save).pack(side="right", padx=4)
            ttk.Button(btn_frame, text="Cancel", command=root.destroy).pack(side="right")

            root.mainloop()
        except Exception as exc:
            log.error("Settings window error: %s", exc)
        finally:
            self._settings_open = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_state(self, state: str) -> None:
        """Update tray icon and tooltip to reflect *state*.

        Accepted states: "connected", "disconnected", "busy", "error",
        plus handoff states passed through from HandoffManager.
        """
        # Map handoff states to tray states
        _map = {
            "idle":         "disconnected",
            "releasing":    "busy_releasing",
            "waiting":      "busy_claiming",
            "connecting":   "busy_claiming",
            "connected":    "connected",
            "disconnected": "disconnected",
            "error":        "error",
        }
        tray_state = _map.get(state, state)
        self._state = tray_state

        if self._icon is None:
            return

        # Directional busy states share the "busy" icon
        icon_state = "busy" if tray_state in ("busy_claiming", "busy_releasing") else tray_state
        try:
            self._icon.icon = _load_or_generate_icon(icon_state)
            self._icon.title = self._make_tooltip()
        except Exception as exc:
            log.debug("set_state update error: %s", exc)

    def run(self) -> None:
        """Start the pystray event loop (blocking)."""
        try:
            import pystray

            initial_icon = _load_or_generate_icon(self._state)
            self._icon = pystray.Icon(
                name="BudBridge",
                icon=initial_icon,
                title=self._make_tooltip(),
                menu=self._build_menu(),
            )
            # Left-click action
            self._icon.on_activate = lambda icon: self._action_claim()

            log.info("System tray icon running.")
            self._icon.run()
        except ImportError:
            log.error("pystray is not installed. Run: pip install pystray")
        except Exception as exc:
            log.error("Tray run error: %s", exc)

    def stop(self) -> None:
        """Stop the tray icon."""
        if self._icon is not None:
            try:
                self._icon.stop()
            except Exception as exc:
                log.debug("Tray stop error: %s", exc)
