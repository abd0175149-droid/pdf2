import shutil
from pathlib import Path
from typing import IO, Iterable, Optional
from uuid import uuid4

from fastapi import UploadFile

from app.core.config import get_settings


class LocalStorage:
    """خدمات التخزين المحلية للملفات المرفوعة والنتائج القابلة للتنزيل."""

    def __init__(self, base_dir: Optional[Path] = None) -> None:
        settings = get_settings()
        self.base_dir = Path(base_dir or settings.storage_dir)
        self.processed_dir = settings.outputs_dir
        self.temp_dir = settings.temp_dir
        self.download_root = settings.public_dir / "downloads"

        for directory in (self.base_dir, self.processed_dir, self.temp_dir, self.download_root):
            directory.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _generate_filename(suffix: str) -> str:
        suffix = suffix if suffix.startswith(".") else f".{suffix.lstrip('.')}"
        return f"{uuid4().hex}{suffix}"

    def save_upload(self, upload: UploadFile, *, temp: bool = False) -> Path:
        suffix = Path(upload.filename or "").suffix or ".bin"
        upload.file.seek(0)
        path = self._save_stream(upload.file, suffix=suffix, directory=self.temp_dir if temp else self.base_dir)
        upload.file.seek(0)
        return path

    def _save_stream(self, stream: IO[bytes], *, suffix: str, directory: Path) -> Path:
        target_name = self._generate_filename(suffix)
        target_path = directory / target_name
        with target_path.open("wb") as buffer:
            shutil.copyfileobj(stream, buffer)
        return target_path

    def save_bytes(self, data: bytes, *, suffix: str, directory: Optional[Path] = None) -> Path:
        directory = directory or self.processed_dir
        target_name = self._generate_filename(suffix)
        target_path = directory / target_name
        target_path.write_bytes(data)
        return target_path

    def move_to_processed(self, path: Path, *, new_name: Optional[str] = None) -> Path:
        destination = self.processed_dir / (new_name or path.name)
        shutil.move(path, destination)
        return destination

    def register_public_download(self, source: Path, original_name: str) -> Path:
        target = self.download_root / original_name
        if target.exists():
            target = self.download_root / f"{source.stem}-{uuid4().hex[:6]}{source.suffix}"
        shutil.copy2(source, target)
        return target

    def cleanup(self, paths: Iterable[Path]) -> None:
        for path in paths:
            if path and path.exists():
                path.unlink(missing_ok=True)
