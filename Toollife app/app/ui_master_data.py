# app/ui_master_data.py
from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox

from .storage import safe_float
from .db import (
    list_tools_simple,
    upsert_tool_inventory,
    deactivate_tool,
    list_parts_with_lines,
    upsert_part,
    deactivate_part,
    set_scrap_cost,
    get_scrap_costs_simple,
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

        nb.add(tab_tools, text="Tool Pricing")
        nb.add(tab_parts, text="Parts & Lines")
        nb.add(tab_scrap, text="Scrap Pricing")

        self._build_tool_pricing(tab_tools)
        self._build_parts(tab_parts)
        self._build_scrap(tab_scrap)

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
        self.tool_save_btn = tk.Button(top, text="Save", command=self.save_tools)
        self.tool_save_btn.pack(side="right", padx=8)

        form = tk.Frame(parent, bg=self.controller.colors["bg"], padx=10, pady=6)
        form.pack(fill="x")

        self.tool_id = tk.StringVar()
        self.tool_name = tk.StringVar()
        self.tool_cost = tk.StringVar()
        self.tool_stock = tk.StringVar()
        self.tool_inserts = tk.StringVar()

        tk.Label(form, text="Tool #", bg=self.controller.colors["bg"], fg=self.controller.colors["fg"]).grid(row=0, column=0, sticky="w")
        self.tool_id_entry = tk.Entry(form, textvariable=self.tool_id, width=16)
        self.tool_id_entry.grid(row=0, column=1, padx=8)

        tk.Label(form, text="Name", bg=self.controller.colors["bg"], fg=self.controller.colors["fg"]).grid(row=0, column=2, sticky="w")
        self.tool_name_entry = tk.Entry(form, textvariable=self.tool_name, width=30)
        self.tool_name_entry.grid(row=0, column=3, padx=8)

        tk.Label(form, text="Unit Cost ($)", bg=self.controller.colors["bg"], fg=self.controller.colors["fg"]).grid(row=0, column=4, sticky="w")
        self.tool_cost_entry = tk.Entry(form, textvariable=self.tool_cost, width=12)
        self.tool_cost_entry.grid(row=0, column=5, padx=8)

        tk.Label(form, text="Stock Qty", bg=self.controller.colors["bg"], fg=self.controller.colors["fg"]).grid(row=1, column=0, sticky="w", pady=(8, 0))
        self.tool_stock_entry = tk.Entry(form, textvariable=self.tool_stock, width=12)
        self.tool_stock_entry.grid(row=1, column=1, padx=8, pady=(8, 0))

        tk.Label(form, text="Inserts/Tool", bg=self.controller.colors["bg"], fg=self.controller.colors["fg"]).grid(row=1, column=2, sticky="w", pady=(8, 0))
        self.tool_inserts_entry = tk.Entry(form, textvariable=self.tool_inserts, width=12)
        self.tool_inserts_entry.grid(row=1, column=3, padx=8, pady=(8, 0))

        self.tool_add_btn = tk.Button(form, text="Add / Update", command=self.add_update_tool)
        self.tool_add_btn.grid(row=0, column=6, padx=10, rowspan=2)
        self.tool_del_btn = tk.Button(form, text="Deactivate Selected", command=self.delete_selected_tool)
        self.tool_del_btn.grid(row=0, column=7, padx=6, rowspan=2)

        cols = ("tool", "name", "unit_cost", "stock_qty", "inserts_per_tool")
        self.tool_tree = ttk.Treeview(parent, columns=cols, show="headings", height=14)
        for c in cols:
            self.tool_tree.heading(c, text=c.upper())
            if c == "unit_cost":
                self.tool_tree.column(c, width=140)
            elif c in ("stock_qty", "inserts_per_tool"):
                self.tool_tree.column(c, width=140)
            else:
                self.tool_tree.column(c, width=220)
        self.tool_tree.pack(fill="both", expand=True, padx=10, pady=10)

        self.refresh_tools()
        self._apply_readonly_tool()

    def _apply_readonly_tool(self):
        if not self.readonly:
            return
        for widget in (
            self.tool_id_entry,
            self.tool_name_entry,
            self.tool_cost_entry,
            self.tool_stock_entry,
            self.tool_inserts_entry,
        ):
            widget.configure(state="readonly")
        self.tool_add_btn.configure(state="disabled")
        self.tool_del_btn.configure(state="disabled")
        self.tool_save_btn.configure(state="disabled")

    def refresh_tools(self):
        for i in self.tool_tree.get_children():
            self.tool_tree.delete(i)

        for tool in list_tools_simple():
            self.tool_tree.insert("", "end", values=(
                tool.get("tool_num", ""),
                tool.get("name", ""),
                tool.get("unit_cost", 0.0),
                tool.get("stock_qty", 0),
                tool.get("inserts_per_tool", 1),
            ))

    def add_update_tool(self):
        tid = self.tool_id.get().strip()
        if not tid:
            messagebox.showerror("Error", "Tool # is required.")
            return

        name = self.tool_name.get().strip()
        cost = safe_float(self.tool_cost.get(), 0.0)
        stock = int(safe_float(self.tool_stock.get(), 0.0))
        inserts = int(safe_float(self.tool_inserts.get(), 1.0))

        upsert_tool_inventory(
            tool_num=tid,
            name=name,
            unit_cost=cost,
            stock_qty=stock,
            inserts_per_tool=inserts,
        )
        log_audit(self.controller.user, f"Updated tool {tid} pricing/inventory")

        self.tool_id.set("")
        self.tool_name.set("")
        self.tool_cost.set("")
        self.tool_stock.set("")
        self.tool_inserts.set("")
        self.refresh_tools()

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
        self.parts_save_btn = tk.Button(top, text="Save", command=self.save_parts)
        self.parts_save_btn.pack(side="right", padx=8)

        form = tk.Frame(parent, bg=self.controller.colors["bg"], padx=10, pady=6)
        form.pack(fill="x")

        self.part_no = tk.StringVar()
        self.part_name = tk.StringVar()
        self.part_lines = tk.StringVar()

        tk.Label(form, text="Part #", bg=self.controller.colors["bg"], fg=self.controller.colors["fg"]).grid(row=0, column=0, sticky="w")
        self.part_no_entry = tk.Entry(form, textvariable=self.part_no, width=18)
        self.part_no_entry.grid(row=0, column=1, padx=8)

        tk.Label(form, text="Name", bg=self.controller.colors["bg"], fg=self.controller.colors["fg"]).grid(row=0, column=2, sticky="w")
        self.part_name_entry = tk.Entry(form, textvariable=self.part_name, width=30)
        self.part_name_entry.grid(row=0, column=3, padx=8)

        tk.Label(form, text="Lines (comma sep)", bg=self.controller.colors["bg"], fg=self.controller.colors["fg"]).grid(row=0, column=4, sticky="w")
        self.part_lines_entry = tk.Entry(form, textvariable=self.part_lines, width=28)
        self.part_lines_entry.grid(row=0, column=5, padx=8)

        self.part_add_btn = tk.Button(form, text="Add / Update", command=self.add_update_part)
        self.part_add_btn.grid(row=0, column=6, padx=10)
        self.part_del_btn = tk.Button(form, text="Delete Selected", command=self.delete_selected_part)
        self.part_del_btn.grid(row=0, column=7, padx=6)

        cols = ("part_number", "name", "lines")
        self.part_tree = ttk.Treeview(parent, columns=cols, show="headings", height=14)
        for c in cols:
            self.part_tree.heading(c, text=c.upper())
            self.part_tree.column(c, width=260 if c != "lines" else 420)
        self.part_tree.pack(fill="both", expand=True, padx=10, pady=10)

        self.refresh_parts()
        self._apply_readonly_parts()

    def _apply_readonly_parts(self):
        if not self.readonly:
            return
        for widget in (
            self.part_no_entry,
            self.part_name_entry,
            self.part_lines_entry,
        ):
            widget.configure(state="readonly")
        self.part_add_btn.configure(state="disabled")
        self.part_del_btn.configure(state="disabled")
        self.parts_save_btn.configure(state="disabled")

    def refresh_parts(self):
        for i in self.part_tree.get_children():
            self.part_tree.delete(i)

        for p in list_parts_with_lines():
            self.part_tree.insert("", "end", values=(
                p.get("part_number", ""),
                p.get("name", ""),
                ", ".join(p.get("lines", []) or []),
            ))

    def add_update_part(self):
        pn = self.part_no.get().strip()
        if not pn:
            messagebox.showerror("Error", "Part # is required.")
            return

        name = self.part_name.get().strip()
        lines = [x.strip() for x in (self.part_lines.get() or "").split(",") if x.strip()]
        upsert_part(pn, name=name, lines=lines)
        log_audit(self.controller.user, f"Updated part {pn} lines/pricing")

        self.part_no.set("")
        self.part_name.set("")
        self.part_lines.set("")
        self.refresh_parts()

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

    def save_parts(self):
        messagebox.showinfo("Saved", "Parts saved.")

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
        self.scrap_save_btn = tk.Button(top, text="Save", command=self.save_scrap)
        self.scrap_save_btn.pack(side="right", padx=8)

        form = tk.Frame(parent, bg=self.controller.colors["bg"], padx=10, pady=6)
        form.pack(fill="x")

        self.scrap_part = tk.StringVar()
        self.scrap_cost = tk.StringVar()

        tk.Label(form, text="Part #", bg=self.controller.colors["bg"], fg=self.controller.colors["fg"]).grid(row=0, column=0, sticky="w")
        self.scrap_part_entry = tk.Entry(form, textvariable=self.scrap_part, width=18)
        self.scrap_part_entry.grid(row=0, column=1, padx=8)

        tk.Label(form, text="Scrap Cost ($)", bg=self.controller.colors["bg"], fg=self.controller.colors["fg"]).grid(row=0, column=2, sticky="w")
        self.scrap_cost_entry = tk.Entry(form, textvariable=self.scrap_cost, width=12)
        self.scrap_cost_entry.grid(row=0, column=3, padx=8)

        self.scrap_add_btn = tk.Button(form, text="Add / Update", command=self.add_update_scrap)
        self.scrap_add_btn.grid(row=0, column=4, padx=10)
        self.scrap_del_btn = tk.Button(form, text="Delete Selected", command=self.delete_selected_scrap)
        self.scrap_del_btn.grid(row=0, column=5, padx=6)

        cols = ("part_number", "scrap_cost")
        self.scrap_tree = ttk.Treeview(parent, columns=cols, show="headings", height=14)
        for c in cols:
            self.scrap_tree.heading(c, text=c.upper())
            self.scrap_tree.column(c, width=260)
        self.scrap_tree.pack(fill="both", expand=True, padx=10, pady=10)

        self.refresh_scrap()
        self._apply_readonly_scrap()

    def _apply_readonly_scrap(self):
        if not self.readonly:
            return
        for widget in (self.scrap_part_entry, self.scrap_cost_entry):
            widget.configure(state="readonly")
        self.scrap_add_btn.configure(state="disabled")
        self.scrap_del_btn.configure(state="disabled")
        self.scrap_save_btn.configure(state="disabled")

    def refresh_scrap(self):
        for i in self.scrap_tree.get_children():
            self.scrap_tree.delete(i)

        m = get_scrap_costs_simple()
        for pn in sorted(m.keys()):
            self.scrap_tree.insert("", "end", values=(pn, m[pn]))

    def add_update_scrap(self):
        pn = self.scrap_part.get().strip()
        if not pn:
            messagebox.showerror("Error", "Part # is required.")
            return

        cost = safe_float(self.scrap_cost.get(), 0.0)
        set_scrap_cost(pn, cost)
        log_audit(self.controller.user, f"Set scrap cost for {pn} to {cost}")

        self.scrap_part.set("")
        self.scrap_cost.set("")
        self.refresh_scrap()

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

    def save_scrap(self):
        messagebox.showinfo("Saved", "Scrap pricing saved.")
