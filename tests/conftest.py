import json
from pathlib import Path

import pytest

from blinka.adapters.reference_files import JsonReferenceSource
from blinka.adapters.sqlite_store import SqliteIntakeStore
from blinka.application.intake import IntakeService
from blinka.config import Settings

REPO = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture
def settings(tmp_path) -> Settings:
    """Facturas y referencias reales del repo; base SQLite aislada por prueba (fuera del repo)."""
    return Settings(
        root=REPO,
        invoices_dir=REPO / "data" / "invoices",
        reference_dir=REPO / "data" / "reference",
        db_path=tmp_path / "blinka.db",
    )


def make_service(settings: Settings) -> IntakeService:
    store = SqliteIntakeStore(settings.db_path)
    store.initialize()
    return IntakeService(settings, store, JsonReferenceSource(settings.reference_dir))


@pytest.fixture
def service(settings) -> IntakeService:
    return make_service(settings)


@pytest.fixture(scope="session")
def expected() -> dict:
    data = json.loads((FIXTURES / "expected_intake.json").read_text(encoding="utf-8"))
    data.pop("_nota", None)
    return data
