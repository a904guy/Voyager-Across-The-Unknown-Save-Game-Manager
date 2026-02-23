#!/usr/bin/env python3
"""
Star Trek Voyager - Across The Unknown
Save Game Manager

Backs up and restores game save files.
F5  = Quick Save (creates a timestamped backup of current saves)
F9  = Quick Load (restores the most recent backup)

Backups are stored in:
  Windows : %APPDATA%/VoyagerSaveManager/backups/
  Linux   : ~/.local/share/VoyagerSaveManager/backups/
"""

import os
import re
import sys
import shutil
import platform
import threading
import time
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk

try:
    from importlib.resources import files
except ImportError:
    from importlib_resources import files

try:
    from pynput import keyboard as pynput_keyboard
    PYNPUT_AVAILABLE = True
except ImportError:
    PYNPUT_AVAILABLE = False

def _resource(filename: str) -> str:
    """Resolve a bundled resource path (works in package and PyInstaller --onefile)."""
    if getattr(sys, "_MEIPASS", None):
        # PyInstaller runtime
        return os.path.join(sys._MEIPASS, filename)
    else:
        # Package installation
        package_files = files("voyager_save_manager")
        return str(package_files.joinpath(filename))


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

APP_NAME      = "VoyagerSaveManager"
STEAM_APP_ID  = "2643390"

# Dark theme colours
C_BG_DARK   = "#0d1117"
C_BG_MID    = "#161b22"
C_BG_LIGHT  = "#21262d"
C_FG_MAIN   = "#c9d1d9"
C_FG_DIM    = "#8b949e"
C_ACCENT    = "#58a6ff"
C_GREEN     = "#3fb950"
C_RED       = "#f85149"
C_YELLOW    = "#d29922"


# ---------------------------------------------------------------------------
# Save-directory detection
# ---------------------------------------------------------------------------

def _parse_vdf_paths(vdf_path: Path) -> list[Path]:
    """Extract library paths from Steam's libraryfolders.vdf."""
    results: list[Path] = []
    try:
        text = vdf_path.read_text(encoding="utf-8", errors="ignore")
        for m in re.finditer(r'"path"\s*"([^"]+)"', text):
            raw = m.group(1).replace("\\\\", os.sep).replace("\\", os.sep)
            p = Path(raw)
            if p.exists() and p not in results:
                results.append(p)
    except Exception:
        pass
    return results


def _steam_library_roots_windows() -> list[Path]:
    """Return all Steam library root folders on Windows."""
    roots: list[Path] = []

    candidates = [
        Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Steam",
        Path(os.environ.get("ProgramFiles",      r"C:\Program Files"))       / "Steam",
        Path(os.environ.get("LOCALAPPDATA",      ""))                        / "Steam",
        Path(os.environ.get("USERPROFILE",       ""))                        / "Steam",
    ]

    for steam_root in candidates:
        vdf = steam_root / "steamapps" / "libraryfolders.vdf"
        if vdf.exists():
            for p in _parse_vdf_paths(vdf):
                if p not in roots:
                    roots.append(p)
            if steam_root not in roots:
                roots.append(steam_root)

    return roots


def find_game_save_dir() -> Path | None:
    """
    Auto-detect the game's active save directory.
    Returns the first existing path found, or None.
    """
    system = platform.system()
    candidates: list[Path] = []

    if system == "Windows":
        local = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        # Standard AppData location (non-Steam or Microsoft Store)
        candidates.append(local / "STVoyager" / "Saved" / "SaveGames")

        # Steam library locations
        for lib in _steam_library_roots_windows():
            base = (lib / "steamapps" / "common"
                    / "Star Trek Voyager - Across the Unknown"
                    / "STVoyager" / "Saved" / "SaveGames")
            if base.exists():
                try:
                    # Subdirs are 64-bit Steam IDs (≥15 digit numbers)
                    id_dirs = [
                        d for d in base.iterdir()
                        if d.is_dir() and d.name.isdigit() and len(d.name) >= 15
                    ]
                    candidates.extend(id_dirs) if id_dirs else candidates.append(base)
                except PermissionError:
                    candidates.append(base)
    else:
        # Linux – Proton/Wine prefix paths
        home = Path.home()
        wine_rel = Path("pfx/drive_c/users/steamuser/AppData/Local"
                        "/STVoyager/Saved/SaveGames")
        compat   = Path(f"steamapps/compatdata/{STEAM_APP_ID}")

        candidates = [
            home / ".local/share/Steam"                                    / compat / wine_rel,
            home / "snap/steam/common/.local/share/Steam"                  / compat / wine_rel,
            home / ".var/app/com.valvesoftware.Steam/.local/share/Steam"   / compat / wine_rel,
        ]

    for p in candidates:
        if p.exists():
            return p

    return None


def get_backup_base_dir() -> Path:
    if platform.system() == "Windows":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    else:
        base = Path.home() / ".local" / "share"
    return base / APP_NAME / "backups"


# ---------------------------------------------------------------------------
# Animated save / load overlay
# ---------------------------------------------------------------------------

class SaveLoadOverlay:
    """
    Borderless always-on-top overlay shown while a save or restore is running.

    Displays badge.png spinning in the centre of the screen:
      Save    (mode='save')  → clockwise,         amber label
      Restore (mode='load')  → counter-clockwise, cyan  label

    Always shown for at least MIN_SECS seconds regardless of operation speed.
    dismiss() is safe to call from a background thread.
    """

    IMG_SIZE = 200
    WIN_W    = 280
    WIN_H    = 270
    FPS      = 30
    MIN_SECS = 2.0
    SPIN_DEG = 4          # degrees per frame

    _SAVE_COLOR = "#FFB300"
    _LOAD_COLOR = "#00BCD4"
    _BG         = "#06080f"

    def __init__(self, parent: tk.Tk, mode: str):
        self.mode            = mode
        self._angle          = 0.0
        self._prog           = 0.0
        self._alpha          = 0.0
        self._phase          = "fadein"
        self._alive          = True
        self._dismiss_wanted = False
        self._show_until     = time.monotonic() + self.MIN_SECS

        self._color    = self._SAVE_COLOR if mode == "save" else self._LOAD_COLOR
        self._spin_dir = 1                if mode == "save" else -1   # +1=CW, -1=CCW
        self._label    = "SAVING"         if mode == "save" else "RESTORING"

        # Load and pre-scale badge image once (graceful fallback if missing)
        try:
            raw = Image.open(_resource("badge.png")).convert("RGBA")
            self._base_img = raw.resize((self.IMG_SIZE, self.IMG_SIZE), Image.LANCZOS)
        except Exception:
            self._base_img = None

        self._win = tk.Toplevel(parent)
        try:
            self._win.overrideredirect(True)
        except Exception:
            pass
        self._win.attributes("-topmost", True)
        self._win.attributes("-alpha", 0.0)
        self._win.configure(bg=self._BG)
        self._win.resizable(False, False)

        self._cv = tk.Canvas(
            self._win, width=self.WIN_W, height=self.WIN_H,
            bg=self._BG, highlightthickness=0,
        )
        self._cv.pack()

        # Centre on screen
        self._win.update_idletasks()
        sw = self._win.winfo_screenwidth()
        sh = self._win.winfo_screenheight()
        self._win.geometry(
            f"{self.WIN_W}x{self.WIN_H}"
            f"+{(sw - self.WIN_W) // 2}+{(sh - self.WIN_H) // 2}"
        )

        self._tk_img = None   # strong reference so GC doesn't collect it
        self._tick()

    # ------------------------------------------------------------------

    def _draw(self):
        cv = self._cv
        cv.delete("all")

        cx     = self.WIN_W // 2
        img_cy = self.WIN_H // 2 - 22

        if self._base_img:
            try:
                rotated      = self._base_img.rotate(
                    self._angle, resample=Image.BICUBIC, expand=False
                )
                self._tk_img = ImageTk.PhotoImage(rotated)
                cv.create_image(cx, img_cy, image=self._tk_img, anchor=tk.CENTER)
            except Exception:
                self._base_img = None   # disable image for remaining frames

        dots = "." * (int(self._prog * 8) % 4)
        cv.create_text(
            cx, self.WIN_H - 50,
            text=self._label + dots,
            fill=self._color,
            font=("Courier", 11, "bold"),
            anchor=tk.CENTER,
        )
        if self.mode == "load":
            cv.create_text(
                cx, self.WIN_H - 30,
                text="reload your save in-game",
                fill="#555577",
                font=("Helvetica", 8),
                anchor=tk.CENTER,
            )

    def _tick(self):
        if not self._alive:
            return
        try:
            if self._phase == "fadein":
                self._alpha = min(0.93, self._alpha + 0.09)
                self._win.attributes("-alpha", self._alpha)
                if self._alpha >= 0.93:
                    self._phase = "running"
            elif self._phase == "fadeout":
                self._alpha = max(0.0, self._alpha - 0.07)
                self._win.attributes("-alpha", self._alpha)
                if self._alpha <= 0.0:
                    self._alive = False
                    self._win.destroy()
                    return

            # Start fading once dismissed AND minimum time has elapsed
            if (self._phase == "running"
                    and self._dismiss_wanted
                    and time.monotonic() >= self._show_until):
                self._phase = "fadeout"

            self._angle = (self._angle + self._spin_dir * self.SPIN_DEG) % 360
            self._prog += 0.014
            self._draw()
            self._win.after(1000 // self.FPS, self._tick)

        except tk.TclError:
            self._alive = False

    # ------------------------------------------------------------------

    def dismiss(self):
        """Signal that the operation finished; overlay fades after MIN_SECS."""
        self._dismiss_wanted = True

    def destroy(self):
        self._alive = False
        try:
            self._win.destroy()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Main application
# ---------------------------------------------------------------------------

class SaveManagerApp:

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Voyager Save Manager")
        self.root.configure(bg=C_BG_DARK)
        self.root.resizable(True, True)
        self.root.minsize(450, 380)

        self.backup_base = get_backup_base_dir()
        self.backup_base.mkdir(parents=True, exist_ok=True)

        self.save_dir: Path | None = find_game_save_dir()
        self.backups:  list[Path]  = []

        self._always_on_top = tk.BooleanVar(value=False)
        self._busy          = False   # prevent overlapping save/restore ops

        self._build_ui()
        self._bind_window_keys()
        self._start_global_hotkeys()
        self._refresh_list()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        root = self.root

        # ── Title ──────────────────────────────────────────────────────
        hdr = tk.Frame(root, bg=C_BG_DARK)
        hdr.pack(fill=tk.X, padx=12, pady=(12, 6))

        tk.Label(hdr, text="STAR TREK VOYAGER",
                 bg=C_BG_DARK, fg=C_ACCENT,
                 font=("Helvetica", 12, "bold")).pack(anchor=tk.W)
        tk.Label(hdr, text="Across the Unknown  —  Save Manager",
                 bg=C_BG_DARK, fg=C_FG_DIM,
                 font=("Helvetica", 8)).pack(anchor=tk.W)

        # ── Save-directory row ─────────────────────────────────────────
        dir_row = tk.Frame(root, bg=C_BG_MID)
        dir_row.pack(fill=tk.X, padx=12, pady=(0, 6))

        inner = tk.Frame(dir_row, bg=C_BG_MID)
        inner.pack(fill=tk.X, padx=8, pady=6)

        tk.Label(inner, text="GAME SAVES", bg=C_BG_MID, fg=C_FG_DIM,
                 font=("Helvetica", 7, "bold")).pack(anchor=tk.W)

        path_row = tk.Frame(inner, bg=C_BG_MID)
        path_row.pack(fill=tk.X)

        self._dir_label = tk.Label(path_row, bg=C_BG_MID,
                                   font=("Courier", 7), anchor=tk.W,
                                   wraplength=330, justify=tk.LEFT)
        self._dir_label.pack(side=tk.LEFT, fill=tk.X, expand=True)

        tk.Button(path_row, text="Browse…",
                  command=self._browse_dir,
                  bg=C_BG_LIGHT, fg=C_FG_DIM,
                  activebackground=C_BG_LIGHT, activeforeground=C_FG_MAIN,
                  font=("Helvetica", 7), relief=tk.FLAT,
                  padx=6, pady=2, cursor="hand2").pack(side=tk.RIGHT, padx=(4, 0))

        self._update_dir_label()

        # ── Quick-action buttons ───────────────────────────────────────
        btn_row = tk.Frame(root, bg=C_BG_DARK)
        btn_row.pack(fill=tk.X, padx=12, pady=4)

        self._save_btn = tk.Button(
            btn_row, text="⚡  Quick Save   [F5]",
            command=self.quick_save,
            bg=C_BG_MID, fg=C_GREEN,
            activebackground=C_BG_LIGHT, activeforeground=C_GREEN,
            font=("Helvetica", 10, "bold"),
            relief=tk.FLAT, padx=14, pady=9,
            cursor="hand2", width=18,
        )
        self._save_btn.pack(side=tk.LEFT, padx=(0, 6))

        self._load_btn = tk.Button(
            btn_row, text="↩  Quick Load   [F9]",
            command=self.quick_load_latest,
            bg=C_BG_MID, fg=C_ACCENT,
            activebackground=C_BG_LIGHT, activeforeground=C_ACCENT,
            font=("Helvetica", 10, "bold"),
            relief=tk.FLAT, padx=14, pady=9,
            cursor="hand2", width=18,
        )
        self._load_btn.pack(side=tk.LEFT)

        tk.Checkbutton(
            root, text="Always on top",
            variable=self._always_on_top,
            command=lambda: root.attributes("-topmost", self._always_on_top.get()),
            bg=C_BG_DARK, fg=C_FG_DIM, selectcolor=C_BG_MID,
            activebackground=C_BG_DARK, activeforeground=C_FG_DIM,
            font=("Helvetica", 8), cursor="hand2",
        ).pack(anchor=tk.E, padx=12)

        # ── Divider ────────────────────────────────────────────────────
        tk.Frame(root, bg=C_BG_LIGHT, height=1).pack(fill=tk.X, padx=12, pady=4)

        # ── Backup list ────────────────────────────────────────────────
        list_frame = tk.Frame(root, bg=C_BG_DARK)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 4))

        list_hdr = tk.Frame(list_frame, bg=C_BG_DARK)
        list_hdr.pack(fill=tk.X)
        tk.Label(list_hdr, text="Saved States",
                 bg=C_BG_DARK, fg=C_FG_DIM,
                 font=("Helvetica", 8, "bold")).pack(side=tk.LEFT, anchor=tk.W)

        # Hint label on the right
        tk.Label(list_hdr, text="double-click or select + Restore",
                 bg=C_BG_DARK, fg=C_BG_LIGHT,
                 font=("Helvetica", 7, "italic")).pack(side=tk.RIGHT)

        lb_wrap = tk.Frame(list_frame, bg=C_BG_MID, bd=0)
        lb_wrap.pack(fill=tk.BOTH, expand=True, pady=4)

        sb = tk.Scrollbar(lb_wrap, bg=C_BG_MID, troughcolor=C_BG_DARK,
                          activebackground=C_ACCENT, relief=tk.FLAT, width=10)
        self._listbox = tk.Listbox(
            lb_wrap,
            bg=C_BG_MID, fg=C_FG_MAIN,
            selectbackground="#1f6feb", selectforeground=C_FG_MAIN,
            font=("Courier", 9),
            height=9,
            yscrollcommand=sb.set,
            relief=tk.FLAT, borderwidth=0,
            highlightthickness=0,
            activestyle="none",
            cursor="hand2",
        )
        sb.config(command=self._listbox.yview)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self._listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=3, pady=3)

        self._listbox.bind("<Double-Button-1>", lambda _e: self.restore_selected())

        # ── List action buttons ────────────────────────────────────────
        act_row = tk.Frame(root, bg=C_BG_DARK)
        act_row.pack(fill=tk.X, padx=12, pady=(0, 4))

        tk.Button(act_row, text="Restore Selected",
                  command=self.restore_selected,
                  bg=C_BG_MID, fg=C_GREEN,
                  activebackground=C_BG_LIGHT, activeforeground=C_GREEN,
                  font=("Helvetica", 9), relief=tk.FLAT,
                  padx=10, pady=4, cursor="hand2").pack(side=tk.LEFT, padx=(0, 6))

        tk.Button(act_row, text="Delete Selected",
                  command=self.delete_selected,
                  bg=C_BG_MID, fg=C_RED,
                  activebackground=C_BG_LIGHT, activeforeground=C_RED,
                  font=("Helvetica", 9), relief=tk.FLAT,
                  padx=10, pady=4, cursor="hand2").pack(side=tk.LEFT)

        # ── Info note ──────────────────────────────────────────────────
        tk.Label(root,
                 text="ℹ  After restoring, reload your save inside the game.",
                 bg=C_BG_DARK, fg=C_BG_LIGHT,
                 font=("Helvetica", 7, "italic"),
                 anchor=tk.W).pack(fill=tk.X, padx=12)

        # ── Status bar ─────────────────────────────────────────────────
        tk.Frame(root, bg=C_BG_LIGHT, height=1).pack(fill=tk.X, padx=12, pady=(4, 0))

        self._status_var   = tk.StringVar(value="Ready  —  F5: Quick Save  |  F9: Quick Load")
        self._status_label = tk.Label(
            root, textvariable=self._status_var,
            bg=C_BG_DARK, fg=C_FG_DIM,
            font=("Helvetica", 8), anchor=tk.W,
        )
        self._status_label.pack(fill=tk.X, padx=12, pady=(3, 8))

    # ------------------------------------------------------------------
    # Directory helpers
    # ------------------------------------------------------------------

    def _update_dir_label(self):
        if self.save_dir and self.save_dir.exists():
            self._dir_label.config(fg=C_GREEN, text=str(self.save_dir))
        elif self.save_dir:
            self._dir_label.config(fg=C_YELLOW,
                                   text=f"{self.save_dir}  (not found – game not run yet?)")
        else:
            self._dir_label.config(fg=C_RED,
                                   text="Save directory not detected — click Browse… to locate")

    def _browse_dir(self):
        initial = str(self.save_dir) if self.save_dir else str(Path.home())
        chosen = filedialog.askdirectory(
            title="Select Game Save Directory", initialdir=initial
        )
        if chosen:
            self.save_dir = Path(chosen)
            self._update_dir_label()
            self._set_status(f"Save directory set: {self.save_dir}", C_GREEN, 4000)

    # ------------------------------------------------------------------
    # Hotkey wiring
    # ------------------------------------------------------------------

    def _bind_window_keys(self):
        """F5 / F9 work while this window is focused."""
        self.root.bind("<F5>", lambda _e: self.quick_save())
        self.root.bind("<F9>", lambda _e: self.quick_load_latest())

    def _start_global_hotkeys(self):
        """F5 / F9 work globally (even while the game is in the foreground)."""
        if not PYNPUT_AVAILABLE:
            self._set_status(
                "pynput not found — hotkeys only work when this window is focused.",
                C_YELLOW
            )
            return

        def _on_press(key):
            try:
                if key == pynput_keyboard.Key.f5:
                    self.root.after(0, self.quick_save)
                elif key == pynput_keyboard.Key.f9:
                    self.root.after(0, self.quick_load_latest)
            except Exception:
                pass

        try:
            listener = pynput_keyboard.Listener(on_press=_on_press, suppress=False)
            listener.daemon = True
            listener.start()
            self._set_status("Ready  —  F5: Quick Save  |  F9: Quick Load  (global)", C_FG_DIM)
        except Exception as exc:
            self._set_status(
                f"Global hotkeys unavailable ({exc}) — use window-focus keys only.",
                C_YELLOW
            )

    # ------------------------------------------------------------------
    # Status bar
    # ------------------------------------------------------------------

    _DEFAULT_STATUS = "Ready  —  F5: Quick Save  |  F9: Quick Load"

    def _set_status(self, msg: str, color: str = C_FG_DIM, duration: int | None = None):
        """Thread-safe status update; reverts after `duration` ms if given."""
        def _apply():
            self._status_var.set(msg)
            self._status_label.config(fg=color)
            if duration:
                self.root.after(duration, _reset)

        def _reset():
            self._status_var.set(self._DEFAULT_STATUS)
            self._status_label.config(fg=C_FG_DIM)

        self.root.after(0, _apply)

    # ------------------------------------------------------------------
    # Backup list
    # ------------------------------------------------------------------

    def _refresh_list(self):
        self._listbox.delete(0, tk.END)
        self.backups = []

        if not self.backup_base.exists():
            return

        dirs = sorted(
            [d for d in self.backup_base.iterdir() if d.is_dir()],
            reverse=True,   # newest first
        )
        self.backups = dirs

        for i, bdir in enumerate(dirs):
            try:
                dt  = datetime.strptime(bdir.name, "%Y-%m-%d_%H-%M-%S")
                ts  = dt.strftime("%Y-%m-%d  %H:%M:%S")
            except ValueError:
                ts = bdir.name

            try:
                n = sum(1 for _ in bdir.iterdir())
            except Exception:
                n = 0

            marker = "►" if i == 0 else " "
            self._listbox.insert(
                tk.END,
                f"  {marker}  {ts}    [{n} file{'s' if n != 1 else ''}]"
            )

        if dirs:
            self._listbox.itemconfig(0, fg=C_GREEN)   # highlight newest

    # ------------------------------------------------------------------
    # Core operations
    # ------------------------------------------------------------------

    def quick_save(self):
        if self._busy:
            return
        if not self.save_dir or not self.save_dir.exists():
            self._set_status("Save directory not found!  Use Browse… to locate it.", C_RED, 5000)
            return

        ts   = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        dest = self.backup_base / ts

        # Avoid duplicate timestamps (rapid key presses)
        counter = 1
        while dest.exists():
            dest = self.backup_base / f"{ts}_{counter}"
            counter += 1

        overlay = SaveLoadOverlay(self.root, "save")

        def _worker():
            self._busy = True
            self.root.after(0, lambda: self._save_btn.config(state=tk.DISABLED))
            self.root.after(0, lambda: self._load_btn.config(state=tk.DISABLED))
            try:
                dest.mkdir(parents=True, exist_ok=True)
                n = 0
                for item in self.save_dir.iterdir():
                    target = dest / item.name
                    if item.is_file():
                        shutil.copy2(item, target)
                    elif item.is_dir():
                        shutil.copytree(item, target)
                    n += 1

                if n == 0:
                    dest.rmdir()
                    self._set_status("No files in save directory — nothing to back up.", C_YELLOW, 5000)
                else:
                    self._set_status(
                        f"Saved: {dest.name}   ({n} item{'s' if n != 1 else ''})",
                        C_GREEN, 5000,
                    )
                    self.root.after(0, self._refresh_list)

            except Exception as exc:
                shutil.rmtree(dest, ignore_errors=True)
                self._set_status(f"Save failed: {exc}", C_RED, 6000)
            finally:
                self._busy = False
                self.root.after(0, lambda: self._save_btn.config(state=tk.NORMAL))
                self.root.after(0, lambda: self._load_btn.config(state=tk.NORMAL))
                self.root.after(0, overlay.dismiss)

        threading.Thread(target=_worker, daemon=True).start()

    def quick_load_latest(self):
        if not self.backups:
            self._set_status("No backups available — press F5 first.", C_YELLOW, 4000)
            return
        self._do_restore(self.backups[0])

    def restore_selected(self):
        sel = self._listbox.curselection()
        if not sel:
            self._set_status("Select a backup from the list first.", C_FG_DIM, 3000)
            return
        idx = sel[0]
        if idx < len(self.backups):
            self._do_restore(self.backups[idx])

    def _do_restore(self, backup: Path):
        if self._busy:
            return
        if not self.save_dir:
            messagebox.showerror("Error", "Game save directory not configured.\nUse Browse… to set it.")
            return
        if not backup.exists():
            self._set_status("Backup no longer exists on disk.", C_RED, 4000)
            self._refresh_list()
            return

        overlay = SaveLoadOverlay(self.root, "load")

        def _worker():
            self._busy = True
            self.root.after(0, lambda: self._save_btn.config(state=tk.DISABLED))
            self.root.after(0, lambda: self._load_btn.config(state=tk.DISABLED))
            try:
                # Wipe current saves
                self.save_dir.mkdir(parents=True, exist_ok=True)
                for item in self.save_dir.iterdir():
                    if item.is_file():
                        item.unlink()
                    elif item.is_dir():
                        shutil.rmtree(item)

                # Copy backup → save dir
                n = 0
                for item in backup.iterdir():
                    target = self.save_dir / item.name
                    if item.is_file():
                        shutil.copy2(item, target)
                    elif item.is_dir():
                        shutil.copytree(item, target)
                    n += 1

                self._set_status(
                    f"Restored: {backup.name}   ({n} item{'s' if n != 1 else ''})  —  reload save in-game",
                    C_GREEN, 8000,
                )
            except Exception as exc:
                self._set_status(f"Restore failed: {exc}", C_RED, 6000)
            finally:
                self._busy = False
                self.root.after(0, lambda: self._save_btn.config(state=tk.NORMAL))
                self.root.after(0, lambda: self._load_btn.config(state=tk.NORMAL))
                self.root.after(0, overlay.dismiss)

        threading.Thread(target=_worker, daemon=True).start()

    def delete_selected(self):
        sel = self._listbox.curselection()
        if not sel:
            self._set_status("Select a backup to delete.", C_FG_DIM, 3000)
            return
        idx = sel[0]
        if idx >= len(self.backups):
            return
        bdir = self.backups[idx]
        if messagebox.askyesno("Delete Backup",
                               f"Permanently delete:\n{bdir.name}\n\nThis cannot be undone."):
            try:
                shutil.rmtree(bdir)
                self._set_status(f"Deleted: {bdir.name}", C_FG_DIM, 3000)
                self._refresh_list()
            except Exception as exc:
                self._set_status(f"Delete failed: {exc}", C_RED, 4000)



# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    root = tk.Tk()

    app = SaveManagerApp(root)  # noqa: F841

    # Centre window on screen
    root.update_idletasks()
    w = root.winfo_reqwidth()
    h = root.winfo_reqheight()
    sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
    root.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 2}")

    root.mainloop()


if __name__ == "__main__":
    main()
