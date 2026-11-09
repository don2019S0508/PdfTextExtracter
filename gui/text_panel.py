"""GUI component for viewing, editing, and managing extracted text."""

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional, Callable


class TextPanel(ttk.Frame):
    """Panel with an editable text box to display and edit extracted text of the whole PDF."""

    def __init__(
        self,
        master: tk.Widget,
        on_text_change: Optional[Callable[[], None]] = None,
        on_run_ocr: Optional[Callable[[], None]] = None,
        **kwargs
    ):
        super().__init__(master, **kwargs)

        self.on_text_change = on_text_change
        self.on_run_ocr = on_run_ocr
        self._build_ui()

    def _build_ui(self) -> None:
        """Construct the toolbar, text area, and stats display."""
        # Header / Toolbar
        self.header_frame = ttk.Frame(self, padding=(5, 5))
        self.header_frame.pack(side=tk.TOP, fill=tk.X)

        self.lbl_title = ttk.Label(
            self.header_frame,
            text="Extracted Text (Editable)",
            font=("TkDefaultFont", 10, "bold")
        )
        self.lbl_title.pack(side=tk.LEFT, padx=(2, 8))

        # OCR Action button
        self.btn_ocr = ttk.Button(
            self.header_frame,
            text="Extract with OCR",
            command=self._handle_ocr_click
        )
        self.btn_ocr.pack(side=tk.LEFT, padx=2)

        # Action buttons
        self.btn_copy = ttk.Button(self.header_frame, text="Copy All", command=self.copy_all)
        self.btn_copy.pack(side=tk.LEFT, padx=2)

        self.btn_select_all = ttk.Button(self.header_frame, text="Select All", command=self.select_all)
        self.btn_select_all.pack(side=tk.LEFT, padx=2)

        self.btn_clear = ttk.Button(self.header_frame, text="Clear", command=self.clear)
        self.btn_clear.pack(side=tk.LEFT, padx=2)

        # Stats label (right aligned)
        self.lbl_stats = ttk.Label(self.header_frame, text="Words: 0 | Chars: 0", foreground="#555555")
        self.lbl_stats.pack(side=tk.RIGHT, padx=5)

        # Text area container with scrollbars
        self.text_frame = ttk.Frame(self)
        self.text_frame.pack(side=tk.BOTTOM, fill=tk.BOTH, expand=True)

        self.v_scroll = ttk.Scrollbar(self.text_frame, orient=tk.VERTICAL)
        self.v_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.h_scroll = ttk.Scrollbar(self.text_frame, orient=tk.HORIZONTAL)
        self.h_scroll.pack(side=tk.BOTTOM, fill=tk.X)

        self.text_box = tk.Text(
            self.text_frame,
            wrap=tk.WORD,
            undo=True,
            font=("Monospace", 10),
            padx=8,
            pady=8,
            xscrollcommand=self.h_scroll.set,
            yscrollcommand=self.v_scroll.set,
        )
        self.text_box.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.v_scroll.config(command=self.text_box.yview)
        self.h_scroll.config(command=self.text_box.xview)

        # Track modifications to update stats
        self.text_box.bind("<KeyRelease>", self._on_text_modified)
        self.text_box.bind("<<Modified>>", self._on_text_modified)

    def set_ocr_running(self, running: bool) -> None:
        """Update button state during OCR extraction."""
        if running:
            self.btn_ocr.config(text="Running OCR...", state=tk.DISABLED)
        else:
            self.btn_ocr.config(text="Extract with OCR", state=tk.NORMAL)

    def _handle_ocr_click(self) -> None:
        if self.on_run_ocr:
            self.on_run_ocr()

    def set_text(self, content: str) -> None:
        """Replace current text with new content and reset undo stack."""
        self.text_box.delete("1.0", tk.END)
        self.text_box.insert("1.0", content)
        self.text_box.edit_reset()
        self._update_stats()

    def get_text(self) -> str:
        """Return the current text content."""
        return self.text_box.get("1.0", "end-1c")

    def clear(self, prompt: bool = True) -> None:
        """Clear all content after confirming if prompt is True and there is content."""
        if prompt and bool(self.get_text().strip()):
            if not messagebox.askyesno("Confirm Clear", "Are you sure you want to clear the extracted text?"):
                return
        self.text_box.delete("1.0", tk.END)
        self._update_stats()
        if self.on_text_change:
            self.on_text_change()

    def select_all(self) -> None:
        """Select all text in the text widget."""
        self.text_box.tag_add("sel", "1.0", tk.END)
        self.text_box.focus_set()

    def copy_all(self) -> None:
        """Copy all text to clipboard."""
        text = self.get_text()
        if not text:
            return
        self.clipboard_clear()
        self.clipboard_append(text)
        messagebox.showinfo("Copied", "All extracted text copied to clipboard.")

    def _on_text_modified(self, _event=None) -> None:
        """Update live stats on modification."""
        self.text_box.edit_modified(False)
        self._update_stats()
        if self.on_text_change:
            self.on_text_change()

    def _update_stats(self) -> None:
        """Calculate and display word and char count."""
        content = self.get_text()
        chars = len(content)
        words = len(content.split())
        self.lbl_stats.config(text=f"Words: {words:,} | Chars: {chars:,}")
