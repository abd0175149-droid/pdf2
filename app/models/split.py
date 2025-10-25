from typing import List

from pydantic import BaseModel, Field, validator


class PageRange(BaseModel):
    start: int = Field(..., ge=1)
    end: int = Field(..., ge=1)

    @validator("end")
    def validate_range(cls, end: int, values: dict) -> int:  # noqa: D417
        start = values.get("start")
        if start and end < start:
            raise ValueError("رقم النهاية يجب أن يكون أكبر أو يساوي البداية.")
        return end


class SplitCommitRequest(BaseModel):
    file_id: str = Field(..., description="معرف الملف المراد تقسيمه.")
    ranges: List[PageRange] = Field(..., min_items=1)
    separate_files: bool = Field(False, description="إنشاء ملف منفصل لكل مدى.")


class PagePreviewRequest(BaseModel):
    file_id: str = Field(..., description="معرف الملف المسجل.")
    pages: List[int] = Field(..., min_items=1)
