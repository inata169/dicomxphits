"""Application-colored modal messages with explicit, cancel-safe confirmation."""
from __future__ import annotations

import tkinter as tk
from tkinter import scrolledtext, ttk
from typing import Mapping


class GuiMessages:
    def __init__(self, parent: tk.Misc, colors: Mapping[str, str]) -> None:
        self.parent = parent
        self.colors = colors

    def _show(self, title: str, message: str, *, kind: str,
              confirm: bool = False, accept: str = "Yes", cancel: str = "No") -> bool:
        colors = self.colors
        dialog = tk.Toplevel(self.parent)
        dialog.title(title)
        dialog.configure(background=colors["navy"])
        dialog.transient(self.parent)
        dialog.columnconfigure(0, weight=1)
        dialog.rowconfigure(1, weight=1)
        dialog.minsize(440, 200)
        tk.Label(dialog, text=title, background=colors["navy"],
                 foreground=colors[kind], font=("Segoe UI Semibold", 15),
                 anchor="w").grid(row=0, column=0, sticky="ew", padx=20, pady=(16, 8))
        body = scrolledtext.ScrolledText(
            dialog, wrap="word", width=72, height=min(18, max(4, len(message) // 65 + message.count("\n") + 1)),
            background=colors["surface"], foreground=colors["text"],
            insertbackground=colors["text"], font=("Segoe UI", 10),
            relief="flat", padx=12, pady=12,
        )
        body.insert("1.0", message)
        body.configure(state="disabled")
        body.grid(row=1, column=0, sticky="nsew", padx=20, pady=(0, 12))
        actions = ttk.Frame(dialog, style="App.TFrame")
        actions.grid(row=2, column=0, sticky="e", padx=20, pady=(0, 16))
        result = False

        def finish(value: bool = False) -> None:
            nonlocal result
            result = value
            dialog.destroy()

        dismiss = ttk.Button(actions, text=cancel if confirm else "OK", command=finish)
        dismiss.pack(side="left", padx=(0, 8))
        if confirm:
            ttk.Button(actions, text=accept, style="Primary.TButton",
                       command=lambda: finish(True)).pack(side="left")
        dialog.protocol("WM_DELETE_WINDOW", finish)
        dialog.bind("<Escape>", lambda _event: finish())
        # Return follows focused buttons; initial focus is always the safe choice.
        dialog.update_idletasks()
        dialog.geometry(
            f"+{max(0, self.parent.winfo_rootx() + (self.parent.winfo_width() - dialog.winfo_width()) // 2)}"
            f"+{max(0, self.parent.winfo_rooty() + (self.parent.winfo_height() - dialog.winfo_height()) // 2)}"
        )
        dialog.grab_set()
        dismiss.focus_set()
        self.parent.wait_window(dialog)
        return result

    def showinfo(self, title: str, message: str) -> None:
        self._show(title, message, kind="cyan")

    def showwarning(self, title: str, message: str) -> None:
        self._show(title, message, kind="warning")

    def showerror(self, title: str, message: str) -> None:
        self._show(title, message, kind="error")

    def askyesno(self, title: str, message: str, *, accept: str = "Yes", cancel: str = "No") -> bool:
        return self._show(title, message, kind="warning", confirm=True, accept=accept, cancel=cancel)
