from typing import Dict

from fastapi import APIRouter, File, HTTPException, UploadFile, status

from app.core.logging import configure_logging
from app.models import CompressionCommitRequest
from app.services.compression_service import CompressionService
from app.storage.local import LocalStorage
from app.storage.registry import get_document, register_document
from app.utils.file_utils import ensure_pdf
from app.utils.pdf_preview import render_page_preview

router = APIRouter(prefix="/pdf/compress", tags=["PDF Compression"])

logger = configure_logging()
storage = LocalStorage()
compression_service = CompressionService(storage)

ALLOWED_LEVELS = {"low", "medium", "high"}


def _card(entry) -> dict:
  preview = render_page_preview(entry.path, 1)
  card = entry.to_card(preview=preview)
  card["is_temp"] = True
  return card


@router.post("/upload", summary="رفع ملف PDF للتحضير لعملية الضغط")
async def upload_pdf(file: UploadFile = File(...)) -> dict:
  ensure_pdf(file)
  temp_path = storage.save_upload(file, temp=True)
  entry = register_document(temp_path, file.filename, expect_pdf=True)
  logger.info("تم رفع ملف للضغط: %s", file.filename)
  return {"status": "ok", "file": _card(entry)}


@router.post("/commit", summary="ضغط الملف بالمستوى المحدد وإرجاع بطاقة النتيجة")
async def commit_compress(payload: CompressionCommitRequest) -> dict:
  if payload.level not in ALLOWED_LEVELS:
    raise HTTPException(
      status_code=status.HTTP_400_BAD_REQUEST,
      detail=f"مستوى الضغط غير مدعوم. الخيارات المتاحة: {', '.join(ALLOWED_LEVELS)}.",
    )

  entry = get_document(payload.file_id, require_pdf=True)
  original_size = entry.size_bytes

  compressed_path = compression_service.compress(entry.path, payload.level)
  output_name = payload.output_filename or f"{entry.path.stem}_{payload.level}.pdf"

  public_path = storage.register_public_download(compressed_path, output_name)
  result_entry = register_document(public_path, output_name, expect_pdf=True)

  preview = render_page_preview(public_path, 1)
  result_card = result_entry.to_card(preview=preview)
  result_card.update(
    {
      "download_url": f"/downloads/{public_path.name}",
      "is_temp": False,
    }
  )

  compressed_size = result_entry.size_bytes
  reduction_bytes = max(0, original_size - compressed_size)
  reduction_percent = round((reduction_bytes / original_size) * 100, 2) if original_size else 0

  stats: Dict[str, float | int] = {
    "original_size": original_size,
    "compressed_size": compressed_size,
    "reduction_bytes": reduction_bytes,
    "reduction_percent": reduction_percent,
  }

  logger.info("اكتملت عملية الضغط للملف %s بمستوى %s", entry.filename, payload.level)

  return {
    "status": "ok",
    "message": "تم ضغط الملف بنجاح.",
    "result": result_card,
    "stats": stats,
    "level": payload.level,
  }
