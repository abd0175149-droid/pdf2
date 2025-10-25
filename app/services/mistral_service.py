import base64
from dataclasses import dataclass
from typing import Optional

from mistralai import Mistral

from app.core.config import get_settings
from app.core.logging import configure_logging

logger = configure_logging()


@dataclass
class OCRText:
    markdown: str
    page_count: int
    word_count: int


class MistralService:
    """واجهة للتعامل مع Mistral OCR واستخراج النصوص مع بيانات إضافية."""

    def __init__(self, api_key: Optional[str] = None) -> None:
        settings = get_settings()
        self.api_key: Optional[str] = api_key or settings.mistral_api_key
        if not self.api_key:
            raise ValueError("يجب توفير مفتاح Mistral API عبر الإعدادات أو النموذج.")

        self.client = Mistral(api_key=self.api_key)
        logger.info("تم تهيئة عميل Mistral OCR.")

    def extract_text(self, file_bytes: bytes) -> OCRText:
        logger.info("إرسال ملف PDF إلى Mistral OCR (عدد البايتات %s).", len(file_bytes))

        try:
            b64_data = base64.b64encode(file_bytes).decode()
            response = self.client.ocr.process(
                model="mistral-ocr-latest",
                document={
                    "type": "document_url",
                    "document_url": f"data:application/pdf;base64,{b64_data}",
                },
                include_image_base64=False,
            )

            if not getattr(response, "pages", None):
                logger.warning("لم يتم استرجاع أي صفحات من خدمة Mistral OCR.")
                return OCRText(markdown="", page_count=0, word_count=0)

            all_text: list[str] = []
            for page in response.pages:
                markdown = getattr(page, "markdown", "").strip()
                if markdown:
                    all_text.append(markdown)

            combined_text = "\n\n".join(all_text)
            page_count = len(all_text)
            word_count = len(combined_text.split())
            logger.info("اكتمل OCR مع %s صفحة و %s كلمة تقريبًا.", page_count, word_count)

            return OCRText(markdown=combined_text, page_count=page_count, word_count=word_count)

        except Exception as exc:  # pragma: no cover - حالات فشل نادرة
            logger.exception("فشل تواصل Mistral OCR: %s", exc)
            raise
