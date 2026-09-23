"""Dependency/bootstrap helpers for GSSE26 RPC.

This module intentionally keeps optional dependencies optional.  The main
entry point calls ``prepare_dependencies()`` before importing ``app.py`` so
the runtime feature flags are initialized before the GUI is constructed.
"""

import os
import subprocess
import sys
import tkinter as tk
from tkinter import messagebox


# Windows registry support
winreg = None
try:
    import winreg as _winreg
    winreg = _winreg
    WINREG_AVAILABLE = True
except Exception:
    WINREG_AVAILABLE = False


# Optional runtime dependencies
TRAY_AVAILABLE = False
HOTKEYS_AVAILABLE = False
pystray = None
PILImage = None
PILImageDraw = None
PILImageFont = None
pynput_keyboard = None


def hide_console_window():
    """Relaunch this GUI with pythonw.exe on Windows to hide the console."""
    if os.name != "nt":
        return

    executable = os.path.basename(sys.executable).lower()
    if executable == "pythonw.exe":
        return

    if getattr(sys, "frozen", False) or not getattr(sys, "argv", None):
        return

    script = os.path.abspath(sys.argv[0])
    pythonw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")

    if not os.path.exists(pythonw):
        return

    try:
        subprocess.Popen(
            [pythonw, script, *sys.argv[1:]],
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        raise SystemExit(0)
    except SystemExit:
        raise
    except Exception:
        pass


def ensure_dependency():
    """Ensure the required Discord RPC package is installed."""
    try:
        from pypresence import Presence  # noqa: F401
    except ImportError:
        answer = messagebox.askyesno(
            "Missing dependency",
            "pypresence is not installed.\n\nInstall it automatically now?",
        )
        if answer:
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", "pypresence"]
            )
        else:
            raise SystemExit


def ensure_optional_dependencies():
    """Offer to install optional tray/hotkey dependencies."""
    missing = []
    for module, package in (
        ("pystray", "pystray"),
        ("PIL", "Pillow"),
        ("pynput", "pynput"),
    ):
        try:
            __import__(module)
        except ImportError:
            missing.append(package)

    if not missing:
        return

    answer = messagebox.askyesno(
        "Optional features",
        "These optional packages enable the system tray, tray icon and "
        "global hotkeys:\n\n"
        + ", ".join(missing)
        + "\n\nInstall them automatically now?\n"
        "(The app still works without them.)",
    )

    if answer:
        try:
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", *missing]
            )
        except Exception:
            pass


def load_optional_dependencies():
    """Load optional modules and update the runtime feature flags."""
    global TRAY_AVAILABLE, HOTKEYS_AVAILABLE
    global pystray, PILImage, PILImageDraw, PILImageFont, pynput_keyboard

    try:
        import pystray as _pystray
        from PIL import Image as _Image
        from PIL import ImageDraw as _ImageDraw

        try:
            from PIL import ImageFont as _ImageFont
        except Exception:
            _ImageFont = None

        pystray = _pystray
        PILImage = _Image
        PILImageDraw = _ImageDraw
        PILImageFont = _ImageFont
        TRAY_AVAILABLE = True
    except Exception:
        TRAY_AVAILABLE = False

    try:
        from pynput import keyboard as _kb
        pynput_keyboard = _kb
        HOTKEYS_AVAILABLE = True
    except Exception:
        HOTKEYS_AVAILABLE = False


def get_config_path():
    """Return the per-user JSON configuration path."""
    if os.name == "nt":
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
    else:
        base = os.path.join(os.path.expanduser("~"), ".config")

    folder = os.path.join(base, "GSSE26RPC")
    try:
        os.makedirs(folder, exist_ok=True)
    except Exception:
        folder = os.path.dirname(os.path.abspath(sys.argv[0]))

    return os.path.join(folder, "config.json")


CONFIG_PATH = get_config_path()


def prepare_dependencies():
    """Run startup/bootstrap dependency checks exactly once from main.py."""
    hide_console_window()
    ensure_dependency()
    ensure_optional_dependencies()
    load_optional_dependencies()
