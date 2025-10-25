from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api import routers
from app.core.config import get_settings
from app.core.logging import configure_logging

settings = get_settings()
logger = configure_logging()

app = FastAPI(title=settings.app_name, version=settings.app_version)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for router in routers:
    app.include_router(router)

downloads_dir = settings.public_dir / "downloads"
app.mount("/downloads", StaticFiles(directory=downloads_dir), name="downloads")


@app.get("/")
async def root() -> dict:
    logger.debug("Root endpoint accessed")
    return {
        "message": "Welcome to Mistral OCR API 🚀",
        "usage": {
            "/health": "Check API status",
            "/ocr/upload": "Upload PDF for OCR",
            "/pdf/merge": "Merge multiple PDF files",
        },
    }


@app.get("/health")
async def health_check() -> dict:
    logger.debug("Health check invoked")
    return {"status": "ok", "message": "PDF Toolkit API is running"}
