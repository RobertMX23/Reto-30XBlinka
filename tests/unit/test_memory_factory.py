from pathlib import Path
import pytest
from blinka.application.memory_factory import build_memory_store
from blinka.config import Settings
from blinka.adapters.in_memory_store import InMemoryFactStore


def _settings(**kwargs):
    return Settings(root=Path("."), invoices_dir=Path("data/invoices"), reference_dir=Path("data/reference"), db_path=Path("var/test.db"), **kwargs)


def test_memory_factory_defaults_to_local():
    assert isinstance(build_memory_store(_settings()), InMemoryFactStore)


def test_vertex_backend_requires_corpus():
    with pytest.raises(ValueError, match="RAG_CORPUS"):
        build_memory_store(_settings(memory_backend="vertex_rag"))
