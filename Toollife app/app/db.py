# app/db.py
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional

from .config import DB_PATH


@contextmanager
def connect():
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA journal_mode = WAL;")
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    schema = """
    CREATE TABLE IF NOT EXISTS meta (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL UNIQUE,
        password TEXT NOT NULL,
        role TEXT NOT NULL,
        name TEXT NOT NULL DEFAULT '',
        line TEXT NOT NULL DEFAULT 'Both',
        is_active INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS lines (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE
    );

    CREATE TABLE IF NOT EXISTS parts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        part_number TEXT NOT NULL UNIQUE,
        name TEXT NOT NULL DEFAULT '',
        is_active INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS part_lines (
        part_id INTEGER NOT NULL,
        line_id INTEGER NOT NULL,
        PRIMARY KEY(part_id, line_id),
        FOREIGN KEY(part_id) REFERENCES parts(id) ON DELETE CASCADE,
        FOREIGN KEY(line_id) REFERENCES lines(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS tools (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tool_num TEXT NOT NULL UNIQUE,
        name TEXT NOT NULL DEFAULT '',
        unit_cost REAL NOT NULL DEFAULT 0.0,
        stock_qty INTEGER NOT NULL DEFAULT 0,
        inserts_per_tool INTEGER NOT NULL DEFAULT 1,
        is_active INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS tool_entries (
        id TEXT PRIMARY KEY,
        date TEXT NOT NULL,
        time TEXT NOT NULL,
        shift TEXT NOT NULL DEFAULT '',
        line TEXT NOT NULL DEFAULT '',
        machine TEXT NOT NULL DEFAULT '',
        part_number TEXT NOT NULL DEFAULT '',
        tool_num TEXT NOT NULL DEFAULT '',
        reason TEXT NOT NULL DEFAULT '',
        downtime_mins REAL NOT NULL DEFAULT 0.0,
        cost REAL NOT NULL DEFAULT 0.0,
        tool_life REAL NOT NULL DEFAULT 0.0,
        tool_changer TEXT NOT NULL DEFAULT '',
        defects_present TEXT NOT NULL DEFAULT '',
        defect_qty REAL NOT NULL DEFAULT 0.0,
        sort_done TEXT NOT NULL DEFAULT '',
        defect_reason TEXT NOT NULL DEFAULT '',
        quality_verified TEXT NOT NULL DEFAULT '',
        quality_user TEXT NOT NULL DEFAULT '',
        quality_time TEXT NOT NULL DEFAULT '',
        leader_sign TEXT NOT NULL DEFAULT '',
        leader_user TEXT NOT NULL DEFAULT '',
        leader_time TEXT NOT NULL DEFAULT '',
        serial_numbers TEXT NOT NULL DEFAULT '',
        andon_flag TEXT NOT NULL DEFAULT '',
        customer_risk TEXT NOT NULL DEFAULT '',
        qc_status TEXT NOT NULL DEFAULT '',
        ncr_id TEXT NOT NULL DEFAULT '',
        ncr_status TEXT NOT NULL DEFAULT '',
        ncr_close_date TEXT NOT NULL DEFAULT '',
        action_status TEXT NOT NULL DEFAULT '',
        action_due_date TEXT NOT NULL DEFAULT '',
        gage_used TEXT NOT NULL DEFAULT '',
        copq_est REAL NOT NULL DEFAULT 0.0
    );

    CREATE TABLE IF NOT EXISTS actions (
        action_id TEXT PRIMARY KEY,
        type TEXT NOT NULL DEFAULT 'Action',
        title TEXT NOT NULL DEFAULT '',
        severity TEXT NOT NULL DEFAULT 'Medium',
        status TEXT NOT NULL DEFAULT 'Open',
        owner TEXT NOT NULL DEFAULT '',
        created_by TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at TEXT NOT NULL DEFAULT (datetime('now')),
        due_date TEXT NOT NULL DEFAULT '',
        line TEXT NOT NULL DEFAULT '',
        part_number TEXT NOT NULL DEFAULT '',
        related_ncr_id TEXT NOT NULL DEFAULT '',
        related_entry_id TEXT NOT NULL DEFAULT '',
        notes TEXT NOT NULL DEFAULT '',
        closed_at TEXT NOT NULL DEFAULT '',
        closed_by TEXT NOT NULL DEFAULT ''
    );

    CREATE TABLE IF NOT EXISTS ncrs (
        ncr_id TEXT PRIMARY KEY,
        status TEXT NOT NULL DEFAULT 'Open',
        part_number TEXT NOT NULL DEFAULT '',
        line TEXT NOT NULL DEFAULT '',
        owner TEXT NOT NULL DEFAULT '',
        description TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        updated_at TEXT NOT NULL DEFAULT (datetime('now')),
        created_by TEXT NOT NULL DEFAULT '',
        close_date TEXT NOT NULL DEFAULT '',
        related_entry_id TEXT NOT NULL DEFAULT '',
        action_id TEXT NOT NULL DEFAULT ''
    );

    CREATE TABLE IF NOT EXISTS user_screen_permissions (
        username TEXT NOT NULL,
        screen TEXT NOT NULL,
        level TEXT NOT NULL DEFAULT 'view',
        updated_at TEXT NOT NULL DEFAULT (datetime('now')),
        PRIMARY KEY(username, screen)
    );

    CREATE TABLE IF NOT EXISTS audit_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        username TEXT NOT NULL DEFAULT '',
        action TEXT NOT NULL DEFAULT ''
    );

    CREATE TABLE IF NOT EXISTS part_costs (
        part_id INTEGER NOT NULL UNIQUE,
        scrap_cost REAL NOT NULL DEFAULT 0.0,
        updated_at TEXT NOT NULL DEFAULT (datetime('now')),
        FOREIGN KEY(part_id) REFERENCES parts(id) ON DELETE CASCADE
    );

    CREATE INDEX IF NOT EXISTS idx_parts_active ON parts(is_active);
    CREATE INDEX IF NOT EXISTS idx_tools_active ON tools(is_active);
    """
    with connect() as conn:
        conn.executescript(schema)
        conn.execute("INSERT OR IGNORE INTO meta(key,value) VALUES('schema_version','1')")
        _ensure_columns(conn, "tools", {
            "stock_qty": "INTEGER NOT NULL DEFAULT 0",
            "inserts_per_tool": "INTEGER NOT NULL DEFAULT 1",
        })
        _ensure_columns(conn, "tool_entries", {
            "tool_life": "REAL NOT NULL DEFAULT 0.0",
        })


def _ensure_columns(conn: sqlite3.Connection, table: str, columns: Dict[str, str]) -> None:
    existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    for name, col_def in columns.items():
        if name not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {col_def}")


def log_audit(username: str, action: str) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO audit_logs(username, action) VALUES(?, ?)",
            (username or "", action or ""),
        )


def get_meta(key: str) -> Optional[str]:
    with connect() as conn:
        row = conn.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return row["value"] if row else None


def set_meta(key: str, value: str) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO meta(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )


def list_audit_logs(limit: int = 500) -> List[Dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT created_at, username, action FROM audit_logs ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]


def seed_default_users(default_users: Dict[str, Dict[str, Any]]) -> None:
    with connect() as conn:
        for username, u in default_users.items():
            conn.execute(
                """
                INSERT OR IGNORE INTO users(username, password, role, name, line)
                VALUES(?,?,?,?,?)
                """,
                (
                    username,
                    u.get("password", ""),
                    u.get("role", "User"),
                    u.get("name", ""),
                    u.get("line", "Both"),
                ),
            )


def ensure_lines(names: Iterable[str]) -> None:
    with connect() as conn:
        for n in names:
            n = (n or "").strip()
            if n:
                conn.execute("INSERT OR IGNORE INTO lines(name) VALUES(?)", (n,))


def upsert_part(part_number: str, name: str = "", lines: Optional[List[str]] = None) -> None:
    lines = lines or []
    with connect() as conn:
        # ensure lines
        for ln in lines:
            ln = (ln or "").strip()
            if ln:
                conn.execute("INSERT OR IGNORE INTO lines(name) VALUES(?)", (ln,))

        conn.execute(
            """
            INSERT INTO parts(part_number, name, is_active)
            VALUES(?, ?, 1)
            ON CONFLICT(part_number) DO UPDATE SET
              name=excluded.name,
              updated_at=datetime('now')
            """,
            (part_number, name),
        )

        part_id = conn.execute(
            "SELECT id FROM parts WHERE part_number=?",
            (part_number,),
        ).fetchone()["id"]

        # rewrite mappings
        conn.execute("DELETE FROM part_lines WHERE part_id=?", (part_id,))
        for ln in lines:
            ln = (ln or "").strip()
            if not ln:
                continue
            line_id = conn.execute("SELECT id FROM lines WHERE name=?", (ln,)).fetchone()["id"]
            conn.execute("INSERT OR IGNORE INTO part_lines(part_id,line_id) VALUES(?,?)", (part_id, line_id))


def deactivate_part(part_number: str) -> None:
    with connect() as conn:
        conn.execute(
            "UPDATE parts SET is_active=0, updated_at=datetime('now') WHERE part_number=?",
            (part_number,),
        )


def upsert_tool(tool_num: str, name: str = "", unit_cost: float = 0.0) -> None:
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO tools(tool_num, name, unit_cost, stock_qty, inserts_per_tool, is_active)
            VALUES(?, ?, ?, 0, 1, 1)
            ON CONFLICT(tool_num) DO UPDATE SET
              name=excluded.name,
              unit_cost=excluded.unit_cost,
              updated_at=datetime('now')
            """,
            (tool_num, name, float(unit_cost)),
        )


def upsert_tool_inventory(
    tool_num: str,
    *,
    name: str = "",
    unit_cost: float = 0.0,
    stock_qty: int = 0,
    inserts_per_tool: int = 1,
) -> None:
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO tools(tool_num, name, unit_cost, stock_qty, inserts_per_tool, is_active)
            VALUES(?, ?, ?, ?, ?, 1)
            ON CONFLICT(tool_num) DO UPDATE SET
              name=excluded.name,
              unit_cost=excluded.unit_cost,
              stock_qty=excluded.stock_qty,
              inserts_per_tool=excluded.inserts_per_tool,
              updated_at=datetime('now')
            """,
            (tool_num, name, float(unit_cost), int(stock_qty), int(inserts_per_tool)),
        )


def get_tool(tool_num: str) -> Optional[Dict[str, Any]]:
    with connect() as conn:
        row = conn.execute(
            "SELECT tool_num, name, unit_cost, stock_qty, inserts_per_tool FROM tools WHERE tool_num=?",
            (tool_num,),
        ).fetchone()
        return dict(row) if row else None


def update_tool_stock(tool_num: str, stock_qty: int) -> None:
    with connect() as conn:
        conn.execute(
            "UPDATE tools SET stock_qty=?, updated_at=datetime('now') WHERE tool_num=?",
            (int(stock_qty), tool_num),
        )


def deactivate_tool(tool_num: str) -> None:
    with connect() as conn:
        conn.execute(
            "UPDATE tools SET is_active=0, updated_at=datetime('now') WHERE tool_num=?",
            (tool_num,),
        )


def set_scrap_cost(part_number: str, scrap_cost: float) -> None:
    with connect() as conn:
        row = conn.execute("SELECT id FROM parts WHERE part_number=?", (part_number,)).fetchone()
        if not row:
            conn.execute(
                "INSERT INTO parts(part_number, name, is_active) VALUES(?, '', 1)",
                (part_number,),
            )
            row = conn.execute("SELECT id FROM parts WHERE part_number=?", (part_number,)).fetchone()

        part_id = row["id"]
        conn.execute(
            """
            INSERT INTO part_costs(part_id, scrap_cost)
            VALUES(?, ?)
            ON CONFLICT(part_id) DO UPDATE SET
              scrap_cost=excluded.scrap_cost,
              updated_at=datetime('now')
            """,
            (part_id, float(scrap_cost)),
        )
def list_parts_with_lines():
    with connect() as conn:
        parts = conn.execute(
            "SELECT id, part_number, name FROM parts WHERE is_active=1 ORDER BY part_number"
        ).fetchall()

        out = []
        for p in parts:
            lines = conn.execute(
                """
                SELECT l.name
                FROM part_lines pl
                JOIN lines l ON l.id = pl.line_id
                WHERE pl.part_id=?
                ORDER BY l.name
                """,
                (p["id"],),
            ).fetchall()
            out.append({
                "id": p["id"],
                "part_number": p["part_number"],
                "name": p["name"],
                "lines": [r["name"] for r in lines],
            })
        return out


def list_tools_simple():
    with connect() as conn:
        rows = conn.execute(
            "SELECT tool_num, name, unit_cost, stock_qty, inserts_per_tool FROM tools WHERE is_active=1 ORDER BY tool_num"
        ).fetchall()
        return [dict(r) for r in rows]


def get_scrap_costs_simple():
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT p.part_number, pc.scrap_cost
            FROM part_costs pc
            JOIN parts p ON p.id = pc.part_id
            ORDER BY p.part_number
            """
        ).fetchall()
        return {r["part_number"]: float(r["scrap_cost"]) for r in rows}


def upsert_user(
    username: str,
    password: str,
    role: str,
    name: str,
    line: str = "Both",
    is_active: int = 1,
) -> None:
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO users(username, password, role, name, line, is_active)
            VALUES(?,?,?,?,?,?)
            ON CONFLICT(username) DO UPDATE SET
              password=excluded.password,
              role=excluded.role,
              name=excluded.name,
              line=excluded.line,
              is_active=excluded.is_active,
              updated_at=datetime('now')
            """,
            (username, password, role, name, line, int(is_active)),
        )


def update_user_fields(username: str, fields: Dict[str, Any]) -> None:
    if not fields:
        return
    allowed = {"password", "role", "name", "line", "is_active"}
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return
    sets = ", ".join([f"{k}=?" for k in updates.keys()])
    params = list(updates.values()) + [username]
    with connect() as conn:
        conn.execute(
            f"UPDATE users SET {sets}, updated_at=datetime('now') WHERE username=?",
            params,
        )


def get_user(username: str) -> Optional[Dict[str, Any]]:
    with connect() as conn:
        row = conn.execute(
            "SELECT username, password, role, name, line, is_active FROM users WHERE username=?",
            (username,),
        ).fetchone()
        return dict(row) if row else None


def list_users() -> List[Dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT username, password, role, name, line, is_active FROM users ORDER BY username"
        ).fetchall()
        return [dict(r) for r in rows]


def set_screen_permission(username: str, screen: str, level: str) -> None:
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO user_screen_permissions(username, screen, level)
            VALUES(?,?,?)
            ON CONFLICT(username, screen) DO UPDATE SET
              level=excluded.level,
              updated_at=datetime('now')
            """,
            (username, screen, level),
        )


def delete_screen_permission(username: str, screen: str) -> None:
    with connect() as conn:
        conn.execute(
            "DELETE FROM user_screen_permissions WHERE username=? AND screen=?",
            (username, screen),
        )


def list_screen_permissions(username: Optional[str] = None) -> List[Dict[str, Any]]:
    with connect() as conn:
        if username:
            rows = conn.execute(
                "SELECT username, screen, level FROM user_screen_permissions WHERE username=?",
                (username,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT username, screen, level FROM user_screen_permissions"
            ).fetchall()
        return [dict(r) for r in rows]


def list_entry_months() -> List[str]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT DISTINCT substr(date,1,7) AS month FROM tool_entries WHERE date != '' ORDER BY month DESC"
        ).fetchall()
        return [r["month"] for r in rows if r["month"]]


def upsert_tool_entry(entry: Dict[str, Any]) -> None:
    if not entry.get("ID") and not entry.get("id"):
        raise ValueError("Entry must include ID")
    entry_id = str(entry.get("ID") or entry.get("id"))
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    record = {
        "id": entry_id,
        "date": entry.get("Date", ""),
        "time": entry.get("Time", ""),
        "shift": entry.get("Shift", ""),
        "line": entry.get("Line", ""),
        "machine": entry.get("Machine", ""),
        "part_number": entry.get("Part_Number", ""),
        "tool_num": entry.get("Tool_Num", ""),
        "reason": entry.get("Reason", ""),
        "downtime_mins": float(entry.get("Downtime_Mins", 0.0) or 0.0),
        "cost": float(entry.get("Cost", 0.0) or 0.0),
        "tool_life": float(entry.get("Tool_Life", 0.0) or 0.0),
        "tool_changer": entry.get("Tool_Changer", ""),
        "defects_present": entry.get("Defects_Present", ""),
        "defect_qty": float(entry.get("Defect_Qty", 0.0) or 0.0),
        "sort_done": entry.get("Sort_Done", ""),
        "defect_reason": entry.get("Defect_Reason", ""),
        "quality_verified": entry.get("Quality_Verified", ""),
        "quality_user": entry.get("Quality_User", ""),
        "quality_time": entry.get("Quality_Time", ""),
        "leader_sign": entry.get("Leader_Sign", ""),
        "leader_user": entry.get("Leader_User", ""),
        "leader_time": entry.get("Leader_Time", ""),
        "serial_numbers": entry.get("Serial_Numbers", ""),
        "andon_flag": entry.get("Andon_Flag", ""),
        "customer_risk": entry.get("Customer_Risk", ""),
        "qc_status": entry.get("QC_Status", ""),
        "ncr_id": entry.get("NCR_ID", ""),
        "ncr_status": entry.get("NCR_Status", ""),
        "ncr_close_date": entry.get("NCR_Close_Date", ""),
        "action_status": entry.get("Action_Status", ""),
        "action_due_date": entry.get("Action_Due_Date", ""),
        "gage_used": entry.get("Gage_Used", ""),
        "copq_est": float(entry.get("COPQ_Est", 0.0) or 0.0),
    }
    with connect() as conn:
        existing = conn.execute(
            "SELECT id FROM tool_entries WHERE id=?",
            (entry_id,),
        ).fetchone()
        if existing:
            sets = ", ".join([f"{k}=?" for k in record.keys() if k != "id"])
            params = [record[k] for k in record.keys() if k != "id"] + [entry_id]
            conn.execute(f"UPDATE tool_entries SET {sets} WHERE id=?", params)
        else:
            columns = ", ".join(record.keys())
            placeholders = ", ".join(["?"] * len(record))
            conn.execute(
                f"INSERT INTO tool_entries ({columns}) VALUES ({placeholders})",
                list(record.values()),
            )


def fetch_tool_entries(month: Optional[str] = None) -> List[Dict[str, Any]]:
    with connect() as conn:
        if month:
            rows = conn.execute(
                "SELECT * FROM tool_entries WHERE substr(date,1,7)=? ORDER BY date DESC, time DESC",
                (month,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM tool_entries ORDER BY date DESC, time DESC"
            ).fetchall()
        return [dict(r) for r in rows]


def upsert_action(action: Dict[str, Any]) -> Dict[str, Any]:
    action_id = action.get("action_id")
    if not action_id:
        action_id = f"A-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        action["action_id"] = action_id
    action.setdefault("type", "Action")
    action.setdefault("severity", "Medium")
    action.setdefault("status", "Open")
    action.setdefault("created_at", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    action.setdefault("notes", "")
    action.setdefault("related", {})

    rel = action.get("related") if isinstance(action.get("related"), dict) else {}
    record = {
        "action_id": action_id,
        "type": action.get("type", "Action"),
        "title": action.get("title", ""),
        "severity": action.get("severity", "Medium"),
        "status": action.get("status", "Open"),
        "owner": action.get("owner", ""),
        "created_by": action.get("created_by", ""),
        "created_at": action.get("created_at"),
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "due_date": action.get("due_date", ""),
        "line": action.get("line", ""),
        "part_number": action.get("part_number", ""),
        "related_ncr_id": rel.get("ncr_id", "") if isinstance(rel, dict) else "",
        "related_entry_id": rel.get("entry_id", "") if isinstance(rel, dict) else "",
        "notes": action.get("notes", ""),
        "closed_at": action.get("closed_at", ""),
        "closed_by": action.get("closed_by", ""),
    }
    with connect() as conn:
        existing = conn.execute(
            "SELECT action_id FROM actions WHERE action_id=?",
            (action_id,),
        ).fetchone()
        if existing:
            sets = ", ".join([f"{k}=?" for k in record.keys() if k != "action_id"])
            params = [record[k] for k in record.keys() if k != "action_id"] + [action_id]
            conn.execute(f"UPDATE actions SET {sets} WHERE action_id=?", params)
        else:
            columns = ", ".join(record.keys())
            placeholders = ", ".join(["?"] * len(record))
            conn.execute(
                f"INSERT INTO actions ({columns}) VALUES ({placeholders})",
                list(record.values()),
            )
    action["updated_at"] = record["updated_at"]
    return action


def list_actions() -> List[Dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM actions ORDER BY updated_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]


def set_action_status(action_id: str, status: str, closed_by: str = "") -> None:
    with connect() as conn:
        closed_at = ""
        if status == "Closed":
            closed_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        conn.execute(
            """
            UPDATE actions
            SET status=?, updated_at=?, closed_at=?, closed_by=?
            WHERE action_id=?
            """,
            (
                status,
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                closed_at,
                closed_by or "",
                action_id,
            ),
        )


def upsert_ncr(ncr: Dict[str, Any]) -> Dict[str, Any]:
    ncr_id = ncr.get("ncr_id")
    if not ncr_id:
        ncr_id = f"NCR-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        ncr["ncr_id"] = ncr_id
    ncr.setdefault("status", "Open")
    ncr.setdefault("created_at", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    record = {
        "ncr_id": ncr_id,
        "status": ncr.get("status", "Open"),
        "part_number": ncr.get("part_number", ""),
        "line": ncr.get("line", ""),
        "owner": ncr.get("owner", ""),
        "description": ncr.get("description", ""),
        "created_at": ncr.get("created_at"),
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "created_by": ncr.get("created_by", ""),
        "close_date": ncr.get("close_date", ""),
        "related_entry_id": ncr.get("related_entry_id", ""),
        "action_id": ncr.get("action_id", ""),
    }
    with connect() as conn:
        existing = conn.execute(
            "SELECT ncr_id FROM ncrs WHERE ncr_id=?",
            (ncr_id,),
        ).fetchone()
        if existing:
            sets = ", ".join([f"{k}=?" for k in record.keys() if k != "ncr_id"])
            params = [record[k] for k in record.keys() if k != "ncr_id"] + [ncr_id]
            conn.execute(f"UPDATE ncrs SET {sets} WHERE ncr_id=?", params)
        else:
            columns = ", ".join(record.keys())
            placeholders = ", ".join(["?"] * len(record))
            conn.execute(
                f"INSERT INTO ncrs ({columns}) VALUES ({placeholders})",
                list(record.values()),
            )
    ncr["updated_at"] = record["updated_at"]
    return ncr


def list_ncrs() -> List[Dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM ncrs ORDER BY updated_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]


def set_ncr_status(ncr_id: str, status: str) -> None:
    close_date = ""
    if status == "Closed":
        close_date = datetime.now().strftime("%Y-%m-%d")
    with connect() as conn:
        conn.execute(
            """
            UPDATE ncrs
            SET status=?, updated_at=?, close_date=?
            WHERE ncr_id=?
            """,
            (status, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), close_date, ncr_id),
        )
