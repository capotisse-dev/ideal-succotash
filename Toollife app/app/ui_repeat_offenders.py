# app/ui_repeat_offenders.py
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, timedelta

import pandas as pd

from .ui_common import HeaderFrame
from .storage import get_df, load_json, safe_int, safe_float
from .config import REPEAT_RULES_FILE, DATA_DIR


class RepeatOffendersUI(tk.Frame):
    """
    Repeat Offenders (Super/Admin):
    - Window-based repeat detection using repeat_rules.json
    - Shows:
      1) Part + Defect repeats
      2) Machine repeats
      3) Tool COPQ repeats (if COPQ present)
    """
    def __init__(self, parent, controller, show_header=True):
        super().__init__(parent, bg=controller.colors["bg"])
        self.controller = controller

        if show_header:
            HeaderFrame(self, controller).pack(fill="x")

        self.rules = load_json(REPEAT_RULES_FILE, {})

        top = tk.Frame(self, bg=controller.colors["bg"], padx=10, pady=10)
        top.pack(fill="x")

        tk.Label(
            top,
            text="Repeat Offenders (Super/Admin)",
            bg=controller.colors["bg"],
            fg=controller.colors["fg"],
            font=("Arial", 16, "bold")
        ).pack(side="left")

        tk.Button(top, text="Refresh", command=self.refresh).pack(side="right")
        tk.Button(top, text="Export Excel", command=self.export).pack(side="right", padx=(0, 8))

        # Controls
        ctrl = tk.Frame(self, bg=controller.colors["bg"], padx=10, pady=(0, 8))
        ctrl.pack(fill="x")

        tk.Label(ctrl, text="Window days:", bg=controller.colors["bg"], fg=controller.colors["fg"]).pack(side="left")
        self.window_var = tk.StringVar(value=str(safe_int(self.rules.get("window_days", 7), 7)))
        tk.Entry(ctrl, textvariable=self.window_var, width=6).pack(side="left", padx=8)

        tk.Label(ctrl, text="Min count:", bg=controller.colors["bg"], fg=controller.colors["fg"]).pack(side="left", padx=(18, 6))
        self.min_count_var = tk.StringVar(value="2")
        tk.Entry(ctrl, textvariable=self.min_count_var, width=6).pack(side="left", padx=8)

        self.status = tk.Label(ctrl, text="", bg=controller.colors["bg"], fg=controller.colors["fg"])
        self.status.pack(side="left", padx=(18, 0))

        # Notebook with 3 tables
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=10, pady=10)

        self.tab_part = tk.Frame(nb)
        self.tab_mach = tk.Frame(nb)
        self.tab_tool = tk.Frame(nb)

        nb.add(self.tab_part, text="Part + Defect")
        nb.add(self.tab_mach, text="Machine")
        nb.add(self.tab_tool, text="Tool COPQ")

        self.tree_part = self._make_tree(self.tab_part, ("rank", "part", "defect", "count", "defect_qty", "downtime_mins", "copq_est"))
        self.tree_mach = self._make_tree(self.tab_mach, ("rank", "machine", "count", "defect_qty", "downtime_mins", "copq_est"))
        self.tree_tool = self._make_tree(self.tab_tool, ("rank", "tool", "count", "defect_qty", "downtime_mins", "copq_est"))

        # Cache
        self._out_part = None
        self._out_mach = None
        self._out_tool = None

        self.refresh()

    def _make_tree(self, parent, cols):
        wrap = tk.Frame(parent)
        wrap.pack(fill="both", expand=True, padx=8, pady=8)
        tree = ttk.Treeview(wrap, columns=cols, show="headings")
        for c in cols:
            tree.heading(c, text=c.upper())
            if c in ("part", "defect", "machine", "tool"):
                tree.column(c, width=220)
            elif c == "rank":
                tree.column(c, width=60)
            else:
                tree.column(c, width=140)
        tree.pack(side="left", fill="both", expand=True)
        ybar = ttk.Scrollbar(wrap, orient="vertical", command=tree.yview)
        ybar.pack(side="right", fill="y")
        xbar = ttk.Scrollbar(parent, orient="horizontal", command=tree.xview)
        xbar.pack(fill="x", padx=8)
        tree.configure(yscrollcommand=ybar.set, xscrollcommand=xbar.set)
        return tree

    def _clear_tree(self, tree):
        for i in tree.get_children():
            tree.delete(i)

    def _date_filter(self, df):
        window_days = safe_int(self.window_var.get(), safe_int(self.rules.get("window_days", 7), 7))
        cutoff = datetime.now().date() - timedelta(days=window_days)

        temp = df.copy()
        temp["_dt"] = pd.to_datetime(temp.get("Date", ""), errors="coerce")
        temp = temp[temp["_dt"].notna()]
        temp = temp[temp["_dt"].dt.date >= cutoff]
        return temp, window_days

    def refresh(self):
        self._clear_tree(self.tree_part)
        self._clear_tree(self.tree_mach)
        self._clear_tree(self.tree_tool)

        df, _ = get_df()
        if df is None or df.empty:
            self.status.config(text="No data.")
            return

        min_count = max(2, safe_int(self.min_count_var.get(), 2))

        sub, window_days = self._date_filter(df)

        # Normalize numeric fields
        sub["_defect_qty"] = sub.get("Defect_Qty", 0).apply(lambda x: safe_int(x, 0))
        sub["_dtmins"] = sub.get("Downtime_Mins", 0).apply(lambda x: safe_float(x, 0.0))
        sub["_copq"] = sub.get("COPQ_Est", 0).apply(lambda x: safe_float(x, 0.0)) if "COPQ_Est" in sub.columns else 0.0

        # Focus only defect-related rows for repeats
        if "Defects_Present" in sub.columns:
            def_mask = sub["Defects_Present"].astype(str).str.lower().eq("yes")
            sub_def = sub[def_mask].copy()
        else:
            sub_def = sub.copy()

        # 1) Part + Defect repeats
        out_part = None
        if "Part_Number" in sub_def.columns and "Defect_Code" in sub_def.columns:
            grp = sub_def.groupby(["Part_Number", "Defect_Code"], dropna=False)
            out_part = grp.agg(
                count=("ID", "count"),
                defect_qty=("_defect_qty", "sum"),
                downtime_mins=("_dtmins", "sum"),
                copq_est=("_copq", "sum")
            ).reset_index()

            out_part = out_part[out_part["count"] >= min_count]
            out_part["Part_Number"] = out_part["Part_Number"].astype(str).replace({"": "(blank)"})
            out_part["Defect_Code"] = out_part["Defect_Code"].astype(str).replace({"": "(blank)"})

            # Score: emphasize repeats + defects + copq
            out_part["_score"] = out_part["count"] * 5 + out_part["defect_qty"] * 2 + out_part["downtime_mins"] * 0.5 + out_part["copq_est"] * 0.01
            out_part = out_part.sort_values("_score", ascending=False).head(50).reset_index(drop=True)

            for i, r in out_part.iterrows():
                self.tree_part.insert("", "end", values=(
                    i + 1,
                    r["Part_Number"],
                    r["Defect_Code"],
                    int(r["count"]),
                    int(r["defect_qty"]),
                    float(r["downtime_mins"]),
                    float(r["copq_est"])
                ))

        # 2) Machine repeats
        out_mach = None
        if "Machine" in sub_def.columns:
            grp = sub_def.groupby(["Machine"], dropna=False)
            out_mach = grp.agg(
                count=("ID", "count"),
                defect_qty=("_defect_qty", "sum"),
                downtime_mins=("_dtmins", "sum"),
                copq_est=("_copq", "sum")
            ).reset_index()

            out_mach = out_mach[out_mach["count"] >= min_count]
            out_mach["Machine"] = out_mach["Machine"].astype(str).replace({"": "(blank)"})
            out_mach["_score"] = out_mach["count"] * 4 + out_mach["defect_qty"] * 1.5 + out_mach["downtime_mins"] * 0.5 + out_mach["copq_est"] * 0.01
            out_mach = out_mach.sort_values("_score", ascending=False).head(50).reset_index(drop=True)

            for i, r in out_mach.iterrows():
                self.tree_mach.insert("", "end", values=(
                    i + 1,
                    r["Machine"],
                    int(r["count"]),
                    int(r["defect_qty"]),
                    float(r["downtime_mins"]),
                    float(r["copq_est"])
                ))

        # 3) Tool COPQ repeats (only meaningful if tool numbers exist)
        out_tool = None
        if "Tool_Num" in sub.columns:
            grp = sub.groupby(["Tool_Num"], dropna=False)
            out_tool = grp.agg(
                count=("ID", "count"),
                defect_qty=("_defect_qty", "sum"),
                downtime_mins=("_dtmins", "sum"),
                copq_est=("_copq", "sum")
            ).reset_index()

            out_tool = out_tool[out_tool["count"] >= min_count]
            out_tool["Tool_Num"] = out_tool["Tool_Num"].astype(str).replace({"": "(blank)"})
            out_tool["_score"] = out_tool["count"] * 3 + out_tool["defect_qty"] * 1.0 + out_tool["downtime_mins"] * 0.4 + out_tool["copq_est"] * 0.02
            out_tool = out_tool.sort_values("_score", ascending=False).head(50).reset_index(drop=True)

            for i, r in out_tool.iterrows():
                self.tree_tool.insert("", "end", values=(
                    i + 1,
                    r["Tool_Num"],
                    int(r["count"]),
                    int(r["defect_qty"]),
                    float(r["downtime_mins"]),
                    float(r["copq_est"])
                ))

        self._out_part = out_part
        self._out_mach = out_mach
        self._out_tool = out_tool

        self.status.config(text=f"Window={window_days}d  MinCount={min_count}  Rows={len(sub)}")

    def export(self):
        if self._out_part is None and self._out_mach is None and self._out_tool is None:
            messagebox.showwarning("Nothing", "Nothing to export yet. Refresh first.")
            return

        now = datetime.now()
        path = f"{DATA_DIR}/repeat_offenders_{now.strftime('%Y_%m_%d_%H%M')}.xlsx"

        try:
            with pd.ExcelWriter(path, engine="openpyxl") as writer:
                if self._out_part is not None:
                    self._out_part.drop(columns=["_score"], errors="ignore").to_excel(writer, sheet_name="Part_Defect", index=False)
                if self._out_mach is not None:
                    self._out_mach.drop(columns=["_score"], errors="ignore").to_excel(writer, sheet_name="Machine", index=False)
                if self._out_tool is not None:
                    self._out_tool.drop(columns=["_score"], errors="ignore").to_excel(writer, sheet_name="Tool", index=False)

            messagebox.showinfo("Exported", f"Exported:\n{path}")
        except Exception as e:
            messagebox.showerror("Export failed", str(e))
