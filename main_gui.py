#!/usr/bin/env python3
"""GUI entry point for PDF Text Extractor."""

import sys
from pathlib import Path

# Ensure the project directory is on sys.path
PROJECT_DIR = Path(__file__).resolve().parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from gui.app import PDFExtractorApp


def main() -> None:
    initial_file = sys.argv[1] if len(sys.argv) > 1 else None
    app = PDFExtractorApp(initial_file=initial_file)
    app.run()


if __name__ == "__main__":
    main()
