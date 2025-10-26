# app/api/ocr.py
from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, UploadFile, HTTPException, Header

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


# ============ Helpers ============
def _card(entry, is_temp: bool = True) -> dict:
    preview = None
    try:
        preview = render_page_preview(entry.path, page_number=1)
    except Exception:
        preview = None
    card = entry.to_card(preview=preview)
    card["is_temp"] = is_temp
    return card

def _safe_file_id(entry, temp_path: Path) -> str:
    return getattr(entry, "id", None) or temp_path.stem

def _resolve_uploaded_pdf(file_id: str) -> Path:
    # عبر السجلّ
    try:
        entry = get_document(file_id, require_pdf=True)
        return entry.path
    except Exception:
        pass
    # Fallback: اسم الملف على القرص
    uploads_dir: Path = getattr(settings, "uploads_dir", settings.public_dir / "uploads")
    pdf_path = uploads_dir / f"{file_id}.pdf"
    if not pdf_path.is_file():
        raise HTTPException(status_code=400, detail="Invalid or expired file_id")
    return pdf_path

def _pick_api_key(
    payload_key: Optional[str],
    auth_header: Optional[str],
    x_key: Optional[str],
    default_key: Optional[str]
) -> Optional[str]:
    # أولوية: payload.api_key → Authorization: Bearer → X-Mistral-Api-Key → settings
    if payload_key:
        return payload_key.strip()
    if auth_header and auth_header.strip().lower().startswith("bearer "):
        return auth_header.strip()[7:].strip()
    if x_key:
        return x_key.strip()
    return (default_key or "").strip() or None


# ============ Endpoints ============
@router.post("/upload", summary="رفع ملف PDF لمعالجته باستخدام OCR")
async def ocr_upload(file: UploadFile = File(...)) -> dict:
    ensure_pdf(file)
    temp_path = storage.save_upload(file, temp=True)
    entry = register_document(temp_path, file.filename, expect_pdf=True)

    card = _card(entry, is_temp=True)
    file_id = _safe_file_id(entry, temp_path)
    page_count = card.get("page_count", 0)

    logger.info("OCR upload: %s (id=%s)", file.filename, file_id)
    return {
        "status": "ok",
        "file": card,               # بطاقة موحّدة
        "file_id": file_id,         # مفاتيح مسطّحة
        "page_count": page_count,   # مفاتيح مسطّحة
    }


@router.post("/commit", summary="تشغيل OCR وإنتاج ملف DOCX")
async def ocr_commit(
    payload: OCRCommitRequest,
    authorization: Optional[str] = Header(None),          # Authorization: Bearer <KEY>
    x_mistral_api_key: Optional[str] = Header(None)       # X-Mistral-Api-Key: <KEY>
) -> dict:
    """
    يقبل المفتاح صراحةً من:
      1) payload.api_key
      2) Authorization: Bearer <KEY>
      3) X-Mistral-Api-Key: <KEY>
      4) settings.mistral_api_key
    ثم ينفّذ OCR ويبني DOCX ويعيد رابط التحميل.
    """
    # 0) المسارات
    public_dir: Path = getattr(settings, "public_dir", Path("public"))
    downloads_dir: Path = public_dir / "downloads"
    outputs_dir: Path = getattr(settings, "outputs_dir", public_dir / "outputs")
    downloads_dir.mkdir(parents=True, exist_ok=True)
    outputs_dir.mkdir(parents=True, exist_ok=True)

    # 1) PDF
    pdf_path = _resolve_uploaded_pdf(payload.file_id)

    # 2) مفتاح Mistral (مصدر صريح)
    api_key = _pick_api_key(
        getattr(payload, "api_key", None),
        authorization,
        x_mistral_api_key,
        getattr(settings, "mistral_api_key", None),
    )
    if not api_key:
        raise HTTPException(status_code=400, detail="Missing API key")

    # 3) قراءة الملف
    try:
        file_bytes = pdf_path.read_bytes()
    except Exception as e:
        logger.exception("Failed to read uploaded PDF (id=%s)", payload.file_id)
        raise HTTPException(status_code=500, detail=f"Failed to read uploaded file: {e}")

    # 4) OCR (قد يفشل خارجيًا → 502)
    try:
        service = MistralService(api_key=api_key)
        ocr_result = service.extract_text(file_bytes)  # expected: markdown/page_count/word_count
    except Exception as e:
        logger.exception("Mistral OCR call failed (id=%s)", payload.file_id)
        raise HTTPException(status_code=502, detail=f"OCR upstream failed: {e}")

    # 5) DOCX
    try:
        builder = DocxBuilder(output_dir=str(outputs_dir))
        docx_path = Path(builder.markdown_to_docx(ocr_result.markdown))
    except Exception as e:
        logger.exception("DOCX build failed (id=%s)", payload.file_id)
        raise HTTPException(status_code=500, detail=f"DOCX build failed: {e}")

    # 6) تسجيل التحميل العام
    output_name = payload.output_filename or f"{pdf_path.stem}_ocr.docx"
    try:
        public_path = storage.register_public_download(docx_path, output_name)
        result_entry = register_document(public_path, output_name, expect_pdf=False)
    except Exception as e:
        logger.exception("Register public download failed (id=%s)", payload.file_id)
        raise HTTPException(status_code=500, detail=f"Register public download failed: {e}")

    # 7) الاستجابة — بطاقة + مفاتيح مسطّحة
    result_card = _card(result_entry, is_temp=False)
    result_card["download_url"] = f"/downloads/{public_path.name}"
    if getattr(ocr_result, "page_count", None) is not None:
        result_card["page_count"] = ocr_result.page_count
    if getattr(ocr_result, "word_count", None) is not None:
        result_card["word_count"] = ocr_result.word_count

    logger.info("OCR done: %s -> %s", pdf_path.name, output_name)

    return {
        "status": "ok",
        "message": "تم إنشاء ملف Word باستخدام OCR.",
        "result": result_card,
        "output_filename": output_name,                       # مسطّح
        "download_url": f"/downloads/{public_path.name}",     # مسطّح
        "page_count": getattr(ocr_result, "page_count", None),
        "word_count": getattr(ocr_result, "word_count", None),
        "text_preview": getattr(ocr_result, "markdown", "")[:800],
    }
