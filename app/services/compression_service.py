from __future__ import annotations

from io import BytesIO
from pathlib import Path

import fitz  # PyMuPDF

from app.storage.local import LocalStorage


class CompressionService:
    """ضغط ملفات PDF باستخدام PyMuPDF مع مستويات جودة متعددة."""

    LEVEL_OPTIONS = {
        "low": dict(garbage=1, deflate=True, deflate_fonts=True, deflate_images=True, clean=False),
        "medium": dict(garbage=2, deflate=True, deflate_fonts=True, deflate_images=True, clean=True),
        "high": dict(garbage=4, deflate=True, deflate_fonts=True, deflate_images=True, clean=True),
    }

    def __init__(self, storage: LocalStorage | None = None) -> None:
        self.storage = storage or LocalStorage()

    def compress(self, pdf_path: Path, level: str = "medium") -> Path:
        options = self.LEVEL_OPTIONS.get(level.lower(), self.LEVEL_OPTIONS["medium"])

        with fitz.open(pdf_path) as document:
            pdf_bytes = document.tobytes(**options)

        return self.storage.save_bytes(pdf_bytes, suffix=".pdf")
