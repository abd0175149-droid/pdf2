from pathlib import Path

from fastapi import APIRouter, File, UploadFile

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.models import OCRCommitRequest
from app.services.docx_builder import DocxBuilder
from app.services.mistral_service import MistralService
from app.storage.local import LocalStorage
from app.storage.registry import get_document, register_document
from app.utils.file_utils import ensure_pdf
from app.utils.pdf_preview import render_page_preview

router = APIRouter(prefix="/ocr", tags=["OCR"])

settings = get_settings()
logger = configure_logging()
storage = LocalStorage()


def _card(entry) -> dict:
    preview = render_page_preview(entry.path, page_number=1)
    card = entry.to_card(preview=preview)
    card["is_temp"] = True
    return card


@router.post("/upload", summary="رفع ملف PDF لمعالجته باستخدام Mistral OCR")
async def upload_pdf(file: UploadFile = File(...)) -> dict:
    ensure_pdf(file)
    temp_path = storage.save_upload(file, temp=True)
    entry = register_document(temp_path, file.filename, expect_pdf=True)
    logger.info("تم رفع ملف لـ OCR: %s", file.filename)
    return {"status": "ok", "file": _card(entry)}


@router.post("/commit", summary="تشغيل OCR وإنتاج ملف DOCX")
async def commit_ocr(payload: OCRCommitRequest) -> dict:
    entry = get_document(payload.file_id, require_pdf=True)
    file_bytes = entry.path.read_bytes()
    logger.info("بدء OCR للملف %s", entry.filename)

    service = MistralService(api_key=payload.api_key)
    ocr_result = service.extract_text(file_bytes)

    builder = DocxBuilder(output_dir=str(settings.outputs_dir))
    docx_path = Path(builder.markdown_to_docx(ocr_result.markdown))

    output_name = payload.output_filename or f"{entry.path.stem}_ocr.docx"
    public_path = storage.register_public_download(docx_path, output_name)
    result_entry = register_document(public_path, output_name, expect_pdf=False)

    card = result_entry.to_card()
    card.update(
        {
            "download_url": f"/downloads/{public_path.name}",
            "page_count": ocr_result.page_count,
            "word_count": ocr_result.word_count,
            "is_temp": False,
        }
    )

    logger.info("اكتمل OCR للملف %s وتم إنشاء %s", entry.filename, output_name)

    return {
        "status": "ok",
        "message": "تم إنشاء ملف Word باستخدام Mistral OCR.",
        "result": card,
        "text_preview": ocr_result.markdown[:800],
    }
