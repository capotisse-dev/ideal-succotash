# app/ui_login.py
import tkinter as tk
from tkinter import messagebox

from .bootstrap import ensure_app_initialized
from .db import get_user, update_user_fields, get_meta, set_meta
from .audit import log_audit
from .ui_common import LIGHT, DARK
from .permissions import screen_access as permission_screen_access, can_edit_screen as permission_can_edit_screen, ROLE_SCREEN_DEFAULTS
from .screen_registry import SCREEN_REGISTRY

# Role UIs
from .ui_toolchanger import ToolChangerUI
from .ui_operator import OperatorUI
from .ui_leader import LeaderUI
from .ui_quality import QualityUI
from .ui_top import TopUI
from .ui_admin import AdminUI
from .ui_super import SuperUI


# -----------------------------
# Role normalization (aliases)
# -----------------------------
ROLE_ALIASES = {
    "toolchanger": "Tool Changer",
    "tool changer": "Tool Changer",
    "tool_change": "Tool Changer",
    "toolchange": "Tool Changer",

    "leader": "Leader",

    "quality": "Quality",
    "qc": "Quality",

    "top": "Top (Super User)",
    "super": "Top (Super User)",
    "top (super user)": "Top (Super User)",

    "admin": "Admin",

    "operator": "Operator",
}

def normalize_role(role_value):
    if role_value is None:
        return ""
    r = str(role_value).strip()
    if not r:
        return ""
    key = r.lower().strip()
    return ROLE_ALIASES.get(key, r)


# -----------------------------
# Role to UI mapping
# -----------------------------
ROLE_TO_UI = {
    "Tool Changer": ToolChangerUI,
    "Operator": OperatorUI,
    "Leader": LeaderUI,
    "Quality": QualityUI,
    "Top (Super User)": SuperUI,  # Super = "all screens console"
    "Admin": AdminUI,
}


# -----------------------------
# Main App (Tk root)
# -----------------------------
class App(tk.Tk):
    def __init__(self):
        super().__init__()

        # Ensure folders/files exist even on double-click launch
        ensure_app_initialized()

        self.title("Tool Life Tracking System")
        self.geometry("1280x850")

        self.is_dark = False
        self.colors = LIGHT

        self.user = None
        self.role = None
        self.user_line = None

        self.container = tk.Frame(self)
        self.container.pack(fill="both", expand=True)

        if get_meta("shown_default_login") != "1":
            messagebox.showinfo(
                "Default Logins",
                "Default logins:\n- admin / admin\n- super / super",
            )
            set_meta("shown_default_login", "1")

        self.show_login()

    def toggle_theme(self):
        self.is_dark = not self.is_dark
        self.colors = DARK if self.is_dark else LIGHT

        if self.user:
            self.route_role()
        else:
            self.show_login()

    def clear(self):
        for w in self.container.winfo_children():
            w.destroy()

    def show_login(self):
        self.clear()
        self.container.configure(bg=self.colors["bg"])
        LoginPage(self.container, self).pack(fill="both", expand=True)

    def login(self, username, role, line=None):
        self.user = username
        self.role = normalize_role(role)
        self.user_line = line or "Both"
        log_audit(username, f"Login as {self.role}")
        self.route_role()

    def route_role(self):
        self.clear()
        self.container.configure(bg=self.colors["bg"])

        role = normalize_role(self.role)
        ui_cls = ROLE_TO_UI.get(role)

        if not ui_cls:
            messagebox.showerror(
                "Role Error",
                f"Unknown role '{self.role}'.\n\n"
                "Valid roles:\n- " + "\n- ".join(sorted(ROLE_TO_UI.keys()))
            )
            self.logout()
            return

        # SuperUI doesn't accept show_header
        if ui_cls is SuperUI:
            ui_cls(self.container, self).pack(fill="both", expand=True)
            return

        # Other screens: try show_header pattern, fall back if not supported
        try:
            ui_cls(self.container, self, show_header=True).pack(fill="both", expand=True)
        except TypeError:
            ui_cls(self.container, self).pack(fill="both", expand=True)

    def screen_access(self, screen: str) -> str:
        return permission_screen_access(self.role, self.user, screen)

    def can_edit_screen(self, screen: str) -> bool:
        return permission_can_edit_screen(self.role, self.user, screen)

    def extra_screens(self):
        defaults = ROLE_SCREEN_DEFAULTS.get(self.role, {})
        extras = []
        for screen in SCREEN_REGISTRY.keys():
            if screen in defaults:
                continue
            if self.screen_access(screen) != "none":
                extras.append(screen)
        return extras

    def logout(self):
        if self.user:
            log_audit(self.user, "Logout")
        self.user = None
        self.role = None
        self.user_line = None
        self.show_login()


# -----------------------------
# Login Page UI
# -----------------------------
class LoginPage(tk.Frame):
    def __init__(self, parent, controller: App):
        super().__init__(parent, bg=controller.colors["bg"])
        self.controller = controller

        card = tk.Frame(
            self,
            padx=40, pady=40,
            relief="raised", borderwidth=2,
            bg=controller.colors["header_bg"]
        )
        card.place(relx=0.5, rely=0.5, anchor="center")

        tk.Label(
            card,
            text="System Login",
            font=("Arial", 20, "bold"),
            bg=controller.colors["header_bg"],
            fg=controller.colors["fg"]
        ).pack(pady=20)

        tk.Label(card, text="Username:", bg=controller.colors["header_bg"], fg=controller.colors["fg"]).pack(anchor="w")
        self.u = tk.Entry(card, width=30, font=("Arial", 12))
        self.u.pack(pady=5)
        self.u.focus_set()

        tk.Label(card, text="Password:", bg=controller.colors["header_bg"], fg=controller.colors["fg"]).pack(anchor="w")
        self.p = tk.Entry(card, width=30, show="*", font=("Arial", 12))
        self.p.pack(pady=5)

        btns = tk.Frame(card, bg=controller.colors["header_bg"])
        btns.pack(pady=20)

        tk.Button(
            btns,
            text="Login",
            bg="#007bff", fg="white",
            font=("Arial", 12, "bold"),
            width=16,
            command=self.check
        ).pack(side="left", padx=6)

        tk.Button(
            btns,
            text="Show/Reset Password",
            bg="#6c757d", fg="white",
            font=("Arial", 10, "bold"),
            width=18,
            command=self.show_or_reset_password
        ).pack(side="left", padx=6)



        # Enter key triggers login
        self.u.bind("<Return>", lambda e: self.check())
        self.p.bind("<Return>", lambda e: self.check())

    def check(self):
        u = self.u.get().strip()
        p = self.p.get()

        if not u:
            messagebox.showerror("Error", "Enter username.")
            return

        rec = get_user(u)
        if not rec:
            messagebox.showerror("Error", "Invalid credentials.")
            return

        if rec.get("password", "") != p:
            messagebox.showerror("Error", "Invalid credentials.")
            return

        role_raw = rec.get("role", "")
        role = normalize_role(role_raw)
        line = rec.get("line", "Both")

        if role not in ROLE_TO_UI:
            messagebox.showerror(
                "Role Error",
                f"User '{u}' has role '{role_raw}', which is not mapped.\n\n"
                "Fix users.json role to one of:\n- " + "\n- ".join(sorted(ROLE_TO_UI.keys()))
            )
            return

        self.controller.login(u, role, line)
        messagebox.showinfo("Welcome", f"welcome '{rec.get('name', u)}'")

    def show_or_reset_password(self):
        u = self.u.get().strip()
        if not u:
            messagebox.showerror("Error", "Enter username first.")
            return
        rec = get_user(u)
        if not rec:
            messagebox.showerror("Error", "User not found.")
            return
        current = rec.get("password", "")
        if messagebox.askyesno("Current Password", f"Current password for {u} is: {current}\n\nReset it?"):
            new_pw = self.p.get().strip()
            if not new_pw:
                messagebox.showerror("Error", "Enter new password in the Password field.")
                return
            update_user_fields(u, {"password": new_pw})
            messagebox.showinfo("Reset", f"Password updated for {u}.")
