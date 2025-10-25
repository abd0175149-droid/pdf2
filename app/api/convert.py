from fastapi import APIRouter, File, UploadFile

from app.core.logging import configure_logging
from app.models import ConversionCommitRequest
from app.services.conversion_service import ConversionService
from app.storage.local import LocalStorage
from app.storage.registry import get_document, register_document
from app.utils.pdf_preview import render_page_preview

router = APIRouter(prefix="/convert", tags=["Conversion"])

logger = configure_logging()
storage = LocalStorage()
conversion_service = ConversionService(storage)


def _card(entry, with_preview: bool) -> dict:
    preview = render_page_preview(entry.path, 1) if with_preview else None
    card = entry.to_card(preview=preview)
    card["is_temp"] = True
    return card


@router.post("/upload", summary="رفع ملف لتحويله إلى PDF")
async def upload_for_conversion(file: UploadFile = File(...)) -> dict:
    temp_path = storage.save_upload(file, temp=True)
    entry = register_document(temp_path, file.filename, expect_pdf=False)
    logger.info("تم رفع ملف للتحويل: %s", file.filename)
    return {"status": "ok", "file": _card(entry, with_preview=False)}


@router.post("/commit", summary="تحويل الملف إلى PDF وإرجاع بطاقة النتيجة")
async def commit_conversion(payload: ConversionCommitRequest) -> dict:
    entry = get_document(payload.file_id, require_pdf=False)
    pdf_path = conversion_service.convert_to_pdf(entry.path)
    output_name = payload.output_filename or f"{entry.path.stem}_converted.pdf"

    public_path = storage.register_public_download(pdf_path, output_name)
    result_entry = register_document(public_path, output_name, expect_pdf=True)

    card = result_entry.to_card(preview=render_page_preview(public_path, 1))
    card["download_url"] = f"/downloads/{public_path.name}"
    card["is_temp"] = False

    logger.info("تم تحويل الملف %s (%s) إلى PDF.", entry.filename, entry.extension)

    return {
        "status": "ok",
        "message": "تم تحويل الملف إلى PDF بنجاح.",
        "result": card,
    }
