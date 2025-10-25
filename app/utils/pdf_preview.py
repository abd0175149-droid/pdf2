import base64
from pathlib import Path
from typing import Optional

import fitz  # PyMuPDF


def render_page_preview(
    pdf_path: Path,
    page_number: int = 1,
    zoom: float = 1.5,
    background: Optional[tuple[int, int, int]] = (255, 255, 255),
) -> str:
    """
    إنشاء صورة مصغرة للصفحة المحددة داخل ملف PDF وإرجاعها كسلسلة base64.

    Args:
        pdf_path: المسار إلى ملف PDF.
        page_number: رقم الصفحة (يبدأ من 1).
        zoom: معامل التكبير للحصول على جودة أفضل.
        background: لون الخلفية RGB للصفحات الشفافة.
    """
    if page_number < 1:
        raise ValueError("page_number must be >= 1")

    with fitz.open(pdf_path) as document:
        if page_number > document.page_count:
            raise ValueError("page_number exceeds document pages")

        page = document.load_page(page_number - 1)
        matrix = fitz.Matrix(zoom, zoom)
        pixmap = page.get_pixmap(matrix=matrix, alpha=False)

        if background and pixmap.alpha:  # pragma: no cover - يحتمل أن تكون شفافة
            pixmap = fitz.Pixmap(fitz.csRGB, pixmap)

        image_bytes = pixmap.tobytes("png")

    encoded = base64.b64encode(image_bytes).decode("utf-8")
    return f"data:image/png;base64,{encoded}"
