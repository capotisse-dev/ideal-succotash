import tkinter as tk
from tkinter import ttk

from .ui_common import HeaderFrame
from .db import list_audit_logs


class AuditTrailUI(tk.Frame):
    def __init__(self, parent, controller, show_header=True):
        super().__init__(parent, bg=controller.colors["bg"])
        self.controller = controller

        if show_header:
            HeaderFrame(self, controller).pack(fill="x")

        top = tk.Frame(self, bg=controller.colors["bg"], padx=10, pady=10)
        top.pack(fill="x")

        tk.Label(
            top,
            text="Audit Trail",
            bg=controller.colors["bg"],
            fg=controller.colors["fg"],
            font=("Arial", 16, "bold"),
        ).pack(side="left")

        tk.Button(top, text="Refresh", command=self.refresh).pack(side="right")

        cols = ("created_at", "username", "action")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", height=18)
        for c in cols:
            self.tree.heading(c, text=c.upper())
            if c == "action":
                self.tree.column(c, width=720)
            else:
                self.tree.column(c, width=200)
        self.tree.pack(fill="both", expand=True, padx=10, pady=10)

        self.refresh()

    def refresh(self):
        for i in self.tree.get_children():
            self.tree.delete(i)
        for row in list_audit_logs():
            self.tree.insert("", "end", values=(
                row.get("created_at", ""),
                row.get("username", ""),
                row.get("action", ""),
            ))
