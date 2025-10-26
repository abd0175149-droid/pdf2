# app/api/ocr.py
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, UploadFile, HTTPException

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
    """يبني بطاقة/كارت موحّد مع معاينة الصفحة الأولى."""
    preview = render_page_preview(entry.path, page_number=1)
    card = entry.to_card(preview=preview)
    card["is_temp"] = True
    return card


@router.post("/upload", summary="رفع ملف PDF لمعالجته باستخدام Mistral OCR")
async def upload_pdf(file: UploadFile = File(...)) -> dict:
    """
    يرفع PDF ويحفظه مؤقتًا ويعيد:
      - file (بطاقة مفصلة)
      - file_id و page_count كمفاتيح مسطّحة لضمان الاتساق مع الواجهة
    """
    ensure_pdf(file)
    temp_path = storage.save_upload(file, temp=True)
    entry = register_document(temp_path, file.filename, expect_pdf=True)

    card = _card(entry)

    # مفاتيح مسطّحة (Top-level) لتوافق كامل مع الواجهة
    file_id = getattr(entry, "id", None) or card.get("file_id") or card.get("id")
    page_count = card.get("page_count", 0)

    logger.info("تم رفع ملف لـ OCR: %s", file.filename)
    return {
        "status": "ok",
        "file": card,              # يبقى الكارد كما هو
        "file_id": file_id,        # مفاتيح مسطّحة
        "page_count": page_count,  # مفاتيح مسطّحة
    }


@router.post("/commit", summary="تشغيل OCR وإنتاج ملف DOCX")
async def commit_ocr(payload: OCRCommitRequest) -> dict:
    """
    يشغّل OCR على الملف المرفوع ثم يبني DOCX ويعيد:
      - result (بطاقة تفصيلية)
      - download_url / output_filename كمفاتيح مسطّحة
      - page_count / word_count / text_preview
    معالجة الأخطاء تُرجع 400/502/500 برسائل واضحة وتمر عبر CORSMiddleware.
    """
    # 0) تأكد من وجود مجلدات الإخراج والتحميل العام
    downloads_dir: Path = settings.public_dir / "downloads"
    outputs_dir: Path = getattr(settings, "outputs_dir", settings.public_dir / "outputs")
    downloads_dir.mkdir(parents=True, exist_ok=True)
    outputs_dir.mkdir(parents=True, exist_ok=True)

    # 1) تحقّق من file_id
    try:
        entry = get_document(payload.file_id, require_pdf=True)
    except Exception as e:
        logger.warning("Invalid/expired file_id %s: %s", payload.file_id, e)
        raise HTTPException(status_code=400, detail="Invalid or expired file_id")

    # 2) اجلب مفتاح Mistral (من الطلب أو من الإعدادات)
    api_key: Optional[str] = payload.api_key or getattr(settings, "mistral_api_key", None)
    if not api_key:
        raise HTTPException(status_code=400, detail="Missing API key")

    # 3) اقرأ الملف المرفوع
    try:
        file_bytes = entry.path.read_bytes()
    except Exception as e:
        logger.exception("Failed reading uploaded file")
        raise HTTPException(status_code=500, detail=f"Failed to read uploaded file: {e}")

    # 4) نفّذ OCR عبر خدمة Mistral
    try:
        service = MistralService(api_key=api_key)
        # يُفترض أن تعيد extract_text كائنًا فيه markdown و page_count و word_count
        ocr_result = service.extract_text(file_bytes)
    except Exception as e:
        logger.exception("Mistral OCR call failed")
        # 502 لأن المشكلة غالبًا خارجية (خدمة OCR)
        raise HTTPException(status_code=502, detail=f"OCR upstream failed: {e}")

    # 5) حوّل Markdown إلى DOCX
    try:
        builder = DocxBuilder(output_dir=str(outputs_dir))
        docx_path = Path(builder.markdown_to_docx(ocr_result.markdown))
    except Exception as e:
        logger.exception("DOCX build failed")
        raise HTTPException(status_code=500, detail=f"DOCX build failed: {e}")

    # 6) سجّل ملف التحميل العام ضمن /downloads
    output_name = payload.output_filename or f"{entry.path.stem}_ocr.docx"
    try:
        public_path = storage.register_public_download(docx_path, output_name)
        result_entry = register_document(public_path, output_name, expect_pdf=False)
    except Exception as e:
        logger.exception("Register public download failed")
        raise HTTPException(status_code=500, detail=f"Register public download failed: {e}")

    # 7) شكّل الاستجابة
    card = result_entry.to_card()
    card.update({
        "download_url": f"/downloads/{public_path.name}",
        "page_count": getattr(ocr_result, "page_count", None),
        "word_count": getattr(ocr_result, "word_count", None),
        "is_temp": False,
    })

    logger.info("اكتمل OCR للملف %s وتم إنشاء %s", entry.filename, output_name)

    return {
        "status": "ok",
        "message": "تم إنشاء ملف Word باستخدام Mistral OCR.",
        "result": card,                                      # للكروت/البطاقات
        "output_filename": output_name,                      # مفاتيح مسطّحة
        "download_url": f"/downloads/{public_path.name}",    # مفاتيح مسطّحة
        "page_count": getattr(ocr_result, "page_count", None),
        "word_count": getattr(ocr_result, "word_count", None),
        "text_preview": getattr(ocr_result, "markdown", "")[:800],
    }
