"""Adaptador opcional para Vertex AI RAG Memory de ADK.

Se importa de forma perezosa: Codespaces puede usar memoria local sin credenciales.
"""
from __future__ import annotations

from blinka.domain.memory_models import MemoryFact, MemorySearchRequest, MemorySearchResult


class AdkRagMemoryStore:
    def __init__(self, *, rag_corpus: str, similarity_top_k: int = 5, vector_distance_threshold: float = 0.6) -> None:
        if not rag_corpus:
            raise ValueError("rag_corpus es obligatorio para el backend ADK RAG.")
        try:
            from google.adk.memory import VertexAiRagMemoryService
        except ImportError as exc:
            raise RuntimeError("Instala google-adk[gcp] para activar Vertex AI RAG.") from exc
        self._service = VertexAiRagMemoryService(
            rag_corpus=rag_corpus,
            similarity_top_k=similarity_top_k,
            vector_distance_threshold=vector_distance_threshold,
        )

    def add_fact(self, fact: MemoryFact) -> None:
        raise NotImplementedError("La escritura de hechos debe implementarse con MemoryEntry y metadatos validados.")

    async def search(self, request: MemorySearchRequest | dict) -> MemorySearchResult:
        request = MemorySearchRequest.model_validate(request)
        response = await self._service.search_memory(query=request.query)
        memories = []
        for entry in getattr(response, "memories", []):
            text = " ".join(
                part.text for part in getattr(getattr(entry, "content", None), "parts", []) if getattr(part, "text", None)
            )
            memories.append(MemoryFact(
                fact_id=f"rag:{len(memories)}", fact_type="retrieved_context", tenant_id=request.tenant_id,
                content={"text": text}, source_type="ADK_RAG", evidence_ids=[],
            ))
        return MemorySearchResult(memories=memories[: request.top_k], query=request.query, source="adk_vertex_rag")
