"""Composicion de dependencias locales (SQLite + referencias JSON). Usado por la CLI y por el adaptador ADK."""

from __future__ import annotations

from typing import Optional

from blinka.adapters.reference_files import JsonReferenceSource
from blinka.adapters.sqlite_store import SqliteIntakeStore
from blinka.application.intake import IntakeService
from blinka.config import Settings


def build_service(settings: Optional[Settings] = None, *, initialize: bool = True) -> IntakeService:
    settings = settings or Settings.from_env()
    store = SqliteIntakeStore(settings.db_path)
    if initialize:
        store.initialize()
    return IntakeService(settings, store, JsonReferenceSource(settings.reference_dir))
