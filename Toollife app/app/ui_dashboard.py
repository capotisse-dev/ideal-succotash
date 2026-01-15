# app/ui_dashboard.py
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, timedelta

import pandas as pd

from .ui_common import HeaderFrame
from .storage import get_df, safe_int, safe_float


class DashboardUI(tk.Frame):
    """
    Dashboard (Super/Admin):
    - Pareto tables: Defect Code, Machine, Tool, Part
    - Trend table by Day: entries, downtime, defects, COPQ
    - Date window selector (last X days)
    """

    def __init__(self, parent, controller, show_header=True):
        super().__init__(parent, bg=controller.colors["bg"])
        self.controller = controller

        if show_header:
            HeaderFrame(self, controller).pack(fill="x")

        # Top bar
        top = tk.Frame(self, bg=controller.colors["bg"], padx=10, pady=10)
        top.pack(fill="x")

        tk.Label(
            top,
            text="On Shift Pass Down (Pareto + Trends)",
            bg=controller.colors["bg"],
            fg=controller.colors["fg"],
            font=("Arial", 16, "bold")
        ).pack(side="left")

        tk.Button(top, text="Refresh", command=self.refresh).pack(side="right")

        # Controls
        ctrl = tk.Frame(self, bg=controller.colors["bg"], padx=10, pady=(0, 8))
        ctrl.pack(fill="x")

        tk.Label(ctrl, text="Window:", bg=controller.colors["bg"], fg=controller.colors["fg"]).pack(side="left")
        self.window_var = ttk.Combobox(ctrl, state="readonly", width=16, values=[
            "Today", "Last 3 Days", "Last 7 Days", "Last 14 Days", "Last 30 Days", "This Month"
        ])
        self.window_var.set("Last 7 Days")
        self.window_var.pack(side="left", padx=8)
        self.window_var.bind("<<ComboboxSelected>>", lambda e: self.refresh())

        tk.Label(ctrl, text="Show Top:", bg=controller.colors["bg"], fg=controller.colors["fg"]).pack(side="left", padx=(18, 6))
        self.topn_var = tk.StringVar(value="15")
        tk.Entry(ctrl, textvariable=self.topn_var, width=6).pack(side="left", padx=8)

        self.status = tk.Label(ctrl, text="", bg=controller.colors["bg"], fg=controller.colors["fg"])
        self.status.pack(side="left", padx=(18, 0))

        # Notebook: Pareto tabs + Trend tab
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=10, pady=10)

        self.tab_defect = tk.Frame(nb)
        self.tab_machine = tk.Frame(nb)
        self.tab_tool = tk.Frame(nb)
        self.tab_part = tk.Frame(nb)
        self.tab_trend = tk.Frame(nb)

        nb.add(self.tab_defect, text="Pareto - Defect")
        nb.add(self.tab_machine, text="Pareto - Machine")
        nb.add(self.tab_tool, text="Pareto - Tool")
        nb.add(self.tab_part, text="Pareto - Part")
        nb.add(self.tab_trend, text="Trend - Daily Totals")

        self.tree_defect = self._make_pareto_tree(self.tab_defect, key_label="Defect_Code")
        self.tree_machine = self._make_pareto_tree(self.tab_machine, key_label="Machine")
        self.tree_tool = self._make_pareto_tree(self.tab_tool, key_label="Tool_Num")
        self.tree_part = self._make_pareto_tree(self.tab_part, key_label="Part_Number")

        self.tree_trend = self._make_trend_tree(self.tab_trend)

        self.refresh()

    # -------------------------
    def _make_pareto_tree(self, parent, key_label: str):
        cols = ("rank", "key", "entries", "defect_qty", "downtime_mins", "copq_est", "pct_defects")
        tree = ttk.Treeview(parent, columns=cols, show="headings", height=18)
        for c in cols:
            tree.heading(c, text=c.upper())
            if c == "key":
                tree.column(c, width=320)
            elif c == "rank":
                tree.column(c, width=60)
            else:
                tree.column(c, width=140)
        tree.pack(fill="both", expand=True, padx=8, pady=8)

        # label at top for clarity
        lbl = ttk.Label(parent, text=f"Grouping key: {key_label}")
        lbl.pack(anchor="w", padx=10, pady=(6, 0))
        return tree

    def _make_trend_tree(self, parent):
        cols = ("date", "entries", "defect_qty", "downtime_mins", "copq_est", "andon_ct", "high_risk_ct")
        tree = ttk.Treeview(parent, columns=cols, show="headings", height=18)
        for c in cols:
            tree.heading(c, text=c.upper())
            tree.column(c, width=160 if c != "date" else 120)
        tree.pack(fill="both", expand=True, padx=8, pady=8)

        note = ttk.Label(parent, text="Trend totals by day (based on Date column).")
        note.pack(anchor="w", padx=10, pady=(6, 0))
        return tree

    def _clear_tree(self, tree):
        for i in tree.get_children():
            tree.delete(i)

    # -------------------------
    def _get_window(self):
        mode = self.window_var.get()
        now = datetime.now()
        today = datetime(now.year, now.month, now.day)

        if mode == "Today":
            return today, now
        if mode == "Last 3 Days":
            return today - timedelta(days=2), now
        if mode == "Last 7 Days":
            return today - timedelta(days=6), now
        if mode == "Last 14 Days":
            return today - timedelta(days=13), now
        if mode == "Last 30 Days":
            return today - timedelta(days=29), now
        # This Month
        start = datetime(now.year, now.month, 1)
        return start, now

    def _topn(self):
        return max(5, safe_int(self.topn_var.get(), 15))

    # -------------------------
    def refresh(self):
        for t in (self.tree_defect, self.tree_machine, self.tree_tool, self.tree_part, self.tree_trend):
            self._clear_tree(t)

        df, fname = get_df()
        if df is None or df.empty:
            self.status.config(text="No data.")
            return

        # Date filter
        df = df.copy()
        df["_dt"] = pd.to_datetime(df.get("Date", ""), errors="coerce")

        start, end = self._get_window()
        sub = df[df["_dt"].notna() & (df["_dt"] >= pd.Timestamp(start)) & (df["_dt"] <= pd.Timestamp(end))].copy()

        if sub.empty:
            self.status.config(text=f"No rows in window ({start.date()} → {end.date()}).")
            return

        # Normalize numeric columns
        sub["_defect_qty"] = sub.get("Defect_Qty", 0).apply(lambda x: safe_int(x, 0))
        sub["_dtmins"] = sub.get("Downtime_Mins", 0).apply(lambda x: safe_float(x, 0.0))
        sub["_copq"] = sub.get("COPQ_Est", 0).apply(lambda x: safe_float(x, 0.0)) if "COPQ_Est" in sub.columns else 0.0

        # Useful flags
        sub["_andon"] = sub.get("Andon_Flag", "").astype(str).str.lower().eq("yes") if "Andon_Flag" in sub.columns else False
        sub["_highrisk"] = sub.get("Customer_Risk", "").isin(["High", "Critical"]) if "Customer_Risk" in sub.columns else False

        topn = self._topn()

        # Build paretos
        self._fill_pareto(self.tree_defect, sub, key="Defect_Code", topn=topn, label="Defect")
        self._fill_pareto(self.tree_machine, sub, key="Machine", topn=topn, label="Machine")
        self._fill_pareto(self.tree_tool, sub, key="Tool_Num", topn=topn, label="Tool")
        self._fill_pareto(self.tree_part, sub, key="Part_Number", topn=topn, label="Part")

        # Trend by day
        self._fill_trend(self.tree_trend, sub)

        self.status.config(text=f"{len(sub)} rows from {fname} | Window: {start.date()} → {end.date()}")

    def _fill_pareto(self, tree, df, key: str, topn: int, label: str):
        if key not in df.columns:
            return

        # If you want defect pareto to focus only on defects, uncomment below:
        # if key == "Defect_Code" and "Defects_Present" in df.columns:
        #     df = df[df["Defects_Present"].astype(str).str.lower().eq("yes")].copy()

        grp = df.groupby(key, dropna=False)

        out = grp.agg(
            entries=("ID", "count"),
            defect_qty=("_defect_qty", "sum"),
            downtime_mins=("_dtmins", "sum"),
            copq_est=("_copq", "sum")
        ).reset_index()

        # Clean blanks
        out[key] = out[key].astype(str)
        out.loc[out[key].str.strip() == "", key] = "(blank)"

        # Percent of defects share (based on defect_qty)
        total_defects = float(out["defect_qty"].sum()) if len(out) else 0.0
        if total_defects > 0:
            out["pct_defects"] = (out["defect_qty"] / total_defects) * 100.0
        else:
            out["pct_defects"] = 0.0

        # Sort primarily by defect_qty then downtime then entries
        out = out.sort_values(["defect_qty", "downtime_mins", "entries"], ascending=False).head(topn).reset_index(drop=True)

        for i, r in out.iterrows():
            tree.insert("", "end", values=(
                i + 1,
                f"{label}: {r[key]}",
                int(r["entries"]),
                int(r["defect_qty"]),
                float(r["downtime_mins"]),
                float(r["copq_est"]),
                float(r["pct_defects"])
            ))

    def _fill_trend(self, tree, df):
        if df.empty:
            return

        df = df.copy()
        df["_day"] = df["_dt"].dt.strftime("%Y-%m-%d")

        out = df.groupby("_day", dropna=False).agg(
            entries=("ID", "count"),
            defect_qty=("_defect_qty", "sum"),
            downtime_mins=("_dtmins", "sum"),
            copq_est=("_copq", "sum"),
            andon_ct=("_andon", "sum"),
            high_risk_ct=("_highrisk", "sum"),
        ).reset_index()

        out = out.sort_values("_day", ascending=False).head(60).reset_index(drop=True)

        for _, r in out.iterrows():
            tree.insert("", "end", values=(
                r["_day"],
                int(r["entries"]),
                int(r["defect_qty"]),
                float(r["downtime_mins"]),
                float(r["copq_est"]),
                int(r["andon_ct"]),
                int(r["high_risk_ct"]),
            ))
