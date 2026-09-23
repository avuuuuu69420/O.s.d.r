"""Static configuration, UI constants, and default presets for GSSE26 RPC."""

# ============================================================
# GSSE26 DISCORD RPC — ENHANCED EDITION
# ============================================================
# Dependencies:
#   Required : pip install pypresence
#   Optional : pip install pystray Pillow pynput
#              (system tray, live preview icon, global hotkeys)
# ============================================================

APP_NAME = "Gay Skibidi Skid External 2026"
WINDOW_TITLE = "Gay Skibidi Skid External 2026 • Discord Rich Presence"
CONFIG_SCHEMA_VERSION = 1

# ---------- Discord RPC configuration ----------
CLIENT_ID = "1548322426037997578"

LARGE_IMAGE = "gse_logo"
LARGE_TEXT = "Gay Skibidi Skid External 2026"

SMALL_IMAGE = ""
SMALL_TEXT = ""

DEFAULT_DETAILS = "Gay Skibidi Skid External 2026"
DEFAULT_STATE = "Idle"

BUTTON_1_LABEL = ""
BUTTON_1_URL = ""

BUTTON_2_LABEL = ""
BUTTON_2_URL = ""

# ---------- Global hotkeys ----------
HOTKEY_START = "<ctrl>+<alt>+s"
HOTKEY_STOP = "<ctrl>+<alt>+x"
HOTKEY_RESET = "<ctrl>+<alt>+r"

# ---------- UI ----------
BG = "#0b0d12"
PANEL = "#121620"
PANEL_2 = "#171c28"
BORDER = "#242b3a"
TEXT = "#f2f4f8"
MUTED = "#8d96a8"
ACCENT = "#7c5cff"
ACCENT_HOVER = "#9278ff"
GREEN = "#39d98a"
RED = "#ff5c70"
YELLOW = "#ffcc66"

DISCORD_BG = "#1e1f22"
DISCORD_PANEL = "#2b2d31"
DISCORD_TEXT = "#f2f3f5"
DISCORD_MUTED = "#b5bac1"
DISCORD_LINK = "#00a8fc"

FONT = "Segoe UI"
MONO = "Consolas"

PRESENCE_KEYS = (
    "details", "state",
    "large_image", "large_text",
    "small_image", "small_text",
    "button1_label", "button1_url",
    "button2_label", "button2_url",
)

DEFAULT_PRESETS = {
    "Coding": {
        "details": "Coding",
        "state": "Deep in the source",
        "large_image": LARGE_IMAGE,
        "large_text": LARGE_TEXT,
        "small_image": "", "small_text": "",
        "button1_label": "", "button1_url": "",
        "button2_label": "", "button2_url": "",
    },
    "Gaming": {
        "details": "Gaming",
        "state": "In a match",
        "large_image": LARGE_IMAGE,
        "large_text": LARGE_TEXT,
        "small_image": "", "small_text": "",
        "button1_label": "", "button1_url": "",
        "button2_label": "", "button2_url": "",
    },
    "AFK": {
        "details": "AFK",
        "state": "Away from keyboard",
        "large_image": LARGE_IMAGE,
        "large_text": LARGE_TEXT,
        "small_image": "", "small_text": "",
        "button1_label": "", "button1_url": "",
        "button2_label": "", "button2_url": "",
    },
}

# Windows registry autostart
