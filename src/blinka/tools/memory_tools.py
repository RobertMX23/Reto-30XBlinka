from __future__ import annotations
from typing import Any
from blinka.domain.memory_models import MemorySearchRequest


def search_blinka_memory(query: str, tenant_id: str, memory_store: Any) -> dict[str, Any]:
    """Herramienta segura: devuelve contexto no autoritativo y nunca texto crudo."""
    result = memory_store.search(MemorySearchRequest(query=query, tenant_id=tenant_id))
    return result.model_dump(mode="json")
