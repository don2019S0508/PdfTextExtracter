"""Main GUI Application orchestrating PDF viewer, text editor, menu, and status bar."""

import os
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
from typing import Optional
from pathlib import Path

from core.pdf_reader import PDFReader
from core.text_extractor import TextExtractor, is_ocr_available
from gui.pdf_panel import PDFPanel
from gui.text_panel import TextPanel


class PDFExtractorApp:
    """Main Application Controller for PDF Text Extractor."""

    def __init__(self, root: Optional[tk.Tk] = None, initial_file: Optional[str] = None):
        if root is None:
            self.root = tk.Tk()
            self._owns_root = True
        else:
            self.root = root
            self._owns_root = False

        self.reader = PDFReader()
        self.current_file_path: Optional[str] = None
        self._is_ocr_busy: bool = False

        self._init_window()
        self._build_layout()
        self._build_menu()
        self._build_status_bar()
        self._bind_shortcuts()

        if initial_file and os.path.isfile(initial_file):
            self.root.after(100, lambda: self.open_pdf(initial_file))

    def _init_window(self) -> None:
        """Configure main window properties with full pull/resize flexibility."""
        self.root.title("PDF Text Extractor")
        self.root.geometry("1100x750")
        self.root.minsize(600, 400)
        self.root.resizable(True, True)
        self.root.protocol("WM_DELETE_WINDOW", self.on_exit)

    def _build_layout(self) -> None:
        """Construct the main two-panel layout with an interactive draggable splitter sash."""
        self.paned_window = tk.PanedWindow(
            self.root,
            orient=tk.HORIZONTAL,
            sashrelief=tk.RAISED,
            sashwidth=6,
            sashpad=2,
            bg="#c8c8c8",
            bd=1,
            relief=tk.FLAT,
            opaqueresize=True
        )
        self.paned_window.pack(fill=tk.BOTH, expand=True, padx=4, pady=(4, 0))

        # Left panel: PDF viewer
        self.pdf_panel = PDFPanel(self.paned_window, on_page_change=self._on_page_changed)
        self.paned_window.add(self.pdf_panel, minsize=200, stretch="always")

        # Right panel: Text editor
        self.text_panel = TextPanel(
            self.paned_window,
            on_text_change=self._on_text_modified,
            on_run_ocr=self.run_ocr
        )
        self.paned_window.add(self.text_panel, minsize=200, stretch="always")

    def _build_menu(self) -> None:
        """Construct the menu bar with File, Edit, Navigate, View, Tools, and Help."""
        self.menubar = tk.Menu(self.root)

        # 1. File menu
        self.file_menu = tk.Menu(self.menubar, tearoff=0)
        self.file_menu.add_command(label="Open PDF...", command=self.open_pdf, accelerator="Ctrl+O")
        self.file_menu.add_command(label="Save Extracted Text As...", command=self.save_text, accelerator="Ctrl+S")
        self.file_menu.add_command(label="Close Document", command=self.close_pdf, accelerator="Ctrl+W")
        self.file_menu.add_separator()
        self.file_menu.add_command(label="Exit", command=self.on_exit, accelerator="Ctrl+Q")
        self.menubar.add_cascade(label="File", menu=self.file_menu)

        # 2. Edit menu
        self.edit_menu = tk.Menu(self.menubar, tearoff=0)
        self.edit_menu.add_command(
            label="Undo",
            command=lambda: self.text_panel.text_box.event_generate("<<Undo>>"),
            accelerator="Ctrl+Z"
        )
        self.edit_menu.add_command(
            label="Redo",
            command=lambda: self.text_panel.text_box.event_generate("<<Redo>>"),
            accelerator="Ctrl+Y"
        )
        self.edit_menu.add_separator()
        self.edit_menu.add_command(
            label="Cut",
            command=lambda: self.text_panel.text_box.event_generate("<<Cut>>"),
            accelerator="Ctrl+X"
        )
        self.edit_menu.add_command(
            label="Copy",
            command=lambda: self.text_panel.text_box.event_generate("<<Copy>>"),
            accelerator="Ctrl+C"
        )
        self.edit_menu.add_command(
            label="Paste",
            command=lambda: self.text_panel.text_box.event_generate("<<Paste>>"),
            accelerator="Ctrl+V"
        )
        self.edit_menu.add_command(
            label="Select All",
            command=lambda: self.text_panel.select_all(),
            accelerator="Ctrl+A"
        )
        self.menubar.add_cascade(label="Edit", menu=self.edit_menu)

        # 3. Navigate menu (Previous, Next, First, Last, Go to Page)
        self.nav_menu = tk.Menu(self.menubar, tearoff=0)
        self.nav_menu.add_command(
            label="Next Page",
            command=self.pdf_panel.next_page,
            accelerator="PgDn / Alt+Right"
        )
        self.nav_menu.add_command(
            label="Previous Page",
            command=self.pdf_panel.prev_page,
            accelerator="PgUp / Alt+Left"
        )
        self.nav_menu.add_separator()
        self.nav_menu.add_command(
            label="First Page",
            command=self.pdf_panel.first_page,
            accelerator="Home"
        )
        self.nav_menu.add_command(
            label="Last Page",
            command=self.pdf_panel.last_page,
            accelerator="End"
        )
        self.nav_menu.add_separator()
        self.nav_menu.add_command(
            label="Go to Page...",
            command=self._prompt_goto_page,
            accelerator="Ctrl+G"
        )
        self.menubar.add_cascade(label="Navigate", menu=self.nav_menu)

        # 4. View menu
        self.view_menu = tk.Menu(self.menubar, tearoff=0)
        self.view_menu.add_command(label="Zoom In", command=self._zoom_in, accelerator="Ctrl++")
        self.view_menu.add_command(label="Zoom Out", command=self._zoom_out, accelerator="Ctrl+-")
        self.view_menu.add_command(label="Fit Page to Width", command=self._fit_to_width, accelerator="Ctrl+F")
        self.view_menu.add_command(label="Reset Zoom (100%)", command=self._zoom_reset, accelerator="Ctrl+0")
        self.menubar.add_cascade(label="View", menu=self.view_menu)

        # 5. Tools menu (OCR)
        self.tools_menu = tk.Menu(self.menubar, tearoff=0)
        self.tools_menu.add_command(
            label="Extract with OCR (Images)...",
            command=self.run_ocr,
            accelerator="Ctrl+Shift+O"
        )
        self.menubar.add_cascade(label="Tools", menu=self.tools_menu)

        # 6. Help menu
        self.help_menu = tk.Menu(self.menubar, tearoff=0)
        self.help_menu.add_command(label="About", command=self._show_about)
        self.menubar.add_cascade(label="Help", menu=self.help_menu)

        self.root.config(menu=self.menubar)

    def _build_status_bar(self) -> None:
        """Construct bottom status bar with a resize grip in the corner."""
        self.status_frame = ttk.Frame(self.root, padding=(6, 3))
        self.status_frame.pack(side=tk.BOTTOM, fill=tk.X)

        self.lbl_status = ttk.Label(self.status_frame, text="Ready. Open a PDF to begin.")
        self.lbl_status.pack(side=tk.LEFT)

        self.sizegrip = ttk.Sizegrip(self.status_frame)
        self.sizegrip.pack(side=tk.RIGHT, anchor=tk.SE)

        self.lbl_doc_info = ttk.Label(self.status_frame, text="", foreground="#666666")
        self.lbl_doc_info.pack(side=tk.RIGHT, padx=(0, 10))

    def _bind_shortcuts(self) -> None:
        """Register global keyboard shortcuts."""
        self.root.bind("<Control-o>", lambda e: self.open_pdf())
        self.root.bind("<Control-O>", lambda e: self.open_pdf())
        self.root.bind("<Control-s>", lambda e: self.save_text())
        self.root.bind("<Control-S>", lambda e: self.save_text())
        self.root.bind("<Control-w>", lambda e: self.close_pdf())
        self.root.bind("<Control-W>", lambda e: self.close_pdf())
        self.root.bind("<Control-q>", lambda e: self.on_exit())
        self.root.bind("<Control-Q>", lambda e: self.on_exit())

        self.root.bind("<Control-g>", lambda e: self._prompt_goto_page())
        self.root.bind("<Control-G>", lambda e: self._prompt_goto_page())

        self.root.bind("<Control-Shift-O>", lambda e: self.run_ocr())
        self.root.bind("<Control-Shift-o>", lambda e: self.run_ocr())

        self.root.bind("<Control-plus>", lambda e: self._zoom_in())
        self.root.bind("<Control-equal>", lambda e: self._zoom_in())
        self.root.bind("<Control-minus>", lambda e: self._zoom_out())
        self.root.bind("<Control-0>", lambda e: self._zoom_reset())
        self.root.bind("<Control-f>", lambda e: self._fit_to_width())
        self.root.bind("<Control-F>", lambda e: self._fit_to_width())

        # Page navigation shortcuts
        self.root.bind("<Prior>", self._on_page_up_key)
        self.root.bind("<Next>", self._on_page_down_key)
        self.root.bind("<Alt-Left>", lambda e: self.pdf_panel.prev_page())
        self.root.bind("<Alt-Right>", lambda e: self.pdf_panel.next_page())
        self.root.bind("<Home>", self._on_home_key)
        self.root.bind("<End>", self._on_end_key)

    def _prompt_goto_page(self) -> None:
        """Show prompt dialog to jump directly to a page."""
        if not self.reader or not self.reader.is_open or self.reader.page_count == 0:
            messagebox.showinfo("No Document", "Please open a PDF document first.")
            return

        page = simpledialog.askinteger(
            "Go to Page",
            f"Enter page number (1 to {self.reader.page_count}):",
            minvalue=1,
            maxvalue=self.reader.page_count,
            initialvalue=self.pdf_panel.current_page + 1
        )
        if page:
            self.pdf_panel.goto_page(page)

    def open_pdf(self, file_path: Optional[str] = None) -> None:
        """Open a PDF file, render the first page, and extract text for the entire document."""
        if not file_path:
            file_path = filedialog.askopenfilename(
                title="Select a PDF File",
                filetypes=[("PDF Files", "*.pdf"), ("All Files", "*.*")]
            )

        if not file_path:
            return

        password: Optional[str] = None
        attempt = 0
        while attempt < 3:
            try:
                self.reader.open(file_path, password=password)
                break
            except ValueError:
                prompt = "Enter PDF password:" if password is None else "Incorrect password. Please try again:"
                password = simpledialog.askstring("Password Protected PDF", prompt, show="*")
                if password is None:
                    return
                attempt += 1
            except Exception as e:
                messagebox.showerror("Error Opening PDF", f"Failed to open PDF:\n{e}")
                return

        if not self.reader.is_open:
            return

        self.current_file_path = file_path
        file_name = Path(file_path).name

        self.pdf_panel.set_reader(self.reader)
        self.set_status(f"Extracting standard text from {self.reader.page_count} pages...")
        self.root.update_idletasks()

        try:
            full_text = TextExtractor.extract_all_text(self.reader, include_page_headers=True, use_ocr=False)
            self.text_panel.set_text(full_text)

            is_image_doc = TextExtractor.detect_image_reliance(self.reader)
            if is_image_doc:
                self.set_status(
                    f"Loaded '{file_name}' ({self.reader.page_count} pages). "
                    "Notice: Image-based pages detected. Click 'Extract with OCR' to read text inside images."
                )
                should_run = messagebox.askyesno(
                    "Image-Based Content Detected",
                    f"'{file_name}' appears to contain text embedded in images rather than selectable text.\n\n"
                    "Would you like to run OCR now to extract text from the images?"
                )
                if should_run:
                    self.run_ocr()
            else:
                self.set_status(f"Loaded '{file_name}' ({self.reader.page_count} pages). Text extracted successfully.")

        except Exception as e:
            messagebox.showerror("Extraction Error", f"Failed to extract text:\n{e}")
            self.set_status(f"Error extracting text from {file_name}.")

        self.root.title(f"PDF Text Extractor - {file_name}")
        self._update_doc_info()

    def run_ocr(self) -> None:
        """Execute OCR extraction on the opened document in a background worker thread."""
        if not self.reader.is_open or self.reader.page_count == 0:
            messagebox.showwarning("No Document", "Please open a PDF document first.")
            return

        if self._is_ocr_busy:
            messagebox.showinfo("Busy", "OCR extraction is already running in the background.")
            return

        if not is_ocr_available():
            messagebox.showerror(
                "OCR Unavailable",
                "The OCR engine (rapidocr_onnxruntime) is not installed.\n"
                "Please run: pip install rapidocr-onnxruntime"
            )
            return

        self._is_ocr_busy = True
        self.text_panel.set_ocr_running(True)
        self.set_status(f"Starting OCR extraction across {self.reader.page_count} pages...")

        worker = threading.Thread(target=self._ocr_worker, daemon=True)
        worker.start()

    def _ocr_worker(self) -> None:
        """Background thread executing OCR across all pages."""
        try:
            def on_progress(current: int, total: int):
                self.root.after(0, lambda c=current, t=total: self.set_status(
                    f"Running OCR on page {c} of {t}... please wait."
                ))

            ocr_text = TextExtractor.extract_all_text(
                self.reader,
                include_page_headers=True,
                use_ocr=True,
                progress_callback=on_progress
            )

            def on_success():
                self.text_panel.set_text(ocr_text)
                self.text_panel.set_ocr_running(False)
                self._is_ocr_busy = False
                file_name = Path(self.current_file_path).name if self.current_file_path else ""
                chars = len(ocr_text)
                self.set_status(f"OCR complete for '{file_name}': {chars:,} characters extracted.")
                messagebox.showinfo("OCR Completed", f"Successfully extracted text via OCR ({chars:,} characters).")

            self.root.after(0, on_success)

        except Exception as e:
            def on_error(err_msg: str):
                self.text_panel.set_ocr_running(False)
                self._is_ocr_busy = False
                self.set_status("OCR extraction failed.")
                messagebox.showerror("OCR Error", f"An error occurred during OCR extraction:\n{err_msg}")

            self.root.after(0, lambda: on_error(str(e)))

    def save_text(self) -> None:
        """Save the editable extracted text to a user-selected file."""
        text_content = self.text_panel.get_text()
        if not text_content.strip():
            messagebox.showwarning("Empty Content", "There is no text to save.")
            return

        initial_name = "extracted_text.txt"
        if self.current_file_path:
            base = Path(self.current_file_path).stem
            initial_name = f"{base}_extracted.txt"

        file_path = filedialog.asksaveasfilename(
            title="Save Extracted Text As",
            initialfile=initial_name,
            defaultextension=".txt",
            filetypes=[
                ("Text Files", "*.txt"),
                ("Markdown Files", "*.md"),
                ("All Files", "*.*")
            ]
        )

        if not file_path:
            return

        try:
            TextExtractor.save_text_to_file(text_content, file_path)
            self.set_status(f"Saved extracted text to: {Path(file_path).name}")
            messagebox.showinfo("Saved", f"Extracted text saved successfully to:\n{file_path}")
        except Exception as e:
            messagebox.showerror("Save Error", f"Failed to save text to file:\n{e}")

    def close_pdf(self) -> None:
        """Close current document and clear UI."""
        self.reader.close()
        self.current_file_path = None
        self.pdf_panel.set_reader(None)
        self.text_panel.clear(prompt=False)
        self.root.title("PDF Text Extractor")
        self.set_status("Ready. Open a PDF to begin.")
        self.lbl_doc_info.config(text="")

    def set_status(self, message: str) -> None:
        """Update status bar text."""
        self.lbl_status.config(text=message)

    def _on_page_changed(self, current: int, total: int) -> None:
        """Callback when page index changes."""
        self._update_doc_info()

    def _on_text_modified(self) -> None:
        """Callback when text area is edited."""
        pass

    def _zoom_in(self) -> None:
        self.pdf_panel.zoom_in()
        self._update_doc_info()

    def _zoom_out(self) -> None:
        self.pdf_panel.zoom_out()
        self._update_doc_info()

    def _zoom_reset(self) -> None:
        self.pdf_panel.zoom_reset()
        self._update_doc_info()

    def _fit_to_width(self) -> None:
        self.pdf_panel.fit_to_width()
        self._update_doc_info()

    def _update_doc_info(self) -> None:
        """Update right-side status label with current page and zoom."""
        if self.reader and self.reader.is_open and self.reader.page_count > 0:
            zoom_pct = int(self.pdf_panel.zoom * 100)
            self.lbl_doc_info.config(
                text=f"Page {self.pdf_panel.current_page + 1} of {self.reader.page_count} | Zoom: {zoom_pct}%"
            )
        else:
            self.lbl_doc_info.config(text="")

    def _on_page_up_key(self, _event) -> None:
        if self.root.focus_get() != self.text_panel.text_box:
            self.pdf_panel.prev_page()

    def _on_page_down_key(self, _event) -> None:
        if self.root.focus_get() != self.text_panel.text_box:
            self.pdf_panel.next_page()

    def _on_home_key(self, _event) -> None:
        if self.root.focus_get() != self.text_panel.text_box:
            self.pdf_panel.first_page()

    def _on_end_key(self, _event) -> None:
        if self.root.focus_get() != self.text_panel.text_box:
            self.pdf_panel.last_page()

    def _show_about(self) -> None:
        """Show About dialog."""
        ocr_status = "Available (RapidOCR)" if is_ocr_available() else "Not Installed"
        messagebox.showinfo(
            "About PDF Text Extractor",
            f"PDF Text Extractor\n\n"
            f"A GUI and CLI utility to view PDFs and extract editable text.\n"
            f"OCR Support: {ocr_status}\n\n"
            f"Powered by PyMuPDF, Tkinter, and RapidOCR."
        )

    def on_exit(self) -> None:
        """Handle window close."""
        self.reader.close()
        self.root.destroy()

    def run(self) -> None:
        """Start the GUI main loop."""
        self.root.mainloop()
