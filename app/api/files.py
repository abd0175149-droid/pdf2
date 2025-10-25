from datetime import datetime
from pathlib import Path

from fastapi import APIRouter

from app.storage.local import LocalStorage
from app.utils.file_utils import file_stats

router = APIRouter(prefix="/files", tags=["Files"])
storage = LocalStorage()


@router.get("/", summary="قائمة الملفات المتاحة للتنزيل من المجلد العام")
async def list_files() -> dict:
    files: list[dict] = []
    download_root: Path = storage.download_root
    for path in sorted(download_root.glob("*")):
        if path.is_file():
            size_bytes, _ = file_stats(path)
            files.append(
                {
                    "filename": path.name,
                    "download_url": f"/downloads/{path.name}",
                    "size_bytes": size_bytes,
                    "updated_at": datetime.utcfromtimestamp(path.stat().st_mtime).isoformat() + "Z",
                }
            )

    return {"files": files}
