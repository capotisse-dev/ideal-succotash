# main.py
from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path


def _write_startup_log(msg: str) -> None:
    try:
        # Import inside so we can still log even if app/config imports fail later
        base = Path(__file__).resolve().parent
        log_dir = base / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        (log_dir / "startup.log").write_text(msg, encoding="utf-8")
    except Exception:
        pass


def _show_fatal_popup(title: str, text: str) -> None:
    # Last-ditch: try to show a Tk popup even if the app didn't initialize.
    try:
        import tkinter as tk
        from tkinter import messagebox

        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(title, text)
        root.destroy()
    except Exception:
        # If even Tk popup fails, nothing else we can do
        pass


def main() -> int:
    try:
        # 1) Initialize app environment FIRST
        from app import initialize_app
        initialize_app()

        # 2) Import UI AFTER init (prevents missing logs/data dirs errors)
        from app.ui_login import App

        # 3) Launch
        app_obj = App()

        # If App is a tk.Frame/controller (not tk.Tk), create a root and mount it
        try:
            import tkinter as tk
        except Exception:
            tk = None

        if tk is not None and isinstance(app_obj, tk.Tk):
            # App is the root window
            app_obj.mainloop()
        else:
            # App is likely a Frame/controller — create root and pack it
            if tk is None:
                raise RuntimeError("Tkinter failed to import, cannot start UI.")
            root = tk.Tk()
            root.title("Toollife App")

            # Optional: set a decent default size
            root.geometry("1200x800")

            # If App expects (root) you can adjust here; we try common patterns
            try:
                app_obj = App(root)
            except TypeError:
                # if App() already created a frame/controller, try packing it
                pass

            # Pack if it's a widget
            if isinstance(app_obj, tk.Widget):
                app_obj.pack(fill="both", expand=True)

            root.mainloop()

        return 0

    except Exception as e:
        tb = traceback.format_exc()
        msg = f"Startup failure:\n\n{tb}"
        _write_startup_log(msg)
        _show_fatal_popup("Toollife App — Startup Error", msg)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
