# app/ui_risk_settings.py
import tkinter as tk
from tkinter import ttk, messagebox

from .ui_common import HeaderFrame
from .storage import load_json, save_json
from .config import RISK_CONFIG_FILE


def _safe_int(s: str, default: int) -> int:
    try:
        return int(float(str(s).strip()))
    except Exception:
        return default


def _safe_float(s: str, default: float) -> float:
    try:
        return float(str(s).strip())
    except Exception:
        return default


class RiskSettingsUI(tk.Frame):
    """
    Super/Admin screen to edit risk_config.json safely.
    """
    def __init__(self, parent, controller, show_header=True):
        super().__init__(parent, bg=controller.colors["bg"])
        self.controller = controller

        if show_header:
            HeaderFrame(self, controller).pack(fill="x")

        self.cfg = load_json(RISK_CONFIG_FILE, {})
        self._ensure_shape()

        # Title + buttons
        top = tk.Frame(self, bg=controller.colors["bg"], padx=10, pady=10)
        top.pack(fill="x")

        tk.Label(
            top,
            text="Risk Settings (Super/Admin)",
            bg=controller.colors["bg"],
            fg=controller.colors["fg"],
            font=("Arial", 16, "bold")
        ).pack(side="left")

        tk.Button(top, text="Reload", command=self.reload).pack(side="right", padx=(8, 0))
        tk.Button(top, text="Save", command=self.save).pack(side="right")

        # Scrollable body
        canvas = tk.Canvas(self, bg=controller.colors["bg"], highlightthickness=0)
        canvas.pack(side="left", fill="both", expand=True)

        vsb = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        vsb.pack(side="right", fill="y")

        canvas.configure(yscrollcommand=vsb.set)
        body = tk.Frame(canvas, bg=controller.colors["bg"])
        canvas.create_window((0, 0), window=body, anchor="nw")

        body.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

        # Vars
        rules = self.cfg["rules"]

        self.var_andon_always_critical = tk.BooleanVar(value=bool(rules.get("andon_always_critical", True)))

        copq = rules["copq_thresholds"]
        self.var_copq_med = tk.StringVar(value=str(copq.get("medium", 250.0)))
        self.var_copq_high = tk.StringVar(value=str(copq.get("high", 750.0)))
        self.var_copq_crit = tk.StringVar(value=str(copq.get("critical", 1500.0)))

        dq = rules["defect_qty_thresholds"]
        self.var_dq_med = tk.StringVar(value=str(dq.get("medium", 5)))
        self.var_dq_high = tk.StringVar(value=str(dq.get("high", 15)))
        self.var_dq_crit = tk.StringVar(value=str(dq.get("critical", 30)))

        rep = rules["repeat_offender_escalation"]
        self.var_rep_watch = tk.StringVar(value=str(rep.get("watch_score", 50)))
        self.var_rep_high = tk.StringVar(value=str(rep.get("high_score", 80)))
        self.var_rep_crit = tk.StringVar(value=str(rep.get("critical_score", 110)))

        oa = rules["overdue_action_escalation"]
        self.var_oa_high_days = tk.StringVar(value=str(oa.get("high_after_days_overdue", 1)))
        self.var_oa_crit_days = tk.StringVar(value=str(oa.get("critical_after_days_overdue", 3)))

        na = rules["ncr_age_escalation"]
        self.var_ncr_high_days = tk.StringVar(value=str(na.get("high_after_days_open", 3)))
        self.var_ncr_crit_days = tk.StringVar(value=str(na.get("critical_after_days_open", 7)))

        gcal = rules["gage_calibration_escalation"]
        self.var_due_soon_days = tk.StringVar(value=str(gcal.get("due_soon_days", 14)))

        gmap = gcal["overdue_criticality_map"]
        self.var_map_low = tk.StringVar(value=str(gmap.get("Low", "Medium")))
        self.var_map_med = tk.StringVar(value=str(gmap.get("Medium", "High")))
        self.var_map_high = tk.StringVar(value=str(gmap.get("High", "Critical")))
        self.var_map_crit = tk.StringVar(value=str(gmap.get("Critical", "Critical")))

        # UI sections
        row = 0
        row = self._section_title(body, "Core Rules", row)
        row = self._bool_row(body, "Andon always triggers Critical severity", self.var_andon_always_critical, row)

        row = self._section_title(body, "COPQ Thresholds ($)", row)
        row = self._triple_row(body, "Medium / High / Critical", self.var_copq_med, self.var_copq_high, self.var_copq_crit, row)

        row = self._section_title(body, "Defect Qty Thresholds", row)
        row = self._triple_row(body, "Medium / High / Critical", self.var_dq_med, self.var_dq_high, self.var_dq_crit, row)

        row = self._section_title(body, "Repeat Offender Escalation Scores", row)
        row = self._triple_row(body, "Watch / High / Critical", self.var_rep_watch, self.var_rep_high, self.var_rep_crit, row)

        row = self._section_title(body, "Overdue Escalation", row)
        row = self._pair_row(body, "Actions overdue → High after days", self.var_oa_high_days, row)
        row = self._pair_row(body, "Actions overdue → Critical after days", self.var_oa_crit_days, row)
        row = self._pair_row(body, "NCR open → High after days", self.var_ncr_high_days, row)
        row = self._pair_row(body, "NCR open → Critical after days", self.var_ncr_crit_days, row)

        row = self._section_title(body, "Gage Calibration Escalation", row)
        row = self._pair_row(body, "Due soon window (days)", self.var_due_soon_days, row)

        row = self._section_title(body, "Overdue Gage Criticality → Severity", row)
        row = self._map_row(body, "If gage criticality is Low", self.var_map_low, row)
        row = self._map_row(body, "If gage criticality is Medium", self.var_map_med, row)
        row = self._map_row(body, "If gage criticality is High", self.var_map_high, row)
        row = self._map_row(body, "If gage criticality is Critical", self.var_map_crit, row)

        # Footer padding
        tk.Frame(body, height=20, bg=controller.colors["bg"]).grid(row=row, column=0, columnspan=4, sticky="we")

    # --------------------------
    # Helpers: layout
    # --------------------------
    def _section_title(self, parent, title: str, row: int) -> int:
        tk.Label(
            parent,
            text=title,
            bg=self.controller.colors["bg"],
            fg=self.controller.colors["fg"],
            font=("Arial", 13, "bold")
        ).grid(row=row, column=0, sticky="w", padx=12, pady=(18, 6))
        return row + 1

    def _bool_row(self, parent, label: str, var: tk.BooleanVar, row: int) -> int:
        frm = tk.Frame(parent, bg=self.controller.colors["bg"])
        frm.grid(row=row, column=0, columnspan=4, sticky="we", padx=12, pady=4)
        tk.Checkbutton(
            frm,
            text=label,
            variable=var,
            bg=self.controller.colors["bg"],
            fg=self.controller.colors["fg"],
            activebackground=self.controller.colors["bg"],
            activeforeground=self.controller.colors["fg"],
            selectcolor=self.controller.colors["bg"]
        ).pack(anchor="w")
        return row + 1

    def _triple_row(self, parent, label: str, v1: tk.StringVar, v2: tk.StringVar, v3: tk.StringVar, row: int) -> int:
        tk.Label(parent, text=label, bg=self.controller.colors["bg"], fg=self.controller.colors["fg"]).grid(
            row=row, column=0, sticky="w", padx=12, pady=4
        )
        e1 = tk.Entry(parent, textvariable=v1, width=10)
        e2 = tk.Entry(parent, textvariable=v2, width=10)
        e3 = tk.Entry(parent, textvariable=v3, width=10)
        e1.grid(row=row, column=1, sticky="w", padx=(6, 6))
        e2.grid(row=row, column=2, sticky="w", padx=(6, 6))
        e3.grid(row=row, column=3, sticky="w", padx=(6, 6))
        return row + 1

    def _pair_row(self, parent, label: str, v: tk.StringVar, row: int) -> int:
        tk.Label(parent, text=label, bg=self.controller.colors["bg"], fg=self.controller.colors["fg"]).grid(
            row=row, column=0, sticky="w", padx=12, pady=4
        )
        tk.Entry(parent, textvariable=v, width=10).grid(row=row, column=1, sticky="w", padx=(6, 6))
        return row + 1

    def _map_row(self, parent, label: str, v: tk.StringVar, row: int) -> int:
        tk.Label(parent, text=label, bg=self.controller.colors["bg"], fg=self.controller.colors["fg"]).grid(
            row=row, column=0, sticky="w", padx=12, pady=4
        )
        cb = ttk.Combobox(parent, textvariable=v, state="readonly", width=12,
                          values=["Low", "Medium", "High", "Critical"])
        cb.grid(row=row, column=1, sticky="w", padx=(6, 6))
        return row + 1

    # --------------------------
    # Config shape + IO
    # --------------------------
    def _ensure_shape(self):
        """
        Ensure cfg has expected keys so UI doesn't crash if file is incomplete.
        """
        if not isinstance(self.cfg, dict):
            self.cfg = {}

        self.cfg.setdefault("severity_levels", ["Low", "Medium", "High", "Critical"])
        self.cfg.setdefault("rules", {})
        rules = self.cfg["rules"]

        rules.setdefault("andon_always_critical", True)
        rules.setdefault("customer_risk_map", {"Low": "Low", "Med": "Medium", "Medium": "Medium", "High": "High", "Critical": "Critical"})

        rules.setdefault("copq_thresholds", {"medium": 250.0, "high": 750.0, "critical": 1500.0})
        rules.setdefault("defect_qty_thresholds", {"medium": 5, "high": 15, "critical": 30})
        rules.setdefault("repeat_offender_escalation", {"watch_score": 50, "high_score": 80, "critical_score": 110})
        rules.setdefault("overdue_action_escalation", {"high_after_days_overdue": 1, "critical_after_days_overdue": 3})
        rules.setdefault("ncr_age_escalation", {"high_after_days_open": 3, "critical_after_days_open": 7})
        rules.setdefault("gage_calibration_escalation", {})
        gcal = rules["gage_calibration_escalation"]
        gcal.setdefault("due_soon_days", 14)
        gcal.setdefault("overdue_criticality_map", {"Low": "Medium", "Medium": "High", "High": "Critical", "Critical": "Critical"})

    def reload(self):
        self.cfg = load_json(RISK_CONFIG_FILE, {})
        self._ensure_shape()
        messagebox.showinfo("Reloaded", "Risk settings reloaded.\n\n(Re-open tab to refresh fields.)")

    def _validate(self) -> str | None:
        # Numeric order checks
        copq_med = _safe_float(self.var_copq_med.get(), 0.0)
        copq_high = _safe_float(self.var_copq_high.get(), 0.0)
        copq_crit = _safe_float(self.var_copq_crit.get(), 0.0)
        if not (0 <= copq_med < copq_high < copq_crit):
            return "COPQ thresholds must be increasing: Medium < High < Critical."

        dq_med = _safe_int(self.var_dq_med.get(), 0)
        dq_high = _safe_int(self.var_dq_high.get(), 0)
        dq_crit = _safe_int(self.var_dq_crit.get(), 0)
        if not (0 <= dq_med < dq_high < dq_crit):
            return "Defect qty thresholds must be increasing: Medium < High < Critical."

        rep_watch = _safe_int(self.var_rep_watch.get(), 0)
        rep_high = _safe_int(self.var_rep_high.get(), 0)
        rep_crit = _safe_int(self.var_rep_crit.get(), 0)
        if not (0 <= rep_watch < rep_high < rep_crit):
            return "Repeat scores must be increasing: Watch < High < Critical."

        due_soon = _safe_int(self.var_due_soon_days.get(), 14)
        if due_soon < 0 or due_soon > 365:
            return "Due soon days must be between 0 and 365."

        # Severity map values must be valid
        valid = {"Low", "Medium", "High", "Critical"}
        if self.var_map_low.get() not in valid or self.var_map_med.get() not in valid or self.var_map_high.get() not in valid or self.var_map_crit.get() not in valid:
            return "Overdue gage mapping must map to Low/Medium/High/Critical."

        return None

    def save(self):
        err = self._validate()
        if err:
            messagebox.showerror("Invalid Settings", err)
            return

        self._ensure_shape()
        rules = self.cfg["rules"]

        rules["andon_always_critical"] = bool(self.var_andon_always_critical.get())

        rules["copq_thresholds"] = {
            "medium": _safe_float(self.var_copq_med.get(), 250.0),
            "high": _safe_float(self.var_copq_high.get(), 750.0),
            "critical": _safe_float(self.var_copq_crit.get(), 1500.0)
        }

        rules["defect_qty_thresholds"] = {
            "medium": _safe_int(self.var_dq_med.get(), 5),
            "high": _safe_int(self.var_dq_high.get(), 15),
            "critical": _safe_int(self.var_dq_crit.get(), 30)
        }

        rules["repeat_offender_escalation"] = {
            "watch_score": _safe_int(self.var_rep_watch.get(), 50),
            "high_score": _safe_int(self.var_rep_high.get(), 80),
            "critical_score": _safe_int(self.var_rep_crit.get(), 110)
        }

        rules["overdue_action_escalation"] = {
            "high_after_days_overdue": _safe_int(self.var_oa_high_days.get(), 1),
            "critical_after_days_overdue": _safe_int(self.var_oa_crit_days.get(), 3)
        }

        rules["ncr_age_escalation"] = {
            "high_after_days_open": _safe_int(self.var_ncr_high_days.get(), 3),
            "critical_after_days_open": _safe_int(self.var_ncr_crit_days.get(), 7)
        }

        gcal = rules.setdefault("gage_calibration_escalation", {})
        gcal["due_soon_days"] = _safe_int(self.var_due_soon_days.get(), 14)
        gcal["overdue_criticality_map"] = {
            "Low": self.var_map_low.get(),
            "Medium": self.var_map_med.get(),
            "High": self.var_map_high.get(),
            "Critical": self.var_map_crit.get()
        }

        save_json(RISK_CONFIG_FILE, self.cfg)
        messagebox.showinfo("Saved", "Risk settings saved successfully.")
