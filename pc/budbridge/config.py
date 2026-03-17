"""BudBridge configuration — load/save config.toml from ~/.budbridge/."""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

try:
    import toml
except ImportError:  # pragma: no cover
    raise SystemExit("Missing dependency: toml. Run: pip install toml")

# ---------------------------------------------------------------------------
# Config directory
# ---------------------------------------------------------------------------

_CONFIG_DIR = Path.home() / ".budbridge"
_CONFIG_FILE = _CONFIG_DIR / "config.toml"

# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class DeviceConfig:
    bt_mac: str = "AA:BB:CC:DD:EE:FF"
    bt_friendly_name: str = "My Headphones"


@dataclass
class NetworkConfig:
    phone_ip: str = ""  # Empty = auto-discover via mDNS
    phone_port: int = 8521
    pc_port: int = 8522
    shared_secret: str = ""


@dataclass
class BehaviorConfig:
    handoff_delay_ms: int = 2500
    retry_count: int = 2
    retry_delay_ms: int = 2000
    bt_method: str = "powershell"  # "btcom", "powershell", or "bleak"


@dataclass
class UIConfig:
    hotkey: str = "ctrl+shift+b"
    auto_start: bool = False
    show_notifications: bool = True


@dataclass
class BudBridgeConfig:
    device: DeviceConfig = field(default_factory=DeviceConfig)
    network: NetworkConfig = field(default_factory=NetworkConfig)
    behavior: BehaviorConfig = field(default_factory=BehaviorConfig)
    ui: UIConfig = field(default_factory=UIConfig)

    # Internal — not persisted
    _config_path: Optional[Path] = field(default=None, repr=False, compare=False)

    def is_configured(self) -> bool:
        """Return True if at minimum the MAC or friendly name look real."""
        return (
            self.device.bt_mac != "AA:BB:CC:DD:EE:FF"
            or self.device.bt_friendly_name != "My Headphones"
        )


# ---------------------------------------------------------------------------
# Serialisation helpers
# ---------------------------------------------------------------------------


def _dataclass_to_dict(obj) -> dict:
    """Recursively convert nested dataclasses to plain dicts, skipping private fields."""
    d = {}
    for k, v in asdict(obj).items():
        if k.startswith("_"):
            continue
        d[k] = v
    return d


def _config_to_toml_dict(cfg: BudBridgeConfig) -> dict:
    return {
        "device": _dataclass_to_dict(cfg.device),
        "network": _dataclass_to_dict(cfg.network),
        "behavior": _dataclass_to_dict(cfg.behavior),
        "ui": _dataclass_to_dict(cfg.ui),
    }


def _dict_to_config(d: dict) -> BudBridgeConfig:
    cfg = BudBridgeConfig()
    if "device" in d:
        sec = d["device"]
        cfg.device = DeviceConfig(
            bt_mac=sec.get("bt_mac", cfg.device.bt_mac),
            bt_friendly_name=sec.get("bt_friendly_name", cfg.device.bt_friendly_name),
        )
    if "network" in d:
        sec = d["network"]
        cfg.network = NetworkConfig(
            phone_ip=sec.get("phone_ip", cfg.network.phone_ip),
            phone_port=int(sec.get("phone_port", cfg.network.phone_port)),
            pc_port=int(sec.get("pc_port", cfg.network.pc_port)),
            shared_secret=sec.get("shared_secret", cfg.network.shared_secret),
        )
    if "behavior" in d:
        sec = d["behavior"]
        cfg.behavior = BehaviorConfig(
            handoff_delay_ms=int(sec.get("handoff_delay_ms", cfg.behavior.handoff_delay_ms)),
            retry_count=int(sec.get("retry_count", cfg.behavior.retry_count)),
            retry_delay_ms=int(sec.get("retry_delay_ms", cfg.behavior.retry_delay_ms)),
            bt_method=sec.get("bt_method", cfg.behavior.bt_method),
        )
    if "ui" in d:
        sec = d["ui"]
        cfg.ui = UIConfig(
            hotkey=sec.get("hotkey", cfg.ui.hotkey),
            auto_start=bool(sec.get("auto_start", cfg.ui.auto_start)),
            show_notifications=bool(sec.get("show_notifications", cfg.ui.show_notifications)),
        )
    return cfg


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def load(path: Optional[Path] = None) -> BudBridgeConfig:
    """Load config from *path* (default: ~/.budbridge/config.toml).

    If the file does not exist it is created from defaults.
    """
    config_path = Path(path) if path else _CONFIG_FILE
    _CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    if not config_path.exists():
        cfg = BudBridgeConfig()
        cfg._config_path = config_path
        save(cfg, config_path)
        return cfg

    try:
        raw = toml.loads(config_path.read_text(encoding="utf-8"))
        cfg = _dict_to_config(raw)
        cfg._config_path = config_path
        return cfg
    except Exception as exc:
        print(f"[config] Warning: failed to parse {config_path}: {exc}. Using defaults.")
        cfg = BudBridgeConfig()
        cfg._config_path = config_path
        return cfg


def save(cfg: BudBridgeConfig, path: Optional[Path] = None) -> None:
    """Persist *cfg* to disk."""
    config_path = Path(path) if path else (cfg._config_path or _CONFIG_FILE)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(toml.dumps(_config_to_toml_dict(cfg)), encoding="utf-8")


def is_configured(cfg: BudBridgeConfig) -> bool:
    """Convenience wrapper around cfg.is_configured()."""
    return cfg.is_configured()


def get_config_path() -> Path:
    return _CONFIG_FILE
