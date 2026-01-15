# app/populate_db.py
from __future__ import annotations

from typing import Any, Dict, List

from .db import init_db, seed_default_users, ensure_lines, upsert_part, upsert_tool, set_scrap_cost
from .storage import load_json
from .config import (
    DEFAULT_USERS,
    PARTS_FILE,
    TOOL_CONFIG_FILE,
    COST_CONFIG_FILE,
)

def _as_dict(x) -> Dict[str, Any]:
    return x if isinstance(x, dict) else {}

def _as_list(x) -> List[Any]:
    return x if isinstance(x, list) else []

def _coerce_lines(v):
    if isinstance(v, str):
        return [s.strip() for s in v.split(",") if s.strip()]
    if isinstance(v, list):
        return [str(s).strip() for s in v if str(s).strip()]
    return []

def _parts_list(raw):
    # Accept: {"parts":[...]} OR [...] OR {"data":[...]}
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict):
        if isinstance(raw.get("parts"), list):
            return raw["parts"]
        if isinstance(raw.get("data"), list):
            return raw["data"]
    return []

def run():
    # 1) Schema + default users
    init_db()
    seed_default_users(DEFAULT_USERS)

    # 2) Parts + line assignments
    raw_parts = load_json(PARTS_FILE, {"parts": []})
    parts = _parts_list(raw_parts)

    all_lines = set()
    for item in parts:
        if isinstance(item, dict):
            for ln in _coerce_lines(item.get("lines", [])):
                all_lines.add(ln)
    ensure_lines(sorted(all_lines))

    for item in parts:
        if isinstance(item, str):
            pn = item.strip()
            if pn:
                upsert_part(pn, name="", lines=[])
        elif isinstance(item, dict):
            pn = (item.get("part_number") or item.get("pn") or item.get("part") or "").strip()
            if not pn:
                continue
            name = (item.get("name") or "").strip()
            lines = _coerce_lines(item.get("lines", []))
            upsert_part(pn, name=name, lines=lines)

    # 3) Tools (tool_config.json)
    raw_tools = load_json(TOOL_CONFIG_FILE, {"tools": {}})
    tool_store = _as_dict(raw_tools)

    tools_map = tool_store.get("tools")
    if isinstance(tools_map, dict):
        for tool_num, info in tools_map.items():
            info = _as_dict(info)
            upsert_tool(
                tool_num=str(tool_num).strip(),
                name=str(info.get("name", "") or "").strip(),
                unit_cost=float(info.get("unit_cost", 0.0) or 0.0),
            )
    else:
        # legacy: file itself is { "T01": {...}, "T02": {...} }
        for tool_num, info in tool_store.items():
            if tool_num == "tools":
                continue
            info = _as_dict(info)
            upsert_tool(
                tool_num=str(tool_num).strip(),
                name=str(info.get("name", "") or "").strip(),
                unit_cost=float(info.get("unit_cost", 0.0) or 0.0),
            )

    # 4) Scrap pricing (cost_config.json -> scrap_cost_by_part)
    raw_cost = load_json(COST_CONFIG_FILE, {})
    cost_store = _as_dict(raw_cost)
    scrap_map = cost_store.get("scrap_cost_by_part", {})
    if isinstance(scrap_map, dict):
        for pn, cost in scrap_map.items():
            pn = str(pn).strip()
            if not pn:
                continue
            try:
                set_scrap_cost(pn, float(cost))
            except Exception:
                continue

    print("✅ SQLite database populated successfully.")
    print("   Seeded users: admin / super")
    print("   Imported: parts, part->lines, tools, scrap costs")

if __name__ == "__main__":
    run()
