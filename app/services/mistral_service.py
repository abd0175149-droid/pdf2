import os
import base64
import logging
from mistralai import Mistral

# إعداد اللوج
logger = logging.getLogger("MistralService")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
formatter = logging.Formatter("[%(levelname)s] %(asctime)s - %(message)s", "%Y-%m-%d %H:%M:%S")
handler.setFormatter(formatter)
logger.addHandler(handler)


class MistralService:
    """خدمة تحليل ملفات PDF عبر واجهة Mistral OCR."""

    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("MISTRAL_API_KEY")
        if not self.api_key:
            raise ValueError("❌ لم يتم توفير مفتاح Mistral API.")
        self.client = Mistral(api_key=self.api_key)
        logger.info(f"✅ تم إنشاء عميل Mistral OCR (المفتاح يبدأ بـ {self.api_key[:6]}***)")

    def extract_text(self, file_bytes: bytes) -> str:
        """يحلل الملف باستخدام واجهة OCR الأصلية من Mistral."""
        logger.info(f"🔑 المفتاح المستخدم للتحليل: {self.api_key[:10]}...")

        try:
            logger.info("🚀 بدأ تحليل الملف باستخدام Mistral OCR API ...")

            # 1️⃣ تحويل الملف إلى base64
            b64_data = base64.b64encode(file_bytes).decode()

            # 2️⃣ استدعاء واجهة OCR الرسمية
            response = self.client.ocr.process(
                model="mistral-ocr-latest",
                document={
                    "type": "document_url",
                    "document_url": f"data:application/pdf;base64,{b64_data}"
                },
                include_image_base64=False,  # يمكن تغييره إلى True لو أردت صورًا
            )

            logger.info("✅ تم استلام الرد من Mistral بنجاح.")

            # 3️⃣ استخراج النصوص من جميع الصفحات
            if not hasattr(response, "pages") or not response.pages:
                logger.warning("⚠️ لم يتم العثور على صفحات في الرد.")
                return "⚠️ لم يتم استخراج أي نص من الملف."

            all_text = []
            for page in response.pages:
                if hasattr(page, "markdown"):
                    all_text.append(page.markdown.strip())

            combined_text = "\n\n".join(all_text)
            logger.info(f"📄 تم استخراج النص من {len(response.pages)} صفحات (إجمالي {len(combined_text)} حرفًا).")

            return combined_text

        except Exception as e:
            logger.exception(f"❌ خطأ أثناء الاتصال بـ Mistral OCR: {e}")
            raise
