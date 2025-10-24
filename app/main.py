from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import os
import logging
from dotenv import load_dotenv
from app.services.mistral_service import MistralService
from app.services.docx_builder import DocxBuilder

# ---------------------------------------------------------------------------
# 🧩 إعداد البيئة والتهيئة العامة
# ---------------------------------------------------------------------------

load_dotenv()
app = FastAPI(title="Mistral OCR API", version="1.3.2")

# 🔹 المسارات الرئيسة
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BASE_DIR)
OUTPUT_DIR = os.path.join(ROOT_DIR, "outputs")
PUBLIC_DIR = os.path.join(ROOT_DIR, "public")

# إنشاء المجلدات إن لم تكن موجودة
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(PUBLIC_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# 🌐 إعداد CORS
# ---------------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # ⚠️ في بيئة الإنتاج استبدلها بنطاقاتك المسموحة
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# 🧾 نظام التسجيل (Logging)
# ---------------------------------------------------------------------------

logger = logging.getLogger("MistralOCR")
logger.setLevel(logging.INFO)
console_handler = logging.StreamHandler()
formatter = logging.Formatter(
    "[%(levelname)s] %(asctime)s - %(message)s",
    "%Y-%m-%d %H:%M:%S",
)
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

# ---------------------------------------------------------------------------
# ⚙️ تحميل ملفات الواجهة (public/)
# ---------------------------------------------------------------------------

# ملاحظة مهمة:
# نحمّل الواجهة في النهاية لتعمل كموقع افتراضي (index.html)
# مع الحفاظ على أن API تعمل على المسارات /ocr و /download
# لذلك نُحمّل StaticFiles *في النهاية* بعد تعريف الـ API.

# ---------------------------------------------------------------------------
# 🧠 مسارات الـ API
# ---------------------------------------------------------------------------

@app.post("/ocr")
async def upload_file(
    file: UploadFile = File(..., description="ملف PDF المطلوب تحليله."),
    api_key: str = Form(None, description="مفتاح Mistral API (اختياري إذا تم تحديده في .env)."),
):
    """
    رفع ملف PDF وتحليله باستخدام Mistral OCR API ثم إنشاء ملف Word داخل مجلد outputs.
    """
    logger.info(f"📥 تم استلام ملف: {file.filename} ({file.content_type})")

    # ✅ التحقق من نوع الملف
    if file.content_type not in ["application/pdf", "application/octet-stream"]:
        logger.warning("⚠️ تم رفض الملف لأنه ليس PDF.")
        raise HTTPException(status_code=400, detail="الملف يجب أن يكون بصيغة PDF فقط.")

    # ✅ قراءة الملف
    file_bytes = await file.read()
    logger.info(f"📄 حجم الملف: {len(file_bytes)} بايت.")

    try:
        # 🔹 تحليل الملف عبر Mistral OCR
        service = MistralService(api_key)
        logger.info("🚀 بدأ تحليل الملف عبر Mistral...")
        result = service.extract_text(file_bytes)
        logger.info("✅ تم استخراج النص بنجاح.")

        # 🔹 تحويل النص إلى ملف Word داخل مجلد outputs
        builder = DocxBuilder(output_dir=OUTPUT_DIR)
        output_path = builder.markdown_to_docx(result)
        filename = os.path.basename(output_path)
        logger.info(f"💾 تم إنشاء ملف Word: {filename}")

        # 🔹 توليد رابط التحميل الكامل
        download_url = f"/download/{filename}"

        return {
            "status": "ok",
            "message": "تم تحليل الملف بنجاح ✅",
            "preview": result[:800],
            "length": len(result),
            "docx_file": filename,
            "download_url": download_url,
        }

    except Exception as e:
        logger.exception(f"❌ حدث خطأ أثناء التحليل: {e}")
        raise HTTPException(status_code=500, detail=f"حدث خطأ أثناء التحليل: {str(e)}")


@app.get("/download/{filename}")
def download_file(filename: str):
    """تحميل ملف Word الناتج من مجلد outputs."""
    file_path = os.path.join(OUTPUT_DIR, filename)

    if not os.path.exists(file_path):
        logger.warning(f"⚠️ الملف المطلوب غير موجود: {file_path}")
        raise HTTPException(status_code=404, detail="الملف غير موجود أو انتهت صلاحيته.")

    logger.info(f"⬇️ يتم الآن تحميل الملف: {file_path}")
    return FileResponse(
        path=file_path,
        filename=filename,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )

# ---------------------------------------------------------------------------
# 🏠 واجهة المستخدم (Static Files)
# ---------------------------------------------------------------------------

# يتم تحميل ملفات الواجهة بعد كل المسارات
# حتى يمكن الوصول إلى index.html وملفات JS/CSS بسهولة
app.mount("/", StaticFiles(directory=PUBLIC_DIR, html=True), name="public")

# ---------------------------------------------------------------------------
# ✅ نهاية الملف
# ---------------------------------------------------------------------------
