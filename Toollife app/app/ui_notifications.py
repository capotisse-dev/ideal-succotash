# app/ui_notifications.py
import tkinter as tk
from tkinter import ttk

from .ui_common import HeaderFrame
from .storage import get_df, load_json
from .config import GAGES_FILE, RISK_CONFIG_FILE
from .quality_engine import generate_notifications


class NotificationsUI(tk.Frame):
    def __init__(self, parent, controller, show_header=True):
        super().__init__(parent, bg=controller.colors["bg"])
        self.controller = controller

        if show_header:
            HeaderFrame(self, controller).pack(fill="x")

        top = tk.Frame(self, bg=controller.colors["bg"], padx=10, pady=10)
        top.pack(fill="x")

        tk.Label(top, text="Notifications (Super/Admin)", bg=controller.colors["bg"],
                 fg=controller.colors["fg"], font=("Arial", 16, "bold")).pack(side="left")

        tk.Button(top, text="Refresh", command=self.refresh).pack(side="right")

        filt = tk.Frame(self, bg=controller.colors["bg"], padx=10, pady=0)
        filt.pack(fill="x")

        tk.Label(filt, text="Minimum severity:", bg=controller.colors["bg"], fg=controller.colors["fg"]).pack(side="left")
        self.min_sev = ttk.Combobox(filt, values=["Medium", "High", "Critical"], state="readonly", width=12)
        self.min_sev.set("High")
        self.min_sev.pack(side="left", padx=8)
        self.min_sev.bind("<<ComboboxSelected>>", lambda e: self.refresh())

        cols = ("severity", "type", "title", "details", "related")
        self.tree = ttk.Treeview(self, columns=cols, show="headings")
        for c in cols:
            self.tree.heading(c, text=c.upper())
            self.tree.column(c, width=160 if c != "details" else 520)
        self.tree.pack(fill="both", expand=True, padx=10, pady=10)

        self.refresh()

    def refresh(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        df, fname = get_df()  # current month
        gages = load_json(GAGES_FILE, {"gages": []})
        risk_cfg = load_json(RISK_CONFIG_FILE, {})

        alerts = generate_notifications(df, gages, risk_cfg)

        # filter + sort
        rank = {"Low": 0, "Medium": 1, "High": 2, "Critical": 3}
        min_needed = rank.get(self.min_sev.get(), 2)

        filtered = [a for a in alerts if rank.get(a.get("severity","Low"), 0) >= min_needed]
        filtered.sort(key=lambda a: rank.get(a.get("severity","Low"), 0), reverse=True)

        for a in filtered:
            rel = a.get("related", {})
            self.tree.insert("", "end", values=(
                a.get("severity",""),
                a.get("type",""),
                a.get("title",""),
                a.get("details",""),
                str(rel)
            ))
