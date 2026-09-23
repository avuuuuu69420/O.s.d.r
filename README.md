# GSSE26 Discord Rich Presence

Split version of the original single-file GSSE26 Discord Rich Presence app.

## Files

- `main.py` — executable entry point
- `app.py` — Tkinter GUI, timer, presets, RPC worker, tray, and hotkeys
- `constants.py` — app defaults, Discord RPC settings, UI constants
- `dependencies.py` — dependency/bootstrap and platform helpers
- `requirements.txt` — required dependency
- `requirements-optional.txt` — optional tray/hotkey dependencies

## Run

```bash
python -m pip install -r requirements.txt
python main.py
```

Optional features:

```bash
python -m pip install -r requirements-optional.txt
```

The original app behavior is retained, including the Discord Rich Presence
settings, timer, presets, reconnect loop, Windows startup option, tray
support, and global hotkeys when their optional dependencies are available.
