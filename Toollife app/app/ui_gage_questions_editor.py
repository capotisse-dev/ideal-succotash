# app/ui_gage_questions_editor.py
import tkinter as tk
from tkinter import ttk, messagebox

from .ui_common import HeaderFrame
from .storage import load_json, save_json
from .config import GAGE_VERIFICATION_Q_FILE, GAGES_FILE


def _unique(seq):
    out = []
    seen = set()
    for x in seq:
        if x not in seen:
            out.append(x)
            seen.add(x)
    return out


class GageQuestionsEditorUI(tk.Frame):
    """
    Super/Admin editor for gage_verification_questions.json
    Structure:
      { "version": 1, "by_type": { "Caliper": [...], "Indicator": [...], ... } }
    """
    def __init__(self, parent, controller, show_header=True):
        super().__init__(parent, bg=controller.colors["bg"])
        self.controller = controller

        if show_header:
            HeaderFrame(self, controller).pack(fill="x")

        self.store = load_json(GAGE_VERIFICATION_Q_FILE, {"version": 1, "by_type": {"Other": []}})
        self._ensure_shape()

        # Try to discover types from gages.json too
        gages = load_json(GAGES_FILE, {"gages": []})
        discovered = [str(g.get("type", "")).strip() for g in gages.get("gages", []) if str(g.get("type", "")).strip()]
        self.type_list = _unique(list(self.store["by_type"].keys()) + discovered + ["Other"])
        self.type_list.sort()

        # Top row
        top = tk.Frame(self, bg=controller.colors["bg"], padx=10, pady=10)
        top.pack(fill="x")

        tk.Label(
            top,
            text="Gage Verification Questions (Super/Admin)",
            bg=controller.colors["bg"],
            fg=controller.colors["fg"],
            font=("Arial", 16, "bold")
        ).pack(side="left")

        tk.Button(top, text="Save", command=self.save).pack(side="right")
        tk.Button(top, text="Reload", command=self.reload).pack(side="right", padx=(0, 8))

        # Type selector
        sel = tk.Frame(self, bg=controller.colors["bg"], padx=10, pady=6)
        sel.pack(fill="x")

        tk.Label(sel, text="Gage Type:", bg=controller.colors["bg"], fg=controller.colors["fg"]).pack(side="left")
        self.sel_type = ttk.Combobox(sel, values=self.type_list, state="readonly", width=22)
        self.sel_type.pack(side="left", padx=8)
        self.sel_type.set(self.type_list[0] if self.type_list else "Other")
        self.sel_type.bind("<<ComboboxSelected>>", lambda e: self.load_type())

        tk.Button(sel, text="New Type", command=self.new_type).pack(side="left", padx=(12, 0))
        tk.Button(sel, text="Delete Type", command=self.delete_type).pack(side="left", padx=(8, 0))

        # Listbox + controls
        body = tk.Frame(self, bg=controller.colors["bg"], padx=10, pady=10)
        body.pack(fill="both", expand=True)

        left = tk.Frame(body, bg=controller.colors["bg"])
        left.pack(side="left", fill="both", expand=True)

        tk.Label(left, text="Questions (order matters):", bg=controller.colors["bg"], fg=controller.colors["fg"]).pack(anchor="w")

        self.listbox = tk.Listbox(left, height=18)
        self.listbox.pack(fill="both", expand=True, pady=(6, 0))

        right = tk.Frame(body, bg=controller.colors["bg"], padx=10)
        right.pack(side="right", fill="y")

        tk.Label(right, text="Add Question:", bg=controller.colors["bg"], fg=controller.colors["fg"]).pack(anchor="w")
        self.new_q_var = tk.StringVar(value="")
        tk.Entry(right, textvariable=self.new_q_var, width=34).pack(anchor="w", pady=(6, 10))

        tk.Button(right, text="Add", command=self.add_question).pack(fill="x")
        tk.Button(right, text="Delete Selected", command=self.delete_selected).pack(fill="x", pady=(8, 0))

        ttk.Separator(right, orient="horizontal").pack(fill="x", pady=12)

        tk.Button(right, text="Move Up", command=lambda: self.move(-1)).pack(fill="x")
        tk.Button(right, text="Move Down", command=lambda: self.move(1)).pack(fill="x", pady=(8, 0))

        ttk.Separator(right, orient="horizontal").pack(fill="x", pady=12)

        tk.Button(right, text="Load Defaults For Type", command=self.load_defaults).pack(fill="x")

        self.load_type()

    # -------------------------
    def _ensure_shape(self):
        if not isinstance(self.store, dict):
            self.store = {"version": 1, "by_type": {"Other": []}}
        self.store.setdefault("version", 1)
        self.store.setdefault("by_type", {"Other": []})
        if "Other" not in self.store["by_type"]:
            self.store["by_type"]["Other"] = []

    def reload(self):
        self.store = load_json(GAGE_VERIFICATION_Q_FILE, {"version": 1, "by_type": {"Other": []}})
        self._ensure_shape()
        messagebox.showinfo("Reloaded", "Reloaded from file.\n\n(If you added new types, reopen tab to refresh type list.)")
        self.load_type()

    def save(self):
        # Save current list back to store first
        self._sync_list_to_store()
        save_json(GAGE_VERIFICATION_Q_FILE, self.store)
        messagebox.showinfo("Saved", "Gage verification questions saved.")

    # -------------------------
    def current_type(self) -> str:
        return str(self.sel_type.get() or "Other").strip() or "Other"

    def _sync_list_to_store(self):
        t = self.current_type()
        self.store["by_type"].setdefault(t, [])
        items = [self.listbox.get(i) for i in range(self.listbox.size())]
        # strip empties
        items = [str(x).strip() for x in items if str(x).strip()]
        self.store["by_type"][t] = items

    def load_type(self):
        t = self.current_type()
        self._ensure_shape()
        self.listbox.delete(0, tk.END)
        for q in self.store["by_type"].get(t, []):
            self.listbox.insert(tk.END, q)

    # -------------------------
    def new_type(self):
        win = tk.Toplevel(self)
        win.title("New Gage Type")
        win.grab_set()

        var = tk.StringVar(value="")

        frm = tk.Frame(win, padx=12, pady=12)
        frm.pack(fill="both", expand=True)

        tk.Label(frm, text="Type name (example: 'Micrometer')").pack(anchor="w")
        tk.Entry(frm, textvariable=var, width=30).pack(anchor="w", pady=(6, 12))

        def create():
            name = var.get().strip()
            if not name:
                messagebox.showerror("Error", "Type name required.")
                return
            # Sync current type before switching
            self._sync_list_to_store()

            self.store["by_type"].setdefault(name, [])
            if name not in self.type_list:
                self.type_list.append(name)
                self.type_list = sorted(_unique(self.type_list))
                self.sel_type.configure(values=self.type_list)
            self.sel_type.set(name)
            self.load_type()
            win.destroy()

        tk.Button(frm, text="Cancel", command=win.destroy).pack(side="right")
        tk.Button(frm, text="Create", command=create).pack(side="right", padx=(0, 8))

    def delete_type(self):
        t = self.current_type()
        if t == "Other":
            messagebox.showwarning("Not allowed", "Cannot delete 'Other' type.")
            return
        if not messagebox.askyesno("Delete Type", f"Delete type '{t}' and its questions?"):
            return

        # Sync current list
        self._sync_list_to_store()

        self.store["by_type"].pop(t, None)
        if t in self.type_list:
            self.type_list.remove(t)
            if not self.type_list:
                self.type_list = ["Other"]
            self.sel_type.configure(values=self.type_list)
            self.sel_type.set(self.type_list[0])
        self.load_type()

    # -------------------------
    def add_question(self):
        q = self.new_q_var.get().strip()
        if not q:
            return
        self.listbox.insert(tk.END, q)
        self.new_q_var.set("")

    def delete_selected(self):
        sel = self.listbox.curselection()
        if not sel:
            return
        # delete from bottom up
        for idx in reversed(sel):
            self.listbox.delete(idx)

    def move(self, delta: int):
        sel = self.listbox.curselection()
        if len(sel) != 1:
            return
        i = sel[0]
        j = i + delta
        if j < 0 or j >= self.listbox.size():
            return
        txt = self.listbox.get(i)
        self.listbox.delete(i)
        self.listbox.insert(j, txt)
        self.listbox.selection_set(j)

    # -------------------------
    def load_defaults(self):
        """
        Injects reasonable defaults into the current type.
        """
        t = self.current_type()
        defaults = {
            "Caliper": [
                "Clean jaws and beam; no debris present",
                "Zero check passes at closed position",
                "Slide movement smooth; no binding",
                "No visible damage or bent jaws",
                "Calibration sticker present and in date"
            ],
            "Indicator": [
                "Tip and stem clean; no chips/debris",
                "Needle returns to zero consistently",
                "No excessive backlash observed",
                "Mounting method stable (no loose mag base)",
                "Calibration sticker present and in date"
            ],
            "Bore Gage": [
                "Contacts clean and undamaged",
                "Master/setting ring available and used",
                "Zero set against master is stable",
                "No excessive play in mechanism",
                "Calibration sticker present and in date"
            ],
            "Other": [
                "Tool/gage clean and undamaged",
                "Correct method per WI available",
                "Calibration status verified"
            ]
        }

        if t not in defaults:
            # generic defaults for unknown types
            defaults[t] = [
                "Tool/gage clean and undamaged",
                "Zero / master check performed",
                "Calibration status verified"
            ]

        if not messagebox.askyesno("Load Defaults", f"Replace questions for '{t}' with defaults?"):
            return

        self.listbox.delete(0, tk.END)
        for q in defaults[t]:
            self.listbox.insert(tk.END, q)
