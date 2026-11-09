"""Text Extractor module for extracting and processing text from PDF documents,
with support for both vector text layers and OCR (Optical Character Recognition) for images.
"""

from pathlib import Path
from typing import List, Optional, Callable, Any
import pymupdf
from core.pdf_reader import PDFReader

_OCR_ENGINE: Optional[Any] = None
_OCR_CHECKED: bool = False
_OCR_AVAILABLE: bool = False


def is_ocr_available() -> bool:
    """Check if the OCR engine (rapidocr_onnxruntime) is installed and available."""
    global _OCR_CHECKED, _OCR_AVAILABLE
    if not _OCR_CHECKED:
        try:
            import rapidocr_onnxruntime  # noqa: F401
            import numpy  # noqa: F401
            _OCR_AVAILABLE = True
        except ImportError:
            _OCR_AVAILABLE = False
        _OCR_CHECKED = True
    return _OCR_AVAILABLE


def get_ocr_engine() -> Any:
    """Get or initialize the cached RapidOCR engine instance."""
    global _OCR_ENGINE
    if not is_ocr_available():
        raise RuntimeError(
            "OCR engine is not available. Please install rapidocr-onnxruntime:\n"
            "pip install rapidocr-onnxruntime"
        )
    if _OCR_ENGINE is None:
        from rapidocr_onnxruntime import RapidOCR
        _OCR_ENGINE = RapidOCR()
    return _OCR_ENGINE


class TextExtractor:
    """Handles extracting and exporting text from PyMuPDF documents."""

    @staticmethod
    def extract_page_vector_text(page: pymupdf.Page, sort: bool = True) -> str:
        """Extract text from a single pymupdf Page using embedded vector text."""
        return page.get_text("text", sort=sort)

    @classmethod
    def extract_page_ocr_text(cls, page: pymupdf.Page, dpi: int = 150) -> str:
        """Extract text from a single pymupdf Page using OCR on the rendered image."""
        import numpy as np

        engine = get_ocr_engine()
        pix = page.get_pixmap(dpi=dpi)
        img_np = np.frombuffer(pix.samples, dtype=np.uint8).reshape((pix.height, pix.width, 3))

        result, _ = engine(img_np)
        if not result:
            return ""

        lines = [item[1] for item in result]
        return "\n".join(lines)

    @classmethod
    def extract_page_text(
        cls,
        page: pymupdf.Page,
        sort: bool = True,
        use_ocr: bool = False,
        dpi: int = 150
    ) -> str:
        """Extract text from a single page using vector extraction or OCR."""
        if use_ocr:
            ocr_text = cls.extract_page_ocr_text(page, dpi=dpi).strip()
            if ocr_text:
                return ocr_text
            # Fallback to vector text if OCR detected nothing
            return cls.extract_page_vector_text(page, sort=sort).strip()

        return cls.extract_page_vector_text(page, sort=sort).strip()

    @classmethod
    def extract_all_text(
        cls,
        reader_or_doc: PDFReader | pymupdf.Document,
        include_page_headers: bool = True,
        sort: bool = True,
        use_ocr: bool = False,
        dpi: int = 150,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> str:
        """Extract text from all pages in the PDF document.

        Args:
            reader_or_doc: A PDFReader instance or pymupdf Document.
            include_page_headers: If True, prepend '--- Page N of M ---' to each page.
            sort: If True, sort characters in reading order.
            use_ocr: If True, use OCR to recognize text inside images.
            dpi: Resolution for page rendering when performing OCR.
            progress_callback: Optional callback receiving (current_page, total_pages).

        Returns:
            The combined extracted text of the entire document.
        """
        doc = reader_or_doc.document if isinstance(reader_or_doc, PDFReader) else reader_or_doc
        if doc is None or doc.is_closed:
            raise RuntimeError("PDF document is not open.")

        total_pages = len(doc)
        extracted_sections: List[str] = []

        for idx, page in enumerate(doc):
            page_text = cls.extract_page_text(page, sort=sort, use_ocr=use_ocr, dpi=dpi)

            if include_page_headers:
                header = f"--- Page {idx + 1} of {total_pages} ---"
                section = f"{header}\n{page_text}" if page_text else f"{header}\n(No text content detected on this page)"
            else:
                section = page_text

            extracted_sections.append(section)

            if progress_callback is not None:
                progress_callback(idx + 1, total_pages)

        return "\n\n".join(extracted_sections)

    @classmethod
    def extract_page_range(
        cls,
        reader_or_doc: PDFReader | pymupdf.Document,
        page_indices: List[int],
        include_page_headers: bool = True,
        sort: bool = True,
        use_ocr: bool = False,
        dpi: int = 150,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> str:
        """Extract text from specific page indices (0-indexed)."""
        doc = reader_or_doc.document if isinstance(reader_or_doc, PDFReader) else reader_or_doc
        if doc is None or doc.is_closed:
            raise RuntimeError("PDF document is not open.")

        total_pages = len(doc)
        extracted_sections: List[str] = []

        for count, idx in enumerate(page_indices, start=1):
            if 0 <= idx < total_pages:
                page = doc.load_page(idx)
                page_text = cls.extract_page_text(page, sort=sort, use_ocr=use_ocr, dpi=dpi)
                if include_page_headers:
                    header = f"--- Page {idx + 1} of {total_pages} ---"
                    section = f"{header}\n{page_text}" if page_text else f"{header}\n(No text content detected on this page)"
                else:
                    section = page_text
                extracted_sections.append(section)

            if progress_callback is not None:
                progress_callback(count, len(page_indices))

        return "\n\n".join(extracted_sections)

    @staticmethod
    def detect_image_reliance(reader_or_doc: PDFReader | pymupdf.Document) -> bool:
        """Check if the document contains images and has very sparse vector text."""
        doc = reader_or_doc.document if isinstance(reader_or_doc, PDFReader) else reader_or_doc
        if doc is None or doc.is_closed or len(doc) == 0:
            return False

        has_images = False
        total_text_len = 0
        pages_to_check = min(len(doc), 5)

        for i in range(pages_to_check):
            page = doc[i]
            if len(page.get_images()) > 0:
                has_images = True
            total_text_len += len(page.get_text().strip())

        avg_text_len = total_text_len / pages_to_check
        # If there are images and average vector text per page is under 120 chars, it's likely image-based
        return has_images and (avg_text_len < 120)

    @staticmethod
    def parse_page_range_string(range_str: str, total_pages: int) -> List[int]:
        """Parse page range strings like '1,3-5,7' into 0-indexed integer list."""
        pages = set()
        for part in range_str.split(","):
            part = part.strip()
            if not part:
                continue
            if "-" in part:
                start_str, end_str = part.split("-", 1)
                start = max(1, int(start_str.strip()))
                end = min(total_pages, int(end_str.strip()))
                for p in range(start, end + 1):
                    pages.add(p - 1)
            else:
                p = int(part)
                if 1 <= p <= total_pages:
                    pages.add(p - 1)
        return sorted(list(pages))

    @staticmethod
    def save_text_to_file(text: str, output_path: str | Path) -> None:
        """Save extracted text to a file using UTF-8 encoding."""
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
