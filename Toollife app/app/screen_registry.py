from __future__ import annotations

from typing import Dict, Tuple, Type
import tkinter as tk

SCREEN_REGISTRY: Dict[str, Tuple[str, str]] = {
    "Dashboard": ("app.ui_dashboard", "DashboardUI"),
    "Notifications": ("app.ui_notifications", "NotificationsUI"),
    "Action Center": ("app.ui_action_center", "ActionCenterUI"),
    "Tool Changer": ("app.ui_toolchanger", "ToolChangerUI"),
    "Operator": ("app.ui_operator", "OperatorUI"),
    "Leader": ("app.ui_leader", "LeaderUI"),
    "Quality": ("app.ui_quality", "QualityUI"),
    "Gages": ("app.ui_gages", "GagesUI"),
    "Risk Settings": ("app.ui_risk_settings", "RiskSettingsUI"),
    "Health Check": ("app.ui_health_check", "HealthCheckUI"),
    "Shift Handoff": ("app.ui_shift_handoff", "ShiftHandoffUI"),
    "Repeat Offenders": ("app.ui_repeat_offenders", "RepeatOffendersUI"),
    "Top level": ("app.ui_top", "TopUI"),
    "Master Data": ("app.ui_master_data", "MasterDataUI"),
    "Admin": ("app.ui_admin", "AdminUI"),
    "Audit Trail": ("app.ui_audit", "AuditTrailUI"),
}


def get_screen_class(screen: str) -> Type[tk.Frame]:
    module_name, class_name = SCREEN_REGISTRY[screen]
    mod = __import__(module_name, fromlist=[class_name])
    return getattr(mod, class_name)
