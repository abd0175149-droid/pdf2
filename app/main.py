# app/main.py
from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api import routers
from app.core.config import get_settings
from app.core.logging import configure_logging

# === إعدادات وتسجيل ===
settings = get_settings()
logger = configure_logging()

app = FastAPI(
    title=getattr(settings, "app_name", "Mistral OCR API"),
    version=getattr(settings, "app_version", "0.1.0"),
)

# === CORS ===
# نقرأ من settings إن وُجدت، وإلا نوفر قيمًا مناسبة بشكل افتراضي.
def _as_list(val: Iterable | str | None, fallback: list[str]) -> list[str]:
    if val is None:
        return fallback
    if isinstance(val, (list, tuple, set)):
        return [str(x).strip() for x in val if str(x).strip()]
    s = str(val).strip()
    if not s:
        return fallback
    # يدعم "a,b,c" أو JSON list مثل '["a","b"]'
    if s.startswith("["):
        try:
            import json
            parsed = json.loads(s)
            return [str(x).strip() for x in parsed if str(x).strip()]
        except Exception:
            pass
    return [x.strip() for x in s.split(",") if x.strip()]

allow_origins = _as_list(
    getattr(settings, "allow_origins", os.getenv("ALLOWED_ORIGINS")),
    fallback=["https://tools.howplatform.net"],
)
allow_origin_regex = getattr(settings, "allow_origin_regex", os.getenv("ALLOWED_ORIGIN_REGEX", None))
allow_methods = _as_list(getattr(settings, "allow_methods", None), fallback=["*"])
allow_headers = _as_list(getattr(settings, "allow_headers", None), fallback=["*"])
expose_headers = _as_list(
    getattr(settings, "expose_headers", None),
    fallback=["Content-Disposition"],
)
allow_credentials = bool(getattr(settings, "allow_credentials", os.getenv("ALLOW_CREDENTIALS", "0") in ("1", "true", "True")))

# ملاحظة أمنية: إذا ستستخدم allow_credentials=True فلا تستخدم allow_origins=["*"].
if allow_credentials and ("*" in allow_origins):
    # حماية من سوء الضبط: استبدل النجمة بأصل واحد افتراضي
    allow_origins = ["https://tools.howplatform.net"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_origin_regex=allow_origin_regex,
    allow_credentials=allow_credentials,   # اجعله False إن لم تستخدم كوكيز/اعتمادات
    allow_methods=allow_methods,           # POST/GET/OPTIONS/... الخ
    allow_headers=allow_headers,           # Content-Type, Accept, Authorization...
    expose_headers=expose_headers,         # لقراءة اسم الملف من الهيدر إن لزم
)

# === Routers ===
for router in routers:
    app.include_router(router)

# === Static downloads ===
public_dir: Path = getattr(settings, "public_dir", Path("public"))
downloads_dir: Path = public_dir / "downloads"
downloads_dir.mkdir(parents=True, exist_ok=True)  # تأكد من وجود المجلد على السيرفر
app.mount("/downloads", StaticFiles(directory=str(downloads_dir)), name="downloads")

# === Basic endpoints ===
@app.get("/")
async def root() -> dict:
    logger.debug("Root endpoint accessed")
    return {"message": "Welcome to Mistral OCR API 🚀"}

@app.get("/health")
async def health_check() -> dict:
    logger.debug("Health check invoked")
    return {"status": "ok", "message": "PDF Toolkit API is running"}
