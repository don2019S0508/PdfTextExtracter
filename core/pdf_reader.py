"""PDF Reader module using PyMuPDF to open, inspect, and render PDF pages."""

from pathlib import Path
from typing import Optional, Dict, Any
import pymupdf
from PIL import Image


class PDFReader:
    """Manages opening, inspecting, and rendering pages of a PDF document."""

    def __init__(self, file_path: Optional[str] = None, password: Optional[str] = None):
        self._doc: Optional[pymupdf.Document] = None
        self._file_path: Optional[str] = None
        if file_path:
            self.open(file_path, password)

    def open(self, file_path: str, password: Optional[str] = None) -> None:
        """Open a PDF file with optional password."""
        path = Path(file_path)
        if not path.is_file():
            raise FileNotFoundError(f"PDF file not found: {file_path}")

        self.close()
        doc = pymupdf.open(str(path))

        if doc.is_encrypted:
            if password is None:
                raise ValueError("PDF is password-protected. Please provide a password.")
            if not doc.authenticate(password):
                doc.close()
                raise ValueError("Incorrect password for protected PDF.")

        self._doc = doc
        self._file_path = str(path.resolve())

    def close(self) -> None:
        """Close the currently open PDF document."""
        if self._doc is not None:
            self._doc.close()
            self._doc = None
            self._file_path = None

    @property
    def is_open(self) -> bool:
        """Check if a PDF document is currently open."""
        return self._doc is not None and not self._doc.is_closed

    @property
    def file_path(self) -> Optional[str]:
        """Return the absolute path of the open PDF document."""
        return self._file_path

    @property
    def page_count(self) -> int:
        """Return the total number of pages."""
        if not self.is_open:
            return 0
        return len(self._doc)

    @property
    def document(self) -> Optional[pymupdf.Document]:
        """Return the underlying pymupdf Document instance."""
        return self._doc

    def get_metadata(self) -> Dict[str, Any]:
        """Return metadata of the opened PDF document."""
        if not self.is_open:
            return {}
        return dict(self._doc.metadata or {})

    def get_page(self, page_index: int) -> pymupdf.Page:
        """Retrieve a specific page object (0-indexed)."""
        if not self.is_open:
            raise RuntimeError("No PDF document currently open.")
        if page_index < 0 or page_index >= self.page_count:
            raise IndexError(f"Page index {page_index} out of range [0, {self.page_count - 1}].")
        return self._doc.load_page(page_index)

    def render_page(self, page_index: int, zoom: float = 1.5) -> Image.Image:
        """Render a PDF page as a PIL Image at the specified zoom/scaling factor."""
        page = self.get_page(page_index)
        matrix = pymupdf.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=matrix, alpha=False)
        img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        return img

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
