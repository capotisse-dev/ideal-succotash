# app/ui_gage_verification.py
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime

import pandas as pd

from .ui_common import HeaderFrame
from .storage import load_json
from .config import (
    GAGES_FILE,
    GAGE_VERIFICATION_Q_FILE,
    gage_verification_log_path,
)


class GageVerificationUI(tk.Frame):
    def __init__(self, parent, controller, show_header=True):
        super().__init__(parent, bg=controller.colors["bg"])
        self.controller = controller

        if show_header:
            HeaderFrame(self, controller).pack(fill="x")

        # Load stores
        self.gages_store = load_json(GAGES_FILE, {"gages": []})
        self.q_store = load_json(GAGE_VERIFICATION_Q_FILE, {"by_type": {"Other": []}})

        self.gage_map = {g.get("gage_id"): g for g in self.gages_store.get("gages", [])}
        self.gage_ids = sorted([g.get("gage_id") for g in self.gages_store.get("gages", []) if g.get("gage_id")])

        # Top title row
        top = tk.Frame(self, bg=controller.colors["bg"], padx=10, pady=10)
        top.pack(fill="x")

        tk.Label(
            top,
            text="Gage Verification (Super/Admin)",
            bg=controller.colors["bg"],
            fg=controller.colors["fg"],
            font=("Arial", 16, "bold")
        ).pack(side="left")

        tk.Button(top, text="Refresh", command=self.reload).pack(side="right")

        # Selector row
        sel = tk.Frame(self, bg=controller.colors["bg"], padx=10, pady=6)
        sel.pack(fill="x")

        tk.Label(sel, text="Select Gage:", bg=controller.colors["bg"], fg=controller.colors["fg"]).pack(side="left")

        self.sel_gage = ttk.Combobox(sel, values=self.gage_ids, state="readonly", width=18)
        self.sel_gage.pack(side="left", padx=8)
        if self.gage_ids:
            self.sel_gage.set(self.gage_ids[0])

        tk.Button(sel, text="Load Checklist", command=self.load_checklist).pack(side="left", padx=(8, 0))

        # Notes row
        notes = tk.Frame(self, bg=controller.colors["bg"], padx=10, pady=6)
        notes.pack(fill="x")

        tk.Label(notes, text="Notes:", bg=controller.colors["bg"], fg=controller.colors["fg"]).pack(side="left")
        self.notes_var = tk.StringVar(value="")
        tk.Entry(notes, textvariable=self.notes_var).pack(side="left", fill="x", expand=True, padx=8)

        # Checklist container (scrollable)
        self.canvas = tk.Canvas(self, bg=controller.colors["bg"], highlightthickness=0)
        self.canvas.pack(side="left", fill="both", expand=True, padx=(10, 0), pady=10)

        self.vsb = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.vsb.pack(side="right", fill="y", pady=10)

        self.canvas.configure(yscrollcommand=self.vsb.set)
        self.check_body = tk.Frame(self.canvas, bg=controller.colors["bg"])
        self.canvas.create_window((0, 0), window=self.check_body, anchor="nw")
        self.check_body.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))

        # Bottom actions
        bottom = tk.Frame(self, bg=controller.colors["bg"], padx=10, pady=10)
        bottom.pack(fill="x")

        tk.Button(bottom, text="Submit Verification", command=self.submit).pack(side="right")
        tk.Button(bottom, text="Clear", command=self.clear).pack(side="right", padx=(0, 8))

        # State
        self.question_vars = []  # list[(question_text, tk.StringVar)]
        self.loaded_for_gid = None

        # Auto-load initial checklist
        self.load_checklist()

    # -------------------------
    def reload(self):
        self.gages_store = load_json(GAGES_FILE, {"gages": []})
        self.q_store = load_json(GAGE_VERIFICATION_Q_FILE, {"by_type": {"Other": []}})

        self.gage_map = {g.get("gage_id"): g for g in self.gages_store.get("gages", [])}
        self.gage_ids = sorted([g.get("gage_id") for g in self.gages_store.get("gages", []) if g.get("gage_id")])

        self.sel_gage.configure(values=self.gage_ids)
        if self.gage_ids and (self.sel_gage.get() not in self.gage_ids):
            self.sel_gage.set(self.gage_ids[0])

        self.load_checklist()

    def clear(self):
        self.notes_var.set("")
        for _, v in self.question_vars:
            v.set("Pass")

    def load_checklist(self):
        gid = self.sel_gage.get().strip()
        if not gid:
            messagebox.showwarning("No gage", "No gage selected.")
            return
        g = self.gage_map.get(gid)
        if not g:
            messagebox.showwarning("Missing gage", f"Gage {gid} not found in gages.json.")
            return

        gtype = str(g.get("type", "Other") or "Other").strip()
        by_type = (self.q_store.get("by_type") or {})
        questions = by_type.get(gtype) or by_type.get("Other") or []

        # Clear previous
        for w in self.check_body.winfo_children():
            w.destroy()
        self.question_vars = []
        self.loaded_for_gid = gid

        # Header
        head = tk.Frame(self.check_body, bg=self.controller.colors["bg"])
        head.pack(fill="x", pady=(0, 8))

        tk.Label(
            head,
            text=f"{gid} — {g.get('name','')} ({gtype})",
            bg=self.controller.colors["bg"],
            fg=self.controller.colors["fg"],
            font=("Arial", 13, "bold")
        ).pack(anchor="w")

        tk.Label(
            head,
            text="Set each check to Pass / Fail / NA then Submit.",
            bg=self.controller.colors["bg"],
            fg=self.controller.colors["fg"]
        ).pack(anchor="w", pady=(2, 0))

        # Questions
        for q in questions:
            row = tk.Frame(self.check_body, bg=self.controller.colors["bg"], padx=6, pady=4)
            row.pack(fill="x")

            tk.Label(
                row,
                text="• " + str(q),
                bg=self.controller.colors["bg"],
                fg=self.controller.colors["fg"],
                wraplength=780,
                justify="left"
            ).pack(side="left", fill="x", expand=True)

            var = tk.StringVar(value="Pass")
            dd = ttk.Combobox(row, textvariable=var, values=["Pass", "Fail", "NA"], state="readonly", width=8)
            dd.pack(side="right", padx=(10, 0))
            self.question_vars.append((str(q), var))

        if not questions:
            tk.Label(
                self.check_body,
                text="No checklist questions found for this gage type. Add questions in gage_verification_questions.json.",
                bg=self.controller.colors["bg"],
                fg=self.controller.colors["fg"]
            ).pack(anchor="w", pady=10)

    # -------------------------
    def submit(self):
        gid = self.sel_gage.get().strip()
        if not gid:
            messagebox.showerror("Missing", "Select a gage first.")
            return

        g = self.gage_map.get(gid)
        if not g:
            messagebox.showerror("Missing", f"Gage {gid} not found.")
            return

        # Determine result and failed items
        failed = [q for q, v in self.question_vars if v.get() == "Fail"]
        result = "Fail" if failed else "Pass"

        # Identify verifier
        verifier = getattr(self.controller, "username", "") or getattr(self.controller, "user", "") or ""

        # Build record row
        now = datetime.now()
        verify_id = f"GV-{now.strftime('%Y%m%d-%H%M%S')}-{gid}"

        record = {
            "Verify_ID": verify_id,
            "Date": now.strftime("%Y-%m-%d"),
            "Time": now.strftime("%H:%M:%S"),
            "Gage_ID": gid,
            "Gage_Name": g.get("name", ""),
            "Gage_Type": g.get("type", ""),
            "Line": g.get("line", ""),
            "Result": result,
            "Failed_Items": ", ".join(failed),
            "Notes": self.notes_var.get().strip(),
            "Verified_By": verifier
        }

        path = gage_verification_log_path(now)

        try:
            df = pd.read_excel(path)
        except Exception:
            # If file missing or corrupted, create fresh
            df = pd.DataFrame(columns=list(record.keys()))

        # Ensure columns exist
        for col in record.keys():
            if col not in df.columns:
                df[col] = ""

        df = pd.concat([df, pd.DataFrame([record])], ignore_index=True)
        df.to_excel(path, index=False)

        messagebox.showinfo("Saved", f"Gage verification saved.\n\nResult: {result}")
        self.clear()
