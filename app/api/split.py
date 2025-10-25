from pathlib import Path
from typing import List
from uuid import uuid4

from fastapi import APIRouter, File, HTTPException, UploadFile, status

from app.core.logging import configure_logging
from app.models import PagePreviewRequest, SplitCommitRequest
from app.services.pdf_service import PDFService
from app.storage.local import LocalStorage
from app.storage.registry import get_document, register_document
from app.utils.file_utils import ensure_pdf
from app.utils.pdf_preview import render_page_preview

router = APIRouter(prefix="/pdf/split", tags=["PDF Split"])

logger = configure_logging()
storage = LocalStorage()
pdf_service = PDFService(storage)


def _card(entry, *, temp: bool = True) -> dict:
    preview = render_page_preview(entry.path, page_number=1)
    card = entry.to_card(preview=preview)
    card["is_temp"] = temp
    return card


@router.post("/upload", summary="رفع ملف PDF لتجهيز بيانات التقسيم")
async def upload_pdf(file: UploadFile = File(...)) -> dict:
    ensure_pdf(file)
    temp_path = storage.save_upload(file, temp=True)
    entry = register_document(temp_path, file.filename, expect_pdf=True)
    logger.info("تم تسجيل ملف للتقسيم: %s", file.filename)
    return {
        "status": "ok",
        "file": _card(entry),
        "page_count": entry.page_count,
    }


@router.post("/page-preview", summary="إرجاع معاينات للصفحات المطلوبة داخل الملف")
async def page_preview(payload: PagePreviewRequest) -> dict:
    entry = get_document(payload.file_id, require_pdf=True)
    previews: List[dict] = []

    for page in payload.pages:
        if page < 1 or page > entry.page_count:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"رقم الصفحة {page} خارج نطاق الملف ({entry.page_count} صفحة).",
            )
        previews.append({"page": page, "preview": render_page_preview(entry.path, page)})

    return {
        "status": "ok",
        "pages": previews,
        "page_count": entry.page_count,
    }


@router.post("/commit", summary="تنفيذ عملية التقسيم وإرجاع الملفات الناتجة")
async def commit_split(payload: SplitCommitRequest) -> dict:
    entry = get_document(payload.file_id, require_pdf=True)
    ranges = [(r.start, r.end) for r in payload.ranges]

    for start, end in ranges:
        if start < 1 or end > entry.page_count:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"المدى ({start}-{end}) خارج نطاق عدد الصفحات ({entry.page_count}).",
            )

    logger.info("تنفيذ تقسيم للملف %s مع المديات %s", entry.filename, ranges)

    output_paths = pdf_service.split(entry.path, ranges, payload.separate_files)
    result_cards: List[dict] = []

    if payload.separate_files:
        grouped = zip(output_paths, ranges)
    else:
        combined_range = (ranges[0][0], ranges[-1][1])
        grouped = [(output_paths[0], combined_range)]

    base_stem = Path(entry.filename or "split").stem
    for index, (chunk_path, page_range) in enumerate(grouped, start=1):
        if payload.separate_files:
            range_label = f"{page_range[0]}-{page_range[1]}"
            display_name = f"{base_stem}_{range_label}_{uuid4().hex[:6]}.pdf"
        else:
            display_name = f"{base_stem}_combined_{uuid4().hex[:6]}.pdf"

        public_path = storage.register_public_download(chunk_path, display_name)
        result_entry = register_document(public_path, display_name, expect_pdf=True)
        preview = render_page_preview(public_path, 1)
        card = result_entry.to_card(preview=preview)
        card.update(
            {
                "download_url": f"/downloads/{public_path.name}",
                "range": {"start": page_range[0], "end": page_range[1]},
                "index": index,
                "is_temp": False,
            }
        )
        if not payload.separate_files:
            card["ranges"] = [{"start": r.start, "end": r.end} for r in payload.ranges]
        result_cards.append(card)

    return {
        "status": "ok",
        "message": "تم تقسيم الملف بنجاح.",
        "original": _card(entry, temp=True),
        "results": result_cards,
        "separate_files": payload.separate_files,
    }
