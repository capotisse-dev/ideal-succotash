import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime

from .ui_common import HeaderFrame, FilePicker, DataTable
from .storage import get_df, save_df
from .ui_action_center import ActionCenterUI
from .ui_audit import AuditTrailUI
from .screen_registry import get_screen_class
from .audit import log_audit

class LeaderUI(tk.Frame):
    def __init__(self, parent, controller, show_header=True):
        super().__init__(parent, bg=controller.colors["bg"])
        self.controller = controller

        if show_header:
            HeaderFrame(self, controller).pack(fill="x")

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=10, pady=10)

        tab_main = tk.Frame(nb, bg=controller.colors["bg"])
        tab_actions = tk.Frame(nb, bg=controller.colors["bg"])
        tab_audit = tk.Frame(nb, bg=controller.colors["bg"])
        nb.add(tab_main, text="Leader")
        nb.add(tab_actions, text="Action Center")
        nb.add(tab_audit, text="Audit Trail")

        try:
            ActionCenterUI(tab_actions, controller, show_header=False).pack(fill="both", expand=True)
        except TypeError:
            ActionCenterUI(tab_actions, controller).pack(fill="both", expand=True)
        try:
            AuditTrailUI(tab_audit, controller, show_header=False).pack(fill="both", expand=True)
        except TypeError:
            AuditTrailUI(tab_audit, controller).pack(fill="both", expand=True)

        for screen in controller.extra_screens():
            tab_extra = tk.Frame(nb, bg=controller.colors["bg"])
            nb.add(tab_extra, text=screen)
            ViewCls = get_screen_class(screen)
            try:
                ViewCls(tab_extra, controller, show_header=False).pack(fill="both", expand=True)
            except TypeError:
                ViewCls(tab_extra, controller).pack(fill="both", expand=True)

        top = tk.Frame(tab_main, bg=controller.colors["bg"], padx=10, pady=10)
        top.pack(fill="x")

        self.picker = FilePicker(top, self.load_pending)
        self.picker.pack(side="left")

        tk.Button(top, text="Sign Selected", command=self.sign_selected).pack(side="left", padx=10)

        cols = ["ID","Date","Time","Line","Machine","Tool_Num","Reason","Downtime_Mins","Leader_Sign","Quality_Verified"]
        self.table = DataTable(tab_main, cols)
        self.table.pack(fill="both", expand=True, padx=10, pady=10)

        self.load_pending(self.picker.get())

    def load_pending(self, filename):
        df, _ = get_df(filename)
        pending = df[df["Leader_Sign"].fillna("Pending").astype(str).str.lower().eq("pending")]
        self._filename = filename
        self.table.load(pending)

    def sign_selected(self):
        sel_id = self.table.selected_id()
        if not sel_id:
            messagebox.showwarning("Select", "Select a row first.")
            return

        df, filename = get_df(self._filename)
        idx = df.index[df["ID"].astype(str) == str(sel_id)]
        if len(idx) == 0:
            messagebox.showerror("Not found", "Row not found.")
            return

        now = datetime.now()
        df.loc[idx, "Leader_Sign"] = "Yes"
        df.loc[idx, "Leader_User"] = self.controller.user
        df.loc[idx, "Leader_Time"] = now.strftime("%Y-%m-%d %H:%M:%S")

        save_df(df, filename)
        log_audit(self.controller.user, f"Leader sign entry {sel_id}")
        self.load_pending(filename)
