from pydantic import BaseModel, Field


class CompressionCommitRequest(BaseModel):
    file_id: str = Field(..., description="معرف الملف المراد ضغطه.")
    level: str = Field(..., description="مستوى الضغط (low | medium | high).")
    output_filename: str | None = Field(default=None, description="اسم الملف الناتج (اختياري).")
