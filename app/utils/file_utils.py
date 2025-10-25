from pathlib import Path
from typing import Iterable, List, Tuple

from fastapi import HTTPException, UploadFile, status


def ensure_pdf(upload: UploadFile) -> None:
    """التحقق من أن الملف المرفوع هو PDF."""
    content_type = (upload.content_type or "").lower()
    if not content_type.endswith("pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="يجب أن يكون الملف من نوع PDF.",
        )


def file_stats(path: Path) -> Tuple[int, str]:
    """إرجاع حجم الملف بالبَيت ونوعه البسيط للاستخدام في الاستجابات."""
    size = path.stat().st_size if path.exists() else 0
    suffix = path.suffix.lower().lstrip(".")
    return size, suffix or "bin"


def parse_page_ranges(ranges: str, total_pages: int) -> List[Tuple[int, int]]:
    """
    تحويل نص النطاقات (مثل 1-3,5,7-) إلى قائمة من الأزواج (بداية، نهاية).
    النهايات غير المحددة تمتد حتى آخر صفحة.
    """
    if not ranges:
        return [(1, total_pages)]

    result: List[Tuple[int, int]] = []
    segments = [segment.strip() for segment in ranges.split(",") if segment.strip()]

    for segment in segments:
        if "-" in segment:
            start_str, end_str = segment.split("-", 1)
            start = int(start_str) if start_str else 1
            end = int(end_str) if end_str else total_pages
        else:
            start = end = int(segment)

        if start < 1 or end > total_pages or start > end:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"نطاق الصفحات غير صالح: {segment}",
            )
        result.append((start, end))

    return result


def clean_temp_files(paths: Iterable[Path]) -> None:
    for path in paths:
        if path and path.exists():
            path.unlink(missing_ok=True)
