# app/__init__.py
from __future__ import annotations
import tkinter as tk


def _normalize_padding(v):
    """Convert tuple paddings like (0, 8) into a safe integer."""
    if isinstance(v, tuple) and v:
        try:
            return int(max(v))
        except Exception:
            return 0
    return v


def _patch_tk_tuple_padding() -> None:
    """
    Fix for Python 3.14 / some Tk builds that crash on tuple padding:
        pady=(0,8) -> TclError: bad screen distance "0 8"

    IMPORTANT: tuple padding can be processed in TWO places:
      1) During widget construction -> Misc._options (before Tcl call)
      2) During widget.configure(...) -> Misc._configure

    We patch both.
    """
    if getattr(tk, "_tuple_padding_patched", False):
        return

    # --- Patch 1: constructor path (Widget.__init__ uses Misc._options)
    _orig_options = tk.Misc._options

    def _fixed_options(self, cnf, kw=None):
        # cnf is usually a dict; kw may be dict
        if isinstance(cnf, dict):
            cnf = dict(cnf)
            for k in ("padx", "pady", "ipadx", "ipady"):
                if k in cnf:
                    cnf[k] = _normalize_padding(cnf[k])

        if isinstance(kw, dict):
            kw = dict(kw)
            for k in ("padx", "pady", "ipadx", "ipady"):
                if k in kw:
                    kw[k] = _normalize_padding(kw[k])

        return _orig_options(self, cnf, kw)

    tk.Misc._options = _fixed_options

    # --- Patch 2: runtime configure path (covers widget.configure(pady=(0,8)))
    _orig_configure = tk.Misc._configure

    def _fixed_configure(self, *args, **kwargs):
        for k in ("padx", "pady", "ipadx", "ipady"):
            if k in kwargs:
                kwargs[k] = _normalize_padding(kwargs[k])

        # dict style: widget.configure({"pady": (0,8)})
        if len(args) >= 1 and isinstance(args[0], dict):
            d = dict(args[0])
            for k in ("padx", "pady", "ipadx", "ipady"):
                if k in d:
                    d[k] = _normalize_padding(d[k])
            args = (d,) + args[1:]

        return _orig_configure(self, *args, **kwargs)

    tk.Misc._configure = _fixed_configure

    tk._tuple_padding_patched = True


def initialize_app() -> None:
    """
    Initialize application environment:
    - Create folders/files/excel schema via bootstrap
    - Apply Tk tuple-padding patch (must run BEFORE any widgets are created)
    """
    from .bootstrap import ensure_app_initialized
    ensure_app_initialized()
    _patch_tk_tuple_padding()
