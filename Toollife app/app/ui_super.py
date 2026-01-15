# app/ui_super.py
from __future__ import annotations

import tkinter as tk
from tkinter import ttk


class _PlaceholderUI(tk.Frame):
    """Shown when a tab's module/class isn't available yet (prevents app crash)."""
    def __init__(self, parent, controller, title="Missing Screen", detail="", show_header=False):
        super().__init__(parent, bg=controller.colors["bg"])
        fg = controller.colors.get("fg", "#FFFFFF")
        bg = controller.colors.get("bg", "#111111")

        wrap = tk.Frame(self, bg=bg, padx=18, pady=18)
        wrap.pack(fill="both", expand=True)

        tk.Label(
            wrap, text=title, bg=bg, fg=fg, font=("Arial", 16, "bold")
        ).pack(anchor="w")

        if detail:
            tk.Label(
                wrap, text=detail, bg=bg, fg=fg, font=("Arial", 11), justify="left"
            ).pack(anchor="w", pady=(10, 0))


def _safe_view(factory, missing_title: str, missing_detail: str):
    """
    Returns a callable/class-like that produces a Frame.
    If factory import fails, returns PlaceholderUI.
    """
    try:
        return factory()
    except Exception:
        return lambda parent, controller, show_header=False: _PlaceholderUI(
            parent, controller, title=missing_title, detail=missing_detail
        )


def _instantiate_view(ViewCls, tab, controller):
    """
    Child screens in this project aren't perfectly consistent:
    some accept show_header=..., some don't.
    """
    try:
        ViewCls(tab, controller, show_header=False).pack(fill="both", expand=True)
    except TypeError:
        ViewCls(tab, controller).pack(fill="both", expand=True)


class SuperUI(tk.Frame):
    """
    Super (Top/Super User) UI:
    - All screens available
    - Safe-loading tabs so missing modules don't crash the whole app
    """
    def __init__(self, parent, controller, show_header=True):
        super().__init__(parent, bg=controller.colors["bg"])
        self.controller = controller

        # Header (if you have one)
        if show_header:
            HeaderFrame = _safe_view(
                lambda: __import__("app.ui_common", fromlist=["HeaderFrame"]).HeaderFrame,
                "Header Missing",
                "app/ui_common.py (HeaderFrame) not found.",
            )
            try:
                HeaderFrame(self, controller).pack(fill="x")
            except Exception:
                pass

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=10, pady=10)

        # ---- Tab factories (lazy imports) ----
        NotificationsUI = _safe_view(
            lambda: __import__("app.ui_notifications", fromlist=["NotificationsUI"]).NotificationsUI,
            "Notifications screen missing",
            "Expected: app/ui_notifications.py → class NotificationsUI",
        )
        LeaderUI = _safe_view(
            lambda: __import__("app.ui_leader", fromlist=["LeaderUI"]).LeaderUI,
            "Leader screen missing",
            "Expected: app/ui_leader.py → class LeaderUI",
        )
        QualityUI = _safe_view(
            lambda: __import__("app.ui_quality", fromlist=["QualityUI"]).QualityUI,
            "Quality screen missing",
            "Expected: app/ui_quality.py → class QualityUI",
        )
        AdminUI = _safe_view(
            lambda: __import__("app.ui_admin", fromlist=["AdminUI"]).AdminUI,
            "Admin screen missing",
            "Expected: app/ui_admin.py → class AdminUI",
        )
        GagesUI = _safe_view(
            lambda: __import__("app.ui_gages", fromlist=["GagesUI"]).GagesUI,
            "Gages screen missing",
            "Expected: app/ui_gages.py → class GagesUI",
        )
        MasterDataUI = _safe_view(
            lambda: __import__("app.ui_master_data", fromlist=["MasterDataUI"]).MasterDataUI,
            "Master Data screen missing",
            "Expected: app/ui_master_data.py → class MasterDataUI",
        )

        # Optional / may not exist yet — we keep them as placeholders if missing
        ToolChangerUI = _safe_view(
            lambda: __import__("app.ui_toolchanger", fromlist=["ToolChangerUI"]).ToolChangerUI,
            "Tool Changer screen missing",
            "Expected: app/ui_toolchanger.py → class ToolChangerUI",
        )
        OperatorUI = _safe_view(
            lambda: __import__("app.ui_operator", fromlist=["OperatorUI"]).OperatorUI,
            "Operator screen missing",
            "Expected: app/ui_operator.py → class OperatorUI",
        )
        ActionCenterUI = _safe_view(
            lambda: __import__("app.ui_action_center", fromlist=["ActionCenterUI"]).ActionCenterUI,
            "Action Center screen missing",
            "Expected: app/ui_action_center.py → class ActionCenterUI",
        )
        AuditTrailUI = _safe_view(
            lambda: __import__("app.ui_audit", fromlist=["AuditTrailUI"]).AuditTrailUI,
            "Audit Trail screen missing",
            "Expected: app/ui_audit.py → class AuditTrailUI",
        )
        DashboardUI = _safe_view(
            lambda: __import__("app.ui_dashboard", fromlist=["DashboardUI"]).DashboardUI,
            "Dashboard screen missing",
            "Expected: app/ui_dashboard.py → class DashboardUI",
        )
        RiskSettingsUI = _safe_view(
            lambda: __import__("app.ui_risk_settings", fromlist=["RiskSettingsUI"]).RiskSettingsUI,
            "Risk Settings screen missing",
            "Expected: app/ui_risk_settings.py → class RiskSettingsUI",
        )
        HealthCheckUI = _safe_view(
            lambda: __import__("app.ui_health_check", fromlist=["HealthCheckUI"]).HealthCheckUI,
            "Health Check screen missing",
            "Expected: app/ui_health_check.py → class HealthCheckUI",
        )
        ShiftHandoffUI = _safe_view(
            lambda: __import__("app.ui_shift_handoff", fromlist=["ShiftHandoffUI"]).ShiftHandoffUI,
            "Shift Handoff screen missing",
            "Expected: app/ui_shift_handoff.py → class ShiftHandoffUI",
        )
        RepeatOffendersUI = _safe_view(
            lambda: __import__("app.ui_repeat_offenders", fromlist=["RepeatOffendersUI"]).RepeatOffendersUI,
            "Repeat Offenders screen missing",
            "Expected: app/ui_repeat_offenders.py → class RepeatOffendersUI",
        )
        TopUI = _safe_view(
            lambda: __import__("app.ui_top", fromlist=["TopUI"]).TopUI,
            "Top/Super Tools screen missing",
            "Expected: app/ui_top.py → class TopUI (optional).",
        )

        # ---- Tabs (Super gets everything) ----
        tabs = [
            ("On Shift Pass Down", DashboardUI),
            ("Notifications", NotificationsUI),
            ("Action Center", ActionCenterUI),
            ("Audit Trail", AuditTrailUI),

            ("Tool Changer", ToolChangerUI),
            ("Operator", OperatorUI),
            ("Leader", LeaderUI),
            ("Quality", QualityUI),

            ("Gages", GagesUI),

            ("Risk Settings", RiskSettingsUI),
            ("Health Check", HealthCheckUI),
            ("Shift Handoff", ShiftHandoffUI),
            ("Repeat Offenders", RepeatOffendersUI),

            ("Top level", TopUI),
            ("Master Data", MasterDataUI),
            ("Admin", AdminUI),
        ]

        # Build tabs
        for name, ViewCls in tabs:
            tab = tk.Frame(nb, bg=controller.colors["bg"])
            nb.add(tab, text=name)
            _instantiate_view(ViewCls, tab, controller)
