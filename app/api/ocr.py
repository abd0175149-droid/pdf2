# app/api/ocr.py
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, UploadFile, HTTPException
from pydantic import BaseModel

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

    # الكارت كما هو (للاستعمال العام في الواجهة)
    card = _card(entry)

    # مفاتيح مسطّحة لضمان التوافق مع أي واجهة/عميل
    file_id = getattr(entry, "id", None) or card.get("file_id") or card.get("id")
    page_count = card.get("page_count", 0)

    logger.info("تم رفع ملف لـ OCR: %s", file.filename)
    return {
        "status": "ok",
        "file": card,              # يبقى كما هو
        "file_id": file_id,        # مفتاح مسطّح
        "page_count": page_count,  # مفتاح مسطّح
    }


@router.post("/commit", summary="تشغيل OCR وإنتاج ملف DOCX")
async def commit_ocr(payload: OCRCommitRequest) -> dict:
    # تحقّق/جلب المستند
    entry = get_document(payload.file_id, require_pdf=True)
    file_bytes = entry.path.read_bytes()
    logger.info("بدء OCR للملف %s", entry.filename)

    # مفتاح الـ OCR (من البودي أو من الإعدادات)
    api_key: Optional[str] = payload.api_key or getattr(settings, "mistral_api_key", None)
    if not api_key:
        raise HTTPException(status_code=400, detail="Missing API key")

    # تأكيد مجلد الإخراج
    Path(settings.outputs_dir).mkdir(parents=True, exist_ok=True)

    try:
        # تنفيذ OCR الفعلي
        service = MistralService(api_key=api_key)
        ocr_result = service.extract_text(file_bytes)

        builder = DocxBuilder(output_dir=str(settings.outputs_dir))
        docx_path = Path(builder.markdown_to_docx(ocr_result.markdown))

        # اسم الملف الناتج
        output_name = payload.output_filename or f"{entry.path.stem}_ocr.docx"

        # وضعه في مجلد التحميلات العامة (يتوافق مع /downloads المربوطة في main.py)
        public_path = storage.register_public_download(docx_path, output_name)
        result_entry = register_document(public_path, output_name, expect_pdf=False)

        # بطاقة النتيجة
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

        # إضافة مفاتيح مسطّحة لضمان الاتّساق مع الواجهة
        return {
            "status": "ok",
            "message": "تم إنشاء ملف Word باستخدام Mistral OCR.",
            "result": card,                                 # يبقى متوافق مع أي كارد/بطاقة
            "output_filename": output_name,                 # مفتاح مسطّح
            "download_url": f"/downloads/{public_path.name}",  # مفتاح مسطّح
            "page_count": ocr_result.page_count,            # مسطّح (مكرر من الكارد)
            "word_count": ocr_result.word_count,            # مسطّح
            "text_preview": ocr_result.markdown[:800],
        }

    except HTTPException:
        # مرّر HTTPException كما هي (400/422..)
        raise
    except Exception as e:
        logger.exception("OCR commit failed")
        # ارجع 500 برسالة واضحة (وسيمر عبر CORSMiddleware)
        raise HTTPException(status_code=500, detail=f"OCR failed: {e}")
