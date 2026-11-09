"""GUI component for viewing PDF pages with vertical page slider, pan, and zoom controls."""

import tkinter as tk
from tkinter import ttk
from typing import Optional, Callable
from PIL import ImageTk, Image
from core.pdf_reader import PDFReader


class PDFPanel(ttk.Frame):
    """Clean PDF displaying panel with a vertical page slider along the right edge."""

    def __init__(
        self,
        master: tk.Widget,
        on_page_change: Optional[Callable[[int, int], None]] = None,
        **kwargs
    ):
        super().__init__(master, **kwargs)

        self.reader: Optional[PDFReader] = None
        self.current_page: int = 0  # 0-indexed
        self.zoom: float = 1.3
        self.on_page_change = on_page_change

        self._photo_image: Optional[ImageTk.PhotoImage] = None
        self._image_item_id: Optional[int] = None
        self._current_image_size: Optional[tuple[int, int]] = None
        self._is_updating_slider: bool = False

        self._build_ui()

    def _build_ui(self) -> None:
        """Construct displaying panel layout expanding all the way to the top."""
        # Main displaying container filling entire panel space
        self.canvas_frame = ttk.Frame(self)
        self.canvas_frame.pack(fill=tk.BOTH, expand=True)

        # Vertical Page Sliding Bar: Controls page navigation directly from the display panel
        self.v_page_slider = tk.Scale(
            self.canvas_frame,
            from_=1,
            to=1,
            orient=tk.VERTICAL,
            resolution=1,
            tickinterval=1,
            width=16,
            sliderlength=26,
            showvalue=True,
            font=("TkDefaultFont", 8),
            highlightthickness=0,
            bd=1,
            relief=tk.GROOVE,
            command=self._on_vertical_slider_moved
        )
        self.v_page_slider.pack(side=tk.RIGHT, fill=tk.Y, padx=(2, 2), pady=2)

        # Horizontal scrollbar at bottom for wide/zoomed pages
        self.h_scroll = ttk.Scrollbar(self.canvas_frame, orient=tk.HORIZONTAL)
        self.h_scroll.pack(side=tk.BOTTOM, fill=tk.X)

        # Canvas for displaying rendered PDF page
        self.canvas = tk.Canvas(
            self.canvas_frame,
            bg="#2e2e2e",
            highlightthickness=0,
            xscrollcommand=self.h_scroll.set,
            cursor="fleur"
        )
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.h_scroll.config(command=self.canvas.xview)

        # Mouse wheel bindings: scroll within page, flip pages at boundary, or Ctrl+scroll to zoom
        self.canvas.bind("<MouseWheel>", self._on_mousewheel)
        self.canvas.bind("<Button-4>", self._on_mousewheel_linux_up)
        self.canvas.bind("<Button-5>", self._on_mousewheel_linux_down)

        # Canvas click & drag to pan (Hand tool)
        self.canvas.bind("<ButtonPress-1>", self._on_pan_start)
        self.canvas.bind("<B1-Motion>", self._on_pan_drag)

        # Dynamic centering and scroll region adjustment on resize
        self.canvas.bind("<Configure>", self._on_canvas_resize)

        self._update_controls_state()
        self._show_placeholder("No PDF loaded. Open a file to begin.")

    def set_reader(self, reader: Optional[PDFReader]) -> None:
        """Set or reset the PDFReader instance and configure the vertical page slider."""
        self.reader = reader
        self.current_page = 0
        has_doc = self.reader is not None and self.reader.is_open and self.reader.page_count > 0

        if has_doc:
            total = self.reader.page_count
            tick = 1
            if total > 50:
                tick = total // 10
            elif total > 20:
                tick = 5
            elif total > 10:
                tick = 2

            self.v_page_slider.config(from_=1, to=max(1, total), tickinterval=tick)

            self._is_updating_slider = True
            try:
                self.v_page_slider.set(1)
            finally:
                self._is_updating_slider = False

            self._render_current_page()
        else:
            self.canvas.delete("all")
            self._image_item_id = None
            self._current_image_size = None
            self.v_page_slider.config(from_=1, to=1, tickinterval=1)
            self._is_updating_slider = True
            try:
                self.v_page_slider.set(1)
            finally:
                self._is_updating_slider = False
            self._show_placeholder("No PDF loaded. Open a file to begin.")

        self._update_controls_state()

    def _render_current_page(self, skip_slider_update: bool = False) -> None:
        """Render the current page onto the canvas and synchronize the vertical slider."""
        if not self.reader or not self.reader.is_open:
            return

        try:
            pil_image = self.reader.render_page(self.current_page, zoom=self.zoom)
            self._photo_image = ImageTk.PhotoImage(pil_image)
            self._current_image_size = pil_image.size

            self.canvas.delete("all")
            img_w, img_h = pil_image.size
            canvas_w = max(self.canvas.winfo_width(), 1)
            canvas_h = max(self.canvas.winfo_height(), 1)

            x = max(img_w // 2, canvas_w // 2)
            y = max(img_h // 2, canvas_h // 2)

            self._image_item_id = self.canvas.create_image(x, y, image=self._photo_image, anchor=tk.CENTER)
            self.canvas.config(scrollregion=(0, 0, max(img_w, canvas_w), max(img_h, canvas_h)))

            # Reset canvas view to top-center when landing on a new page
            self.canvas.yview_moveto(0.0)

            if not skip_slider_update:
                self._is_updating_slider = True
                try:
                    self.v_page_slider.set(self.current_page + 1)
                finally:
                    self._is_updating_slider = False

            if self.on_page_change:
                self.on_page_change(self.current_page + 1, self.reader.page_count)

        except Exception as e:
            self.canvas.delete("all")
            self._image_item_id = None
            self._current_image_size = None
            self._show_placeholder(f"Failed to render page: {e}")

        self._update_controls_state()

    def _on_vertical_slider_moved(self, value: str) -> None:
        """Handle vertical page slider movements to move between pages."""
        if self._is_updating_slider or not self.reader or not self.reader.is_open or self.reader.page_count <= 1:
            return
        try:
            page_num = int(round(float(value)))
            target_idx = max(0, min(page_num - 1, self.reader.page_count - 1))
            if target_idx != self.current_page:
                self.current_page = target_idx
                self._render_current_page(skip_slider_update=True)
        except (ValueError, TypeError):
            pass

    def _on_canvas_resize(self, _event=None) -> None:
        """Adjust image positioning and scroll region when panel is resized."""
        if self._image_item_id and self._current_image_size:
            img_w, img_h = self._current_image_size
            canvas_w = self.canvas.winfo_width()
            canvas_h = self.canvas.winfo_height()

            x = max(img_w // 2, canvas_w // 2)
            y = max(img_h // 2, canvas_h // 2)

            self.canvas.coords(self._image_item_id, x, y)
            self.canvas.config(scrollregion=(0, 0, max(img_w, canvas_w), max(img_h, canvas_h)))

    def _on_pan_start(self, event) -> None:
        """Start drag-to-pan."""
        self.canvas.scan_mark(event.x, event.y)

    def _on_pan_drag(self, event) -> None:
        """Drag-to-pan in all directions."""
        self.canvas.scan_dragto(event.x, event.y, gain=1)

    def _show_placeholder(self, message: str) -> None:
        """Show placeholder text in canvas."""
        self.canvas.delete("all")
        w = max(self.canvas.winfo_width(), 400)
        h = max(self.canvas.winfo_height(), 400)
        self.canvas.create_text(
            w // 2, h // 2,
            text=message,
            fill="#dcdcdc",
            font=("TkDefaultFont", 11),
            justify=tk.CENTER
        )
        self.canvas.config(scrollregion=(0, 0, w, h))

    def _update_controls_state(self) -> None:
        """Enable or disable controls according to document status."""
        has_doc = self.reader is not None and self.reader.is_open and self.reader.page_count > 0
        state_slider = tk.NORMAL if (has_doc and self.reader.page_count > 1) else tk.DISABLED
        self.v_page_slider.config(state=state_slider)

    def prev_page(self) -> None:
        """Navigate to previous page."""
        if self.reader and self.current_page > 0:
            self.current_page -= 1
            self._render_current_page()

    def next_page(self) -> None:
        """Navigate to next page."""
        if self.reader and self.current_page < self.reader.page_count - 1:
            self.current_page += 1
            self._render_current_page()

    def first_page(self) -> None:
        """Navigate to the first page."""
        if self.reader and self.current_page != 0:
            self.current_page = 0
            self._render_current_page()

    def last_page(self) -> None:
        """Navigate to the last page."""
        if self.reader and self.current_page != self.reader.page_count - 1:
            self.current_page = self.reader.page_count - 1
            self._render_current_page()

    def goto_page(self, page_number: int) -> None:
        """Go to a specific 1-indexed page number."""
        if not self.reader or self.reader.page_count == 0:
            return
        idx = max(0, min(page_number - 1, self.reader.page_count - 1))
        if idx != self.current_page:
            self.current_page = idx
            self._render_current_page()

    def zoom_in(self) -> None:
        """Increase render zoom."""
        if self.zoom < 3.0:
            self.zoom = round(self.zoom + 0.2, 2)
            self._render_current_page(skip_slider_update=True)

    def zoom_out(self) -> None:
        """Decrease render zoom."""
        if self.zoom > 0.4:
            self.zoom = round(self.zoom - 0.2, 2)
            self._render_current_page(skip_slider_update=True)

    def zoom_reset(self) -> None:
        """Reset render zoom to 100%."""
        self.zoom = 1.0
        self._render_current_page(skip_slider_update=True)

    def fit_to_width(self) -> None:
        """Scale current page to fit the visible width of the canvas."""
        if not self.reader or not self.reader.is_open or self.reader.page_count == 0:
            return
        page = self.reader.get_page(self.current_page)
        canvas_w = max(100, self.canvas.winfo_width() - 25)
        page_w = page.rect.width
        if page_w > 0:
            new_zoom = max(0.4, min(3.0, canvas_w / page_w))
            self.zoom = round(new_zoom, 2)
            self._render_current_page(skip_slider_update=True)

    def _on_mousewheel(self, event) -> None:
        """Windows/macOS scroll: Ctrl+Scroll to zoom, or scroll/flip page."""
        if event.state & 0x0004:  # Control key pressed
            if event.delta > 0:
                self.zoom_in()
            else:
                self.zoom_out()
        else:
            if event.delta < 0:
                self._scroll_or_advance_next()
            else:
                self._scroll_or_retreat_prev()

    def _on_mousewheel_linux_up(self, event) -> None:
        """Linux scroll up: Ctrl+Scroll to zoom in, or scroll/flip to prev page."""
        if event.state & 0x0004:  # Control key
            self.zoom_in()
        else:
            self._scroll_or_retreat_prev()

    def _on_mousewheel_linux_down(self, event) -> None:
        """Linux scroll down: Ctrl+Scroll to zoom out, or scroll/flip to next page."""
        if event.state & 0x0004:  # Control key
            self.zoom_out()
        else:
            self._scroll_or_advance_next()

    def _scroll_or_advance_next(self) -> None:
        """Advance to next page if canvas is at bottom, else scroll down."""
        y_top, y_bot = self.canvas.yview()
        if y_bot >= 0.98 or (y_top <= 0.01 and y_bot >= 0.98):
            self.next_page()
        else:
            self.canvas.yview_scroll(3, "units")

    def _scroll_or_retreat_prev(self) -> None:
        """Go to previous page if canvas is at top, else scroll up."""
        y_top, _ = self.canvas.yview()
        if y_top <= 0.02:
            self.prev_page()
        else:
            self.canvas.yview_scroll(-3, "units")
