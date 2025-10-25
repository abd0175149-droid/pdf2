from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Iterable, List, Sequence, Tuple

from pypdf import PdfReader, PdfWriter
from reportlab.lib.colors import Color
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from app.storage.local import LocalStorage
from app.utils.pdf_preview import render_page_preview


class PDFService:
    """خدمات أساسية للتعامل مع ملفات PDF (دمج، تقسيم، وإضافة علامات مائية)."""

    def __init__(self, storage: LocalStorage | None = None) -> None:
        self.storage = storage or LocalStorage()

    # ------------------------------------------------------------------
    # دمج ملفات PDF
    # ------------------------------------------------------------------
    def merge(self, pdf_paths: Sequence[Path]) -> Path:
        writer = PdfWriter()
        for path in pdf_paths:
            reader = PdfReader(str(path))
            for page in reader.pages:
                writer.add_page(page)
        return self._write_writer(writer)

    # ------------------------------------------------------------------
    # تقسيم ملف PDF إلى نطاقات متعددة
    # ------------------------------------------------------------------
    def split(
        self,
        pdf_path: Path,
        ranges: List[Tuple[int, int]],
        separate_files: bool = False,
    ) -> List[Path]:
        reader = PdfReader(str(pdf_path))
        outputs: List[Path] = []

        if separate_files:
            for start, end in ranges:
                writer = PdfWriter()
                for page_number in range(start - 1, end):
                    writer.add_page(reader.pages[page_number])
                outputs.append(self._write_writer(writer))
        else:
            writer = PdfWriter()
            for start, end in ranges:
                for page_number in range(start - 1, end):
                    writer.add_page(reader.pages[page_number])
            outputs.append(self._write_writer(writer))

        return outputs

    # ------------------------------------------------------------------
    # إضافة علامة مائية نصية بسيطة
    # ------------------------------------------------------------------
    def add_text_watermark(
        self,
        pdf_path: Path,
        text: str,
        opacity: float = 0.3,
        position: str = "center",
        font_size: int | None = None,
    ) -> Path:
        reader = PdfReader(str(pdf_path))
        writer = PdfWriter()

        for page in reader.pages:
            width = float(page.mediabox.width)
            height = float(page.mediabox.height)
            watermark_pdf = self._create_watermark_page(
                width=width,
                height=height,
                text=text,
                opacity=opacity,
                position=position,
                font_size=font_size,
            )
            watermark_page = watermark_pdf.pages[0]
            page.merge_page(watermark_page)
            writer.add_page(page)

        return self._write_writer(writer)

    def preview_text_watermark(
        self,
        pdf_path: Path,
        text: str,
        opacity: float = 0.3,
        position: str = "center",
        font_size: int | None = None,
    ) -> str:
        temp_path = self.add_text_watermark(
            pdf_path=pdf_path,
            text=text,
            opacity=opacity,
            position=position,
            font_size=font_size,
        )
        try:
            return render_page_preview(temp_path, page_number=1)
        finally:
            temp_path.unlink(missing_ok=True)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _write_writer(self, writer: PdfWriter) -> Path:
        buffer = BytesIO()
        writer.write(buffer)
        buffer.seek(0)
        return self.storage.save_bytes(buffer.getvalue(), suffix=".pdf")

    @staticmethod
    def _create_watermark_page(
        width: float,
        height: float,
        text: str,
        opacity: float,
        position: str,
        font_size: int | None = None,
    ) -> PdfReader:
        packet = BytesIO()
        page_size = (width, height) if width and height else letter
        c = canvas.Canvas(packet, pagesize=page_size)

        try:
            c.setFillAlpha(opacity)
        except AttributeError:  # pragma: no cover - لإصدارات ReportLab القديمة
            pass

        grey = Color(0.4, 0.4, 0.4, alpha=opacity)
        c.setFillColor(grey)

        font_size = font_size or max(24, int(min(page_size) / 10))
        c.setFont("Helvetica-Bold", font_size)

        if position == "diagonal":
            PDFService._draw_diagonal_watermark(c, text, page_size)
        elif position == "tile":
            PDFService._draw_tiled_watermark(c, text, page_size, font_size)
        else:
            PDFService._draw_centered_watermark(c, text, page_size, font_size, position)

        c.save()
        packet.seek(0)
        return PdfReader(packet)

    @staticmethod
    def _draw_centered_watermark(
        canvas_: canvas.Canvas,
        text: str,
        page_size: Tuple[float, float],
        font_size: int,
        position: str,
    ) -> None:
        width, height = page_size
        x = width / 2
        if position == "top":
            y = height - font_size * 2
        elif position == "bottom":
            y = font_size * 2
        else:
            y = height / 2
        canvas_.drawCentredString(x, y, text)

    @staticmethod
    def _draw_diagonal_watermark(canvas_: canvas.Canvas, text: str, page_size: Tuple[float, float]) -> None:
        width, height = page_size
        canvas_.saveState()
        canvas_.translate(width / 2, height / 2)
        canvas_.rotate(45)
        canvas_.drawCentredString(0, 0, text)
        canvas_.restoreState()

    @staticmethod
    def _draw_tiled_watermark(
        canvas_: canvas.Canvas,
        text: str,
        page_size: Tuple[float, float],
        font_size: int,
    ) -> None:
        width, height = page_size
        step_x = max(font_size * len(text) * 0.8, 100)
        step_y = font_size * 2
        angle = 30

        for x in PDFService._frange(-width, width * 2, step_x):
            for y in PDFService._frange(-height, height * 2, step_y):
                canvas_.saveState()
                canvas_.translate(x, y)
                canvas_.rotate(angle)
                canvas_.drawString(0, 0, text)
                canvas_.restoreState()

    @staticmethod
    def _frange(start: float, stop: float, step: float) -> Iterable[float]:
        value = start
        while value < stop:
            yield value
            value += step
