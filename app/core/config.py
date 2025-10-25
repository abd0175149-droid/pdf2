from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """إعدادات التطبيق العامة مع تحميل القيم من ملف .env عند توفره."""

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[2] / ".env",
        env_file_encoding="utf-8",
    )

    app_name: str = "PDF Toolkit API"
    app_version: str = "0.1.0"

    base_dir: Path = Field(default_factory=lambda: Path(__file__).resolve().parents[2])
    storage_dir: Optional[Path] = None
    public_dir: Optional[Path] = None
    outputs_dir: Optional[Path] = None
    temp_dir: Optional[Path] = None

    mistral_api_key: Optional[str] = Field(default=None, env="MISTRAL_API_KEY")

    allow_origins: list[str] = Field(default_factory=lambda: ["*"])

    def configure_paths(self) -> None:
        """تهيئة المسارات الافتراضية وإنشاء المجلدات في حال غيابها."""
        self.storage_dir = (self.storage_dir or (self.base_dir / "outputs")).resolve()
        self.public_dir = (self.public_dir or (self.base_dir / "public")).resolve()
        self.outputs_dir = (self.outputs_dir or (self.storage_dir / "processed")).resolve()
        self.temp_dir = (self.temp_dir or (self.storage_dir / "tmp")).resolve()

        for directory in (self.storage_dir, self.outputs_dir, self.temp_dir, self.public_dir):
            directory.mkdir(parents=True, exist_ok=True)

        (self.public_dir / "downloads").mkdir(parents=True, exist_ok=True)


@lru_cache()
def get_settings() -> Settings:
    settings = Settings()
    settings.configure_paths()
    return settings
