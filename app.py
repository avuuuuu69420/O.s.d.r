"""Main Tkinter application for GSSE26 Discord Rich Presence."""

import json
import os
import queue
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk

from constants import *
from dependencies import (
    CONFIG_PATH,
    HOTKEYS_AVAILABLE,
    PILImage,
    PILImageDraw,
    PILImageFont,
    TRAY_AVAILABLE,
    WINREG_AVAILABLE,
    pynput_keyboard,
    pystray,
    winreg,
)
from pypresence import Presence

class GSSE26RPC:
    def __init__(self, root):
        self.root = root
        self.root.title(WINDOW_TITLE)
        self.root.geometry("1040x790")
        self.root.minsize(960, 700)
        self.root.configure(bg=BG)

        # ---- RPC state (owned by worker thread) ----
        self.rpc = None
        self.rpc_connected = False
        self.want_connected = True
        self.reconnect_backoff = 1
        self.next_connect_attempt = 0.0

        # ---- presence hand-off between Tk thread and worker ----
        self.latest_presence = {}
        self.presence_version = 0
        self.last_applied_version = -1

        # ---- lifecycle ----
        self.running = True
        self.quitting = False
        self.worker = None
        self.tray = None
        self.hotkey_listener = None

        # ---- timer ----
        self.timer_running = False
        self.timer_start = None
        self.base_seconds = 0
        self.elapsed_seconds = 0
        self.discord_epoch = None
        self.last_presence_push = 0

        # ---- cross-thread UI queue (tray / hotkeys / worker -> Tk) ----
        self.ui_queue = queue.Queue()

        # ---- data vars ----
        self.details_var = tk.StringVar(value=DEFAULT_DETAILS)
        self.state_var = tk.StringVar(value=DEFAULT_STATE)
        self.large_image_var = tk.StringVar(value=LARGE_IMAGE)
        self.large_text_var = tk.StringVar(value=LARGE_TEXT)
        self.small_image_var = tk.StringVar(value=SMALL_IMAGE)
        self.small_text_var = tk.StringVar(value=SMALL_TEXT)
        self.button1_label = tk.StringVar(value=BUTTON_1_LABEL)
        self.button1_url = tk.StringVar(value=BUTTON_1_URL)
        self.button2_label = tk.StringVar(value=BUTTON_2_LABEL)
        self.button2_url = tk.StringVar(value=BUTTON_2_URL)

        self.vars = {
            "details": self.details_var,
            "state": self.state_var,
            "large_image": self.large_image_var,
            "large_text": self.large_text_var,
            "small_image": self.small_image_var,
            "small_text": self.small_text_var,
            "button1_label": self.button1_label,
            "button1_url": self.button1_url,
            "button2_label": self.button2_label,
            "button2_url": self.button2_url,
        }

        # ---- config / presets ----
        self.presets = {k: dict(v) for k, v in DEFAULT_PRESETS.items()}
        self.current_preset = tk.StringVar(value="")

        # ---- settings ----
        self.minimize_to_tray_var = tk.BooleanVar(value=True)
        self.run_at_startup_var = tk.BooleanVar(value=False)
        self.hotkeys_enabled_var = tk.BooleanVar(value=HOTKEYS_AVAILABLE)

        self.minutes_var = tk.StringVar(value="0")
        self.seconds_var = tk.StringVar(value="0")

        self.build_style()
        self.build_ui()
        self.add_traces()

        # Load config (touches widgets, so after build_ui)
        self.load_config()

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        # Background services
        self.setup_tray()
        if self.hotkeys_enabled_var.get():
            self.setup_hotkeys()

        # Start loops
        self.root.after(50, self.poll_ui_queue)
        self.root.after(100, self.tick)
        self.start_worker()

        self.log("Application started.")
        if TRAY_AVAILABLE:
            self.log("System tray ready. Closing the window hides it to tray.")
        else:
            self.log("pystray not found — tray features disabled.", "warn")
        if HOTKEYS_AVAILABLE:
            self.log("Global hotkeys active: Ctrl+Alt+S / X / R.")
        else:
            self.log("pynput not found — global hotkeys disabled.", "warn")

    # --------------------------------------------------------
    # Styling
    # --------------------------------------------------------
    def build_style(self):
        style = ttk.Style()
        style.theme_use("clam")

        style.configure("TNotebook", background=BG, borderwidth=0)
        style.configure(
            "TNotebook.Tab",
            background=PANEL,
            foreground=MUTED,
            padding=(22, 10),
            font=(FONT, 10, "bold"),
            borderwidth=0,
        )
        style.map(
            "TNotebook.Tab",
            background=[("selected", PANEL_2)],
            foreground=[("selected", TEXT)],
        )

        style.configure(
            "TEntry",
            fieldbackground=PANEL_2,
            background=PANEL_2,
            foreground=TEXT,
            borderwidth=0,
            padding=9,
        )
        style.configure(
            "TCombobox",
            fieldbackground=PANEL_2,
            background=PANEL_2,
            foreground=TEXT,
            arrowcolor=TEXT,
            borderwidth=0,
            padding=6,
        )
        style.map(
            "TCombobox",
            fieldbackground=[("readonly", PANEL_2)],
            foreground=[("readonly", TEXT)],
        )
        style.configure(
            "TCheckbutton",
            background=BG,
            foreground=TEXT,
            font=(FONT, 10),
            focuscolor=BG,
        )
        style.map(
            "TCheckbutton",
            background=[("active", BG)],
            foreground=[("active", TEXT)],
        )
        style.configure(
            "Vertical.TScrollbar",
            background=PANEL_2,
            troughcolor=PANEL,
            borderwidth=0,
            arrowcolor=MUTED,
        )

    def make_button(self, parent, text, command, kind="normal", width=None):
        if kind == "primary":
            bg, active, fg = ACCENT, ACCENT_HOVER, "white"
        elif kind == "danger":
            bg, active, fg = "#3a1820", "#55212d", RED
        elif kind == "success":
            bg, active, fg = "#163a2b", "#20563e", GREEN
        else:
            bg, active, fg = PANEL_2, "#202738", TEXT

        options = dict(
            text=text,
            command=command,
            bg=bg,
            activebackground=active,
            fg=fg,
            activeforeground=fg,
            relief="flat",
            bd=0,
            highlightthickness=0,
            font=(FONT, 10, "bold"),
            cursor="hand2",
            padx=16,
            pady=9,
        )
        if width:
            options["width"] = width
        return tk.Button(parent, **options)

    def card(self, parent, **kwargs):
        return tk.Frame(
            parent,
            bg=PANEL,
            highlightbackground=BORDER,
            highlightthickness=1,
            **kwargs
        )

    def label(self, parent, text="", size=10, color=TEXT, bold=False, **kwargs):
        return tk.Label(
            parent,
            text=text,
            bg=kwargs.pop("bg", parent.cget("bg")),
            fg=color,
            font=(FONT, size, "bold" if bold else "normal"),
            **kwargs
        )

    # --------------------------------------------------------
    # UI
    # --------------------------------------------------------
    def build_ui(self):
        header = tk.Frame(self.root, bg=BG)
        header.pack(fill="x", padx=28, pady=(20, 10))

        logo = tk.Frame(header, bg=ACCENT, width=48, height=48)
        logo.pack(side="left")
        logo.pack_propagate(False)
        tk.Label(
            logo, text="G", bg=ACCENT, fg="white", font=(FONT, 22, "bold")
        ).pack(expand=True)

        title_box = tk.Frame(header, bg=BG)
        title_box.pack(side="left", padx=14)
        self.label(title_box, APP_NAME, 19, TEXT, True, bg=BG).pack(anchor="w")
        self.label(
            title_box, "Discord Rich Presence • Enhanced", 9, MUTED, bg=BG
        ).pack(anchor="w", pady=(2, 0))

        self.connection_pill = tk.Label(
            header,
            text="●  DISCONNECTED",
            bg="#27151a",
            fg=RED,
            font=(FONT, 9, "bold"),
            padx=13,
            pady=7,
        )
        self.connection_pill.pack(side="right", pady=5)

        # ---- bottom bar ----
        bottom = tk.Frame(self.root, bg=PANEL, height=58)
        bottom.pack(fill="x", side="bottom")
        bottom.pack_propagate(False)

        self.status_text = tk.Label(
            bottom, text="Starting Discord RPC...", bg=PANEL, fg=MUTED,
            font=(FONT, 9)
        )
        self.status_text.pack(side="left", padx=22)

        self.power_button = self.make_button(
            bottom, "DISCONNECT", self.toggle_connection, "primary"
        )
        self.power_button.pack(side="right", padx=18, pady=10)

        self.logs_toggle_btn = self.make_button(
            bottom, "HIDE LOGS", self.toggle_logs
        )
        self.logs_toggle_btn.pack(side="right", pady=10)

        # ---- log panel (bottom, collapsible) ----
        self.build_log_panel()

        # ---- notebook ----
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill="both", expand=True, padx=22, pady=8)

        presence_tab = tk.Frame(notebook, bg=BG)
        timer_tab = tk.Frame(notebook, bg=BG)
        settings_tab = tk.Frame(notebook, bg=BG)

        notebook.add(presence_tab, text="  Presence  ")
        notebook.add(timer_tab, text="  Timer  ")
        notebook.add(settings_tab, text="  Settings  ")

        self.build_presence_tab(presence_tab)
        self.build_timer_tab(timer_tab)
        self.build_settings_tab(settings_tab)

    def build_log_panel(self):
        self.log_frame = tk.Frame(self.root, bg=PANEL)
        self.log_frame.pack(fill="x", side="bottom")

        head = tk.Frame(self.log_frame, bg=PANEL)
        head.pack(fill="x", padx=16, pady=(8, 0))
        self.label(head, "ACTIVITY LOG", 9, MUTED, True, bg=PANEL).pack(
            side="left"
        )
        self.make_button(head, "CLEAR", self.clear_log).pack(side="right")

        body = tk.Frame(self.log_frame, bg=PANEL)
        body.pack(fill="x", padx=16, pady=(6, 10))

        scroll = ttk.Scrollbar(body)
        scroll.pack(side="right", fill="y")

        self.log_text = tk.Text(
            body,
            height=6,
            bg="#0e1118",
            fg=TEXT,
            insertbackground=TEXT,
            relief="flat",
            bd=0,
            font=(MONO, 9),
            wrap="word",
            state="disabled",
            yscrollcommand=scroll.set,
        )
        self.log_text.pack(side="left", fill="x", expand=True)
        scroll.config(command=self.log_text.yview)

    def toggle_logs(self):
        if self.log_frame.winfo_ismapped():
            self.log_frame.pack_forget()
            self.logs_toggle_btn.config(text="SHOW LOGS")
        else:
            self.log_frame.pack(fill="x", side="bottom")
            self.logs_toggle_btn.config(text="HIDE LOGS")

    def build_presence_tab(self, parent):
        # Preset bar
        bar = self.card(parent)
        bar.pack(fill="x", pady=(8, 0))

        self.label(bar, "PRESET", 9, MUTED, True, bg=PANEL).pack(
            side="left", padx=(20, 10), pady=14
        )
        self.preset_combo = ttk.Combobox(
            bar,
            textvariable=self.current_preset,
            state="readonly",
            width=22,
            values=[],
        )
        self.preset_combo.pack(side="left", pady=14)
        self.preset_combo.bind(
            "<<ComboboxSelected>>", lambda e: self.load_preset()
        )

        self.make_button(bar, "LOAD", self.load_preset).pack(
            side="left", padx=(10, 0), pady=14
        )
        self.make_button(bar, "SAVE AS...", self.save_preset_as).pack(
            side="left", padx=6, pady=14
        )
        self.make_button(bar, "DELETE", self.delete_preset, "danger").pack(
            side="left", pady=14
        )

        container = tk.Frame(parent, bg=BG)
        container.pack(fill="both", expand=True)
        container.columnconfigure(0, weight=1, uniform="col")
        container.columnconfigure(1, weight=1, uniform="col")
        container.columnconfigure(2, weight=0)
        container.rowconfigure(0, weight=1)

        left = self.card(container)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 7), pady=8)

        mid = self.card(container)
        mid.grid(row=0, column=1, sticky="nsew", padx=7, pady=8)

        right = self.card(container)
        right.grid(row=0, column=2, sticky="nsew", padx=(7, 0), pady=8)

        # ----- left column -----
        self.label(left, "RICH PRESENCE", 10, MUTED, True, bg=PANEL).pack(
            anchor="w", padx=20, pady=(16, 3)
        )
        self.label(left, "What Discord displays", 9, MUTED, bg=PANEL).pack(
            anchor="w", padx=20, pady=(0, 12)
        )
        self.add_field(left, "Details", self.details_var)
        self.add_field(left, "State", self.state_var)
        self.add_field(left, "Large image key", self.large_image_var)
        self.add_field(left, "Large image hover text", self.large_text_var)

        # ----- middle column -----
        self.label(mid, "IMAGES & BUTTONS", 10, MUTED, True, bg=PANEL).pack(
            anchor="w", padx=20, pady=(16, 3)
        )
        self.label(mid, "Optional asset / button settings", 9, MUTED,
                   bg=PANEL).pack(anchor="w", padx=20, pady=(0, 12))

        self.add_field(mid, "Small image key", self.small_image_var)
        self.add_field(mid, "Small image hover text", self.small_text_var)

        self.label(mid, "Button 1", 9, TEXT, True, bg=PANEL).pack(
            anchor="w", padx=20, pady=(8, 4)
        )
        self.add_field(mid, "Button 1 text", self.button1_label)
        self.add_field(mid, "Button 1 URL", self.button1_url)

        self.label(mid, "Button 2", 9, TEXT, True, bg=PANEL).pack(
            anchor="w", padx=20, pady=(8, 4)
        )
        self.add_field(mid, "Button 2 text", self.button2_label)
        self.add_field(mid, "Button 2 URL", self.button2_url)

        self.make_button(
            mid, "APPLY PRESENCE", self.apply_presence, "primary"
        ).pack(anchor="w", padx=20, pady=(14, 18))

        # ----- right column: live preview -----
        self.build_preview(right)

    def add_field(self, parent, title, variable):
        self.label(parent, title, 9, MUTED, bg=PANEL).pack(
            anchor="w", padx=20, pady=(4, 3)
        )
        entry = ttk.Entry(parent, textvariable=variable)
        entry.pack(fill="x", padx=20, pady=(0, 6))

    def build_preview(self, parent):
        self.label(parent, "LIVE PREVIEW", 10, MUTED, True, bg=PANEL).pack(
            anchor="w", padx=20, pady=(16, 3)
        )
        self.label(parent, "Approximate Discord card", 9, MUTED,
                   bg=PANEL).pack(anchor="w", padx=20, pady=(0, 12))

        disc = tk.Frame(
            parent, bg=DISCORD_BG,
            highlightbackground=DISCORD_PANEL, highlightthickness=1
        )
        disc.pack(fill="x", padx=20, pady=(0, 18))

        body = tk.Frame(disc, bg=DISCORD_BG)
        body.pack(fill="x", padx=14, pady=14)

        img_wrap = tk.Frame(body, bg=DISCORD_BG)
        img_wrap.pack(side="left", anchor="n")
        self.preview_canvas = tk.Canvas(
            img_wrap, width=84, height=84, bg=DISCORD_BG,
            highlightthickness=0
        )
        self.preview_canvas.pack()

        text_box = tk.Frame(body, bg=DISCORD_BG)
        text_box.pack(side="left", fill="x", expand=True, padx=(12, 0))

        self.preview_app = tk.Label(
            text_box, text=APP_NAME, bg=DISCORD_BG, fg=DISCORD_MUTED,
            font=(FONT, 8), anchor="w", justify="left", wraplength=150
        )
        self.preview_app.pack(anchor="w")

        self.preview_details = tk.Label(
            text_box, text="", bg=DISCORD_BG, fg=DISCORD_TEXT,
            font=(FONT, 11, "bold"), anchor="w", justify="left",
            wraplength=150
        )
        self.preview_details.pack(anchor="w", pady=(2, 0))

        self.preview_state = tk.Label(
            text_box, text="", bg=DISCORD_BG, fg=DISCORD_MUTED,
            font=(FONT, 9), anchor="w", justify="left", wraplength=150
        )
        self.preview_state.pack(anchor="w", pady=(1, 0))

        self.preview_timer = tk.Label(
            text_box, text="", bg=DISCORD_BG, fg=DISCORD_MUTED,
            font=(FONT, 9), anchor="w"
        )
        self.preview_timer.pack(anchor="w", pady=(3, 0))

        self.preview_buttons_box = tk.Frame(disc, bg=DISCORD_BG)
        self.preview_buttons_box.pack(fill="x", padx=14, pady=(0, 14))

    def build_timer_tab(self, parent):
        top = self.card(parent)
        top.pack(fill="x", pady=8)

        self.label(top, "ACTIVITY TIMER", 10, MUTED, True, bg=PANEL).pack(
            anchor="w", padx=20, pady=(18, 2)
        )
        self.label(
            top,
            "The timer is synchronized with Discord's elapsed-time display.",
            9, MUTED, bg=PANEL
        ).pack(anchor="w", padx=20, pady=(0, 12))

        timer_box = tk.Frame(top, bg=PANEL)
        timer_box.pack(fill="x", padx=20, pady=(0, 18))

        self.timer_display = tk.Label(
            timer_box, text="00:00", bg=PANEL, fg=TEXT,
            font=(FONT, 42, "bold")
        )
        self.timer_display.pack(side="left")

        self.timer_state = tk.Label(
            timer_box, text="READY", bg="#222936", fg=MUTED,
            font=(FONT, 9, "bold"), padx=10, pady=5
        )
        self.timer_state.pack(side="right", pady=10)

        controls = self.card(parent)
        controls.pack(fill="x", pady=8)

        self.label(controls, "CUSTOM START TIME", 10, MUTED, True,
                   bg=PANEL).pack(anchor="w", padx=20, pady=(18, 10))

        row = tk.Frame(controls, bg=PANEL)
        row.pack(fill="x", padx=20)

        self.label(row, "Minutes", 9, MUTED, bg=PANEL).pack(side="left")
        ttk.Entry(row, textvariable=self.minutes_var, width=9).pack(
            side="left", padx=(8, 20)
        )
        self.label(row, "Seconds", 9, MUTED, bg=PANEL).pack(side="left")
        ttk.Entry(row, textvariable=self.seconds_var, width=9).pack(
            side="left", padx=8
        )

        btns = tk.Frame(controls, bg=PANEL)
        btns.pack(fill="x", padx=20, pady=18)

        self.make_button(btns, "▶  START", self.start_timer,
                         "success").pack(side="left")
        self.make_button(btns, "■  STOP", self.stop_timer,
                         "danger").pack(side="left", padx=8)
        self.make_button(btns, "↻  RESET", self.reset_timer).pack(side="left")

        self.label(
            controls,
            "Hotkeys: Ctrl+Alt+S = start   •   Ctrl+Alt+X = stop   •   "
            "Ctrl+Alt+R = reset",
            9, MUTED, bg=PANEL
        ).pack(anchor="w", padx=20, pady=(0, 18))

    def build_settings_tab(self, parent):
        card = self.card(parent)
        card.pack(fill="x", pady=8)

        self.label(card, "BACKGROUND & SYSTEM", 10, MUTED, True,
                   bg=PANEL).pack(anchor="w", padx=20, pady=(18, 12))

        tray_state = "available" if TRAY_AVAILABLE else "unavailable (install pystray)"
        run_state = "available" if WINREG_AVAILABLE else "Windows only"
        hot_state = "available" if HOTKEYS_AVAILABLE else "unavailable (install pynput)"

        ttk.Checkbutton(
            card,
            text=f"Minimize to system tray on close  —  tray {tray_state}",
            variable=self.minimize_to_tray_var,
            command=self.save_config,
        ).pack(anchor="w", padx=20, pady=6)

        self.startup_cb = ttk.Checkbutton(
            card,
            text=f"Run at Windows startup  —  {run_state}",
            variable=self.run_at_startup_var,
            command=self.on_startup_toggle,
        )
        self.startup_cb.pack(anchor="w", padx=20, pady=6)
        if not WINREG_AVAILABLE:
            self.startup_cb.state(["disabled"])

        self.hotkey_cb = ttk.Checkbutton(
            card,
            text=f"Enable global hotkeys  —  {hot_state}",
            variable=self.hotkeys_enabled_var,
            command=self.on_hotkeys_toggle,
        )
        self.hotkey_cb.pack(anchor="w", padx=20, pady=6)
        if not HOTKEYS_AVAILABLE:
            self.hotkey_cb.state(["disabled"])

        self.label(
            card,
            "Ctrl+Alt+S = start timer   •   Ctrl+Alt+X = stop   •   "
            "Ctrl+Alt+R = reset",
            9, MUTED, bg=PANEL
        ).pack(anchor="w", padx=20, pady=(2, 14))

        path_row = tk.Frame(card, bg=PANEL)
        path_row.pack(fill="x", padx=20, pady=(0, 18))
        self.label(path_row, f"Config: {CONFIG_PATH}", 9, MUTED,
                   bg=PANEL).pack(side="left")
        self.make_button(
            path_row, "OPEN FOLDER", self.open_config_folder
        ).pack(side="right")

    # --------------------------------------------------------
    # Cross-thread plumbing
    # --------------------------------------------------------
    def post_ui(self, fn):
        """Schedule a callable to run on the Tk main thread."""
        self.ui_queue.put(fn)

    def poll_ui_queue(self):
        try:
            while True:
                fn = self.ui_queue.get_nowait()
                try:
                    fn()
                except Exception:
                    pass
        except queue.Empty:
            pass
        if self.running:
            self.root.after(50, self.poll_ui_queue)

    def log(self, message, level="info"):
        prefix = {
            "info": "·",
            "warn": "!",
            "error": "x",
        }.get(level, "·")
        line = f"[{time.strftime('%H:%M:%S')}] {prefix} {message}\n"
        self.post_ui(lambda: self._append_log(line))

    def _append_log(self, line):
        if not hasattr(self, "log_text"):
            return
        try:
            self.log_text.config(state="normal")
            self.log_text.insert("end", line)
            # Trim old lines to keep memory bounded.
            line_count = int(self.log_text.index("end-1c").split(".")[0])
            if line_count > 400:
                self.log_text.delete("1.0", "120.0")
            self.log_text.see("end")
            self.log_text.config(state="disabled")
        except Exception:
            pass

    def clear_log(self):
        try:
            self.log_text.config(state="normal")
            self.log_text.delete("1.0", "end")
            self.log_text.config(state="disabled")
        except Exception:
            pass

    def add_traces(self):
        for var in self.vars.values():
            var.trace_add("write", lambda *a: self.update_preview())
        self.update_preview()

    # --------------------------------------------------------
    # Presence data (built on the Tk thread)
    # --------------------------------------------------------
    def collect_presence(self):
        return {k: v.get() for k, v in self.vars.items()}

    def apply_presence_dict(self, data):
        for key, var in self.vars.items():
            if key in data and data[key] is not None:
                var.set(str(data[key]))

    def build_presence_kwargs(self):
        kwargs = {
            "details": self.details_var.get().strip() or APP_NAME,
            "state": self.current_state(),
            "large_image": self.large_image_var.get().strip() or None,
            "large_text": self.large_text_var.get().strip() or None,
        }

        small = self.small_image_var.get().strip()
        if small:
            kwargs["small_image"] = small
            kwargs["small_text"] = self.small_text_var.get().strip() or None

        buttons = []
        if self.button1_label.get().strip() and self.button1_url.get().strip():
            buttons.append({
                "label": self.button1_label.get().strip(),
                "url": self.button1_url.get().strip(),
            })
        if self.button2_label.get().strip() and self.button2_url.get().strip():
            buttons.append({
                "label": self.button2_label.get().strip(),
                "url": self.button2_url.get().strip(),
            })
        if buttons:
            kwargs["buttons"] = buttons

        if self.timer_running and self.discord_epoch is not None:
            kwargs["start"] = int(self.discord_epoch)

        return {k: v for k, v in kwargs.items() if v is not None}

    def request_presence_update(self):
        """Publish the newest presence payload for the worker thread."""
        if not self.rpc_connected:
            return
        self.latest_presence = self.build_presence_kwargs()
        self.presence_version += 1

    def current_state(self):
        if self.timer_running:
            custom = self.state_var.get().strip() or "Playing"
            return f"{custom} • {time.strftime('%H:%M:%S')}"
        return self.state_var.get().strip() or "Idle"

    def collect_buttons(self):
        out = []
        if self.button1_label.get().strip() and self.button1_url.get().strip():
            out.append(self.button1_label.get().strip())
        if self.button2_label.get().strip() and self.button2_url.get().strip():
            out.append(self.button2_label.get().strip())
        return out

    def apply_presence(self):
        if not self.rpc_connected:
            messagebox.showwarning("RPC offline", "Connect Discord RPC first.")
            return
        self.request_presence_update()
        self.status_text.config(text="Presence updated.")
        self.log("Presence applied.")

    # --------------------------------------------------------
    # Live preview
    # --------------------------------------------------------
    def draw_preview_image(self):
        c = self.preview_canvas
        c.delete("all")
        c.create_rectangle(0, 0, 84, 84, fill=DISCORD_PANEL, outline="#3a3c42")

        large = self.large_image_var.get().strip()
        if large:
            c.create_text(42, 42, text=large[:2].upper(), fill=ACCENT,
                          font=(FONT, 20, "bold"))
        else:
            c.create_text(42, 42, text="IMG", fill="#5a5d64",
                          font=(FONT, 10, "bold"))

        small = self.small_image_var.get().strip()
        if small:
            c.create_oval(58, 58, 84, 84, fill=ACCENT, outline=DISCORD_BG,
                          width=2)
            c.create_text(71, 71, text=small[:2].upper(), fill="white",
                          font=(FONT, 8, "bold"))

    def update_preview(self):
        if not hasattr(self, "preview_details"):
            return
        self.preview_details.config(
            text=self.details_var.get().strip() or APP_NAME
        )
        self.preview_state.config(
            text=self.state_var.get().strip() or "Idle"
        )
        self.draw_preview_image()

        for child in self.preview_buttons_box.winfo_children():
            child.destroy()
        for label in self.collect_buttons():
            row = tk.Frame(
                self.preview_buttons_box, bg=DISCORD_PANEL,
                highlightbackground="#3a3c42", highlightthickness=1
            )
            row.pack(fill="x", pady=2)
            tk.Label(
                row, text=label, bg=DISCORD_PANEL, fg=DISCORD_LINK,
                font=(FONT, 9, "bold")
            ).pack(pady=6)

        self.update_preview_timer()

    def update_preview_timer(self):
        if not hasattr(self, "preview_timer"):
            return
        if self.timer_running:
            self.preview_timer.config(
                text=f"⏱  {self.format_time(self.get_elapsed())} elapsed"
            )
        else:
            self.preview_timer.config(text="")

    # --------------------------------------------------------
    # Config / presets
    # --------------------------------------------------------
    def default_config(self):
        return {
            "schema_version": CONFIG_SCHEMA_VERSION,
            "presence": {
                "details": DEFAULT_DETAILS,
                "state": DEFAULT_STATE,
                "large_image": LARGE_IMAGE,
                "large_text": LARGE_TEXT,
                "small_image": SMALL_IMAGE,
                "small_text": SMALL_TEXT,
                "button1_label": BUTTON_1_LABEL,
                "button1_url": BUTTON_1_URL,
                "button2_label": BUTTON_2_LABEL,
                "button2_url": BUTTON_2_URL,
            },
            "presets": {k: dict(v) for k, v in DEFAULT_PRESETS.items()},
            "settings": {
                "minimize_to_tray": True,
                "hotkeys_enabled": HOTKEYS_AVAILABLE,
            },
        }

    def load_config(self):
        defaults = self.default_config()
        data = {}

        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                if not isinstance(data, dict):
                    raise ValueError("config root is not an object")
            except Exception as exc:
                self.log(f"Config load failed ({exc}); using defaults.",
                         "warn")
                data = {}

        presence = data.get("presence", {})
        for key, var in self.vars.items():
            var.set(str(presence.get(key, defaults["presence"][key])))

        presets = data.get("presets")
        if isinstance(presets, dict) and presets:
            cleaned = {}
            for name, values in list(presets.items())[:50]:
                if isinstance(values, dict):
                    cleaned[str(name)] = {
                        k: str(values.get(k, "")) for k in PRESENCE_KEYS
                    }
            self.presets = cleaned or defaults["presets"]
        else:
            self.presets = defaults["presets"]

        settings = data.get("settings", {})
        self.minimize_to_tray_var.set(
            bool(settings.get("minimize_to_tray", True))
        )
        self.hotkeys_enabled_var.set(
            bool(settings.get("hotkeys_enabled", HOTKEYS_AVAILABLE))
            and HOTKEYS_AVAILABLE
        )

        self.refresh_preset_list()
        self.run_at_startup_var.set(self.is_run_at_startup())
        self.update_preview()

    def save_config(self):
        data = {
            "schema_version": CONFIG_SCHEMA_VERSION,
            "presence": self.collect_presence(),
            "presets": self.presets,
            "settings": {
                "minimize_to_tray": bool(self.minimize_to_tray_var.get()),
                "hotkeys_enabled": bool(self.hotkeys_enabled_var.get()),
            },
        }
        try:
            tmp = CONFIG_PATH + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2)
            os.replace(tmp, CONFIG_PATH)
        except Exception as exc:
            self.log(f"Config save failed: {exc}", "error")

    def refresh_preset_list(self):
        names = sorted(self.presets.keys())
        self.preset_combo.configure(values=names)
        if self.current_preset.get() not in names:
            self.current_preset.set(names[0] if names else "")

    def load_preset(self):
        name = self.current_preset.get()
        if name not in self.presets:
            return
        self.apply_presence_dict(self.presets[name])
        self.update_preview()
        self.log(f"Loaded preset '{name}'.")
        self.request_presence_update()
        self.status_text.config(text=f"Preset '{name}' loaded.")

    def save_preset_as(self):
        name = simpledialog.askstring(
            "Save preset", "Preset name:", parent=self.root
        )
        if not name:
            return
        name = name.strip()
        if not name:
            return
        if len(self.presets) >= 50 and name not in self.presets:
            messagebox.showwarning("Too many presets",
                                   "Limit is 50 presets.")
            return
        self.presets[name] = self.collect_presence()
        self.refresh_preset_list()
        self.current_preset.set(name)
        self.save_config()
        self.log(f"Saved preset '{name}'.")
        self.status_text.config(text=f"Saved preset '{name}'.")

    def delete_preset(self):
        name = self.current_preset.get()
        if not name or name not in self.presets:
            return
        if not messagebox.askyesno(
            "Delete preset", f"Delete preset '{name}'?"
        ):
            return
        del self.presets[name]
        self.refresh_preset_list()
        self.save_config()
        self.log(f"Deleted preset '{name}'.")

    def open_config_folder(self):
        folder = os.path.dirname(CONFIG_PATH)
        try:
            if os.name == "nt":
                os.startfile(folder)  # noqa: S606
            elif sys.platform == "darwin":
                subprocess.Popen(["open", folder])
            else:
                subprocess.Popen(["xdg-open", folder])
        except Exception as exc:
            self.log(f"Could not open folder: {exc}", "warn")

    # --------------------------------------------------------
    # Run at startup (Windows registry)
    # --------------------------------------------------------
    def startup_command(self):
        if getattr(sys, "frozen", False):
            return f'"{os.path.abspath(sys.executable)}"'
        pythonw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
        if not os.path.exists(pythonw):
            pythonw = sys.executable
        script = os.path.abspath(sys.argv[0])
        return f'"{pythonw}" "{script}"'

    def is_run_at_startup(self):
        if not WINREG_AVAILABLE:
            return False
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, WIN_RUN_KEY) as key:
                winreg.QueryValueEx(key, WIN_RUN_VALUE)
            return True
        except Exception:
            return False

    def on_startup_toggle(self):
        enable = bool(self.run_at_startup_var.get())
        if not WINREG_AVAILABLE:
            self.log("Autostart requires Windows.", "warn")
            return
        try:
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, WIN_RUN_KEY) as key:
                if enable:
                    winreg.SetValueEx(
                        key, WIN_RUN_VALUE, 0, winreg.REG_SZ,
                        self.startup_command()
                    )
                else:
                    try:
                        winreg.DeleteValue(key, WIN_RUN_VALUE)
                    except FileNotFoundError:
                        pass
            self.log("Run at startup " + ("enabled." if enable else "disabled."))
        except Exception as exc:
            self.log(f"Autostart change failed: {exc}", "error")
            # Re-sync checkbox with the real registry state.
            self.run_at_startup_var.set(self.is_run_at_startup())

    # --------------------------------------------------------
    # Timer
    # --------------------------------------------------------
    def get_elapsed(self):
        if not self.timer_running or self.timer_start is None:
            return self.base_seconds
        return max(0, self.base_seconds + int(time.time() - self.timer_start))

    @staticmethod
    def format_time(total):
        total = max(0, int(total))
        hours, remainder = divmod(total, 3600)
        minutes, seconds = divmod(remainder, 60)
        if hours:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        return f"{minutes:02d}:{seconds:02d}"

    def start_timer(self):
        if not self.rpc_connected:
            messagebox.showwarning("RPC offline", "Connect Discord RPC first.")
            return
        if self.timer_running:
            return
        try:
            minutes = int(self.minutes_var.get())
            seconds = int(self.seconds_var.get())
            if minutes < 0 or seconds < 0:
                raise ValueError
            self.base_seconds = minutes * 60 + seconds
        except ValueError:
            messagebox.showerror(
                "Invalid time",
                "Minutes and seconds must be non-negative whole numbers."
            )
            return

        self.timer_start = time.time()
        self.discord_epoch = self.timer_start - self.base_seconds
        self.timer_running = True
        self.timer_state.config(text="RUNNING", bg="#123024", fg=GREEN)
        self.status_text.config(text="Activity timer running.")
        self.log("Timer started.")
        self.request_presence_update()
        self.update_preview_timer()

    def stop_timer(self):
        if not self.timer_running:
            return
        self.base_seconds = self.get_elapsed()
        self.timer_running = False
        self.timer_start = None
        self.timer_state.config(text="PAUSED", bg="#302916", fg=YELLOW)
        self.status_text.config(text="Timer paused.")
        self.log("Timer paused.")
        self.update_timer_display()
        self.request_presence_update()
        self.update_preview_timer()

    def reset_timer(self):
        self.timer_running = False
        self.timer_start = None
        self.discord_epoch = None
        self.base_seconds = 0
        self.elapsed_seconds = 0
        self.timer_state.config(text="READY", bg="#222936", fg=MUTED)
        self.update_timer_display()
        self.log("Timer reset.")
        self.request_presence_update()
        self.update_preview_timer()

    def update_timer_display(self):
        value = self.get_elapsed()
        self.elapsed_seconds = value
        self.timer_display.config(text=self.format_time(value))

    # --------------------------------------------------------
    # Main-thread tick (UI + presence cadence)
    # --------------------------------------------------------
    def tick(self):
        if not self.running:
            return
        if self.timer_running:
            self.update_timer_display()
            self.update_preview_timer()
            now = time.time()
            if now - self.last_presence_push >= 1:
                self.request_presence_update()
                self.last_presence_push = now
        self.root.after(250, self.tick)

    # --------------------------------------------------------
    # RPC worker (owns all pypresence access)
    # --------------------------------------------------------
    def start_worker(self):
        self.worker = threading.Thread(target=self.rpc_worker, daemon=True)
        self.worker.start()

    def rpc_worker(self):
        while self.running:
            # ---- user asked to disconnect ----
            if not self.want_connected:
                if self.rpc_connected:
                    self._safe_close()
                    self.rpc_connected = False
                    self.post_ui(self.on_disconnected)
                time.sleep(0.2)
                continue

            # ---- not connected: attempt connect with backoff ----
            if not self.rpc_connected:
                now = time.time()
                if now >= self.next_connect_attempt:
                    try:
                        rpc = Presence(CLIENT_ID)
                        rpc.connect()
                        self.rpc = rpc
                        self.rpc_connected = True
                        self.reconnect_backoff = 1
                        self.post_ui(self.on_connected)
                    except Exception as exc:
                        self.rpc = None
                        self.rpc_connected = False
                        self.post_ui(
                            lambda e=exc: self.on_connect_failed(e)
                        )
                        self.next_connect_attempt = (
                            time.time() + self.reconnect_backoff
                        )
                        self.reconnect_backoff = min(
                            self.reconnect_backoff * 2, 30
                        )
                time.sleep(0.25)
                continue

            # ---- connected: push newest presence if changed ----
            if self.presence_version != self.last_applied_version:
                data = self.latest_presence
                self.last_applied_version = self.presence_version
                if data:
                    try:
                        self.rpc.update(**data)
                    except Exception as exc:
                        self.post_ui(
                            lambda e=exc: self.on_update_failed(e)
                        )
            time.sleep(0.1)

    def _safe_close(self):
        if self.rpc:
            try:
                self.rpc.close()
            except Exception:
                pass
        self.rpc = None

    def on_connected(self):
        self.set_connection_ui(True)
        self.status_text.config(text="Discord RPC is connected.")
        self.log("Connected to Discord.")
        self.request_presence_update()

    def on_disconnected(self):
        self.set_connection_ui(False)
        self.status_text.config(text="RPC disconnected.")
        self.log("Disconnected from Discord.")

    def on_connect_failed(self, exc):
        self.set_connection_ui(False)
        self.status_text.config(
            text=f"Discord connection failed: {exc} (retrying)"
        )
        self.log(f"Connect failed: {exc} — retrying.", "warn")

    def on_update_failed(self, exc):
        self.log(f"RPC update failed: {exc}", "error")
        # Force a reconnect on the next worker pass.
        self.rpc_connected = False
        self._safe_close()
        self.next_connect_attempt = 0.0

    def toggle_connection(self):
        if self.want_connected:
            self.want_connected = False
            self.status_text.config(text="Disconnecting...")
        else:
            self.want_connected = True
            self.reconnect_backoff = 1
            self.next_connect_attempt = 0.0
            self.status_text.config(text="Connecting...")

    def set_connection_ui(self, connected):
        if connected:
            self.connection_pill.config(text="●  CONNECTED", bg="#123024",
                                        fg=GREEN)
            self.power_button.config(text="DISCONNECT")
        else:
            self.connection_pill.config(text="●  DISCONNECTED",
                                        bg="#27151a", fg=RED)
            self.power_button.config(text="CONNECT")

    # --------------------------------------------------------
    # Global hotkeys
    # --------------------------------------------------------
    def setup_hotkeys(self):
        if not HOTKEYS_AVAILABLE or self.hotkey_listener is not None:
            return
        try:
            self.hotkey_listener = pynput_keyboard.GlobalHotKeys({
                HOTKEY_START: lambda: self.post_ui(self.start_timer),
                HOTKEY_STOP: lambda: self.post_ui(self.stop_timer),
                HOTKEY_RESET: lambda: self.post_ui(self.reset_timer),
            })
            self.hotkey_listener.daemon = True
            self.hotkey_listener.start()
            self.log("Global hotkeys enabled.")
        except Exception as exc:
            self.hotkey_listener = None
            self.log(f"Hotkeys failed to start: {exc}", "error")

    def stop_hotkeys(self):
        if self.hotkey_listener is None:
            return
        try:
            self.hotkey_listener.stop()
        except Exception:
            pass
        self.hotkey_listener = None

    def on_hotkeys_toggle(self):
        if self.hotkeys_enabled_var.get():
            self.setup_hotkeys()
        else:
            self.stop_hotkeys()
            self.log("Global hotkeys disabled.")
        self.save_config()

    # --------------------------------------------------------
    # System tray
    # --------------------------------------------------------
    def build_tray_image(self):
        size = 64
        img = PILImage.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = PILImageDraw.Draw(img)
        draw.rounded_rectangle((2, 2, size - 2, size - 2), radius=16,
                               fill=(124, 92, 255, 255))
        try:
            font = PILImageFont.truetype("arialbd.ttf", 34)
        except Exception:
            try:
                font = PILImageFont.truetype("arial.ttf", 34)
            except Exception:
                font = None
        if font is not None:
            draw.text((size / 2, size / 2), "G", fill="white", font=font,
                      anchor="mm")
        else:
            draw.text((size / 2, size / 2), "G", fill="white", anchor="mm")
        return img

    def setup_tray(self):
        if not TRAY_AVAILABLE:
            return
        try:
            image = self.build_tray_image()
            menu = pystray.Menu(
                pystray.MenuItem(
                    "Show window",
                    lambda: self.post_ui(self.show_window),
                    default=True,
                ),
                pystray.MenuItem(
                    "Hide to tray",
                    lambda: self.post_ui(self.hide_window),
                ),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem(
                    "Connect / Disconnect",
                    lambda: self.post_ui(self.toggle_connection),
                ),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem(
                    "Quit", lambda: self.post_ui(self.real_quit)
                ),
            )
            self.tray = pystray.Icon(WIN_RUN_VALUE, image, WINDOW_TITLE, menu)
            threading.Thread(target=self.tray.run, daemon=True).start()
        except Exception as exc:
            self.tray = None
            self.log(f"Tray setup failed: {exc}", "warn")

    def show_window(self):
        try:
            self.root.deiconify()
            self.root.lift()
            self.root.focus_force()
        except Exception:
            pass

    def hide_window(self):
        try:
            self.root.withdraw()
            self.log("Window hidden to tray.")
        except Exception:
            pass

    # --------------------------------------------------------
    # Shutdown
    # --------------------------------------------------------
    def on_close(self):
        """Close button: hide to tray if enabled, else really quit."""
        self.save_config()
        if self.minimize_to_tray_var.get() and self.tray is not None:
            self.hide_window()
            return
        self.real_quit()

    def real_quit(self):
        if self.quitting:
            return
        self.quitting = True
        self.save_config()

        self.running = False
        self.want_connected = False

        if self.worker and self.worker.is_alive():
            try:
                self.worker.join(timeout=1.0)
            except Exception:
                pass

        self._safe_close()
        self.stop_hotkeys()

        if self.tray is not None:
            try:
                self.tray.stop()
            except Exception:
                pass
            self.tray = None

        try:
            self.root.destroy()
        except Exception:
            pass
