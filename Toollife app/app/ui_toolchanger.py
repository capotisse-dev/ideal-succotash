import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime

from .ui_common import HeaderFrame
from .ui_action_center import ActionCenterUI
from .ui_audit import AuditTrailUI
from .screen_registry import get_screen_class
from .storage import next_id, safe_int, safe_float, load_json, parts_for_line
from .config import REASONS_FILE
from .db import get_tool, update_tool_stock, upsert_tool_entry
from .audit import log_audit

class ToolChangerUI(tk.Frame):
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
        nb.add(tab_main, text="Tool Changer")
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

        body = tk.Frame(tab_main, bg=controller.colors["bg"], padx=20, pady=20)
        body.pack(fill="both", expand=True)

        style = {"bg": controller.colors["bg"], "fg": controller.colors["fg"]}

        tk.Label(body, text="Tool Changer Entry", font=("Arial", 16, "bold"), **style).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 15))

        # Line
        tk.Label(body, text="Line:", **style).grid(row=1, column=0, sticky="e", pady=5)
        self.line_cb = ttk.Combobox(body, values=["U725", "JL"], state="readonly", width=20)
        self.line_cb.current(0)
        self.line_cb.grid(row=1, column=1, sticky="w")
        self.line_cb.bind("<<ComboboxSelected>>", self.update_machines)

        # Shift
        tk.Label(body, text="Shift:", **style).grid(row=2, column=0, sticky="e", pady=5)
        self.shift_cb = ttk.Combobox(body, values=["1st", "2nd", "3rd"], state="readonly", width=20)
        self.shift_cb.current(0)
        self.shift_cb.grid(row=2, column=1, sticky="w")

        # Machine
        tk.Label(body, text="Machine:", **style).grid(row=3, column=0, sticky="e", pady=5)
        self.mach_cb = ttk.Combobox(body, state="readonly", width=20)
        self.mach_cb.grid(row=3, column=1, sticky="w")
        self.mach_cb.bind("<<ComboboxSelected>>", self.update_tools)

        # Part
        tk.Label(body, text="Part #:", **style).grid(row=4, column=0, sticky="e", pady=5)
        self.part_cb = ttk.Combobox(body, values=[], width=20)  # allow typing
        self.part_cb.grid(row=4, column=1, sticky="w")

        # Tool
        tk.Label(body, text="Tool #:", **style).grid(row=5, column=0, sticky="e", pady=5)
        self.tool_cb = ttk.Combobox(body, state="readonly", width=20)
        self.tool_cb.grid(row=5, column=1, sticky="w")
        self.tool_cb.bind("<<ComboboxSelected>>", self.update_stock_display)

        self.stock_lbl = tk.Label(body, text="Stock: N/A", fg="blue", bg=controller.colors["bg"], font=("Arial", 10, "bold"))
        self.stock_lbl.grid(row=5, column=2, sticky="w", padx=10)

        # Reason
        tk.Label(body, text="Reason:", **style).grid(row=6, column=0, sticky="e", pady=5)
        reasons = load_json(REASONS_FILE, [])
        self.reason_cb = ttk.Combobox(body, values=reasons, state="readonly", width=28)
        self.reason_cb.grid(row=6, column=1, sticky="w")

        # Tool life
        tk.Label(body, text="Tool Life:", **style).grid(row=7, column=0, sticky="e", pady=5)
        self.life_entry = tk.Entry(body, width=10)
        self.life_entry.insert(0, "0")
        self.life_entry.grid(row=7, column=1, sticky="w")

        # Downtime
        tk.Label(body, text="Downtime (min):", **style).grid(row=8, column=0, sticky="e", pady=5)
        self.down_entry = tk.Entry(body, width=10)
        self.down_entry.insert(0, "0")
        self.down_entry.grid(row=8, column=1, sticky="w")

        # Defects?
        self.defect_var = tk.BooleanVar(value=False)
        tk.Checkbutton(
            body, text="Were defects produced?", variable=self.defect_var, command=self.toggle_defect,
            bg=controller.colors["bg"], fg=controller.colors["fg"], font=("Arial", 12)
        ).grid(row=9, column=0, columnspan=2, sticky="w", pady=(10, 0))

        self.defect_frame = tk.Frame(body, borderwidth=1, relief="solid", padx=10, pady=10, bg=controller.colors["bg"])
        tk.Label(self.defect_frame, text="Defect Qty:", **style).pack(anchor="w")
        self.qty_entry = tk.Entry(self.defect_frame)
        self.qty_entry.insert(0, "0")
        self.qty_entry.pack(fill="x", pady=5)

        self.sort_var = tk.BooleanVar(value=False)
        tk.Checkbutton(self.defect_frame, text="Was sort done?", variable=self.sort_var,
                       bg=controller.colors["bg"], fg=controller.colors["fg"]).pack(anchor="w")

        tk.Label(self.defect_frame, text="Defect Reason:", **style).pack(anchor="w", pady=(10, 0))
        self.defect_reason = tk.Entry(self.defect_frame)
        self.defect_reason.pack(fill="x", pady=5)

        # Submit
        tk.Button(
            body, text="SUBMIT ENTRY", command=self.submit,
            bg="#28a745", fg="white", font=("Arial", 14, "bold"), height=2
        ).grid(row=11, column=0, columnspan=3, pady=20, sticky="we")

        self.update_machines()

    def update_machines(self, event=None):
        line = self.line_cb.get()
        if line == "U725":
            machs = [f"Machine {i}" for i in range(1, 10)]
        else:
            machs = [f"Machine {i}" for i in range(1, 9)] + ["FF1", "FF2", "FF3"]
        self.mach_cb["values"] = machs
        self.mach_cb.set("")
        self.tool_cb.set("")
        self.stock_lbl.config(text="Stock: N/A")
        self.update_parts()

    def update_parts(self):
        parts = parts_for_line(self.line_cb.get())
        self.part_cb["values"] = parts

    def update_tools(self, event=None):
        line = self.line_cb.get()
        machine = self.mach_cb.get()
        if not machine:
            return

        tools = []
        if line == "U725":
            tools = [str(i) for i in range(1, 24)] + ["60"]
        elif line == "JL":
            if machine.startswith("Machine"):
                num = int(machine.split(" ")[1])
                if 1 <= num <= 4:
                    tools = ["2", "4", "5", "9", "10", "11", "15", "16", "25", "26", "40"]
                elif 5 <= num <= 8:
                    tools = ["2", "5", "6", "10", "11", "16", "21", "23", "25", "26", "27", "40"]
            elif machine.startswith("FF"):
                tools = [str(i) for i in range(201, 216)] + ["60"]

        try:
            tools.sort(key=int)
        except Exception:
            tools.sort()

        self.tool_cb["values"] = tools

    def update_stock_display(self, event=None):
        tool = self.tool_cb.get()
        if not tool:
            self.stock_lbl.config(text="Stock: N/A")
            return
        info = get_tool(tool)
        if info:
            self.stock_lbl.config(text=f"Stock: {info.get('stock_qty', 'N/A')}")
        else:
            self.stock_lbl.config(text="Stock: N/A")

    def toggle_defect(self):
        if self.defect_var.get():
            self.defect_frame.grid(row=10, column=0, columnspan=2, sticky="we", pady=10)
        else:
            self.defect_frame.grid_remove()

    def submit(self):
        if not self.mach_cb.get() or not self.tool_cb.get() or not self.reason_cb.get():
            messagebox.showwarning("Missing Info", "Select Machine, Tool, and Reason")
            return
        if not self.life_entry.get().strip():
            messagebox.showwarning("Missing Info", "Enter tool life for this change.")
            return

        downtime = safe_int(self.down_entry.get(), 0)
        tool_life = safe_float(self.life_entry.get(), 0.0)

        tool_num = self.tool_cb.get()
        cost = 0.0

        # Inventory decrement (if configured)
        info = get_tool(tool_num)
        if info:
            cost = safe_float(info.get("unit_cost", 0), 0.0)
            stock = safe_int(info.get("stock_qty", 0), 0)
            if stock <= 0:
                if not messagebox.askyesno("Stock Warning", f"Tool {tool_num} is out of stock! Submit anyway?"):
                    return
            else:
                update_tool_stock(tool_num, stock - 1)

        now = datetime.now()

        defects = "Yes" if self.defect_var.get() else "No"
        defect_qty = safe_int(self.qty_entry.get(), 0)
        sort = "Yes" if self.sort_var.get() else "No"
        defect_reason = self.defect_reason.get().strip() if self.defect_var.get() else ""

        new_row = {
            "ID": next_id(),
            "Date": now.strftime("%Y-%m-%d"),
            "Time": now.strftime("%H:%M:%S"),
            "Shift": self.shift_cb.get(),
            "Line": self.line_cb.get(),
            "Machine": self.mach_cb.get(),
            "Part_Number": self.part_cb.get(),
            "Tool_Num": str(self.tool_cb.get()),
            "Reason": self.reason_cb.get(),
            "Downtime_Mins": downtime,
            "Cost": float(cost),
            "Tool_Life": float(tool_life),
            "Tool_Changer": self.controller.user,
            "Defects_Present": defects,
            "Defect_Qty": defect_qty,
            "Sort_Done": sort,
            "Defect_Reason": defect_reason,
            "Quality_Verified": "Pending",
            "Quality_User": "",
            "Quality_Time": "",
            "Leader_Sign": "Pending",
            "Leader_User": "",
            "Leader_Time": "",
            "Serial_Numbers": ""
        }

        upsert_tool_entry(new_row)
        log_audit(self.controller.user, f"Tool change entry {new_row['ID']} saved")

        messagebox.showinfo("Saved", f"Entry saved.\nTool cost: ${cost:,.2f}")

        # reset defect UI
        self.defect_var.set(False)
        self.toggle_defect()
        self.qty_entry.delete(0, "end"); self.qty_entry.insert(0, "0")
        self.sort_var.set(False)
        self.defect_reason.delete(0, "end")
        self.life_entry.delete(0, "end"); self.life_entry.insert(0, "0")
        self.update_stock_display()
