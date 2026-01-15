# app/ui_health_check.py
import tkinter as tk
from tkinter import ttk

from datetime import datetime, timedelta

from .ui_common import HeaderFrame
from .storage import get_df, load_json, safe_int, safe_float
from .config import GAGES_FILE, RISK_CONFIG_FILE


def _parse_date(s: str):
    s = str(s or "").strip()
    if not s:
        return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%Y/%m/%d", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(s, fmt)
        except Exception:
            pass
    return None


def _gage_due_status(g, risk_cfg):
    rules = (risk_cfg or {}).get("rules", {}) or {}
    due_soon_days = safe_int((rules.get("gage_calibration_escalation", {}) or {}).get("due_soon_days", 14), 14)

    last = _parse_date(g.get("last_calibration_date", ""))
    freq = safe_int(g.get("calibration_frequency_days", 0), 0)

    if not last or freq <= 0:
        return {"next_due": "", "status": "Unknown", "days_until_due": None}

    next_due = last + timedelta(days=freq)
    days_until = (next_due.date() - datetime.now().date()).days

    if days_until < 0:
        status = "Overdue"
    elif days_until <= due_soon_days:
        status = "Due Soon"
    else:
        status = "OK"

    return {"next_due": next_due.strftime("%Y-%m-%d"), "status": status, "days_until_due": days_until}


def _severity_rank(sev: str) -> int:
    return {"Low": 0, "Medium": 1, "High": 2, "Critical": 3}.get(sev, 0)


class HealthCheckUI(tk.Frame):
    def __init__(self, parent, controller, show_header=True):
        super().__init__(parent, bg=controller.colors["bg"])
        self.controller = controller

        if show_header:
            HeaderFrame(self, controller).pack(fill="x")

        self.risk_cfg = load_json(RISK_CONFIG_FILE, {})
        self.gage_store = load_json(GAGES_FILE, {"gages": []})
        self.gage_map = {g.get("gage_id"): g for g in self.gage_store.get("gages", []) if g.get("gage_id")}

        # Top bar
        top = tk.Frame(self, bg=controller.colors["bg"], padx=10, pady=10)
        top.pack(fill="x")

        tk.Label(
            top,
            text="Health Check (Super/Admin)",
            bg=controller.colors["bg"],
            fg=controller.colors["fg"],
            font=("Arial", 16, "bold")
        ).pack(side="left")

        tk.Button(top, text="Refresh", command=self.refresh).pack(side="right")

        # Filters (no tuple padding)
        filt = tk.Frame(self, bg=controller.colors["bg"], padx=10, pady=8)
        filt.pack(fill="x")

        tk.Label(filt, text="Minimum severity:", bg=controller.colors["bg"], fg=controller.colors["fg"]).pack(side="left")
        self.min_sev = ttk.Combobox(filt, values=["Low", "Medium", "High", "Critical"], state="readonly", width=12)
        self.min_sev.set("Medium")
        self.min_sev.pack(side="left", padx=8)
        self.min_sev.bind("<<ComboboxSelected>>", lambda e: self.refresh())

        tk.Label(filt, text="Show only missing fields:", bg=controller.colors["bg"], fg=controller.colors["fg"]).pack(side="left", padx=18)
        self.only_missing = tk.BooleanVar(value=False)
        tk.Checkbutton(
            filt,
            variable=self.only_missing,
            bg=controller.colors["bg"],
            fg=controller.colors["fg"],
            activebackground=controller.colors["bg"],
            activeforeground=controller.colors["fg"],
            selectcolor=controller.colors["bg"],
            command=self.refresh
        ).pack(side="left")

        # Results table
        cols = ("severity", "entry_id", "category", "issue", "suggestion")
        self.tree = ttk.Treeview(self, columns=cols, show="headings")
        for c in cols:
            self.tree.heading(c, text=c.upper())
            if c == "issue":
                self.tree.column(c, width=520)
            elif c == "suggestion":
                self.tree.column(c, width=380)
            else:
                self.tree.column(c, width=140)
        self.tree.pack(fill="both", expand=True, padx=10, pady=10)

        self.status = tk.Label(self, text="", bg=controller.colors["bg"], fg=controller.colors["fg"])
        self.status.pack(anchor="w", padx=12, pady=10)

        self.refresh()

    def refresh(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        df, _ = get_df()
        issues = self.run_checks(df)

        min_rank = _severity_rank(self.min_sev.get())
        only_missing = bool(self.only_missing.get())

        filtered = []
        for it in issues:
            if _severity_rank(it["severity"]) < min_rank:
                continue
            if only_missing and it["category"] != "Missing Field":
                continue
            filtered.append(it)

        filtered.sort(key=lambda x: _severity_rank(x["severity"]), reverse=True)

        for it in filtered:
            self.tree.insert("", "end", values=(
                it["severity"],
                it.get("entry_id", ""),
                it["category"],
                it["issue"],
                it["suggestion"]
            ))

        self.status.config(text=f"Found {len(filtered)} issues (filtered) — {len(issues)} total issues scanned.")

    def run_checks(self, df):
        issues = []
        if df is None or df.empty:
            return issues

        required = ["Line", "Machine", "Tool_Num", "Reason", "Part_Number"]

        gage_status = {}
        for gid, g in self.gage_map.items():
            ds = _gage_due_status(g, self.risk_cfg)
            gage_status[gid] = {
                "status": ds["status"],
                "next_due": ds["next_due"],
                "criticality": str(g.get("criticality", "Medium") or "Medium")
            }

        def add(sev, entry_id, cat, issue, suggestion):
            issues.append({
                "severity": sev,
                "entry_id": entry_id,
                "category": cat,
                "issue": issue,
                "suggestion": suggestion
            })

        for _, r in df.iterrows():
            entry_id = str(r.get("ID", "") or "")

            for col in required:
                if not str(r.get(col, "") or "").strip():
                    add("High", entry_id, "Missing Field",
                        f"Missing required field: {col}",
                        f"Fill {col} before saving/closing.")

            defects_present = str(r.get("Defects_Present", "") or "").strip().lower()
            defect_qty = safe_int(r.get("Defect_Qty", 0), 0)
            defect_code = str(r.get("Defect_Code", "") or "").strip()

            if defects_present == "yes" and defect_qty <= 0:
                add("High", entry_id, "Defects Logic",
                    "Defects_Present=Yes but Defect_Qty is 0/blank",
                    "Enter a valid defect quantity (or set Defects_Present=No).")

            if defects_present == "no" and defect_qty > 0:
                add("Medium", entry_id, "Defects Logic",
                    "Defects_Present=No but Defect_Qty > 0",
                    "Set Defects_Present=Yes or set Defect_Qty to 0.")

            if defects_present == "yes" and not defect_code:
                add("High", entry_id, "Defect Classification",
                    "Defects present but Defect_Code is blank",
                    "Select a Defect_Code for Pareto and NCR tracking.")

            qc_status = str(r.get("QC_Status", "") or "").strip()
            q_user = str(r.get("Quality_User", "") or "").strip()
            q_time = str(r.get("Quality_Time", "") or "").strip()

            if qc_status in ("Verified", "Closed") and (not q_user or not q_time):
                add("Medium", entry_id, "QC Workflow",
                    f"QC_Status={qc_status} but missing Quality_User/Quality_Time",
                    "Set Quality_User and Quality_Time when verifying.")

            ncr_id = str(r.get("NCR_ID", "") or "").strip()
            ncr_status = str(r.get("NCR_Status", "") or "").strip()
            ncr_close = str(r.get("NCR_Close_Date", "") or "").strip()

            if ncr_id and ncr_status == "Closed" and not ncr_close:
                add("High", entry_id, "NCR",
                    "NCR_Status=Closed but NCR_Close_Date is blank",
                    "Enter NCR_Close_Date or reopen the NCR.")

            action_status = str(r.get("Action_Status", "") or "").strip()
            due_str = str(r.get("Action_Due_Date", "") or "").strip()
            if action_status in ("Open", "Overdue") and due_str:
                due_dt = _parse_date(due_str)
                if due_dt and due_dt.date() < datetime.now().date():
                    add("High", entry_id, "Actions",
                        f"Action is overdue (due {due_dt.strftime('%Y-%m-%d')})",
                        "Complete the action or update the due date/owner.")

            g_used = str(r.get("Gage_Used", "") or "").strip()
            if g_used:
                gs = gage_status.get(g_used)
                if gs:
                    if gs["status"] == "Overdue":
                        crit = gs["criticality"]
                        sev = "High"
                        if crit in ("High", "Critical"):
                            sev = "Critical"
                        add(sev, entry_id, "Gage Calibration",
                            f"Gage {g_used} is Overdue (criticality={crit}, due {gs['next_due']})",
                            "Stop using this gage until calibrated (or correct last calibration date).")
                    elif gs["status"] == "Due Soon":
                        crit = gs["criticality"]
                        add("Medium", entry_id, "Gage Calibration",
                            f"Gage {g_used} is Due Soon (criticality={crit}, due {gs['next_due']})",
                            "Plan calibration before due date to avoid escalation.")
                else:
                    add("Medium", entry_id, "Gage Calibration",
                        f"Gage_Used={g_used} not found in gages.json",
                        "Add gage in Gages & Calibration Manager or correct the gage ID.")

        return issues
