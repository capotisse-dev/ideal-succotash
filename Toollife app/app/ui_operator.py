# app/ui_operator.py
from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime

from .ui_common import HeaderFrame
from .storage import safe_int, safe_float
from .db import list_downtime_codes, list_lines, upsert_operator_entry


class OperatorUI(tk.Frame):
    """Operator entry screen for cell/parts and downtime capture."""

    def __init__(self, parent, controller, show_header=True):
        super().__init__(parent, bg=controller.colors["bg"])
        self.controller = controller

        if show_header:
            HeaderFrame(self, controller).pack(fill="x")

        body = tk.Frame(self, bg=controller.colors["bg"], padx=20, pady=20)
        body.pack(fill="both", expand=True)

        style = {"bg": controller.colors["bg"], "fg": controller.colors["fg"]}

        tk.Label(body, text="Operator Entry", font=("Arial", 16, "bold"), **style).grid(
            row=0, column=0, columnspan=4, sticky="w", pady=(0, 15)
        )

        # Line selection
        tk.Label(body, text="Line:", **style).grid(row=1, column=0, sticky="e", pady=6)
        line_options = list_lines()
        if not line_options:
            line_options = ["U725", "JL"]
        self.line_var = tk.StringVar(value=controller.user_line or "Both")
        self.line_cb = ttk.Combobox(body, values=line_options, state="readonly", width=18)
        if self.line_var.get() in line_options:
            self.line_cb.set(self.line_var.get())
        else:
            self.line_cb.current(0)
        self.line_cb.grid(row=1, column=1, sticky="w")

        # Cell ran
        tk.Label(body, text="Cell Ran:", **style).grid(row=2, column=0, sticky="e", pady=6)
        self.cell_entry = tk.Entry(body, width=24)
        self.cell_entry.grid(row=2, column=1, sticky="w")

        # Parts ran
        tk.Label(body, text="Parts Ran:", **style).grid(row=3, column=0, sticky="e", pady=6)
        self.parts_entry = tk.Entry(body, width=24)
        self.parts_entry.grid(row=3, column=1, sticky="w")

        # Downtime selection
        tk.Label(body, text="Downtime Code:", **style).grid(row=4, column=0, sticky="e", pady=6)
        self.downtime_var = tk.StringVar(value="")
        self.downtime_cb = ttk.Combobox(
            body,
            values=[c["code"] for c in list_downtime_codes()],
            textvariable=self.downtime_var,
            state="readonly",
            width=24,
        )
        self.downtime_cb.grid(row=4, column=1, sticky="w")
        self.downtime_cb.bind("<<ComboboxSelected>>", self._toggle_downtime_fields)

        self.downtime_frame = tk.Frame(body, bg=controller.colors["bg"])
        self.downtime_frame.grid(row=4, column=2, columnspan=2, sticky="w", padx=20)

        tk.Label(self.downtime_frame, text="Total Time (min):", **style).grid(row=0, column=0, sticky="w")
        self.dt_total_entry = tk.Entry(self.downtime_frame, width=10)
        self.dt_total_entry.grid(row=0, column=1, padx=(6, 12))

        tk.Label(self.downtime_frame, text="# Occurrences:", **style).grid(row=0, column=2, sticky="w")
        self.dt_occ_entry = tk.Entry(self.downtime_frame, width=10)
        self.dt_occ_entry.grid(row=0, column=3, padx=(6, 12))

        tk.Label(self.downtime_frame, text="Comments:", **style).grid(row=0, column=4, sticky="w")
        self.dt_comment_entry = tk.Entry(self.downtime_frame, width=28)
        self.dt_comment_entry.grid(row=0, column=5, padx=(6, 0))

        self._toggle_downtime_fields()

        tk.Button(
            body,
            text="Submit",
            command=self.submit,
            bg="#28a745",
            fg="white",
            font=("Arial", 12, "bold"),
            width=16,
        ).grid(row=6, column=0, columnspan=4, pady=20, sticky="w")

    def _toggle_downtime_fields(self, event=None):
        enabled = bool(self.downtime_var.get())
        state = "normal" if enabled else "disabled"
        for entry in (self.dt_total_entry, self.dt_occ_entry, self.dt_comment_entry):
            entry.configure(state=state)
            if not enabled:
                entry.delete(0, "end")

    def submit(self):
        cell = self.cell_entry.get().strip()
        parts = self.parts_entry.get().strip()
        if not cell:
            messagebox.showerror("Missing Info", "Enter the cell ran.")
            return
        if not parts:
            messagebox.showerror("Missing Info", "Enter the parts ran.")
            return

        downtime_code = self.downtime_var.get().strip()
        dt_total = safe_float(self.dt_total_entry.get(), 0.0) if downtime_code else 0.0
        dt_occ = safe_int(self.dt_occ_entry.get(), 0) if downtime_code else 0
        dt_comments = self.dt_comment_entry.get().strip() if downtime_code else ""

        now = datetime.now()
        entry_id = f"OP-{now.strftime('%Y%m%d-%H%M%S')}"
        upsert_operator_entry({
            "id": entry_id,
            "date": now.strftime("%Y-%m-%d"),
            "time": now.strftime("%H:%M:%S"),
            "username": self.controller.user or "",
            "line": self.line_cb.get(),
            "cell_ran": cell,
            "parts_ran": parts,
            "downtime_code": downtime_code,
            "downtime_total_time": dt_total,
            "downtime_occurrences": dt_occ,
            "downtime_comments": dt_comments,
        })

        messagebox.showinfo("Saved", "Operator entry saved.")
        self.cell_entry.delete(0, "end")
        self.parts_entry.delete(0, "end")
        self.downtime_var.set("")
        self._toggle_downtime_fields()
