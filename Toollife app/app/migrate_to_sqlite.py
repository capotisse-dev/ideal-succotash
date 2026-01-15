# app/migrate_to_sqlite.py
from __future__ import annotations

from typing import Any, Dict, List

from .db import (
    init_db,
    seed_default_users,
    upsert_part,
    upsert_tool_inventory,
    set_scrap_cost,
    ensure_lines,
    upsert_tool_entry,
)
from .storage import load_json
from .config import DATA_DIR
import os
import pandas as pd
from .config import (
    DEFAULT_USERS,
    USERS_FILE,
    PARTS_FILE,
    TOOL_CONFIG_FILE,
    COST_CONFIG_FILE,
)

def _as_list(v):
    return v if isinstance(v, list) else []

def _as_dict(v):
    return v if isinstance(v, dict) else {}

def run_migration() -> None:
    init_db()

    # Users (if your users.json exists, migrate; also seed defaults)
    seed_default_users(DEFAULT_USERS)
    users = load_json(USERS_FILE, {}) or {}
    if isinstance(users, dict):
        # Expect shape: { "admin": {...}, "super": {...} } in some versions
        # If your users.json is different, we can adjust.
        pass

    # Parts
    raw_parts = load_json(PARTS_FILE, {"parts": []})
    parts_list: List[Any]
    if isinstance(raw_parts, list):
        parts_list = raw_parts
    elif isinstance(raw_parts, dict):
        parts_list = raw_parts.get("parts", []) if isinstance(raw_parts.get("parts"), list) else []
    else:
        parts_list = []

    # Ensure lines exist first (optional)
    all_lines = set()
    for item in parts_list:
        if isinstance(item, dict):
            for ln in _as_list(item.get("lines", [])):
                if isinstance(ln, str) and ln.strip():
                    all_lines.add(ln.strip())
    ensure_lines(sorted(all_lines))

    for item in parts_list:
        if isinstance(item, str):
            pn = item.strip()
            if pn:
                upsert_part(pn, name="", lines=[])
        elif isinstance(item, dict):
            pn = (item.get("part_number") or item.get("pn") or item.get("part") or "").strip()
            name = (item.get("name") or "").strip()
            lines = item.get("lines") or []
            if isinstance(lines, str):
                lines = [x.strip() for x in lines.split(",") if x.strip()]
            if not isinstance(lines, list):
                lines = []
            if pn:
                upsert_part(pn, name=name, lines=lines)

    # Tools
    raw_tool = load_json(TOOL_CONFIG_FILE, {"tools": {}})
    tool_store = _as_dict(raw_tool)
    tools_map = tool_store.get("tools")
    if isinstance(tools_map, dict):
        for tool_num, info in tools_map.items():
            if not tool_num:
                continue
            info = info if isinstance(info, dict) else {}
            upsert_tool_inventory(
                tool_num=str(tool_num),
                name=str(info.get("name", "") or ""),
                unit_cost=float(info.get("unit_cost", 0.0) or 0.0),
                stock_qty=int(info.get("stock", 0) or 0),
                inserts_per_tool=int(info.get("inserts", 1) or 1),
            )
    else:
        # legacy: tool_store might already be a {tool_num: {...}}
        for tool_num, info in tool_store.items():
            if tool_num == "tools":
                continue
            info = info if isinstance(info, dict) else {}
            tool_id = str(tool_num).replace("Tool ", "").strip()
            upsert_tool_inventory(
                tool_num=tool_id or str(tool_num),
                name=str(info.get("name", "") or ""),
                unit_cost=float(info.get("cost", info.get("unit_cost", 0.0)) or 0.0),
                stock_qty=int(info.get("stock", 0) or 0),
                inserts_per_tool=int(info.get("inserts", 1) or 1),
            )

    # Scrap costs
    raw_cost = load_json(COST_CONFIG_FILE, {}) or {}
    if isinstance(raw_cost, dict):
        m = raw_cost.get("scrap_cost_by_part", {})
        if isinstance(m, dict):
            for pn, cost in m.items():
                try:
                    set_scrap_cost(str(pn), float(cost))
                except Exception:
                    continue

    # Tool entry history from Excel -> SQLite (if any)
    for fn in os.listdir(DATA_DIR):
        if not fn.lower().startswith("tool_life_data_") or not fn.lower().endswith(".xlsx"):
            continue
        path = os.path.join(DATA_DIR, fn)
        try:
            df = pd.read_excel(path)
        except Exception:
            continue
        for _, row in df.iterrows():
            try:
                upsert_tool_entry(row.to_dict())
            except Exception:
                continue

    print("✅ Migration complete.")

if __name__ == "__main__":
    run_migration()
