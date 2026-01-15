# app/quality_engine.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from .storage import safe_int, safe_float
from .config import current_month_iso


def _now() -> datetime:
    return datetime.now()


def _parse_date(d: str) -> Optional[datetime]:
    if not d:
        return None
    s = str(d).strip()
    if not s:
        return None
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(s, fmt)
        except Exception:
            pass
    return None


def _days_between(a: datetime, b: datetime) -> int:
    return (a.date() - b.date()).days


def compute_copq_for_row(row: Dict[str, Any], cost_cfg: Dict[str, Any]) -> Tuple[float, float, float]:
    """
    Returns (downtime_cost_est, scrap_cost_est, copq_est).
    """
    line = str(row.get("Line", "") or "").strip()
    part = str(row.get("Part_Number", "") or "").strip()

    downtime_mins = safe_float(row.get("Downtime_Mins", 0), 0.0)
    defect_qty = safe_int(row.get("Defect_Qty", 0), 0)

    dt_rate = safe_float(cost_cfg.get("downtime_cost_per_min", {}).get(line, 0.0), 0.0)
    scrap_default = safe_float(cost_cfg.get("scrap_cost_default", 0.0), 0.0)
    scrap_by_part = cost_cfg.get("scrap_cost_by_part", {}) or {}
    scrap_rate = safe_float(scrap_by_part.get(part, scrap_default), scrap_default)

    downtime_cost = downtime_mins * dt_rate
    scrap_cost = defect_qty * scrap_rate
    copq = downtime_cost + scrap_cost
    return downtime_cost, scrap_cost, copq


def gage_due_status(gage: Dict[str, Any], risk_cfg: Dict[str, Any]) -> Dict[str, Any]:
    """
    Computes due dates + due status.
    Returns dict with next_due_date, days_until_due, status in {OK, Due Soon, Overdue}.
    """
    rules = (risk_cfg or {}).get("rules", {}) or {}
    due_soon_days = safe_int(rules.get("gage_calibration_escalation", {}).get("due_soon_days", 14), 14)

    last_cal = _parse_date(str(gage.get("last_calibration_date", "") or ""))
    freq_days = safe_int(gage.get("calibration_frequency_days", 0), 0)

    if not last_cal or freq_days <= 0:
        return {
            "next_due_date": "",
            "days_until_due": None,
            "status": "Unknown"
        }

    next_due = last_cal + timedelta(days=freq_days)
    days_until = _days_between(next_due, _now())

    if days_until < 0:
        status = "Overdue"
    elif days_until <= due_soon_days:
        status = "Due Soon"
    else:
        status = "OK"

    return {
        "next_due_date": next_due.strftime("%Y-%m-%d"),
        "days_until_due": days_until,
        "status": status
    }


def assign_risk_severity(
    row: Dict[str, Any],
    risk_cfg: Dict[str, Any],
    repeat_score: int = 0,
    is_overdue_action: bool = False,
    is_overdue_ncr: bool = False,
    gage_overdue_severity: Optional[str] = None
) -> Tuple[str, List[str]]:
    """
    Returns (severity, reasons).
    Severity in {Low, Medium, High, Critical}
    """
    rules = (risk_cfg or {}).get("rules", {}) or {}
    reasons: List[str] = []

    # Base
    severity_rank = {"Low": 0, "Medium": 1, "High": 2, "Critical": 3}
    current = "Low"

    def bump(to_level: str, why: str):
        nonlocal current
        if severity_rank.get(to_level, 0) > severity_rank.get(current, 0):
            current = to_level
        reasons.append(why)

    # Andon
    andon = str(row.get("Andon_Flag", "") or "").strip().lower()
    if rules.get("andon_always_critical", True) and andon == "yes":
        bump("Critical", "Andon flagged")

    # Customer risk (if operator/QC set it)
    cust = str(row.get("Customer_Risk", "") or "").strip()
    if cust:
        mapped = (rules.get("customer_risk_map", {}) or {}).get(cust, cust)
        if mapped in severity_rank:
            bump(mapped, f"Customer risk = {cust}")

    # COPQ thresholds
    copq = safe_float(row.get("COPQ_Est", 0.0), 0.0)
    copq_thr = rules.get("copq_thresholds", {}) or {}
    if copq >= safe_float(copq_thr.get("critical", 1e18), 1e18):
        bump("Critical", f"COPQ >= {copq_thr.get('critical')}")
    elif copq >= safe_float(copq_thr.get("high", 1e18), 1e18):
        bump("High", f"COPQ >= {copq_thr.get('high')}")
    elif copq >= safe_float(copq_thr.get("medium", 1e18), 1e18):
        bump("Medium", f"COPQ >= {copq_thr.get('medium')}")

    # Defect qty thresholds
    dq = safe_int(row.get("Defect_Qty", 0), 0)
    dq_thr = rules.get("defect_qty_thresholds", {}) or {}
    if dq >= safe_int(dq_thr.get("critical", 10**9), 10**9):
        bump("Critical", f"Defect qty >= {dq_thr.get('critical')}")
    elif dq >= safe_int(dq_thr.get("high", 10**9), 10**9):
        bump("High", f"Defect qty >= {dq_thr.get('high')}")
    elif dq >= safe_int(dq_thr.get("medium", 10**9), 10**9):
        bump("Medium", f"Defect qty >= {dq_thr.get('medium')}")

    # Repeat score escalation
    rep = rules.get("repeat_offender_escalation", {}) or {}
    if repeat_score >= safe_int(rep.get("critical_score", 10**9), 10**9):
        bump("Critical", f"Repeat score >= {rep.get('critical_score')}")
    elif repeat_score >= safe_int(rep.get("high_score", 10**9), 10**9):
        bump("High", f"Repeat score >= {rep.get('high_score')}")
    elif repeat_score >= safe_int(rep.get("watch_score", 10**9), 10**9):
        bump("Medium", f"Repeat score >= {rep.get('watch_score')}")

    # Overdue action/NCR
    if is_overdue_action:
        bump("High", "Overdue action item")
    if is_overdue_ncr:
        bump("High", "NCR aging threshold exceeded")

    # Gage overdue severity (if computed elsewhere)
    if gage_overdue_severity and gage_overdue_severity in severity_rank:
        bump(gage_overdue_severity, f"Gage calibration status triggers {gage_overdue_severity}")

    return current, reasons


def detect_repeat_offenders(df: pd.DataFrame, repeat_rules: Dict[str, Any]) -> pd.DataFrame:
    """
    Adds Repeat_Flag / Repeat_Score / Repeat_Reason (best-effort).
    Uses window_days and thresholds from repeat_rules.json.
    """
    if df.empty:
        return df

    window_days = safe_int(repeat_rules.get("window_days", 7), 7)
    part_thr = safe_int(repeat_rules.get("part_defect_repeat_threshold", 3), 3)
    mach_thr = safe_int(repeat_rules.get("machine_defect_repeat_threshold", 5), 5)

    weights = repeat_rules.get("weights", {}) or {}
    w_part = safe_int(weights.get("part_defect_repeat", 40), 40)
    w_mach = safe_int(weights.get("machine_repeat", 25), 25)

    score_bands = repeat_rules.get("score_bands", {}) or {}
    watch_min = safe_int(score_bands.get("watch_min", 40), 40)
    repeat_min = safe_int(score_bands.get("repeat_min", 80), 80)

    # Build a date column
    temp = df.copy()
    if "Date" in temp.columns:
        temp["_dt"] = pd.to_datetime(temp["Date"], errors="coerce")
    else:
        temp["_dt"] = pd.NaT

    cutoff = pd.Timestamp(_now().date() - timedelta(days=window_days))
    recent = temp[temp["_dt"].notna() & (temp["_dt"] >= cutoff)].copy()

    # Base fields if missing
    for col in ("Repeat_Flag", "Repeat_Score", "Repeat_Reason"):
        if col not in temp.columns:
            temp[col] = ""

    # Count repeats by (Part_Number, Defect_Code) where defects present
    recent_def = recent[recent.get("Defects_Present", "").astype(str).str.lower().eq("yes")].copy()
    if not recent_def.empty:
        part_counts = recent_def.groupby(["Part_Number", "Defect_Code"]).size().reset_index(name="cnt")
    else:
        part_counts = pd.DataFrame(columns=["Part_Number", "Defect_Code", "cnt"])

    # Count repeats by Machine (defects)
    if not recent_def.empty:
        mach_counts = recent_def.groupby(["Machine"]).size().reset_index(name="cnt")
    else:
        mach_counts = pd.DataFrame(columns=["Machine", "cnt"])

    # Apply scoring row-by-row
    reasons_out = []
    scores_out = []
    flags_out = []

    for _, r in temp.iterrows():
        score = 0
        reasons = []

        part = str(r.get("Part_Number", "") or "")
        dcode = str(r.get("Defect_Code", "") or "")
        mach = str(r.get("Machine", "") or "")
        defects_yes = str(r.get("Defects_Present", "") or "").lower() == "yes"

        if defects_yes and part and dcode:
            match = part_counts[(part_counts["Part_Number"] == part) & (part_counts["Defect_Code"] == dcode)]
            if not match.empty:
                cnt = int(match.iloc[0]["cnt"])
                if cnt >= part_thr:
                    score += w_part
                    reasons.append(f"Part+Defect repeats ({cnt} in {window_days}d)")

        if defects_yes and mach:
            mm = mach_counts[mach_counts["Machine"] == mach]
            if not mm.empty:
                cntm = int(mm.iloc[0]["cnt"])
                if cntm >= mach_thr:
                    score += w_mach
                    reasons.append(f"Machine repeat defects ({cntm} in {window_days}d)")

        if score >= repeat_min:
            flag = "Repeat"
        elif score >= watch_min:
            flag = "Watch"
        else:
            flag = "None"

        scores_out.append(score)
        flags_out.append(flag)
        reasons_out.append("; ".join(reasons))

    temp["Repeat_Score"] = scores_out
    temp["Repeat_Flag"] = flags_out
    temp["Repeat_Reason"] = reasons_out

    temp.drop(columns=["_dt"], inplace=True, errors="ignore")
    return temp


def generate_notifications(
    df: pd.DataFrame,
    gages_store: Dict[str, Any],
    risk_cfg: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Generates a list of alerts (dicts) for Super/Admin.
    Does not persist ack here; UI can persist elsewhere.
    """
    alerts: List[Dict[str, Any]] = []

    # 1) High/Critical entries by Customer_Risk / Andon / COPQ
    if not df.empty:
        temp = df.copy()
        # ensure COPQ exists if possible
        # (we won't compute here to avoid config dependency; UI can compute before)
        for _, r in temp.iterrows():
            sev = str(r.get("Customer_Risk", "") or "").strip()
            andon = str(r.get("Andon_Flag", "") or "").strip().lower()
            copq = safe_float(r.get("COPQ_Est", 0.0), 0.0)

            if andon == "yes":
                alerts.append({
                    "severity": "Critical",
                    "type": "Andon",
                    "title": "Andon event",
                    "details": f"{r.get('Line','')} {r.get('Machine','')} Tool {r.get('Tool_Num','')} Part {r.get('Part_Number','')}",
                    "related": {"entry_id": str(r.get("ID",""))}
                })
                continue

            if sev in ("High", "Critical"):
                alerts.append({
                    "severity": sev,
                    "type": "Risk",
                    "title": f"{sev} customer risk entry",
                    "details": f"{r.get('Line','')} {r.get('Machine','')} Part {r.get('Part_Number','')} Defect {r.get('Defect_Code','')}",
                    "related": {"entry_id": str(r.get("ID",""))}
                })

            # COPQ high/critical based on config
            rules = (risk_cfg or {}).get("rules", {}) or {}
            thr = rules.get("copq_thresholds", {}) or {}
            if copq >= safe_float(thr.get("critical", 1e18), 1e18):
                alerts.append({
                    "severity": "Critical",
                    "type": "COPQ",
                    "title": "Critical COPQ event",
                    "details": f"Entry {r.get('ID','')} COPQ ${copq:,.2f}",
                    "related": {"entry_id": str(r.get("ID",""))}
                })
            elif copq >= safe_float(thr.get("high", 1e18), 1e18):
                alerts.append({
                    "severity": "High",
                    "type": "COPQ",
                    "title": "High COPQ event",
                    "details": f"Entry {r.get('ID','')} COPQ ${copq:,.2f}",
                    "related": {"entry_id": str(r.get("ID",""))}
                })

    # 2) Gage calibration due/overdue
    gages = (gages_store or {}).get("gages", []) or []
    for g in gages:
        ds = gage_due_status(g, risk_cfg)
        if ds["status"] in ("Overdue", "Due Soon"):
            crit = str(g.get("criticality", "Medium") or "Medium")
            severity = "High" if ds["status"] == "Overdue" else "Medium"

            # escalate overdue based on criticality map if provided
            rules = (risk_cfg or {}).get("rules", {}) or {}
            gmap = (rules.get("gage_calibration_escalation", {}) or {}).get("overdue_criticality_map", {}) or {}
            if ds["status"] == "Overdue":
                severity = gmap.get(crit, "High")

            alerts.append({
                "severity": severity,
                "type": "Calibration",
                "title": f"Gage {ds['status']}",
                "details": f"{g.get('gage_id','')} {g.get('name','')} ({crit}) due {ds['next_due_date']}",
                "related": {"gage_id": str(g.get("gage_id",""))}
            })

    return alerts


def health_check(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """
    Returns a list of issues (dicts) for a future Health Check screen.
    """
    issues: List[Dict[str, Any]] = []
    if df.empty:
        return issues

    for _, r in df.iterrows():
        entry_id = str(r.get("ID",""))
        # basic required
        for col in ("Line", "Machine", "Tool_Num", "Reason"):
            if not str(r.get(col,"") or "").strip():
                issues.append({"severity":"High", "entry_id": entry_id, "issue": f"Missing {col}"})

        # defects logic
        defects = str(r.get("Defects_Present","") or "").strip().lower()
        qty = safe_int(r.get("Defect_Qty", 0), 0)
        if defects == "yes" and qty <= 0:
            issues.append({"severity":"High", "entry_id": entry_id, "issue":"Defects=Yes but Defect_Qty<=0"})
        if defects == "no" and qty > 0:
            issues.append({"severity":"Medium", "entry_id": entry_id, "issue":"Defects=No but Defect_Qty>0"})

    return issues
