from fastapi import APIRouter, File, HTTPException, UploadFile

from app.core.logging import configure_logging
from app.models import WatermarkCommitRequest, WatermarkOptions
from app.services.pdf_service import PDFService
from app.storage.local import LocalStorage
from app.storage.registry import get_document, register_document
from app.utils.file_utils import ensure_pdf
from app.utils.pdf_preview import render_page_preview

router = APIRouter(prefix="/pdf/watermark", tags=["PDF Watermark"])

logger = configure_logging()
storage = LocalStorage()
pdf_service = PDFService(storage)

ALLOWED_POSITIONS = {"center", "top", "bottom", "diagonal", "tile"}


def _card(entry) -> dict:
    preview = render_page_preview(entry.path, 1)
    card = entry.to_card(preview=preview)
    card["is_temp"] = True
    return card


def _validate_options(options: WatermarkOptions) -> None:
    if options.position not in ALLOWED_POSITIONS:
        raise HTTPException(
            status_code=400,
            detail=f"موضع العلامة المائية غير مدعوم. الخيارات المتاحة: {', '.join(ALLOWED_POSITIONS)}.",
        )
    if not (0 < options.opacity <= 1):
        raise HTTPException(status_code=400, detail="يجب أن تكون قيمة الشفافية بين 0 و 1.")


@router.post("/upload", summary="رفع ملف لتحضير تطبيق العلامة المائية")
async def upload_pdf(file: UploadFile = File(...)) -> dict:
    ensure_pdf(file)
    temp_path = storage.save_upload(file, temp=True)
    entry = register_document(temp_path, file.filename, expect_pdf=True)
    logger.info("تم رفع ملف للعلامة المائية: %s", file.filename)
    return {"status": "ok", "file": _card(entry)}


@router.post("/preview", summary="عرض معاينة فورية للعلامة المائية")
async def preview_watermark(options: WatermarkOptions) -> dict:
    _validate_options(options)
    entry = get_document(options.file_id, require_pdf=True)
    preview_image = pdf_service.preview_text_watermark(
        entry.path,
        text=options.text,
        opacity=options.opacity,
        position=options.position,
        font_size=options.font_size or None,
    )
    return {
        "status": "ok",
        "preview": preview_image,
    }


@router.post("/commit", summary="تطبيق العلامة المائية وإرجاع ملف جديد")
async def commit_watermark(payload: WatermarkCommitRequest) -> dict:
    _validate_options(payload)
    entry = get_document(payload.file_id, require_pdf=True)

    result_path = pdf_service.add_text_watermark(
        entry.path,
        text=payload.text,
        opacity=payload.opacity,
        position=payload.position,
        font_size=payload.font_size or None,
    )

    output_name = payload.output_filename or f"{entry.path.stem}_wm.pdf"
    public_path = storage.register_public_download(result_path, output_name)
    result_entry = register_document(public_path, output_name, expect_pdf=True)

    card = result_entry.to_card(preview=render_page_preview(public_path, 1))
    card["download_url"] = f"/downloads/{public_path.name}"
    card["is_temp"] = False

    logger.info("تم تطبيق العلامة المائية على الملف %s", entry.filename)

    return {
        "status": "ok",
        "message": "تم تطبيق العلامة المائية بنجاح.",
        "result": card,
    }
