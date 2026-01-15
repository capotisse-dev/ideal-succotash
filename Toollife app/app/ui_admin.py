# app/ui_admin.py
import tkinter as tk
from tkinter import ttk, messagebox

from .ui_common import HeaderFrame
from .ui_action_center import ActionCenterUI
from .ui_audit import AuditTrailUI
from .db import (
    list_users,
    get_user,
    upsert_user,
    update_user_fields,
    list_screen_permissions,
    set_screen_permission,
    delete_screen_permission,
)
from .permissions import ROLE_SCREEN_DEFAULTS
from .audit import log_audit


class AdminUI(tk.Frame):
    """
    Admin UI (restricted):
    - NO direct editing of production data.
    - Can manage users only:
        * create users
        * set username, password, display name, role
    - Includes Action Center tab (Admin can create/assign).
    """
    ROLE_OPTIONS = [
        "Operator",
        "Tool Changer",
        "Leader",
        "Quality",
        "Top (Super User)",
        "Admin"
    ]
    SCREEN_LEVELS = ["view", "edit", "none"]

    def __init__(self, parent, controller, show_header=True):
        super().__init__(parent, bg=controller.colors["bg"])
        self.controller = controller

        if show_header:
            HeaderFrame(self, controller).pack(fill="x")

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=10, pady=10)

        # Tabs
        tab_users = tk.Frame(nb, bg=controller.colors["bg"])
        tab_actions = tk.Frame(nb, bg=controller.colors["bg"])
        tab_access = tk.Frame(nb, bg=controller.colors["bg"])
        tab_audit = tk.Frame(nb, bg=controller.colors["bg"])

        nb.add(tab_users, text="User Management")
        nb.add(tab_actions, text="Action Center")
        nb.add(tab_access, text="Screen Access")
        nb.add(tab_audit, text="Audit Trail")

        self._build_user_management(tab_users)
        # Action Center: no extra header inside tab
        try:
            ActionCenterUI(tab_actions, controller, show_header=False).pack(fill="both", expand=True)
        except TypeError:
            ActionCenterUI(tab_actions, controller).pack(fill="both", expand=True)
        self._build_access_management(tab_access)
        try:
            AuditTrailUI(tab_audit, controller, show_header=False).pack(fill="both", expand=True)
        except TypeError:
            AuditTrailUI(tab_audit, controller).pack(fill="both", expand=True)

    # -------------------------
    def _build_user_management(self, parent):
        top = tk.Frame(parent, bg=self.controller.colors["bg"], padx=10, pady=10)
        top.pack(fill="x")

        tk.Label(
            top,
            text="User Management (Admin Only)",
            bg=self.controller.colors["bg"],
            fg=self.controller.colors["fg"],
            font=("Arial", 16, "bold")
        ).pack(side="left")

        tk.Button(top, text="Refresh", command=self.refresh_users).pack(side="right")

        form = tk.LabelFrame(
            parent,
            text="User Details",
            padx=10,
            pady=10,
            bg=self.controller.colors["bg"],
            fg=self.controller.colors["fg"],
        )
        form.pack(fill="x", padx=10, pady=(0, 10))

        self.var_username = tk.StringVar(value="")
        self.var_name = tk.StringVar(value="")
        self.var_role = tk.StringVar(value=self.ROLE_OPTIONS[0])
        self.var_line = tk.StringVar(value="Both")
        self.var_current_password = tk.StringVar(value="")
        self.var_new_password = tk.StringVar(value="")

        self._form_row(form, "Username", self.var_username)
        self._form_row(form, "Display Name", self.var_name)

        r = tk.Frame(form, bg=self.controller.colors["bg"])
        r.pack(fill="x", pady=4)
        tk.Label(
            r,
            text="Role",
            width=14,
            anchor="w",
            bg=self.controller.colors["bg"],
            fg=self.controller.colors["fg"],
        ).pack(side="left")
        ttk.Combobox(r, textvariable=self.var_role, state="readonly", values=self.ROLE_OPTIONS, width=24).pack(side="left")

        self._form_row(form, "Line", self.var_line)
        self._form_row(form, "Current Password", self.var_current_password, readonly=True)
        self._form_row(form, "New Password", self.var_new_password, show="*")

        btns = tk.Frame(form, bg=self.controller.colors["bg"])
        btns.pack(fill="x", pady=(10, 0))
        tk.Button(btns, text="Create User", command=self.create_user).pack(side="right")
        tk.Button(btns, text="Update User", command=self.update_user).pack(side="right", padx=(0, 8))
        tk.Button(btns, text="Reset Password", command=self.reset_password).pack(side="right", padx=(0, 8))

        listbox_frame = tk.LabelFrame(
            parent,
            text="Existing Users",
            padx=10,
            pady=10,
            bg=self.controller.colors["bg"],
            fg=self.controller.colors["fg"],
        )
        listbox_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        cols = ("username", "name", "role", "line")
        self.tree = ttk.Treeview(listbox_frame, columns=cols, show="headings", height=14)
        for c in cols:
            self.tree.heading(c, text=c.upper())
            if c == "username":
                self.tree.column(c, width=200)
            elif c == "name":
                self.tree.column(c, width=220)
            elif c == "role":
                self.tree.column(c, width=160)
            else:
                self.tree.column(c, width=120)
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", self.load_selected_user)

        self.refresh_users()

    def _form_row(self, parent, label, var, show=None, readonly: bool = False):
        r = tk.Frame(parent, bg=self.controller.colors["bg"])
        r.pack(fill="x", pady=4)
        tk.Label(
            r,
            text=label,
            width=14,
            anchor="w",
            bg=self.controller.colors["bg"],
            fg=self.controller.colors["fg"],
        ).pack(side="left")
        e = tk.Entry(r, textvariable=var, show=show) if show else tk.Entry(r, textvariable=var)
        e.pack(side="left", fill="x", expand=True)
        if readonly:
            e.configure(state="readonly")

    # -------------------------
    def refresh_users(self):
        for i in self.tree.get_children():
            self.tree.delete(i)

        users = list_users()
        for u in users:
            self.tree.insert("", "end", values=(
                u.get("username", ""),
                u.get("name", ""),
                u.get("role", ""),
                u.get("line", "Both"),
            ))
        if hasattr(self, "access_user_combo"):
            self.access_user_combo.configure(values=[u.get("username") for u in users])

    def create_user(self):
        username = self.var_username.get().strip()
        name = self.var_name.get().strip()
        role = self.var_role.get().strip()
        line = self.var_line.get().strip() or "Both"
        password = self.var_new_password.get().strip()

        if not username:
            messagebox.showerror("Error", "Username is required.")
            return
        if not password:
            messagebox.showerror("Error", "Password is required.")
            return
        if not name:
            messagebox.showerror("Error", "Display Name is required.")
            return
        if role not in self.ROLE_OPTIONS:
            messagebox.showerror("Error", "Select a valid role.")
            return

        if get_user(username):
            messagebox.showerror("Error", f"Username '{username}' already exists.")
            return

        upsert_user(username=username, password=password, role=role, name=name, line=line)
        log_audit(self.controller.user, f"Created user {username} ({role})")

        # Clear inputs
        self.var_username.set("")
        self.var_name.set("")
        self.var_role.set(self.ROLE_OPTIONS[0])
        self.var_line.set("Both")
        self.var_current_password.set("")
        self.var_new_password.set("")

        messagebox.showinfo("Created", f"welcome '{name}'")
        self.refresh_users()

    def load_selected_user(self, event=None):
        sel = self.tree.selection()
        if not sel:
            return
        username = self.tree.item(sel[0], "values")[0]
        user = get_user(username)
        if not user:
            return
        self.var_username.set(user.get("username", ""))
        self.var_name.set(user.get("name", ""))
        self.var_role.set(user.get("role", self.ROLE_OPTIONS[0]))
        self.var_line.set(user.get("line", "Both"))
        self.var_current_password.set(user.get("password", ""))
        self.var_new_password.set("")

    def update_user(self):
        username = self.var_username.get().strip()
        if not username:
            messagebox.showerror("Error", "Select a user to update.")
            return
        role = self.var_role.get().strip()
        name = self.var_name.get().strip()
        line = self.var_line.get().strip() or "Both"
        update_user_fields(username, {"role": role, "name": name, "line": line})
        log_audit(self.controller.user, f"Updated user {username}")
        messagebox.showinfo("Updated", f"welcome '{name}'")
        self.refresh_users()

    def reset_password(self):
        username = self.var_username.get().strip()
        new_password = self.var_new_password.get().strip()
        if not username:
            messagebox.showerror("Error", "Select a user first.")
            return
        if not new_password:
            messagebox.showerror("Error", "Enter a new password.")
            return
        update_user_fields(username, {"password": new_password})
        self.var_current_password.set(new_password)
        self.var_new_password.set("")
        log_audit(self.controller.user, f"Reset password for {username}")
        messagebox.showinfo("Password Reset", f"Password updated for {username}.")

    # -------------------------
    def _build_access_management(self, parent):
        top = tk.Frame(parent, bg=self.controller.colors["bg"], padx=10, pady=10)
        top.pack(fill="x")

        tk.Label(
            top,
            text="Screen Access Overrides",
            bg=self.controller.colors["bg"],
            fg=self.controller.colors["fg"],
            font=("Arial", 16, "bold"),
        ).pack(side="left")

        tk.Button(top, text="Refresh", command=self.refresh_access).pack(side="right")

        form = tk.LabelFrame(
            parent,
            text="Assign Screen Access",
            padx=10,
            pady=10,
            bg=self.controller.colors["bg"],
            fg=self.controller.colors["fg"],
        )
        form.pack(fill="x", padx=10, pady=(0, 10))

        self.access_user = tk.StringVar(value="")
        self.access_screen = tk.StringVar(value="")
        self.access_level = tk.StringVar(value=self.SCREEN_LEVELS[0])

        row_user = tk.Frame(form, bg=self.controller.colors["bg"])
        row_user.pack(fill="x", pady=4)
        tk.Label(
            row_user,
            text="User",
            width=14,
            anchor="w",
            bg=self.controller.colors["bg"],
            fg=self.controller.colors["fg"],
        ).pack(side="left")
        self.access_user_combo = ttk.Combobox(
            row_user,
            textvariable=self.access_user,
            values=[u.get("username") for u in list_users()],
            state="readonly",
            width=24,
        )
        self.access_user_combo.pack(side="left")

        row_screen = tk.Frame(form, bg=self.controller.colors["bg"])
        row_screen.pack(fill="x", pady=4)
        tk.Label(
            row_screen,
            text="Screen",
            width=14,
            anchor="w",
            bg=self.controller.colors["bg"],
            fg=self.controller.colors["fg"],
        ).pack(side="left")
        self.screen_options = sorted({screen for screens in ROLE_SCREEN_DEFAULTS.values() for screen in screens})
        self.access_screen_combo = ttk.Combobox(
            row_screen,
            textvariable=self.access_screen,
            values=self.screen_options,
            state="readonly",
            width=24,
        )
        self.access_screen_combo.pack(side="left")

        row_level = tk.Frame(form, bg=self.controller.colors["bg"])
        row_level.pack(fill="x", pady=4)
        tk.Label(
            row_level,
            text="Level",
            width=14,
            anchor="w",
            bg=self.controller.colors["bg"],
            fg=self.controller.colors["fg"],
        ).pack(side="left")
        self.access_level_combo = ttk.Combobox(
            row_level,
            textvariable=self.access_level,
            values=self.SCREEN_LEVELS,
            state="readonly",
            width=24,
        )
        self.access_level_combo.pack(side="left")

        btns = tk.Frame(form, bg=self.controller.colors["bg"])
        btns.pack(fill="x", pady=(10, 0))
        tk.Button(btns, text="Save Access", command=self.save_access).pack(side="right")
        tk.Button(btns, text="Remove Access", command=self.remove_access).pack(side="right", padx=(0, 8))

        list_frame = tk.LabelFrame(
            parent,
            text="Current Overrides",
            padx=10,
            pady=10,
            bg=self.controller.colors["bg"],
            fg=self.controller.colors["fg"],
        )
        list_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        cols = ("username", "screen", "level")
        self.access_tree = ttk.Treeview(list_frame, columns=cols, show="headings", height=12)
        for c in cols:
            self.access_tree.heading(c, text=c.upper())
            self.access_tree.column(c, width=220)
        self.access_tree.pack(fill="both", expand=True)
        self.access_tree.bind("<<TreeviewSelect>>", self.load_access_selection)

        self.refresh_access()

    def refresh_access(self):
        for i in self.access_tree.get_children():
            self.access_tree.delete(i)
        for row in list_screen_permissions():
            self.access_tree.insert("", "end", values=(
                row.get("username", ""),
                row.get("screen", ""),
                row.get("level", ""),
            ))

    def load_access_selection(self, event=None):
        sel = self.access_tree.selection()
        if not sel:
            return
        username, screen, level = self.access_tree.item(sel[0], "values")
        self.access_user.set(username)
        self.access_screen.set(screen)
        self.access_level.set(level)

    def save_access(self):
        username = self.access_user.get().strip()
        screen = self.access_screen.get().strip()
        level = self.access_level.get().strip()
        if not username or not screen:
            messagebox.showerror("Error", "Select a user and screen.")
            return
        if level == "none":
            delete_screen_permission(username, screen)
            log_audit(self.controller.user, f"Removed access {screen} for {username}")
        else:
            set_screen_permission(username, screen, level)
            log_audit(self.controller.user, f"Set access {screen}={level} for {username}")
        self.refresh_access()

    def remove_access(self):
        username = self.access_user.get().strip()
        screen = self.access_screen.get().strip()
        if not username or not screen:
            messagebox.showerror("Error", "Select a user and screen.")
            return
        delete_screen_permission(username, screen)
        log_audit(self.controller.user, f"Removed access {screen} for {username}")
        self.refresh_access()
