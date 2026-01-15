from typing import Dict

# Levels: none, view, edit, override
PERMISSIONS = {
    "Top (Super User)": {
        "view_data": "edit",
        "edit_any": "override",
        "manage_tools": "edit",
        "manage_users": "none",
        "export": "edit",
    },
    "Admin": {
        "view_data": "edit",
        "edit_any": "edit",
        "manage_tools": "edit",
        "manage_users": "edit",
        "export": "edit",
    },
}

ROLE_SCREEN_DEFAULTS = {
    "Operator": {"Operator": "edit"},
    "Tool Changer": {"Tool Changer": "edit", "Action Center": "view", "Audit Trail": "view"},
    "Leader": {"Leader": "edit", "Action Center": "view", "Audit Trail": "view"},
    "Quality": {"Quality": "edit", "Action Center": "view", "Audit Trail": "view"},
    "Admin": {"Admin": "edit", "Action Center": "edit", "Audit Trail": "view"},
    "Top (Super User)": {
        "Dashboard": "edit",
        "Notifications": "edit",
        "Action Center": "edit",
        "Tool Changer": "edit",
        "Operator": "edit",
        "Leader": "edit",
        "Quality": "edit",
        "Gages": "edit",
        "Risk Settings": "edit",
        "Health Check": "edit",
        "Shift Handoff": "edit",
        "Repeat Offenders": "edit",
        "Top level": "edit",
        "Master Data": "edit",
        "Admin": "edit",
        "Audit Trail": "view",
    },
}


def can(role: str, key: str, at_least="view"):
    order = {"none": 0, "view": 1, "edit": 2, "override": 3}
    have = PERMISSIONS.get(role, {}).get(key, "none")
    return order.get(have, 0) >= order.get(at_least, 1)


def _level_rank(level: str) -> int:
    return {"none": 0, "view": 1, "edit": 2, "override": 3}.get(level, 0)


def get_user_screen_permissions(username: str) -> Dict[str, str]:
    from .db import list_screen_permissions

    perms = {}
    for row in list_screen_permissions(username):
        perms[row["screen"]] = row.get("level", "view")
    return perms


def screen_access(role: str, username: str, screen: str) -> str:
    defaults = ROLE_SCREEN_DEFAULTS.get(role, {})
    level = defaults.get(screen, "none")
    overrides = get_user_screen_permissions(username)
    if screen in overrides:
        level = overrides[screen]
    return level


def can_view_screen(role: str, username: str, screen: str) -> bool:
    return _level_rank(screen_access(role, username, screen)) >= _level_rank("view")


def can_edit_screen(role: str, username: str, screen: str) -> bool:
    return _level_rank(screen_access(role, username, screen)) >= _level_rank("edit")
