"""PyInstaller build script for BudBridge.

Usage:
    python build.py           # build the executable
    python build.py --clean   # remove dist/ and build/ before building
    python build.py --icons   # regenerate icons before building
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent


def clean() -> None:
    """Remove PyInstaller output directories."""
    for d in ["dist", "build"]:
        p = HERE / d
        if p.exists():
            shutil.rmtree(p)
            print(f"Removed {p}")
    spec = HERE / "BudBridge.spec"
    if spec.exists():
        spec.unlink()
        print(f"Removed {spec}")


def generate_icons() -> None:
    """Run assets/generate_icons.py to create .ico files."""
    script = HERE / "assets" / "generate_icons.py"
    if not script.exists():
        print(f"Icon generator not found: {script}")
        return
    subprocess.run([sys.executable, str(script)], check=True)


def build() -> None:
    icon_path = HERE / "assets" / "budbridge.ico"
    if not icon_path.exists():
        print("budbridge.ico not found — generating icons first…")
        generate_icons()

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--onefile",
        "--noconsole",
        "--name",
        "BudBridge",
        "--icon",
        str(HERE / "assets" / "budbridge.ico"),
        "--add-data",
        f"{HERE / 'assets'};assets",
        "--add-data",
        f"{HERE / 'config.toml.example'};.",
        # Make sure the budbridge package is found
        "--paths",
        str(HERE),
        str(HERE / "budbridge" / "main.py"),
    ]

    print("Running PyInstaller…")
    print(" ".join(str(c) for c in cmd))
    subprocess.run(cmd, check=True, cwd=str(HERE))
    print(f"\nBuild complete. Executable: {HERE / 'dist' / 'BudBridge.exe'}")


def main() -> None:
    args = sys.argv[1:]

    if "--clean" in args:
        clean()

    if "--icons" in args:
        generate_icons()

    build()


if __name__ == "__main__":
    main()
