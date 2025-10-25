from typing import List

from pydantic import BaseModel, Field


class MergeCommitRequest(BaseModel):
    file_ids: List[str] = Field(..., description="قائمة معرفات الملفات بالترتيب المطلوب للدمج.")
    output_filename: str | None = Field(default=None, description="اسم الملف الناتج (اختياري).")


class MergeCard(BaseModel):
    file_id: str
    filename: str
    page_count: int
    size_bytes: int
    preview: str
