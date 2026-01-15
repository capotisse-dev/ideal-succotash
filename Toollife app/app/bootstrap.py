# app/bootstrap.py
from __future__ import annotations

import os
import json
from datetime import datetime

import pandas as pd

from .config import (
    DATA_DIR, LOGS_DIR, BACKUPS_DIR,
    USERS_FILE, REASONS_FILE, PARTS_FILE, TOOL_CONFIG_FILE,
    DEFECT_CODES_FILE, ANDON_REASONS_FILE, COST_CONFIG_FILE, RISK_CONFIG_FILE,
    REPEAT_RULES_FILE, LPA_CHECKLIST_FILE, GAGES_FILE, GAGE_VERIFICATION_Q_FILE,
    NCRS_FILE, ACTIONS_FILE,
    alerts_file_for_month, month_excel_path, gage_verification_log_path,
    COLUMNS,
    DEFAULT_USERS, DEFAULT_REASONS, DEFAULT_PARTS, DEFAULT_TOOL_CONFIG,
    DEFAULT_DEFECT_CODES, DEFAULT_ANDON_REASONS, DEFAULT_COST_CONFIG, DEFAULT_RISK_CONFIG,
    DEFAULT_REPEAT_RULES, DEFAULT_LPA_CHECKLIST, DEFAULT_GAGES, DEFAULT_GAGE_VERIFICATION_Q,
    DEFAULT_NCRS, DEFAULT_ACTIONS, DEFAULT_LINES, DEFAULT_DOWNTIME_CODES, DEFAULT_LINE_TOOL_MAP
)

from .db import (
    init_db,
    seed_default_users,
    get_meta,
    set_meta,
    ensure_lines,
    upsert_downtime_code,
    list_tools_simple,
    upsert_tool_inventory,
    set_tool_lines,
)
from .migrate_to_sqlite import run_migration


# ----------------------------
# JSON helpers (legacy storage)
# ----------------------------
def _write_json_if_missing(path: str, default_obj) -> None:
    if os.path.exists(path):
        return
    with open(path, "w", encoding="utf-8") as f:
        json.dump(default_obj, f, indent=2)


def _ensure_dirs() -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(LOGS_DIR, exist_ok=True)
    os.makedirs(BACKUPS_DIR, exist_ok=True)


def _ensure_json_files() -> None:
    """
    Keep these for compatibility while the app still reads some config/data from JSON.
    As we migrate screens to SQLite, we can remove these one-by-one.
    """
    _write_json_if_missing(USERS_FILE, DEFAULT_USERS)
    _write_json_if_missing(REASONS_FILE, DEFAULT_REASONS)
    _write_json_if_missing(PARTS_FILE, DEFAULT_PARTS)
    _write_json_if_missing(TOOL_CONFIG_FILE, DEFAULT_TOOL_CONFIG)

    _write_json_if_missing(DEFECT_CODES_FILE, DEFAULT_DEFECT_CODES)
    _write_json_if_missing(ANDON_REASONS_FILE, DEFAULT_ANDON_REASONS)
    _write_json_if_missing(COST_CONFIG_FILE, DEFAULT_COST_CONFIG)
    _write_json_if_missing(RISK_CONFIG_FILE, DEFAULT_RISK_CONFIG)
    _write_json_if_missing(REPEAT_RULES_FILE, DEFAULT_REPEAT_RULES)
    _write_json_if_missing(LPA_CHECKLIST_FILE, DEFAULT_LPA_CHECKLIST)
    _write_json_if_missing(GAGES_FILE, DEFAULT_GAGES)
    _write_json_if_missing(GAGE_VERIFICATION_Q_FILE, DEFAULT_GAGE_VERIFICATION_Q)

    _write_json_if_missing(NCRS_FILE, DEFAULT_NCRS)
    _write_json_if_missing(ACTIONS_FILE, DEFAULT_ACTIONS)

    # Monthly alerts store (current month)
    now = datetime.now()
    alert_path = alerts_file_for_month(now)
    if not os.path.exists(alert_path):
        _write_json_if_missing(
            alert_path,
            {"version": 1, "month": now.strftime("%Y-%m"), "alerts": []},
        )


def _ensure_default_users() -> None:
    """Ensure default admin/super accounts exist."""
    users = {}
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, "r", encoding="utf-8") as f:
                users = json.load(f) or {}
        except json.JSONDecodeError:
            users = {}

    changed = False
    for username, defaults in DEFAULT_USERS.items():
        if username not in users:
            users[username] = defaults
            changed = True

    if changed:
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(users, f, indent=2)


# ----------------------------
# Excel helpers (legacy storage)
# ----------------------------
def _ensure_month_excel_schema(xlsx_path: str) -> None:
    """Create the month Excel if missing; if exists, add any missing columns."""
    if not os.path.exists(xlsx_path):
        df = pd.DataFrame(columns=COLUMNS)
        df.to_excel(xlsx_path, index=False)
        return

    try:
        df = pd.read_excel(xlsx_path)
    except Exception:
        # If corrupted/unreadable, do NOT overwrite silently.
        # Create a safe new file and leave the original for recovery.
        base = os.path.splitext(xlsx_path)[0]
        rescue = base + "_RESCUE_" + datetime.now().strftime("%Y%m%d_%H%M%S") + ".xlsx"
        pd.DataFrame(columns=COLUMNS).to_excel(rescue, index=False)
        return

    changed = False
    for col in COLUMNS:
        if col not in df.columns:
            df[col] = ""
            changed = True

    if changed:
        df = df[COLUMNS]
        df.to_excel(xlsx_path, index=False)


def _ensure_gage_verification_log(xlsx_path: str) -> None:
    """Create the gage verification log (current month) if missing, with a clean schema."""
    if os.path.exists(xlsx_path):
        return

    cols = [
        "Verify_ID",
        "Date",
        "Time",
        "Gage_ID",
        "Gage_Name",
        "Gage_Type",
        "Line",
        "Result",           # Pass/Fail
        "Failed_Items",     # comma list
        "Notes",
        "Verified_By",
    ]
    pd.DataFrame(columns=cols).to_excel(xlsx_path, index=False)


def _seed_default_tools() -> None:
    from .db import list_tools_simple, upsert_tool_inventory, set_tool_lines

    if list_tools_simple():
        return
    for line, tools in DEFAULT_LINE_TOOL_MAP.items():
        for tool_num in tools:
            upsert_tool_inventory(
                tool_num=str(tool_num),
                name="",
                unit_cost=0.0,
                stock_qty=0,
                inserts_per_tool=1,
            )
            set_tool_lines(str(tool_num), [line])


def _seed_default_tools() -> None:
    from .db import list_tools_simple, upsert_tool_inventory, set_tool_lines

    if list_tools_simple():
        return
    for line, tools in DEFAULT_LINE_TOOL_MAP.items():
        for tool_num in tools:
            upsert_tool_inventory(
                tool_num=str(tool_num),
                name="",
                unit_cost=0.0,
                stock_qty=0,
                inserts_per_tool=1,
            )
            set_tool_lines(str(tool_num), [line])


def _seed_default_tools() -> None:
    if list_tools_simple():
        return
    for line, tools in DEFAULT_LINE_TOOL_MAP.items():
        for tool_num in tools:
            upsert_tool_inventory(
                tool_num=str(tool_num),
                name="",
                unit_cost=0.0,
                stock_qty=0,
                inserts_per_tool=1,
            )
            set_tool_lines(str(tool_num), [line])


def _seed_default_tools() -> None:
    if list_tools_simple():
        return
    for line, tools in DEFAULT_LINE_TOOL_MAP.items():
        for tool_num in tools:
            upsert_tool_inventory(
                tool_num=str(tool_num),
                name="",
                unit_cost=0.0,
                stock_qty=0,
                inserts_per_tool=1,
            )
            set_tool_lines(str(tool_num), [line])


# ----------------------------
# Public entry point
# ----------------------------
def ensure_app_initialized() -> None:
    """
    Safe to call multiple times. This is your one place to prepare the app environment.
    """
    _ensure_dirs()

    # SQLite (new system of record)
    init_db()
    seed_default_users(DEFAULT_USERS)
    ensure_lines(DEFAULT_LINES)
    for code in DEFAULT_DOWNTIME_CODES:
        upsert_downtime_code(code)
    if get_meta("json_migrated") != "1":
        run_migration()
        set_meta("json_migrated", "1")
    _seed_default_tools()

    # Legacy files still used elsewhere in the app (for now)
    _ensure_json_files()
    _ensure_default_users()
    # SQLite (new system of record)
    init_db()
    seed_default_users(DEFAULT_USERS)
    ensure_lines(DEFAULT_LINES)
    for code in DEFAULT_DOWNTIME_CODES:
        upsert_downtime_code(code)
    if get_meta("json_migrated") != "1":
        run_migration()
        set_meta("json_migrated", "1")
    _seed_default_tools()

    # Legacy files still used elsewhere in the app (for now)
    _ensure_json_files()
    _ensure_default_users()

    # Ensure month Excel exists and matches schema
    now = datetime.now()
    _ensure_month_excel_schema(month_excel_path(now))

    # Ensure gage verification log exists for current month
    _ensure_gage_verification_log(gage_verification_log_path(now))
