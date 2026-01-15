# app/ui_gages.py
import tkinter as tk
from tkinter import ttk

from .ui_common import HeaderFrame
from .ui_gage_verification import GageVerificationUI
from .ui_gage_questions_editor import GageQuestionsEditorUI


class GagesUI(tk.Frame):
    """
    Combined Gages screen:
    - Gage Verification
    - Gage Verification Questions (Admin/Super)
    """

    def __init__(self, parent, controller, show_header=True):
        super().__init__(parent, bg=controller.colors["bg"])
        self.controller = controller

        if show_header:
            HeaderFrame(self, controller).pack(fill="x")

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=10, pady=10)

        tab_verify = tk.Frame(nb, bg=controller.colors["bg"])
        tab_questions = tk.Frame(nb, bg=controller.colors["bg"])

        nb.add(tab_verify, text="Gage Verification")
        nb.add(tab_questions, text="Verification Questions")

        GageVerificationUI(tab_verify, controller, show_header=False).pack(fill="both", expand=True)
        GageQuestionsEditorUI(tab_questions, controller, show_header=False).pack(fill="both", expand=True)
