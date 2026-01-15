# app/ui_shift_handoff.py
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, timedelta

import pandas as pd

from .ui_common import HeaderFrame
from .storage import get_df, safe_int, safe_float
from .config import DATA_DIR
from .db import get_scrap_costs_simple


def _parse_date(s):
    # Accepts Date column formats. If parsing fails returns None.
    try:
        return pd.to_datetime(s, errors="coerce")
    except Exception:
        return pd.NaT


class ShiftHandoffUI(tk.Frame):
    """
    Super/Admin shift handoff summary generator.
    - Picks a date range
    - Summarizes key metrics
    - Shows top machines/parts/defects by qty and COPQ (if present)
    - Export to Excel
    """
    def __init__(self, parent, controller, show_header=True):
        super().__init__(parent, bg=controller.colors["bg"])
        self.controller = controller

        if show_header:
            HeaderFrame(self, controller).pack(fill="x")

        top = tk.Frame(self, bg=controller.colors["bg"], padx=10, pady=10)
        top.pack(fill="x")

        tk.Label(
            top,
            text="Shift Handoff Summary (Super/Admin)",
            bg=controller.colors["bg"],
            fg=controller.colors["fg"],
            font=("Arial", 16, "bold")
        ).pack(side="left")

        tk.Button(top, text="Generate", command=self.generate).pack(side="right")
        tk.Button(top, text="Export Excel", command=self.export).pack(side="right", padx=(0, 8))

        # Range selector
        rng = tk.Frame(self, bg=controller.colors["bg"], padx=10, pady=(0, 8))
        rng.pack(fill="x")

        tk.Label(rng, text="Range:", bg=controller.colors["bg"], fg=controller.colors["fg"]).pack(side="left")

        self.range_mode = ttk.Combobox(rng, state="readonly", width=18, values=[
            "Today",
            "Last 24 Hours",
            "Custom"
        ])
        self.range_mode.set("Today")
        self.range_mode.pack(side="left", padx=8)
        self.range_mode.bind("<<ComboboxSelected>>", lambda e: self._toggle_custom())

        tk.Label(rng, text="Start (YYYY-MM-DD):", bg=controller.colors["bg"], fg=controller.colors["fg"]).pack(side="left", padx=(18, 6))
        self.start_var = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))
        self.start_ent = tk.Entry(rng, textvariable=self.start_var, width=12)
        self.start_ent.pack(side="left")

        tk.Label(rng, text="End (YYYY-MM-DD):", bg=controller.colors["bg"], fg=controller.colors["fg"]).pack(side="left", padx=(18, 6))
        self.end_var = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))
        self.end_ent = tk.Entry(rng, textvariable=self.end_var, width=12)
        self.end_ent.pack(side="left")

        self._toggle_custom()

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=10, pady=10)

        self.tab_summary = tk.Frame(nb, bg=controller.colors["bg"])
        self.tab_scrap = tk.Frame(nb, bg=controller.colors["bg"])

        nb.add(self.tab_summary, text="Summary")
        nb.add(self.tab_scrap, text="Scrap Cost")

        # Summary text
        self.summary = tk.Text(self.tab_summary, height=14, wrap="word")
        self.summary.pack(fill="x", padx=10, pady=(0, 10))

        # Tables
        cols = ("rank", "key", "count", "defect_qty", "downtime_mins", "copq_est")
        self.tree = ttk.Treeview(self.tab_summary, columns=cols, show="headings", height=14)
        for c in cols:
            self.tree.heading(c, text=c.upper())
            if c == "key":
                self.tree.column(c, width=320)
            else:
                self.tree.column(c, width=120)
        self.tree.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        self.scrap_canvas = tk.Canvas(self.tab_scrap, bg="white", height=360)
        self.scrap_canvas.pack(fill="both", expand=True, padx=10, pady=10)

        # cache last generated
        self._last_df = None
        self._last_summary_rows = None

        self.generate()

    def _toggle_custom(self):
        custom = (self.range_mode.get() == "Custom")
        state = "normal" if custom else "disabled"
        self.start_ent.config(state=state)
        self.end_ent.config(state=state)

    def _get_range(self):
        mode = self.range_mode.get()
        now = datetime.now()

        if mode == "Today":
            start = datetime(now.year, now.month, now.day)
            end = now
            return start, end

        if mode == "Last 24 Hours":
            start = now - timedelta(hours=24)
            end = now
            return start, end

        # Custom
        try:
            s = datetime.strptime(self.start_var.get().strip(), "%Y-%m-%d")
            e = datetime.strptime(self.end_var.get().strip(), "%Y-%m-%d")
            # include whole end day
            end = datetime(e.year, e.month, e.day, 23, 59, 59)
            return s, end
        except Exception:
            return None, None

    def generate(self):
        self.summary.delete("1.0", tk.END)
        for item in self.tree.get_children():
            self.tree.delete(item)

        df, fname = get_df()
        if df is None or df.empty:
            self.summary.insert(tk.END, "No data found in current month file.\n")
            return

        # Ensure Date parsed
        df = df.copy()
        df["_dt"] = pd.to_datetime(df.get("Date", ""), errors="coerce")

        start, end = self._get_range()
        if not start or not end:
            messagebox.showerror("Invalid range", "Fix your start/end dates (YYYY-MM-DD).")
            return

        # Filter range
        mask = df["_dt"].notna() & (df["_dt"] >= pd.Timestamp(start)) & (df["_dt"] <= pd.Timestamp(end))
        sub = df.loc[mask].copy()

        self._last_df = sub

        # Normalize numeric fields
        sub["_defect_qty"] = sub.get("Defect_Qty", 0).apply(lambda x: safe_int(x, 0))
        sub["_dtmins"] = sub.get("Downtime_Mins", 0).apply(lambda x: safe_float(x, 0.0))

        # Metrics
        total_entries = len(sub)
        total_downtime = sub["_dtmins"].sum()
        total_defects = sub["_defect_qty"].sum()

        # Tool changes: assume every row is a tool change entry
        tool_changes = total_entries

        # Andon count
        andon_count = sub.get("Andon_Flag", "").astype(str).str.lower().eq("yes").sum() if "Andon_Flag" in sub.columns else 0

        # High/Critical risk count
        risk_high = sub.get("Customer_Risk", "").isin(["High", "Critical"]).sum() if "Customer_Risk" in sub.columns else 0

        # COPQ total if present
        copq_total = 0.0
        if "COPQ_Est" in sub.columns:
            copq_total = sub["COPQ_Est"].apply(lambda x: safe_float(x, 0.0)).sum()

        scrap_costs = get_scrap_costs_simple()
        sub["_scrap_cost"] = sub.get("Part_Number", "").map(scrap_costs).fillna(0.0) * sub["_defect_qty"]
        scrap_total = float(sub["_scrap_cost"].sum())

        # Open actions
        open_actions = sub.get("Action_Status", "").isin(["Open", "Overdue"]).sum() if "Action_Status" in sub.columns else 0

        # Compose summary
        self.summary.insert(tk.END, f"Source file: {fname}\n")
        self.summary.insert(tk.END, f"Range: {start.strftime('%Y-%m-%d %H:%M')} → {end.strftime('%Y-%m-%d %H:%M')}\n\n")

        self.summary.insert(tk.END, f"Tool change entries: {tool_changes}\n")
        self.summary.insert(tk.END, f"Total downtime (mins): {total_downtime:.1f}\n")
        self.summary.insert(tk.END, f"Total defects (qty): {total_defects}\n")
        self.summary.insert(tk.END, f"Andon events: {andon_count}\n")
        self.summary.insert(tk.END, f"High/Critical risk entries: {risk_high}\n")
        self.summary.insert(tk.END, f"Open/Overdue actions (rows): {open_actions}\n")
        self.summary.insert(tk.END, f"Total COPQ estimate: ${copq_total:,.2f}\n\n")
        self.summary.insert(tk.END, f"Total scrap cost: ${scrap_total:,.2f}\n\n")

        self.summary.insert(tk.END, "Top offenders table below = combined score by count/defects/downtime/COPQ.\n")

        # Build offender table: machines + parts + defect codes together
        rows = []
        def add_group(col_name, label):
            if col_name not in sub.columns:
                return
            grp = sub.groupby(col_name, dropna=False)
            for key, g in grp:
                key = str(key).strip() if str(key).strip() else "(blank)"
                count = len(g)
                dqty = g.get("Defect_Qty", pd.Series([])).apply(lambda x: safe_int(x, 0)).sum()
                dt = g.get("Downtime_Mins", pd.Series([])).apply(lambda x: safe_float(x, 0.0)).sum()
                copq = g.get("COPQ_Est", pd.Series([])).apply(lambda x: safe_float(x, 0.0)).sum() if "COPQ_Est" in g.columns else 0.0
                rows.append({
                    "group": label,
                    "key": f"{label}: {key}",
                    "count": count,
                    "defect_qty": dqty,
                    "downtime_mins": dt,
                    "copq_est": copq
                })

        add_group("Machine", "Machine")
        add_group("Part_Number", "Part")
        add_group("Defect_Code", "Defect")

        if not rows:
            self.summary.insert(tk.END, "\nNo grouping fields found to generate offender table.\n")
            return

        out = pd.DataFrame(rows)

        # Score: weighted simple (tune later)
        out["_score"] = (
            out["count"] * 1.0 +
            out["defect_qty"] * 2.0 +
            out["downtime_mins"] * 0.5 +
            out["copq_est"] * 0.01
        )

        out = out.sort_values("_score", ascending=False).head(25).reset_index(drop=True)

        self._last_summary_rows = out

        for i, r in out.iterrows():
            self.tree.insert("", "end", values=(
                i + 1,
                r["key"],
                int(r["count"]),
                int(r["defect_qty"]),
                float(r["downtime_mins"]),
                float(r["copq_est"])
            ))

        self._update_scrap_chart(sub, start, end)

    def _update_scrap_chart(self, df: pd.DataFrame, start: datetime, end: datetime):
        self.scrap_canvas.delete("all")
        if df.empty:
            self.scrap_canvas.create_text(10, 10, anchor="nw", text="No scrap data in range.")
            return

        days = max(1, (end.date() - start.date()).days + 1)
        if days > 31:
            df["_bucket"] = df["_dt"].dt.to_period("W").apply(lambda p: p.start_time.strftime("%Y-%m-%d"))
            label = "Week Starting"
        else:
            df["_bucket"] = df["_dt"].dt.strftime("%Y-%m-%d")
            label = "Date"

        out = df.groupby("_bucket", dropna=False).agg(scrap_cost=("_scrap_cost", "sum")).reset_index()
        out = out.sort_values("_bucket").reset_index(drop=True)
        if out.empty:
            self.scrap_canvas.create_text(10, 10, anchor="nw", text="No scrap costs recorded.")
            return

        width = max(640, self.scrap_canvas.winfo_width() or 640)
        height = max(300, self.scrap_canvas.winfo_height() or 300)
        padding = 60
        chart_w = width - padding * 2
        chart_h = height - padding * 2

        max_val = max(out["scrap_cost"].max(), 1.0)
        bar_w = max(6, chart_w / max(len(out), 1))
        x = padding

        self.scrap_canvas.create_text(padding, 10, anchor="nw", text=f"Scrap Cost by {label}")

        for _, row in out.iterrows():
            val = float(row["scrap_cost"])
            bar_h = (val / max_val) * chart_h
            self.scrap_canvas.create_rectangle(
                x,
                padding + chart_h - bar_h,
                x + bar_w * 0.8,
                padding + chart_h,
                fill="#4c78a8",
                outline=""
            )
            self.scrap_canvas.create_text(x + bar_w * 0.4, padding + chart_h + 8, anchor="n", text=row["_bucket"], angle=45)
            x += bar_w

    def export(self):
        if self._last_df is None or self._last_summary_rows is None:
            messagebox.showwarning("Nothing to export", "Generate a report first.")
            return

        now = datetime.now()
        path = f"{DATA_DIR}/shift_handoff_{now.strftime('%Y_%m_%d_%H%M')}.xlsx"

        try:
            with pd.ExcelWriter(path, engine="openpyxl") as writer:
                self._last_df.drop(columns=["_dt"], errors="ignore").to_excel(writer, sheet_name="Filtered_Entries", index=False)
                self._last_summary_rows.drop(columns=["_score"], errors="ignore").to_excel(writer, sheet_name="Top_Offenders", index=False)

            messagebox.showinfo("Exported", f"Exported:\n{path}")
        except Exception as e:
            messagebox.showerror("Export failed", str(e))
