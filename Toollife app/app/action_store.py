# app/action_store.py
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from .db import (
    list_users,
    list_actions,
    list_ncrs,
    upsert_action as db_upsert_action,
    upsert_ncr as db_upsert_ncr,
    set_action_status as db_set_action_status,
    set_ncr_status as db_set_ncr_status,
    log_audit,
)


def now_iso() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def new_id(prefix: str) -> str:
    return f"{prefix}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"


def list_usernames() -> List[str]:
    return sorted([u["username"] for u in list_users()])


def load_actions_store() -> Dict[str, Any]:
    actions = []
    for a in list_actions():
        rel = {}
        if a.get("related_ncr_id"):
            rel["ncr_id"] = a.get("related_ncr_id")
        if a.get("related_entry_id"):
            rel["entry_id"] = a.get("related_entry_id")
        a = dict(a)
        a["related"] = rel
        actions.append(a)
    return {"version": 1, "actions": actions}


def save_actions_store(store: Dict[str, Any]) -> None:
    return None


def load_ncrs_store() -> Dict[str, Any]:
    return {"version": 1, "ncrs": list_ncrs()}


def save_ncrs_store(store: Dict[str, Any]) -> None:
    return None


def upsert_action(action: Dict[str, Any], actor: str = "") -> Dict[str, Any]:
    """
    Action schema (minimal):
    {
      "action_id", "type": "Action"|"NCR",
      "title", "severity": Low/Medium/High/Critical,
      "status": Open/In Progress/Blocked/Closed,
      "owner", "created_by", "created_at",
      "due_date", "line", "part_number",
      "related": { "ncr_id": "...", "entry_id": "..." },
      "notes"
    }
    """
    if not action.get("action_id"):
        action["action_id"] = new_id("A")
    action.setdefault("type", "Action")
    action.setdefault("severity", "Medium")
    action.setdefault("status", "Open")
    action.setdefault("created_at", now_iso())
    action.setdefault("notes", "")
    action.setdefault("related", {})

    saved = db_upsert_action(action)
    if actor:
        log_audit(actor, f"Updated action {saved.get('action_id')}: {saved.get('status')}")
    return saved


def set_action_status(action_id: str, status: str, closed_by: Optional[str] = None, actor: str = "") -> None:
    db_set_action_status(action_id, status, closed_by or "")
    if actor:
        log_audit(actor, f"Set action {action_id} status to {status}")


def upsert_ncr(ncr: Dict[str, Any], actor: str = "") -> Dict[str, Any]:
    """
    NCR schema (minimal):
    {
      "ncr_id", "status": Open/Contained/Verified/Closed,
      "part_number", "line", "owner",
      "description", "created_at", "created_by",
      "close_date", "related_entry_id"
    }
    """
    if not ncr.get("ncr_id"):
        ncr["ncr_id"] = new_id("NCR")
    ncr.setdefault("status", "Open")
    ncr.setdefault("created_at", now_iso())

    saved = db_upsert_ncr(ncr)
    if actor:
        log_audit(actor, f"Updated NCR {saved.get('ncr_id')} status {saved.get('status')}")
    return saved


def set_ncr_status(ncr_id: str, status: str, actor: str = "") -> None:
    db_set_ncr_status(ncr_id, status)
    if actor:
        log_audit(actor, f"Set NCR {ncr_id} status to {status}")


def create_ncr_and_action(
    *,
    title: str,
    description: str,
    severity: str,
    owner: str,
    created_by: str,
    line: str = "",
    part_number: str = "",
    due_date: str = "",
    related_entry_id: str = ""
) -> Dict[str, Any]:
    """
    Creates an NCR record AND creates a linked Action Center item (type="NCR").
    """
    ncr = upsert_ncr({
        "status": "Open",
        "part_number": part_number,
        "line": line,
        "owner": owner,
        "description": description,
        "created_by": created_by,
        "related_entry_id": related_entry_id,
    }, actor=created_by)

    action = upsert_action({
        "type": "NCR",
        "title": title or f"NCR {ncr['ncr_id']}",
        "severity": severity,
        "status": "Open",
        "owner": owner,
        "created_by": created_by,
        "due_date": due_date,
        "line": line,
        "part_number": part_number,
        "related": {"ncr_id": ncr["ncr_id"], "entry_id": related_entry_id},
        "notes": description
    }, actor=created_by)

    # back-link (optional)
    ncr = upsert_ncr({**ncr, "action_id": action["action_id"]}, actor=created_by)

    return {"ncr": ncr, "action": action}
