"""Configuracion local sin secretos. Se lee del entorno (y de un .env opcional)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Optional

from dotenv import load_dotenv

DEFAULT_MAX_SOURCE_BYTES = 256 * 1024
DEFAULT_MAX_PDF_PAGES = 100
DEFAULT_MAX_EXTRACTED_TEXT_BYTES = 1024 * 1024


@dataclass(frozen=True)
class Settings:
    root: Path
    invoices_dir: Path
    reference_dir: Path
    db_path: Path
    max_source_bytes: int = DEFAULT_MAX_SOURCE_BYTES
    max_pdf_pages: int = DEFAULT_MAX_PDF_PAGES
    max_extracted_text_bytes: int = DEFAULT_MAX_EXTRACTED_TEXT_BYTES

    @classmethod
    def from_env(
        cls,
        root: Optional[Path] = None,
        env: Optional[Mapping[str, str]] = None,
    ) -> "Settings":
        if env is None:
            base = Path(root) if root else Path(os.environ.get("BLINKA_ROOT") or Path(__file__).resolve().parents[2])
            load_dotenv(base / ".env", override=False)
            env = os.environ
        base = Path(root) if root else Path(env.get("BLINKA_ROOT") or Path(__file__).resolve().parents[2])
        base = base.resolve()

        def _path(name: str, default: str) -> Path:
            raw = Path(env.get(name) or default)
            return (raw if raw.is_absolute() else base / raw).resolve()

        return cls(
            root=base,
            invoices_dir=_path("BLINKA_INVOICES_DIR", "data/invoices"),
            reference_dir=_path("BLINKA_REFERENCE_DIR", "data/reference"),
            db_path=_path("BLINKA_DB_PATH", "var/blinka.db"),
            max_pdf_pages=int(env.get("BLINKA_MAX_PDF_PAGES") or DEFAULT_MAX_PDF_PAGES),
            max_extracted_text_bytes=int(env.get("BLINKA_MAX_EXTRACTED_TEXT_BYTES") or DEFAULT_MAX_EXTRACTED_TEXT_BYTES),
        )
