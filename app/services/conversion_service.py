from __future__ import annotations

from pathlib import Path
from typing import Iterable
from uuid import uuid4

from docx import Document as DocxDocument
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from app.storage.local import LocalStorage


class ConversionService:
    """تحويل الملفات النصية والمستندات الشائعة إلى PDF دون الاعتماد على برامج خارجية."""

    def __init__(self, storage: LocalStorage | None = None) -> None:
        self.storage = storage or LocalStorage()

    # ------------------------------------------------------------------
    def convert_to_pdf(self, source_path: Path) -> Path:
        suffix = source_path.suffix.lower()
        if suffix == ".pdf":
            return self._duplicate_pdf(source_path)
        if suffix == ".docx":
            return self._docx_to_pdf(source_path)
        if suffix in {".txt", ".md"}:
            return self._text_to_pdf(source_path)

        raise ValueError("صيغة الملف غير مدعومة للتحويل إلى PDF (يدعم DOCX وTXT وMD وPDF).")

    # ------------------------------------------------------------------
    def _duplicate_pdf(self, source_path: Path) -> Path:
        target_path = self.storage.processed_dir / f"{uuid4().hex}.pdf"
        target_path.write_bytes(source_path.read_bytes())
        return target_path

    def _docx_to_pdf(self, docx_path: Path) -> Path:
        document = DocxDocument(docx_path)
        target_path = self.storage.processed_dir / f"{uuid4().hex}.pdf"
        c = canvas.Canvas(str(target_path), pagesize=A4)
        width, height = A4
        margin = 40
        y = height - margin

        for paragraph in document.paragraphs:
            lines = self._wrap_text(paragraph.text, max_chars=90)
            if not lines:
                y -= 20
            for line in lines:
                c.drawRightString(width - margin, y, line)
                y -= 20
                if y < margin:
                    c.showPage()
                    y = height - margin

        c.save()
        return target_path

    def _text_to_pdf(self, text_path: Path) -> Path:
        content = text_path.read_text(encoding="utf-8", errors="ignore")
        target_path = self.storage.processed_dir / f"{uuid4().hex}.pdf"
        c = canvas.Canvas(str(target_path), pagesize=A4)
        width, height = A4
        margin = 40
        y = height - margin

        for line in content.splitlines():
            for chunk in self._wrap_text(line, max_chars=90):
                c.drawRightString(width - margin, y, chunk)
                y -= 20
                if y < margin:
                    c.showPage()
                    y = height - margin

        c.save()
        return target_path

    # ------------------------------------------------------------------
    @staticmethod
    def _wrap_text(text: str, max_chars: int) -> list[str]:
        stripped = (text or "").strip()
        if not stripped:
            return []
        words = stripped.split()
        lines: list[str] = []
        current: list[str] = []
        count = 0
        for word in words:
            length = len(word)
            if count + length + (1 if current else 0) > max_chars:
                lines.append(" ".join(current))
                current = [word]
                count = length
            else:
                current.append(word)
                count += length + (1 if current[:-1] else 0)
        if current:
            lines.append(" ".join(current))
        return lines or [stripped]
