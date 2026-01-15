# app/config.py
from __future__ import annotations

from pathlib import Path
from datetime import datetime

# ----------------------------
# Project structure
# ----------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent

BASE_DIR = str(PROJECT_ROOT)
APP_DIR = str(PROJECT_ROOT / "app")
DATA_DIR = str(PROJECT_ROOT / "data")
LOGS_DIR = str(PROJECT_ROOT / "logs")
LOG_DIR = LOGS_DIR  # compat alias
BACKUPS_DIR = str(PROJECT_ROOT / "backups")

# Logs
AUDIT_LOG_FILE = str(Path(LOGS_DIR) / "audit.log")
AUDIT_LOGFILE = AUDIT_LOG_FILE  # compat alias
STARTUP_LOG_FILE = str(Path(LOGS_DIR) / "startup.log")

# ----------------------------
# Core data files
# ----------------------------
USERS_FILE = str(Path(DATA_DIR) / "users.json")

REASONS_FILE = str(Path(DATA_DIR) / "reasons.json")
PARTS_FILE = str(Path(DATA_DIR) / "parts.json")
TOOL_CONFIG_FILE = str(Path(DATA_DIR) / "tool_config.json")

DEFECT_CODES_FILE = str(Path(DATA_DIR) / "defect_codes.json")
ANDON_REASONS_FILE = str(Path(DATA_DIR) / "andon_reasons.json")

COST_CONFIG_FILE = str(Path(DATA_DIR) / "cost_config.json")
RISK_CONFIG_FILE = str(Path(DATA_DIR) / "risk_config.json")
REPEAT_RULES_FILE = str(Path(DATA_DIR) / "repeat_rules.json")
LPA_CHECKLIST_FILE = str(Path(DATA_DIR) / "lpa_checklist.json")

GAGES_FILE = str(Path(DATA_DIR) / "gages.json")
GAGE_VERIFICATION_Q_FILE = str(Path(DATA_DIR) / "gage_verification_questions.json")
DB_PATH = str(Path(DATA_DIR) / "toollife.db")

# Action/NCR system
NCRS_FILE = str(Path(DATA_DIR) / "ncrs.json")
ACTIONS_FILE = str(Path(DATA_DIR) / "actions.json")

# ----------------------------
# Date helpers expected by modules
# ----------------------------
def current_month_iso(dt: datetime | None = None) -> str:
    """Returns YYYY-MM."""
    if dt is None:
        dt = datetime.now()
    return dt.strftime("%Y-%m")


# ----------------------------
# Excel / Alerts paths
# ----------------------------
def month_excel_path(dt: datetime | None = None) -> str:
    """
    Main monthly workbook.
    IMPORTANT: storage.list_month_files() looks for tool_life_data_YYYY_MM.xlsx
    so we use that naming convention to match. :contentReference[oaicite:5]{index=5}
    """
    if dt is None:
        dt = datetime.now()
    return str(Path(DATA_DIR) / f"tool_life_data_{dt.strftime('%Y_%m')}.xlsx")


def alerts_file_for_month(dt: datetime | None = None) -> str:
    if dt is None:
        dt = datetime.now()
    return str(Path(DATA_DIR) / f"alerts_{dt.strftime('%Y_%m')}.json")


def gage_verification_log_path(dt: datetime | None = None) -> str:
    if dt is None:
        dt = datetime.now()
    return str(Path(DATA_DIR) / f"gage_verifications_{dt.strftime('%Y_%m')}.xlsx")


# ----------------------------
# Excel schema
# ----------------------------
# Must include columns used by UI screens (Leader/Quality signoff, etc.) :contentReference[oaicite:6]{index=6}
COLUMNS = [
    # identity
    "ID", "Date", "Time",

    # routing
    "Line", "Machine",

    # tool/part context
    "Tool_Num", "Part_Number", "Reason",

    # downtime / defects
    "Downtime_Mins",
    "Defects_Present", "Defect_Qty", "Defect_Code",

    # quality / risk flags
    "Andon_Flag",
    "Customer_Risk",

    # QC workflow fields used by logic/notifications
    "QC_Status",
    "Quality_Verified",          # Leader UI expects this column exists
    "Quality_User",
    "Quality_Time",

    # Leader workflow fields used by LeaderUI
    "Leader_Sign",
    "Leader_User",
    "Leader_Time",

    # NCR fields (Excel-side tracking)
    "NCR_ID",
    "NCR_Status",
    "NCR_Close_Date",

    # Action fields (Excel-side tracking)
    "Action_Status",
    "Action_Due_Date",

    # Gage / cost fields
    "Gage_Used",
    "COPQ_Est",
]

# ----------------------------
# DEFAULT STORES (bootstrap expects these names) :contentReference[oaicite:7]{index=7}
# ----------------------------
DEFAULT_USERS = {
    "super": {"password": "super", "role": "Top (Super User)", "name": "Super User", "line": "Both"},
    "admin": {"password": "admin", "role": "Admin", "name": "Admin User", "line": "Both"},
}

DEFAULT_REASONS = []
DEFAULT_PARTS = []
DEFAULT_TOOL_CONFIG = {}
DEFAULT_LINES = ["U725", "JL"]
DEFAULT_DOWNTIME_CODES = []
# Default tool numbers to seed on first launch per line.
DEFAULT_LINE_TOOL_MAP = {
    "U725": [str(i) for i in range(1, 24)] + ["60"],
    "JL": [
        "2", "4", "5", "6", "9", "10", "11", "15", "16",
        "21", "23", "25", "26", "27", "40", "60",
    ] + [str(i) for i in range(201, 216)],
}
DEFAULT_TOOL_CONFIG = {}
DEFAULT_LINES = ["U725", "JL"]
DEFAULT_DOWNTIME_CODES = []

DEFAULT_DEFECT_CODES = []
DEFAULT_ANDON_REASONS = []

DEFAULT_COST_CONFIG = {
    # Example structure (optional):
    # "downtime_cost_per_min": {"Line1": 10.0},
    # "scrap_cost_default": 0.0,
    # "scrap_cost_by_part": {"PN123": 5.0}
}

DEFAULT_RISK_CONFIG = {
    "rules": {
        "andon_always_critical": True,
        "customer_risk_map": {
            # Optional: allow operator to choose values that map to severity bands
            # "Customer Hold": "Critical"
        },
        "copq_thresholds": {
            # Optional: if you use COPQ escalation alerts
            "medium": 500.0,
            "high": 2000.0,
            "critical": 5000.0
        },
        "defect_qty_thresholds": {
            "medium": 5,
            "high": 20,
            "critical": 50
        },
        "repeat_offender_escalation": {
            "watch_score": 40,
            "high_score": 80,
            "critical_score": 120
        },
        "gage_calibration_escalation": {
            "due_soon_days": 14,
            "overdue_criticality_map": {
                "Low": "High",
                "Medium": "High",
                "High": "Critical",
                "Critical": "Critical"
            }
        }
    }
}

DEFAULT_REPEAT_RULES = {
    "window_days": 7,
    "part_defect_repeat_threshold": 3,
    "machine_defect_repeat_threshold": 5,
    "weights": {
        "part_defect_repeat": 40,
        "machine_repeat": 25
    },
    "score_bands": {
        "watch_min": 40,
        "repeat_min": 80
    }
}

DEFAULT_LPA_CHECKLIST = []

DEFAULT_GAGES = {"gages": []}
DEFAULT_GAGE_VERIFICATION_Q = {
    "by_type": {
        "Other": [
            "Tool/gage clean and undamaged",
            "Zero / master check performed",
            "Calibration status verified"
        ]
    }
}

DEFAULT_NCRS = {"version": 1, "ncrs": []}
DEFAULT_ACTIONS = {"version": 1, "actions": []}
