from __future__ import annotations

import mimetypes
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional
from uuid import uuid4

from fastapi import HTTPException, status
from pypdf import PdfReader


@dataclass
class RegisteredFile:
    file_id: str
    path: Path
    filename: str
    size_bytes: int
    created_at: datetime
    mime_type: str
    extension: str
    page_count: Optional[int] = None
    is_pdf: bool = False

    def to_card(self, preview: Optional[str] = None) -> dict:
        card: dict = {
            "file_id": self.file_id,
            "filename": self.filename,
            "size_bytes": self.size_bytes,
            "extension": self.extension,
        }
        if self.page_count is not None:
            card["page_count"] = self.page_count
        if preview:
            card["preview"] = preview
        return card


_registry: Dict[str, RegisteredFile] = {}
_ttl = timedelta(hours=2)


def register_document(path: Path, filename: str | None = None, expect_pdf: bool = True) -> RegisteredFile:
    """تسجيل ملف مؤقتًا وإرجاع بياناته مع التحقق من كونه PDF عند الحاجة."""
    cleanup()
    filename = filename or path.name
    extension = path.suffix.lower().lstrip(".")
    mime_type, _ = mimetypes.guess_type(filename)
    mime_type = mime_type or "application/octet-stream"
    is_pdf = extension == "pdf"

    if expect_pdf and not is_pdf:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="الملف المرفوع ليس من نوع PDF.",
        )

    page_count: Optional[int] = None
    if is_pdf:
        reader = PdfReader(str(path))
        page_count = len(reader.pages)

    size_bytes = path.stat().st_size if path.exists() else 0

    file_id = uuid4().hex
    entry = RegisteredFile(
        file_id=file_id,
        path=path,
        filename=filename,
        size_bytes=size_bytes,
        created_at=datetime.utcnow(),
        mime_type=mime_type,
        extension=extension,
        page_count=page_count,
        is_pdf=is_pdf,
    )
    _registry[file_id] = entry
    return entry


def get_document(file_id: str, require_pdf: bool = False) -> RegisteredFile:
    cleanup()
    entry = _registry.get(file_id)
    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="المعرف المطلوب غير موجود أو انتهت صلاحيته.",
        )
    if not entry.path.exists():
        _registry.pop(file_id, None)
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="الملف لم يعد متاحًا على الخادم.",
        )
    if require_pdf and not entry.is_pdf:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="الملف المختار ليس من نوع PDF.",
        )
    return entry


def unregister_document(file_id: str) -> None:
    _registry.pop(file_id, None)


def cleanup() -> None:
    """حذف السجلات المنتهية الصلاحية وفق مدة الاحتفاظ المحددة."""
    now = datetime.utcnow()
    expired = [file_id for file_id, entry in _registry.items() if now - entry.created_at > _ttl]
    for file_id in expired:
        _registry.pop(file_id, None)
