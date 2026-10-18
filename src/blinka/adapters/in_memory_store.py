from __future__ import annotations
from blinka.domain.memory_models import MemoryFact, MemorySearchRequest, MemorySearchResult


class InMemoryFactStore:
    """Memoria local para desarrollo; filtra por tenant y no es autoridad."""
    def __init__(self) -> None:
        self._facts: list[MemoryFact] = []

    def add_fact(self, fact: MemoryFact) -> None:
        if fact.moves_money or fact.source_trust != "VALIDATED_STRUCTURED_DATA":
            raise ValueError("Solo se permiten hechos estructurados y no financieros.")
        self._facts.append(fact)

    def search(self, request: MemorySearchRequest | dict) -> MemorySearchResult:
        request = MemorySearchRequest.model_validate(request)
        tokens = {token.casefold() for token in request.query.split() if token.strip()}
        candidates = [fact for fact in self._facts if fact.tenant_id == request.tenant_id]
        ranked = sorted(candidates, key=lambda fact: sum(token in str(fact.content).casefold() for token in tokens), reverse=True)
        return MemorySearchResult(memories=ranked[:request.top_k], query=request.query, source="local", authoritative=False)
