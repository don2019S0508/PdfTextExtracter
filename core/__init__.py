"""Core package for PDF reading and text extraction."""

from core.pdf_reader import PDFReader
from core.text_extractor import TextExtractor, is_ocr_available

__all__ = ["PDFReader", "TextExtractor", "is_ocr_available"]
