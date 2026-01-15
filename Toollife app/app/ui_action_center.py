# app/ui_action_center.py
import tkinter as tk
from tkinter import ttk, messagebox

from .ui_common import HeaderFrame
from .action_store import (
    load_actions_store,
    create_ncr_and_action,
    upsert_action,
    set_action_status,
    set_ncr_status,
    list_usernames,
    load_ncrs_store,
)


def _rank(sev: str) -> int:
    return {"Low": 0, "Medium": 1, "High": 2, "Critical": 3}.get(sev, 0)


class ActionCenterUI(tk.Frame):
    """
    Shared Action Center for Leader/Quality/Admin/Super.

    Permissions:
    - Admin + Top (Super User): can create & assign to any user
    - Others: can view/update items assigned to them (and optionally close)
    """
    def __init__(self, parent, controller, show_header=True):
        super().__init__(parent, bg=controller.colors["bg"])
        self.controller = controller

        if show_header:
            HeaderFrame(self, controller).pack(fill="x")

        self.username = getattr(controller, "username", "") or getattr(controller, "user", "") or ""
        self.role = getattr(controller, "role", "") or ""

        self.can_create = self.role in ("Admin", "Top (Super User)", "Top", "Super", "Super User", "Top (Super User)")

        # Top bar
        top = tk.Frame(self, bg=controller.colors["bg"], padx=10, pady=10)
        top.pack(fill="x")

        tk.Label(top, text="Action Center", bg=controller.colors["bg"], fg=controller.colors["fg"],
                 font=("Arial", 16, "bold")).pack(side="left")

        tk.Button(top, text="Refresh", command=self.refresh).pack(side="right")

        if self.can_create:
            tk.Button(top, text="New NCR", command=self.new_ncr).pack(side="right", padx=(0, 8))
            tk.Button(top, text="New Action", command=self.new_action).pack(side="right", padx=(0, 8))

        # Filters
        filt = tk.Frame(self, bg=controller.colors["bg"], padx=10, pady=(0, 8))
        filt.pack(fill="x")

        tk.Label(filt, text="View:", bg=controller.colors["bg"], fg=controller.colors["fg"]).pack(side="left")
        self.view_mode = ttk.Combobox(filt, state="readonly", width=18, values=["My Items", "All Items"])
        self.view_mode.set("My Items")
        self.view_mode.pack(side="left", padx=8)

        if not self.can_create:
            self.view_mode.set("My Items")
            self.view_mode.configure(values=["My Items"])
        self.view_mode.bind("<<ComboboxSelected>>", lambda e: self.refresh())

        tk.Label(filt, text="Min severity:", bg=controller.colors["bg"], fg=controller.colors["fg"]).pack(side="left", padx=(18, 6))
        self.min_sev = ttk.Combobox(filt, state="readonly", width=12, values=["Low", "Medium", "High", "Critical"])
        self.min_sev.set("Low")
        self.min_sev.pack(side="left", padx=8)
        self.min_sev.bind("<<ComboboxSelected>>", lambda e: self.refresh())

        tk.Label(filt, text="Status:", bg=controller.colors["bg"], fg=controller.colors["fg"]).pack(side="left", padx=(18, 6))
        self.status_filter = ttk.Combobox(filt, state="readonly", width=14, values=["All", "Open", "In Progress", "Blocked", "Closed"])
        self.status_filter.set("All")
        self.status_filter.pack(side="left", padx=8)
        self.status_filter.bind("<<ComboboxSelected>>", lambda e: self.refresh())

        # Table
        cols = ("id", "type", "title", "severity", "status", "owner", "due", "line", "part", "related")
        self.tree = ttk.Treeview(self, columns=cols, show="headings", height=18)
        for c in cols:
            self.tree.heading(c, text=c.upper())
            if c == "title":
                self.tree.column(c, width=360)
            elif c == "related":
                self.tree.column(c, width=240)
            else:
                self.tree.column(c, width=120)
        self.tree.pack(fill="both", expand=True, padx=10, pady=10)

        # Buttons
        btn = tk.Frame(self, bg=controller.colors["bg"], padx=10, pady=(0, 10))
        btn.pack(fill="x")

        tk.Button(btn, text="Edit", command=self.edit_selected).pack(side="left")
        tk.Button(btn, text="Set In Progress", command=lambda: self.set_status_selected("In Progress")).pack(side="left", padx=(8, 0))
        tk.Button(btn, text="Set Blocked", command=lambda: self.set_status_selected("Blocked")).pack(side="left", padx=(8, 0))
        tk.Button(btn, text="Close", command=lambda: self.set_status_selected("Closed")).pack(side="left", padx=(8, 0))

        self.status_lbl = tk.Label(self, text="", bg=controller.colors["bg"], fg=controller.colors["fg"])
        self.status_lbl.pack(anchor="w", padx=12, pady=(0, 10))

        self.refresh()

    # -------------------------
    def _all_actions(self):
        store = load_actions_store()
        return store.get("actions", []) or []

    def refresh(self):
        for i in self.tree.get_children():
            self.tree.delete(i)

        actions = self._all_actions()

        # Filters
        min_rank = _rank(self.min_sev.get())
        stat = self.status_filter.get()
        view = self.view_mode.get()

        out = []
        for a in actions:
            sev = a.get("severity", "Low")
            if _rank(sev) < min_rank:
                continue
            if stat != "All" and a.get("status") != stat:
                continue
            if view == "My Items" and self.username and a.get("owner") != self.username:
                continue
            out.append(a)

        # Sort: open first, then severity
        def sort_key(a):
            closed = (a.get("status") == "Closed")
            return (closed, -_rank(a.get("severity", "Low")), a.get("due_date") or "", a.get("updated_at") or "")

        out.sort(key=sort_key)

        for a in out:
            rel = a.get("related") or {}
            rel_txt = ""
            if isinstance(rel, dict):
                if rel.get("ncr_id"):
                    rel_txt += f"NCR:{rel.get('ncr_id')} "
                if rel.get("entry_id"):
                    rel_txt += f"Entry:{rel.get('entry_id')}"
                rel_txt = rel_txt.strip()

            self.tree.insert("", "end", values=(
                a.get("action_id", ""),
                a.get("type", ""),
                a.get("title", ""),
                a.get("severity", ""),
                a.get("status", ""),
                a.get("owner", ""),
                a.get("due_date", ""),
                a.get("line", ""),
                a.get("part_number", ""),
                rel_txt
            ))

        self.status_lbl.config(text=f"Showing {len(out)} items")

    def _selected_action_id(self):
        sel = self.tree.selection()
        if not sel:
            return None
        vals = self.tree.item(sel[0], "values")
        return vals[0] if vals else None

    def _find_action(self, action_id):
        for a in self._all_actions():
            if a.get("action_id") == action_id:
                return a
        return None

    # -------------------------
    def _can_edit_action(self, a):
        if self.can_create:
            return True
        return a.get("owner") == self.username

    def set_status_selected(self, status: str):
        aid = self._selected_action_id()
        if not aid:
            messagebox.showwarning("Select", "Select an item first.")
            return

        a = self._find_action(aid)
        if not a:
            messagebox.showerror("Missing", "Action not found.")
            return

        if not self._can_edit_action(a):
            messagebox.showerror("Not allowed", "You can only update items assigned to you.")
            return

        set_action_status(aid, status, closed_by=self.username, actor=self.username)

        # If it's an NCR-linked action, mirror status into ncrs.json
        rel = a.get("related") or {}
        if isinstance(rel, dict) and rel.get("ncr_id"):
            # Basic mapping
            if status == "Closed":
                set_ncr_status(rel["ncr_id"], "Closed", actor=self.username)
            elif status in ("Open", "In Progress", "Blocked"):
                # keep NCR open unless closed
                set_ncr_status(rel["ncr_id"], "Open", actor=self.username)

        self.refresh()

    # -------------------------
    def edit_selected(self):
        aid = self._selected_action_id()
        if not aid:
            messagebox.showwarning("Select", "Select an item first.")
            return

        a = self._find_action(aid)
        if not a:
            messagebox.showerror("Missing", "Action not found.")
            return

        if not self._can_edit_action(a):
            messagebox.showerror("Not allowed", "You can only edit items assigned to you.")
            return

        self._open_action_editor(a)

    def new_action(self):
        self._open_action_editor(None)

    def new_ncr(self):
        self._open_ncr_editor()

    # -------------------------
    def _open_action_editor(self, existing):
        win = tk.Toplevel(self)
        win.title("Action Editor")
        win.grab_set()

        def row(lbl, var, width=40):
            r = tk.Frame(win, padx=10, pady=4)
            r.pack(fill="x")
            tk.Label(r, text=lbl, width=16, anchor="w").pack(side="left")
            e = tk.Entry(r, textvariable=var, width=width)
            e.pack(side="left", fill="x", expand=True)
            return e

        title = tk.StringVar(value=(existing or {}).get("title", ""))
        severity = tk.StringVar(value=(existing or {}).get("severity", "Medium"))
        status = tk.StringVar(value=(existing or {}).get("status", "Open"))
        owner = tk.StringVar(value=(existing or {}).get("owner", self.username))
        due = tk.StringVar(value=(existing or {}).get("due_date", ""))
        line = tk.StringVar(value=(existing or {}).get("line", ""))
        part = tk.StringVar(value=(existing or {}).get("part_number", ""))
        notes = tk.StringVar(value=(existing or {}).get("notes", ""))

        row("Title", title)
        r2 = tk.Frame(win, padx=10, pady=4); r2.pack(fill="x")
        tk.Label(r2, text="Severity", width=16, anchor="w").pack(side="left")
        ttk.Combobox(r2, textvariable=severity, state="readonly", width=18,
                     values=["Low", "Medium", "High", "Critical"]).pack(side="left")
        tk.Label(r2, text="Status", width=10, anchor="w").pack(side="left", padx=(12, 0))
        ttk.Combobox(r2, textvariable=status, state="readonly", width=14,
                     values=["Open", "In Progress", "Blocked", "Closed"]).pack(side="left")

        r3 = tk.Frame(win, padx=10, pady=4); r3.pack(fill="x")
        tk.Label(r3, text="Owner", width=16, anchor="w").pack(side="left")

        users = list_usernames() or [self.username] if self.username else []
        if self.can_create:
            ttk.Combobox(r3, textvariable=owner, state="readonly", width=22, values=users).pack(side="left")
        else:
            tk.Entry(r3, textvariable=owner, state="disabled", width=24).pack(side="left")

        row("Due Date", due)
        row("Line", line)
        row("Part #", part)
        row("Notes", notes)

        def save_it():
            if not title.get().strip():
                messagebox.showerror("Error", "Title is required.")
                return

            payload = {
                "action_id": (existing or {}).get("action_id", ""),
                "type": (existing or {}).get("type", "Action"),
                "title": title.get().strip(),
                "severity": severity.get().strip(),
                "status": status.get().strip(),
                "owner": owner.get().strip(),
                "due_date": due.get().strip(),
                "line": line.get().strip(),
                "part_number": part.get().strip(),
                "notes": notes.get().strip(),
                "created_by": (existing or {}).get("created_by", self.username),
                "related": (existing or {}).get("related", {}),
            }

            upsert_action(payload, actor=self.username)
            win.destroy()
            self.refresh()

        btn = tk.Frame(win, padx=10, pady=10); btn.pack(fill="x")
        tk.Button(btn, text="Cancel", command=win.destroy).pack(side="right")
        tk.Button(btn, text="Save", command=save_it).pack(side="right", padx=(0, 8))

    def _open_ncr_editor(self):
        if not self.can_create:
            messagebox.showerror("Not allowed", "Only Admin/Super can create NCRs.")
            return

        win = tk.Toplevel(self)
        win.title("New NCR")
        win.grab_set()

        def row(lbl, var, width=46):
            r = tk.Frame(win, padx=10, pady=4)
            r.pack(fill="x")
            tk.Label(r, text=lbl, width=16, anchor="w").pack(side="left")
            tk.Entry(r, textvariable=var, width=width).pack(side="left", fill="x", expand=True)

        title = tk.StringVar(value="")
        description = tk.StringVar(value="")
        severity = tk.StringVar(value="High")
        owner = tk.StringVar(value=self.username)
        due = tk.StringVar(value="")
        line = tk.StringVar(value="")
        part = tk.StringVar(value="")
        entry_id = tk.StringVar(value="")

        row("Title", title)
        row("Description", description)

        r2 = tk.Frame(win, padx=10, pady=4); r2.pack(fill="x")
        tk.Label(r2, text="Severity", width=16, anchor="w").pack(side="left")
        ttk.Combobox(r2, textvariable=severity, state="readonly", width=18,
                     values=["Low", "Medium", "High", "Critical"]).pack(side="left")

        r3 = tk.Frame(win, padx=10, pady=4); r3.pack(fill="x")
        tk.Label(r3, text="Assign to", width=16, anchor="w").pack(side="left")
        users = list_usernames() or ([self.username] if self.username else [])
        ttk.Combobox(r3, textvariable=owner, state="readonly", width=22, values=users).pack(side="left")

        row("Due Date", due)
        row("Line", line)
        row("Part #", part)
        row("Related Entry ID", entry_id)

        def create_it():
            if not title.get().strip():
                messagebox.showerror("Error", "Title is required.")
                return

            out = create_ncr_and_action(
                title=title.get().strip(),
                description=description.get().strip(),
                severity=severity.get().strip(),
                owner=owner.get().strip(),
                created_by=self.username,
                line=line.get().strip(),
                part_number=part.get().strip(),
                due_date=due.get().strip(),
                related_entry_id=entry_id.get().strip()
            )

            messagebox.showinfo("Created", f"Created {out['ncr']['ncr_id']} and linked action {out['action']['action_id']}.")
            win.destroy()
            self.refresh()

        btn = tk.Frame(win, padx=10, pady=10); btn.pack(fill="x")
        tk.Button(btn, text="Cancel", command=win.destroy).pack(side="right")
        tk.Button(btn, text="Create", command=create_it).pack(side="right", padx=(0, 8))
