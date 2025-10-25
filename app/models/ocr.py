from pydantic import BaseModel, Field


class OCRCommitRequest(BaseModel):
    file_id: str = Field(..., description="معرف الملف المرفوع.")
    api_key: str | None = Field(default=None, description="مفتاح Mistral البديل (اختياري).")
    output_filename: str | None = Field(default=None, description="اسم ملف DOCX الناتج (اختياري).")
