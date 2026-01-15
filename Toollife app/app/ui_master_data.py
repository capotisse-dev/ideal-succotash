# app/ui_master_data.py
from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox

from .storage import safe_float, safe_int
from .db import (
    list_tools_simple,
    upsert_tool_inventory,
    deactivate_tool,
    list_tools_for_line,
    list_lines,
    get_tool_lines,
    set_tool_lines,
    list_tool_inserts,
    replace_tool_inserts,
    get_tool_parts,
    set_tool_parts,
    list_parts_with_lines,
    upsert_part,
    deactivate_part,
    set_scrap_cost,
    get_scrap_costs_simple,
    list_downtime_codes,
    upsert_downtime_code,
    deactivate_downtime_code,
)
from .audit import log_audit



class MasterDataUI(tk.Frame):
    """
    Super/Admin Master Data:
      - Tool pricing
      - Parts + line assignments
      - Scrap pricing by part
    Robust against legacy JSON shapes.
    """

    def __init__(self, parent, controller, show_header=True):
        super().__init__(parent, bg=controller.colors["bg"])
        self.controller = controller
        self.readonly = not controller.can_edit_screen("Master Data")

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=10, pady=10)

        tab_tools = tk.Frame(nb, bg=controller.colors["bg"])
        tab_parts = tk.Frame(nb, bg=controller.colors["bg"])
        tab_scrap = tk.Frame(nb, bg=controller.colors["bg"])
        tab_downtime = tk.Frame(nb, bg=controller.colors["bg"])

        nb.add(tab_tools, text="Tool Pricing")
        nb.add(tab_parts, text="Parts & Lines")
        nb.add(tab_scrap, text="Scrap Pricing")
        nb.add(tab_downtime, text="Downtime Codes")

        self._build_tool_pricing(tab_tools)
        self._build_parts(tab_parts)
        self._build_scrap(tab_scrap)
        self._build_downtime(tab_downtime)

    # -------------------- TOOL PRICING --------------------
    def _build_tool_pricing(self, parent):
        top = tk.Frame(parent, bg=self.controller.colors["bg"], padx=10, pady=10)
        top.pack(fill="x")

        tk.Label(
            top,
            text="Tool Pricing",
            bg=self.controller.colors["bg"],
            fg=self.controller.colors["fg"],
            font=("Arial", 14, "bold"),
        ).pack(side="left")

        tk.Button(top, text="Refresh", command=self.refresh_tools).pack(side="right")
        self.tool_add_btn = tk.Button(top, text="Add Tool", command=lambda: self._open_tool_editor())
        self.tool_add_btn.pack(side="right", padx=8)

        filter_frame = tk.Frame(parent, bg=self.controller.colors["bg"], padx=10, pady=6)
        filter_frame.pack(fill="x")

        tk.Label(filter_frame, text="Line Filter:", bg=self.controller.colors["bg"], fg=self.controller.colors["fg"]).pack(side="left")
        self.tool_line_filter = tk.StringVar(value="All")
        line_options = ["All"] + (list_lines() or [])
        self.tool_line_combo = ttk.Combobox(
            filter_frame,
            values=line_options,
            textvariable=self.tool_line_filter,
            state="readonly",
            width=18,
        )
        self.tool_line_combo.pack(side="left", padx=8)
        self.tool_line_combo.bind("<<ComboboxSelected>>", lambda e: self.refresh_tools())

        self.tool_del_btn = tk.Button(filter_frame, text="Deactivate Selected", command=self.delete_selected_tool)
        self.tool_del_btn.pack(side="right")

        cols = ("tool", "name", "unit_cost", "stock_qty", "lines", "parts")
        self.tool_tree = ttk.Treeview(parent, columns=cols, show="headings", height=14)
        for c in cols:
            self.tool_tree.heading(c, text=c.upper())
            if c == "unit_cost":
                self.tool_tree.column(c, width=140)
            elif c == "stock_qty":
                self.tool_tree.column(c, width=140)
            elif c in ("lines", "parts"):
                self.tool_tree.column(c, width=220)
            else:
                self.tool_tree.column(c, width=220)
        self.tool_tree.pack(fill="both", expand=True, padx=10, pady=10)
        self.tool_tree.bind("<Double-1>", lambda e: self._open_tool_editor(self._selected_tool()))

        self.refresh_tools()
        self._apply_readonly_tool()

    def _apply_readonly_tool(self):
        if not self.readonly:
            return
        self.tool_add_btn.configure(state="disabled")
        self.tool_del_btn.configure(state="disabled")

    def refresh_tools(self):
        for i in self.tool_tree.get_children():
            self.tool_tree.delete(i)

        line_filter = self.tool_line_filter.get() if hasattr(self, "tool_line_filter") else "All"
        tool_rows = list_tools_simple()
        if line_filter and line_filter != "All":
            allowed = set(list_tools_for_line(line_filter, include_unassigned=False))
            tool_rows = [t for t in tool_rows if t.get("tool_num") in allowed]

        for tool in tool_rows:
            tool_num = tool.get("tool_num", "")
            self.tool_tree.insert("", "end", values=(
                tool_num,
                tool.get("name", ""),
                tool.get("unit_cost", 0.0),
                tool.get("stock_qty", 0),
                ", ".join(get_tool_lines(tool_num)),
                ", ".join(get_tool_parts(tool_num)),
            ))

    def _selected_tool(self):
        sel = self.tool_tree.selection()
        if not sel:
            return ""
        return self.tool_tree.item(sel[0], "values")[0]

    def _open_tool_editor(self, tool_num: str = ""):
        if self.readonly:
            return
        top = tk.Toplevel(self)
        top.title("Tool Editor")
        top.geometry("740x640")

        is_new = not tool_num
        tool_data = {}
        if tool_num:
            for t in list_tools_simple():
                if t.get("tool_num") == tool_num:
                    tool_data = t
                    break

        form = tk.Frame(top, padx=12, pady=12)
        form.pack(fill="both", expand=True)

        tk.Label(form, text="Tool #").grid(row=0, column=0, sticky="w")
        tool_num_var = tk.StringVar(value=tool_num)
        tool_num_entry = tk.Entry(form, textvariable=tool_num_var, width=18)
        tool_num_entry.grid(row=0, column=1, sticky="w")
        if not is_new:
            tool_num_entry.configure(state="readonly")

        tk.Label(form, text="Name").grid(row=0, column=2, sticky="w", padx=(12, 0))
        tool_name_var = tk.StringVar(value=tool_data.get("name", ""))
        tk.Entry(form, textvariable=tool_name_var, width=30).grid(row=0, column=3, sticky="w")

        tk.Label(form, text="Unit Cost ($)").grid(row=1, column=0, sticky="w", pady=(8, 0))
        tool_cost_var = tk.StringVar(value=str(tool_data.get("unit_cost", 0.0)))
        tk.Entry(form, textvariable=tool_cost_var, width=12).grid(row=1, column=1, sticky="w", pady=(8, 0))

        tk.Label(form, text="Stock Qty").grid(row=1, column=2, sticky="w", padx=(12, 0), pady=(8, 0))
        tool_stock_var = tk.StringVar(value=str(tool_data.get("stock_qty", 0)))
        tk.Entry(form, textvariable=tool_stock_var, width=12).grid(row=1, column=3, sticky="w", pady=(8, 0))

        line_frame = tk.LabelFrame(form, text="Lines", padx=8, pady=8)
        line_frame.grid(row=2, column=0, columnspan=4, sticky="we", pady=10)
        line_opts = list_lines() or ["U725", "JL"]
        selected_lines = set(get_tool_lines(tool_num)) if tool_num else set()
        line_vars = {}
        for idx, line in enumerate(line_opts):
            var = tk.BooleanVar(value=line in selected_lines)
            line_vars[line] = var
            tk.Checkbutton(line_frame, text=line, variable=var).grid(row=0, column=idx, sticky="w", padx=6)

        parts_frame = tk.LabelFrame(form, text="Parts", padx=8, pady=8)
        parts_frame.grid(row=3, column=0, columnspan=4, sticky="we", pady=10)
        part_options = [p.get("part_number", "") for p in list_parts_with_lines()]
        selected_parts = set(get_tool_parts(tool_num)) if tool_num else set()
        part_vars = {}
        for idx, pn in enumerate(part_options):
            var = tk.BooleanVar(value=pn in selected_parts)
            part_vars[pn] = var
            tk.Checkbutton(parts_frame, text=pn, variable=var).grid(row=idx // 4, column=idx % 4, sticky="w", padx=6)

        inserts_frame = tk.LabelFrame(form, text="Insert Types", padx=8, pady=8)
        inserts_frame.grid(row=4, column=0, columnspan=4, sticky="we", pady=10)

        inserts_nb = ttk.Notebook(inserts_frame)
        inserts_nb.pack(fill="both", expand=True)

        insert_tabs = []
        for ins in list_tool_inserts(tool_num):
            insert_tabs.append(self._populate_insert_tab(inserts_nb, ins))
        if not insert_tabs:
            insert_tabs.append(self._populate_insert_tab(inserts_nb, {}))

        def add_insert_tab():
            insert_tabs.append(self._populate_insert_tab(inserts_nb, {}))

        tk.Button(inserts_frame, text="Add Insert Type", command=add_insert_tab).pack(pady=6)

        calc_lbl = tk.Label(form, text="Calculated change cost: $0.00")
        calc_lbl.grid(row=5, column=0, columnspan=4, sticky="w", pady=(8, 0))

        def recalc_cost():
            cost = self._calculate_insert_cost(self._collect_insert_data(insert_tabs))
            calc_lbl.config(text=f"Calculated change cost: ${cost:,.4f}")

        tk.Button(form, text="Recalculate Cost", command=recalc_cost).grid(row=6, column=0, pady=8, sticky="w")

        def save():
            tnum = tool_num_var.get().strip()
            if not tnum:
                messagebox.showerror("Error", "Tool # is required.")
                return
            upsert_tool_inventory(
                tool_num=tnum,
                name=tool_name_var.get().strip(),
                unit_cost=safe_float(tool_cost_var.get(), 0.0),
                stock_qty=safe_int(tool_stock_var.get(), 0),
                inserts_per_tool=1,
            )
            set_tool_lines(tnum, [ln for ln, var in line_vars.items() if var.get()])
            set_tool_parts(tnum, [pn for pn, var in part_vars.items() if var.get()])
            replace_tool_inserts(tnum, self._collect_insert_data(insert_tabs))
            log_audit(self.controller.user, f"Updated tool {tnum} configuration")
            self.refresh_tools()
            top.destroy()

        tk.Button(form, text="Save Tool", command=save, bg="#28a745", fg="white").grid(row=6, column=3, pady=8, sticky="e")
        recalc_cost()

    def delete_selected_tool(self):
        sel = self.tool_tree.selection()
        if not sel:
            return
        tool = self.tool_tree.item(sel[0], "values")[0]
        if not tool:
            return
        if not messagebox.askyesno("Confirm", f"Delete tool '{tool}'?"):
            return
        deactivate_tool(tool)
        log_audit(self.controller.user, f"Deactivated tool {tool}")
        self.refresh_tools()

    def save_tools(self):
        messagebox.showinfo("Saved", "Tool pricing saved.")

    def _populate_insert_tab(self, notebook: ttk.Notebook, data: dict):
        frame = tk.Frame(notebook)
        notebook.add(frame, text=data.get("insert_name") or "Insert")

        fields = {}
        labels = [
            ("Insert Name", "insert_name"),
            ("# Inserts", "insert_count"),
            ("Price/Insert", "price_per_insert"),
            ("Sides/Insert", "sides_per_insert"),
            ("Tool Life", "tool_life"),
        ]
        for row, (label, key) in enumerate(labels):
            tk.Label(frame, text=label).grid(row=row, column=0, sticky="w", pady=4, padx=6)
            var = tk.StringVar(value=str(data.get(key, "")))
            entry = tk.Entry(frame, textvariable=var, width=18)
            entry.grid(row=row, column=1, sticky="w", pady=4)
            fields[key] = var
        return {"frame": frame, "fields": fields, "notebook": notebook}

    def _collect_insert_data(self, insert_tabs):
        data = []
        for tab in insert_tabs:
            fields = tab["fields"]
            name = fields["insert_name"].get().strip()
            data.append({
                "insert_name": name,
                "insert_count": safe_int(fields["insert_count"].get(), 0),
                "price_per_insert": safe_float(fields["price_per_insert"].get(), 0.0),
                "sides_per_insert": safe_int(fields["sides_per_insert"].get(), 1),
                "tool_life": safe_float(fields["tool_life"].get(), 0.0),
            })
            if name:
                tab["notebook"].tab(tab["frame"], text=name)
        return data

    def _calculate_insert_cost(self, inserts):
        total = 0.0
        for ins in inserts:
            count = safe_float(ins.get("insert_count", 0), 0.0)
            price = safe_float(ins.get("price_per_insert", 0), 0.0)
            life = safe_float(ins.get("tool_life", 0), 0.0)
            sides = safe_float(ins.get("sides_per_insert", 1), 1.0)
            if life <= 0 or sides <= 0:
                continue
            total += ((count * price) / life) / sides
        return total

    # -------------------- PARTS & LINES --------------------
    def _build_parts(self, parent):
        top = tk.Frame(parent, bg=self.controller.colors["bg"], padx=10, pady=10)
        top.pack(fill="x")

        tk.Label(
            top,
            text="Parts & Line Assignment",
            bg=self.controller.colors["bg"],
            fg=self.controller.colors["fg"],
            font=("Arial", 14, "bold"),
        ).pack(side="left")

        tk.Button(top, text="Refresh", command=self.refresh_parts).pack(side="right")
        self.part_add_btn = tk.Button(top, text="Add Part", command=lambda: self._open_part_editor())
        self.part_add_btn.pack(side="right", padx=8)

        cols = ("part_number", "name", "lines")
        self.part_tree = ttk.Treeview(parent, columns=cols, show="headings", height=14)
        for c in cols:
            self.part_tree.heading(c, text=c.upper())
            self.part_tree.column(c, width=260 if c != "lines" else 420)
        self.part_tree.pack(fill="both", expand=True, padx=10, pady=10)
        self.part_tree.bind("<Double-1>", lambda e: self._open_part_editor(self._selected_part()))

        self.part_del_btn = tk.Button(parent, text="Delete Selected", command=self.delete_selected_part)
        self.part_del_btn.pack(anchor="e", padx=10, pady=(0, 10))

        self.refresh_parts()
        self._apply_readonly_parts()

    def _apply_readonly_parts(self):
        if not self.readonly:
            return
        self.part_add_btn.configure(state="disabled")
        self.part_del_btn.configure(state="disabled")

    def refresh_parts(self):
        for i in self.part_tree.get_children():
            self.part_tree.delete(i)

        for p in list_parts_with_lines():
            self.part_tree.insert("", "end", values=(
                p.get("part_number", ""),
                p.get("name", ""),
                ", ".join(p.get("lines", []) or []),
            ))

    def _selected_part(self):
        sel = self.part_tree.selection()
        if not sel:
            return ""
        return self.part_tree.item(sel[0], "values")[0]

    def _open_part_editor(self, part_number: str = ""):
        if self.readonly:
            return
        top = tk.Toplevel(self)
        top.title("Part Editor")
        top.geometry("520x360")

        existing = {}
        for p in list_parts_with_lines():
            if p.get("part_number") == part_number:
                existing = p
                break

        form = tk.Frame(top, padx=12, pady=12)
        form.pack(fill="both", expand=True)

        tk.Label(form, text="Part #").grid(row=0, column=0, sticky="w")
        part_var = tk.StringVar(value=part_number)
        part_entry = tk.Entry(form, textvariable=part_var, width=24)
        part_entry.grid(row=0, column=1, sticky="w")
        if part_number:
            part_entry.configure(state="readonly")

        tk.Label(form, text="Name").grid(row=1, column=0, sticky="w", pady=(8, 0))
        name_var = tk.StringVar(value=existing.get("name", ""))
        tk.Entry(form, textvariable=name_var, width=30).grid(row=1, column=1, sticky="w", pady=(8, 0))

        line_frame = tk.LabelFrame(form, text="Lines", padx=8, pady=8)
        line_frame.grid(row=2, column=0, columnspan=2, sticky="we", pady=10)
        line_opts = list_lines() or ["U725", "JL"]
        selected = set(existing.get("lines", []) or [])
        line_vars = {}
        for idx, line in enumerate(line_opts):
            var = tk.BooleanVar(value=line in selected)
            line_vars[line] = var
            tk.Checkbutton(line_frame, text=line, variable=var).grid(row=0, column=idx, sticky="w", padx=6)

        def save():
            pn = part_var.get().strip()
            if not pn:
                messagebox.showerror("Error", "Part # is required.")
                return
            name = name_var.get().strip()
            lines = [ln for ln, var in line_vars.items() if var.get()]
            upsert_part(pn, name=name, lines=lines)
            log_audit(self.controller.user, f"Updated part {pn} lines/pricing")
            self.refresh_parts()
            top.destroy()

        tk.Button(form, text="Save Part", command=save, bg="#28a745", fg="white").grid(row=3, column=1, sticky="e", pady=10)

    def delete_selected_part(self):
        sel = self.part_tree.selection()
        if not sel:
            return
        pn = self.part_tree.item(sel[0], "values")[0]
        if not pn:
            return
        if not messagebox.askyesno("Confirm", f"Delete part '{pn}'?"):
            return

        deactivate_part(pn)
        log_audit(self.controller.user, f"Deactivated part {pn}")
        self.refresh_parts()

    # -------------------- SCRAP PRICING --------------------
    def _build_scrap(self, parent):
        top = tk.Frame(parent, bg=self.controller.colors["bg"], padx=10, pady=10)
        top.pack(fill="x")

        tk.Label(
            top,
            text="Scrap Pricing (by Part)",
            bg=self.controller.colors["bg"],
            fg=self.controller.colors["fg"],
            font=("Arial", 14, "bold"),
        ).pack(side="left")

        tk.Button(top, text="Refresh", command=self.refresh_scrap).pack(side="right")
        self.scrap_add_btn = tk.Button(top, text="Add Scrap Cost", command=lambda: self._open_scrap_editor())
        self.scrap_add_btn.pack(side="right", padx=8)

        cols = ("part_number", "scrap_cost")
        self.scrap_tree = ttk.Treeview(parent, columns=cols, show="headings", height=14)
        for c in cols:
            self.scrap_tree.heading(c, text=c.upper())
            self.scrap_tree.column(c, width=260)
        self.scrap_tree.pack(fill="both", expand=True, padx=10, pady=10)
        self.scrap_tree.bind("<Double-1>", lambda e: self._open_scrap_editor(self._selected_scrap_part()))

        self.scrap_del_btn = tk.Button(parent, text="Delete Selected", command=self.delete_selected_scrap)
        self.scrap_del_btn.pack(anchor="e", padx=10, pady=(0, 10))

        self.refresh_scrap()
        self._apply_readonly_scrap()

    def _apply_readonly_scrap(self):
        if not self.readonly:
            return
        self.scrap_add_btn.configure(state="disabled")
        self.scrap_del_btn.configure(state="disabled")

    def refresh_scrap(self):
        for i in self.scrap_tree.get_children():
            self.scrap_tree.delete(i)

        m = get_scrap_costs_simple()
        for pn in sorted(m.keys()):
            self.scrap_tree.insert("", "end", values=(pn, m[pn]))
    def _selected_scrap_part(self):
        sel = self.scrap_tree.selection()
        if not sel:
            return ""
        return self.scrap_tree.item(sel[0], "values")[0]

    def _open_scrap_editor(self, part_number: str = ""):
        if self.readonly:
            return
        top = tk.Toplevel(self)
        top.title("Scrap Cost Editor")
        top.geometry("420x220")

        existing_costs = get_scrap_costs_simple()
        cost_val = existing_costs.get(part_number, "")

        form = tk.Frame(top, padx=12, pady=12)
        form.pack(fill="both", expand=True)

        tk.Label(form, text="Part #").grid(row=0, column=0, sticky="w")
        pn_var = tk.StringVar(value=part_number)
        pn_entry = tk.Entry(form, textvariable=pn_var, width=18)
        pn_entry.grid(row=0, column=1, sticky="w")
        if part_number:
            pn_entry.configure(state="readonly")

        tk.Label(form, text="Scrap Cost ($)").grid(row=1, column=0, sticky="w", pady=(8, 0))
        cost_var = tk.StringVar(value=str(cost_val))
        tk.Entry(form, textvariable=cost_var, width=12).grid(row=1, column=1, sticky="w", pady=(8, 0))

        def save():
            pn = pn_var.get().strip()
            if not pn:
                messagebox.showerror("Error", "Part # is required.")
                return
            cost = safe_float(cost_var.get(), 0.0)
            set_scrap_cost(pn, cost)
            log_audit(self.controller.user, f"Set scrap cost for {pn} to {cost}")
            self.refresh_scrap()
            top.destroy()

        tk.Button(form, text="Save Scrap Cost", command=save, bg="#28a745", fg="white").grid(row=2, column=1, sticky="e", pady=12)

    def delete_selected_scrap(self):
        sel = self.scrap_tree.selection()
        if not sel:
            return
        pn = self.scrap_tree.item(sel[0], "values")[0]
        if not pn:
            return
        if not messagebox.askyesno("Confirm", f"Delete scrap price for '{pn}'?"):
            return
        set_scrap_cost(pn, 0.0)
        log_audit(self.controller.user, f"Cleared scrap cost for {pn}")
        self.refresh_scrap()

    # -------------------- DOWNTIME CODES --------------------
    def _build_downtime(self, parent):
        top = tk.Frame(parent, bg=self.controller.colors["bg"], padx=10, pady=10)
        top.pack(fill="x")

        tk.Label(
            top,
            text="Downtime Codes",
            bg=self.controller.colors["bg"],
            fg=self.controller.colors["fg"],
            font=("Arial", 14, "bold"),
        ).pack(side="left")

        tk.Button(top, text="Refresh", command=self.refresh_downtime).pack(side="right")
        self.downtime_add_btn = tk.Button(top, text="Add Code", command=lambda: self._open_downtime_editor())
        self.downtime_add_btn.pack(side="right", padx=8)

        cols = ("code", "description", "active")
        self.downtime_tree = ttk.Treeview(parent, columns=cols, show="headings", height=14)
        for c in cols:
            self.downtime_tree.heading(c, text=c.upper())
            self.downtime_tree.column(c, width=220)
        self.downtime_tree.pack(fill="both", expand=True, padx=10, pady=10)
        self.downtime_tree.bind("<Double-1>", lambda e: self._open_downtime_editor(self._selected_downtime()))

        self.downtime_del_btn = tk.Button(parent, text="Deactivate Selected", command=self.delete_selected_downtime)
        self.downtime_del_btn.pack(anchor="e", padx=10, pady=(0, 10))

        self.refresh_downtime()
        if self.readonly:
            self.downtime_add_btn.configure(state="disabled")
            self.downtime_del_btn.configure(state="disabled")

    def refresh_downtime(self):
        for i in self.downtime_tree.get_children():
            self.downtime_tree.delete(i)

        for row in list_downtime_codes(active_only=False):
            self.downtime_tree.insert("", "end", values=(
                row.get("code", ""),
                row.get("description", ""),
                "Yes" if row.get("is_active", 1) else "No",
            ))

    def _selected_downtime(self):
        sel = self.downtime_tree.selection()
        if not sel:
            return ""
        return self.downtime_tree.item(sel[0], "values")[0]

    def _open_downtime_editor(self, code: str = ""):
        if self.readonly:
            return
        top = tk.Toplevel(self)
        top.title("Downtime Code Editor")
        top.geometry("420x220")

        existing = {row["code"]: row for row in list_downtime_codes(active_only=False)}
        info = existing.get(code, {})

        form = tk.Frame(top, padx=12, pady=12)
        form.pack(fill="both", expand=True)

        tk.Label(form, text="Code").grid(row=0, column=0, sticky="w")
        code_var = tk.StringVar(value=code)
        code_entry = tk.Entry(form, textvariable=code_var, width=18)
        code_entry.grid(row=0, column=1, sticky="w")
        if code:
            code_entry.configure(state="readonly")

        tk.Label(form, text="Description").grid(row=1, column=0, sticky="w", pady=(8, 0))
        desc_var = tk.StringVar(value=info.get("description", ""))
        tk.Entry(form, textvariable=desc_var, width=30).grid(row=1, column=1, sticky="w", pady=(8, 0))

        def save():
            code_val = code_var.get().strip()
            if not code_val:
                messagebox.showerror("Error", "Code is required.")
                return
            upsert_downtime_code(code_val, desc_var.get().strip())
            log_audit(self.controller.user, f"Updated downtime code {code_val}")
            self.refresh_downtime()
            top.destroy()

        tk.Button(form, text="Save Code", command=save, bg="#28a745", fg="white").grid(row=2, column=1, sticky="e", pady=12)

    def delete_selected_downtime(self):
        code = self._selected_downtime()
        if not code:
            return
        if not messagebox.askyesno("Confirm", f"Deactivate downtime code '{code}'?"):
            return
        deactivate_downtime_code(code)
        log_audit(self.controller.user, f"Deactivated downtime code {code}")
        self.refresh_downtime()
