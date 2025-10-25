from pydantic import BaseModel, Field


class ConversionCommitRequest(BaseModel):
    file_id: str = Field(..., description="معرف الملف الذي تم رفعه مسبقًا.")
    output_filename: str | None = Field(default=None, description="اسم ملف PDF الناتج (اختياري).")
