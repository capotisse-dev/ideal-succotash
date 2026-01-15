import os
import shutil
import tkinter as tk
from tkinter import messagebox, simpledialog, filedialog
import pandas as pd

from .ui_common import HeaderFrame, FilePicker, DataTable
from .storage import get_df, save_df, safe_int, safe_float
from .db import (
    list_tools_simple,
    upsert_tool_inventory,
    get_tool,
    list_machines,
    upsert_machine,
    get_machine,
    list_machine_maintenance,
    add_machine_maintenance,
    list_machine_programs,
    add_machine_program,
    next_machine_program_revision,
)
from .config import MACHINES_DIR
from .audit import log_audit

class TopUI(tk.Frame):
    def __init__(self, parent, controller, show_header=True):
        super().__init__(parent, bg=controller.colors["bg"])
        self.controller = controller
        self.readonly = not controller.can_edit_screen("Top level")
        if show_header:
            HeaderFrame(self, controller).pack(fill="x")


        nb = tk.ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=10, pady=10)

        self.tab_data = tk.Frame(nb)
        self.tab_tools = tk.Frame(nb)
        self.tab_machines = tk.Frame(nb)

        nb.add(self.tab_data, text="Data (Override/Edit)")
        nb.add(self.tab_tools, text="Manage Tools ($/Stock)")
        nb.add(self.tab_machines, text="Machines")

        self._build_data_tab()
        self._build_tools_tab()
        self._build_machines_tab()

    # ---------- Data Tab ----------
    def _build_data_tab(self):
        ctrl = tk.Frame(self.tab_data)
        ctrl.pack(fill="x", pady=8)

        self.picker = FilePicker(ctrl, self.load_data)
        self.picker.pack(side="left")

        self.override_btn = tk.Button(ctrl, text="Override Edit Selected", command=self.override_edit)
        self.override_btn.pack(side="left", padx=10)

        cols = [
            "ID","Date","Time","Shift","Line","Machine","Part_Number","Tool_Num",
            "Reason","Downtime_Mins","Cost","Tool_Life","Defects_Present","Defect_Qty","Sort_Done",
            "Defect_Reason","Quality_Verified","Leader_Sign","Serial_Numbers"
        ]
        self.table = DataTable(self.tab_data, cols)
        self.table.pack(fill="both", expand=True, padx=10, pady=10)

        self.load_data(self.picker.get())
        if self.readonly:
            self.override_btn.configure(state="disabled")

    def load_data(self, filename):
        df, _ = get_df(filename)
        self._df = df
        self._filename = filename
        self.table.load(df)

    def override_edit(self):
        sel_id = self.table.selected_id()
        if not sel_id:
            messagebox.showwarning("Select", "Select a row first.")
            return

        df, filename = get_df(self._filename)
        idx = df.index[df["ID"].astype(str) == str(sel_id)]
        if len(idx) == 0:
            messagebox.showerror("Not found", "Row not found in file.")
            return
        i = idx[0]

        top = tk.Toplevel(self)
        top.title(f"Override Edit - ID {sel_id}")
        top.geometry("520x420")

        fields = [
            ("Downtime_Mins", "Downtime (min)"),
            ("Cost", "Cost ($)"),
            ("Serial_Numbers", "Serial Numbers (comma-separated)"),
            ("Reason", "Tool Change Reason"),
            ("Defect_Reason", "Defect Reason"),
        ]
        entries = {}
        for col, label in fields:
            tk.Label(top, text=label).pack(anchor="w", padx=10, pady=(10, 0))
            e = tk.Entry(top)
            e.insert(0, str(df.at[i, col] if pd.notna(df.at[i, col]) else ""))
            e.pack(fill="x", padx=10)
            entries[col] = e

        def save():
            df.at[i, "Downtime_Mins"] = safe_int(entries["Downtime_Mins"].get(), 0)
            df.at[i, "Cost"] = safe_float(entries["Cost"].get(), 0.0)
            df.at[i, "Serial_Numbers"] = entries["Serial_Numbers"].get().strip()
            df.at[i, "Reason"] = entries["Reason"].get().strip()
            df.at[i, "Defect_Reason"] = entries["Defect_Reason"].get().strip()

            save_df(df, filename)
            top.destroy()
            self.load_data(filename)
            log_audit(self.controller.user, f"Override edit entry {sel_id}")

        tk.Button(top, text="Save Override", command=save, bg="#ff9800", fg="white").pack(pady=18)

    # ---------- Tools Tab ----------
    def _build_tools_tab(self):
        f = tk.Frame(self.tab_tools, padx=20, pady=20)
        f.pack(fill="both", expand=True)

        tk.Label(f, text="Tool Inventory & Cost Configuration", font=("Arial", 14, "bold")).pack(pady=10)

        self.tool_list = tk.Listbox(f, height=15)
        self.tool_list.pack(fill="x", pady=10)
        self.tool_list.bind("<<ListboxSelect>>", self.load_tool_details)

        editor = tk.Frame(f)
        editor.pack(pady=10)

        tk.Label(editor, text="Tool Name:").grid(row=0, column=0)
        self.t_name = tk.Entry(editor, state="readonly")
        self.t_name.grid(row=0, column=1)

        tk.Label(editor, text="Cost ($):").grid(row=1, column=0)
        self.t_cost = tk.Entry(editor)
        self.t_cost.grid(row=1, column=1)

        tk.Label(editor, text="Stock Qty:").grid(row=2, column=0)
        self.t_stock = tk.Entry(editor)
        self.t_stock.grid(row=2, column=1)

        tk.Label(editor, text="Inserts per Tool:").grid(row=3, column=0)
        self.t_inserts = tk.Entry(editor)
        self.t_inserts.grid(row=3, column=1)

        self.save_tool_btn = tk.Button(editor, text="Save Changes", command=self.save_tool_details, bg="green", fg="white")
        self.save_tool_btn.grid(row=4, column=0, columnspan=2, pady=10)

        self.add_tool_btn = tk.Button(f, text="Add New Tool", command=self.add_new_tool)
        self.add_tool_btn.pack()

        self.refresh_tool_list()

    def refresh_tool_list(self):
        self.tool_list.delete(0, "end")
        self._tools = list_tools_simple()
        for tool in self._tools:
            t = tool.get("tool_num", "")
            self.tool_list.insert(
                "end",
                f"{t} | Stock: {tool.get('stock_qty', 0)} | ${tool.get('unit_cost', 0)}"
            )

    def load_tool_details(self, event=None):
        sel = self.tool_list.curselection()
        if not sel:
            return
        txt = self.tool_list.get(sel[0])
        tool_name = txt.split(" |")[0]
        d = get_tool(tool_name) or {}

        self.t_name.config(state="normal")
        self.t_name.delete(0, "end")
        self.t_name.insert(0, tool_name)
        self.t_name.config(state="readonly")

        self.t_cost.delete(0, "end"); self.t_cost.insert(0, d.get("unit_cost", 0))
        self.t_stock.delete(0, "end"); self.t_stock.insert(0, d.get("stock_qty", 0))
        self.t_inserts.delete(0, "end"); self.t_inserts.insert(0, d.get("inserts_per_tool", 1))

    def save_tool_details(self):
        name = self.t_name.get()
        if not name:
            return
        upsert_tool_inventory(
            tool_num=name,
            name="",
            unit_cost=safe_float(self.t_cost.get(), 0.0),
            stock_qty=safe_int(self.t_stock.get(), 0),
            inserts_per_tool=safe_int(self.t_inserts.get(), 1),
        )
        messagebox.showinfo("Saved", f"Updated {name}")
        log_audit(self.controller.user, f"Updated tool {name} inventory")
        self.refresh_tool_list()
        if self.readonly:
            self.save_tool_btn.configure(state="disabled")
            self.add_tool_btn.configure(state="disabled")

    def add_new_tool(self):
        name = simpledialog.askstring("New Tool", "Enter Tool Name (e.g., Tool 55):")
        if name:
            upsert_tool_inventory(
                tool_num=name,
                name="",
                unit_cost=0.0,
                stock_qty=0,
                inserts_per_tool=1,
            )
            self.refresh_tool_list()

    # ---------- Machines Tab ----------
    def _build_machines_tab(self):
        f = tk.Frame(self.tab_machines, padx=20, pady=20)
        f.pack(fill="both", expand=True)

        tk.Label(f, text="Machine Information", font=("Arial", 14, "bold")).pack(anchor="w")

        self.machine_list = tk.Listbox(f, height=14)
        self.machine_list.pack(fill="x", pady=10)
        self.machine_list.bind("<<ListboxSelect>>", self.load_machine_details)

        btns = tk.Frame(f)
        btns.pack(fill="x")
        tk.Button(btns, text="Add Machine", command=self.add_machine).pack(side="left")
        tk.Button(btns, text="Edit Machine", command=self.edit_machine).pack(side="left", padx=8)

        self.refresh_machine_list()

    def refresh_machine_list(self):
        self.machine_list.delete(0, "end")
        self._machines = list_machines()
        for m in self._machines:
            self.machine_list.insert("end", f"{m.get('machine_number', '')} | Line {m.get('line', '')}")

    def _selected_machine_number(self):
        sel = self.machine_list.curselection()
        if not sel:
            return ""
        txt = self.machine_list.get(sel[0])
        return txt.split(" |")[0].strip()

    def load_machine_details(self, event=None):
        pass

    def add_machine(self):
        self._open_machine_editor("")

    def edit_machine(self):
        machine_number = self._selected_machine_number()
        if not machine_number:
            messagebox.showwarning("Select", "Select a machine first.")
            return
        self._open_machine_editor(machine_number)

    def _open_machine_editor(self, machine_number: str):
        top = tk.Toplevel(self)
        top.title("Machine Editor")
        top.geometry("760x620")

        info = get_machine(machine_number) or {}

        nb = tk.ttk.Notebook(top)
        nb.pack(fill="both", expand=True, padx=10, pady=10)

        tab_info = tk.Frame(nb)
        tab_maint = tk.Frame(nb)
        tab_prog = tk.Frame(nb)
        nb.add(tab_info, text="Info")
        nb.add(tab_maint, text="Maintenance")
        nb.add(tab_prog, text="Programs")

        form = tk.Frame(tab_info, padx=12, pady=12)
        form.pack(fill="both", expand=True)

        fields = [
            ("Machine #", "machine_number"),
            ("Line", "line"),
            ("Serial #", "serial_number"),
            ("Age", "age"),
            ("Spindle Connection", "spindle_connection"),
            ("Coolant Type", "coolant_type"),
        ]
        vars_map = {}
        for row, (label, key) in enumerate(fields):
            tk.Label(form, text=label).grid(row=row, column=0, sticky="w", pady=6)
            var = tk.StringVar(value=str(info.get(key, "")))
            entry = tk.Entry(form, textvariable=var, width=30)
            entry.grid(row=row, column=1, sticky="w")
            if key == "machine_number" and machine_number:
                entry.configure(state="readonly")
            vars_map[key] = var

        def save_info():
            mnum = vars_map["machine_number"].get().strip()
            if not mnum:
                messagebox.showerror("Error", "Machine # is required.")
                return
            upsert_machine(
                mnum,
                line=vars_map["line"].get().strip(),
                serial_number=vars_map["serial_number"].get().strip(),
                age=vars_map["age"].get().strip(),
                spindle_connection=vars_map["spindle_connection"].get().strip(),
                coolant_type=vars_map["coolant_type"].get().strip(),
            )
            log_audit(self.controller.user, f"Updated machine {mnum}")
            self.refresh_machine_list()

        tk.Button(form, text="Save", command=save_info, bg="#28a745", fg="white").grid(row=len(fields), column=1, sticky="e", pady=10)

        maint_frame = tk.Frame(tab_maint, padx=12, pady=12)
        maint_frame.pack(fill="both", expand=True)

        maint_cols = ("issue", "solution", "downtime_mins", "created_at")
        maint_tree = tk.ttk.Treeview(maint_frame, columns=maint_cols, show="headings", height=12)
        for c in maint_cols:
            maint_tree.heading(c, text=c.upper())
            maint_tree.column(c, width=160)
        maint_tree.pack(fill="both", expand=True)

        def refresh_maintenance():
            for i in maint_tree.get_children():
                maint_tree.delete(i)
            mrow = get_machine(vars_map["machine_number"].get().strip())
            if not mrow:
                return
            for row in list_machine_maintenance(mrow["id"]):
                maint_tree.insert("", "end", values=(
                    row.get("issue", ""),
                    row.get("solution", ""),
                    row.get("downtime_mins", 0.0),
                    row.get("created_at", ""),
                ))

        def add_maintenance():
            mrow = get_machine(vars_map["machine_number"].get().strip())
            if not mrow:
                messagebox.showerror("Error", "Save machine info first.")
                return
            issue = simpledialog.askstring("Maintenance Issue", "Issue:")
            if issue is None:
                return
            solution = simpledialog.askstring("Maintenance Solution", "Solution:") or ""
            downtime = simpledialog.askstring("Downtime (mins)", "Downtime (mins):") or "0"
            add_machine_maintenance(
                mrow["id"],
                issue=issue,
                solution=solution,
                downtime_mins=safe_float(downtime, 0.0),
            )
            refresh_maintenance()

        tk.Button(maint_frame, text="Add Maintenance Event", command=add_maintenance).pack(pady=8, anchor="e")
        refresh_maintenance()

        prog_frame = tk.Frame(tab_prog, padx=12, pady=12)
        prog_frame.pack(fill="both", expand=True)

        prog_cols = ("program_name", "revision", "created_at")
        prog_tree = tk.ttk.Treeview(prog_frame, columns=prog_cols, show="headings", height=12)
        for c in prog_cols:
            prog_tree.heading(c, text=c.upper())
            prog_tree.column(c, width=160)
        prog_tree.pack(fill="both", expand=True)

        def refresh_programs():
            for i in prog_tree.get_children():
                prog_tree.delete(i)
            mrow = get_machine(vars_map["machine_number"].get().strip())
            if not mrow:
                return
            for row in list_machine_programs(mrow["id"]):
                prog_tree.insert("", "end", values=(
                    row.get("program_name", ""),
                    row.get("revision", 1),
                    row.get("created_at", ""),
                ))

        def add_program():
            mrow = get_machine(vars_map["machine_number"].get().strip())
            if not mrow:
                messagebox.showerror("Error", "Save machine info first.")
                return
            program_name = simpledialog.askstring("Program Name", "Program name:")
            if not program_name:
                return
            file_paths = filedialog.askopenfilenames(
                title="Select program files",
                filetypes=[
                    ("Program Files", "*.txt *.csv *.svg *.nd"),
                ],
            )
            if not file_paths:
                return
            revision = next_machine_program_revision(mrow["id"], program_name)
            add_machine_program(mrow["id"], program_name, revision)

            dest_dir = os.path.join(
                MACHINES_DIR,
                vars_map["machine_number"].get().strip(),
                "programs",
                program_name,
                f"rev{revision}",
            )
            os.makedirs(dest_dir, exist_ok=True)
            for path in file_paths:
                shutil.copy2(path, os.path.join(dest_dir, os.path.basename(path)))

            refresh_programs()

        tk.Button(prog_frame, text="Add Program Revision", command=add_program).pack(pady=8, anchor="e")
        refresh_programs()
