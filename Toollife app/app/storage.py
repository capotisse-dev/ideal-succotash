# app/storage.py
import os
import json
from datetime import datetime
from typing import Any, Tuple, Optional

import pandas as pd

from .config import (
    DATA_DIR,
    COLUMNS,
)
from .db import fetch_tool_entries, list_entry_months, upsert_tool_entry

# -----------------------------
# JSON helpers (safe writes)
# -----------------------------
def load_json(path: str, default: Any):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default
        
def parts_for_line(selected_line: str):
    from .db import list_parts_with_lines
    out = []
    for p in list_parts_with_lines():
        lines = p.get("lines", []) or []
        if not selected_line or selected_line in lines:
            out.append(p.get("part_number", ""))
    return sorted([x for x in out if x])

def save_json(path: str, obj: Any) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2)
    os.replace(tmp, path)


ENTRY_COLUMNS = [
    "ID",
    "Date",
    "Time",
    "Shift",
    "Line",
    "Machine",
    "Part_Number",
    "Tool_Num",
    "Reason",
    "Downtime_Mins",
    "Cost",
    "Tool_Life",
    "Tool_Changer",
    "Defects_Present",
    "Defect_Qty",
    "Sort_Done",
    "Defect_Reason",
    "Quality_Verified",
    "Quality_User",
    "Quality_Time",
    "Leader_Sign",
    "Leader_User",
    "Leader_Time",
    "Serial_Numbers",
    "Andon_Flag",
    "Customer_Risk",
    "QC_Status",
    "NCR_ID",
    "NCR_Status",
    "NCR_Close_Date",
    "Action_Status",
    "Action_Due_Date",
    "Gage_Used",
    "COPQ_Est",
]


def ensure_df_schema(df: pd.DataFrame) -> pd.DataFrame:
    """
    Ensures df has all required columns and returns df ordered by ENTRY_COLUMNS.
    Missing columns are added as blank.
    Extra columns are preserved at the end.
    """
    for col in ENTRY_COLUMNS:
        if col not in df.columns:
            df[col] = ""

    extras = [c for c in df.columns if c not in ENTRY_COLUMNS]
    df = df[ENTRY_COLUMNS + extras]
    return df


def list_month_files() -> list[str]:
    months = list_entry_months()
    if not months:
        months = [datetime.now().strftime("%Y-%m")]
    return months


def _normalize_month(value: Optional[str]) -> str:
    if value:
        return str(value)
    return datetime.now().strftime("%Y-%m")


def get_df(filename: Optional[str] = None) -> Tuple[pd.DataFrame, str]:
    """
    Load a month of entries from SQLite into DataFrame.
    Returns (df, month_key).
    """
    month = _normalize_month(filename)
    rows = fetch_tool_entries(month)
    if rows:
        df = pd.DataFrame(rows)
        df = df.rename(columns={
            "id": "ID",
            "date": "Date",
            "time": "Time",
            "shift": "Shift",
            "line": "Line",
            "machine": "Machine",
            "part_number": "Part_Number",
            "tool_num": "Tool_Num",
            "reason": "Reason",
            "downtime_mins": "Downtime_Mins",
            "cost": "Cost",
            "tool_life": "Tool_Life",
            "tool_changer": "Tool_Changer",
            "defects_present": "Defects_Present",
            "defect_qty": "Defect_Qty",
            "sort_done": "Sort_Done",
            "defect_reason": "Defect_Reason",
            "quality_verified": "Quality_Verified",
            "quality_user": "Quality_User",
            "quality_time": "Quality_Time",
            "leader_sign": "Leader_Sign",
            "leader_user": "Leader_User",
            "leader_time": "Leader_Time",
            "serial_numbers": "Serial_Numbers",
            "andon_flag": "Andon_Flag",
            "customer_risk": "Customer_Risk",
            "qc_status": "QC_Status",
            "ncr_id": "NCR_ID",
            "ncr_status": "NCR_Status",
            "ncr_close_date": "NCR_Close_Date",
            "action_status": "Action_Status",
            "action_due_date": "Action_Due_Date",
            "gage_used": "Gage_Used",
            "copq_est": "COPQ_Est",
        })
    else:
        df = pd.DataFrame(columns=ENTRY_COLUMNS)
    df = ensure_df_schema(df)
    return df, month


def save_df(df: pd.DataFrame, filename: str) -> None:
    """
    Save DataFrame rows back to SQLite.
    filename is treated as month key (YYYY-MM).
    """
    df = ensure_df_schema(df)
    for _, row in df.iterrows():
        upsert_tool_entry(row.to_dict())


# -----------------------------
# Common converters
# -----------------------------
def safe_int(val: Any, default: int = 0) -> int:
    try:
        if val is None or (isinstance(val, float) and pd.isna(val)):
            return default
        s = str(val).strip()
        if s == "":
            return default
        return int(float(s))
    except Exception:
        return default

def safe_float(val: Any, default: float = 0.0) -> float:
    try:
        if val is None or (isinstance(val, float) and pd.isna(val)):
            return default
        s = str(val).strip()
        if s == "":
            return default
        return float(s)
    except Exception:
        return default


# -----------------------------
# ID helper
# -----------------------------
def next_id(df: Optional[pd.DataFrame] = None) -> str:
    """
    Generates a reasonably unique ID for a new row.
    Format: YYYYMMDD-HHMMSS-XXXX
    """
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    count = len(df) if df is not None else 0
    suffix = str(count % 10000).zfill(4)
    return f"{ts}-{suffix}"
