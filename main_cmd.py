#!/usr/bin/env python3
"""CLI entry point for PDF Text Extractor with optional OCR support."""

import sys
import argparse
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_DIR = Path(__file__).resolve().parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from core.pdf_reader import PDFReader
from core.text_extractor import TextExtractor, is_ocr_available


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract text from a PDF file via command line (supports vector text & OCR for images).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Examples:\n"
               "  python main_cmd.py document.pdf\n"
               "  python main_cmd.py document.pdf --ocr\n"
               "  python main_cmd.py document.pdf -o output.txt\n"
               "  python main_cmd.py document.pdf -p 1-3,5 --no-headers --ocr\n"
               "  python main_cmd.py document.pdf --info\n"
    )

    parser.add_argument("input", help="Path to the PDF file")
    parser.add_argument(
        "-o", "--output",
        help="Path to output text file (if omitted, prints to standard output)",
        default=None
    )
    parser.add_argument(
        "-p", "--pages",
        help="Pages to extract (e.g., '1-5', '1,3,7', default: all)",
        default="all"
    )
    parser.add_argument(
        "--ocr",
        action="store_true",
        help="Use OCR to extract text embedded inside images in the PDF"
    )
    parser.add_argument(
        "--no-headers",
        action="store_true",
        help="Omit page separator headers ('--- Page X of Y ---')"
    )
    parser.add_argument(
        "--password",
        help="Password for encrypted PDF documents",
        default=None
    )
    parser.add_argument(
        "--info",
        action="store_true",
        help="Display PDF document metadata and page count only"
    )

    return parser.parse_args()


def main() -> int:
    args = parse_args()
    pdf_path = Path(args.input)

    if not pdf_path.exists():
        print(f"Error: PDF file '{args.input}' does not exist.", file=sys.stderr)
        return 1

    if args.ocr and not is_ocr_available():
        print(
            "Error: OCR requested but 'rapidocr-onnxruntime' is not installed.\n"
            "Run: pip install rapidocr-onnxruntime",
            file=sys.stderr
        )
        return 1

    try:
        reader = PDFReader(str(pdf_path), password=args.password)
    except Exception as e:
        print(f"Error opening PDF: {e}", file=sys.stderr)
        return 1

    try:
        if args.info:
            print(f"File: {reader.file_path}")
            print(f"Pages: {reader.page_count}")
            metadata = reader.get_metadata()
            print("Metadata:")
            for k, v in metadata.items():
                if v:
                    print(f"  {k}: {v}")
            has_img_reliance = TextExtractor.detect_image_reliance(reader)
            print(f"Image-Based Content: {'Yes (OCR recommended)' if has_img_reliance else 'No'}")
            return 0

        total_pages = reader.page_count
        if total_pages == 0:
            print("Document contains 0 pages.", file=sys.stderr)
            return 1

        include_headers = not args.no_headers

        def progress(curr, tot):
            if args.output:
                print(f"\rProcessing page {curr}/{tot}...", end="", flush=True)

        if args.pages.lower() == "all":
            extracted_text = TextExtractor.extract_all_text(
                reader,
                include_page_headers=include_headers,
                use_ocr=args.ocr,
                progress_callback=progress if args.ocr and args.output else None
            )
        else:
            page_indices = TextExtractor.parse_page_range_string(args.pages, total_pages)
            if not page_indices:
                print(f"Error: No valid pages parsed from '{args.pages}'. (Document has {total_pages} pages)", file=sys.stderr)
                return 1
            extracted_text = TextExtractor.extract_page_range(
                reader,
                page_indices,
                include_page_headers=include_headers,
                use_ocr=args.ocr,
                progress_callback=progress if args.ocr and args.output else None
            )

        if args.output:
            if args.ocr:
                print()  # newline after progress
            out_path = Path(args.output)
            TextExtractor.save_text_to_file(extracted_text, out_path)
            print(f"Successfully extracted text to: {out_path} ({len(extracted_text)} characters)")
        else:
            print(extracted_text)

        return 0

    finally:
        reader.close()


if __name__ == "__main__":
    sys.exit(main())
