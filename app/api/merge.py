from typing import List
from uuid import uuid4

from fastapi import APIRouter, File, HTTPException, UploadFile, status

from app.core.logging import configure_logging
from app.models import MergeCommitRequest
from app.services.pdf_service import PDFService
from app.storage.local import LocalStorage
from app.storage.registry import get_document, register_document
from app.utils.file_utils import ensure_pdf
from app.utils.pdf_preview import render_page_preview

router = APIRouter(prefix="/pdf/merge", tags=["PDF Merge"])

logger = configure_logging()
storage = LocalStorage()
pdf_service = PDFService(storage)


def _card_from_entry(entry) -> dict:
    preview = render_page_preview(entry.path, page_number=1)
    card = entry.to_card(preview=preview)
    card["is_temp"] = True
    return card


@router.post("/cards", summary="إنشاء بطاقات الملفات مع معاينة الصفحة الأولى")
async def prepare_merge_cards(files: List[UploadFile] = File(...)) -> dict:
    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="يجب اختيار ملف PDF واحد على الأقل.",
        )

    cards: List[dict] = []
    for upload in files:
        ensure_pdf(upload)
        temp_path = storage.save_upload(upload, temp=True)
        entry = register_document(temp_path, upload.filename, expect_pdf=True)
        cards.append(_card_from_entry(entry))
        logger.info("تم تسجيل ملف للدمج: %s", upload.filename)

    return {"status": "ok", "files": cards}


@router.post("/commit", summary="دمج الملفات بالترتيب المحدد وإرجاع ملف نهائي")
async def commit_merge(payload: MergeCommitRequest) -> dict:
    if len(payload.file_ids) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="يجب توفير معرفين على الأقل لإتمام الدمج.",
        )

    entries = [get_document(file_id, require_pdf=True) for file_id in payload.file_ids]

    merged_path = pdf_service.merge([entry.path for entry in entries])
    output_name = payload.output_filename or f"merged_{uuid4().hex[:8]}.pdf"

    public_path = storage.register_public_download(merged_path, output_name)
    result_entry = register_document(public_path, output_name, expect_pdf=True)
    preview = render_page_preview(public_path, page_number=1)

    result_card = result_entry.to_card(preview=preview)
    result_card["download_url"] = f"/downloads/{public_path.name}"
    result_card["is_temp"] = False

    logger.info("تم دمج %s ملفات في ملف واحد: %s", len(entries), output_name)

    return {
        "status": "ok",
        "message": "تم دمج الملفات بنجاح.",
        "result": result_card,
    }
