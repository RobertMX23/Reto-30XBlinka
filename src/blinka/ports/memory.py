from __future__ import annotations
from typing import Protocol
from blinka.domain.memory_models import MemoryFact, MemorySearchRequest, MemorySearchResult


class MemoryStore(Protocol):
    def add_fact(self, fact: MemoryFact) -> None: ...
    def search(self, request: MemorySearchRequest) -> MemorySearchResult: ...
