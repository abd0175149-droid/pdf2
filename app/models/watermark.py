from typing import Literal

from pydantic import BaseModel, Field


class WatermarkOptions(BaseModel):
    file_id: str = Field(..., description="معرف ملف PDF المسجل.")
    text: str = Field(..., description="نص العلامة المائية.")
    opacity: float = Field(..., gt=0, le=1, description="قيمة الشفافية بين 0 و 1.")
    position: Literal["center", "top", "bottom", "diagonal", "tile"] = Field(
        "center", description="موضع العلامة المائية."
    )
    font_size: int = Field(0, ge=0, description="حجم الخط (0 لاختيار تلقائي).")


class WatermarkCommitRequest(WatermarkOptions):
    output_filename: str | None = Field(default=None, description="اسم الملف الناتج (اختياري).")
