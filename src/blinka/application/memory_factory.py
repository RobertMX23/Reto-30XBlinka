from __future__ import annotations
from blinka.config import Settings
from blinka.adapters.in_memory_store import InMemoryFactStore


def build_memory_store(settings: Settings):
    if settings.memory_backend == "local":
        return InMemoryFactStore()
    if settings.memory_backend == "vertex_rag":
        if not settings.memory_rag_corpus:
            raise ValueError("BLINKA_MEMORY_RAG_CORPUS es obligatorio con backend vertex_rag.")
        from blinka.adapters.adk_memory_store import AdkRagMemoryStore
        return AdkRagMemoryStore(rag_corpus=settings.memory_rag_corpus)
    raise ValueError(f"Backend de memoria no soportado: {settings.memory_backend}")
