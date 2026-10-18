"""Coordinación local de lotes; cada documento conserva el flujo individual."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Callable

from blinka.domain.batch_models import BatchItem, BatchRequest, BatchResult, BatchState
from blinka.domain.input_models import WorkflowState
from blinka.ports.batch_storage import BatchStore


ItemProcessor = Callable[[BatchItem], BatchItem]


def process_batch(request: BatchRequest, processor: ItemProcessor) -> BatchResult:
    """Procesa items con concurrencia limitada y agrega resultados sin mover dinero."""
    items = list(request.items)

    def run(item: BatchItem) -> BatchItem:
        return processor(item.model_copy(update={"attempt": item.attempt + 1, "state": WorkflowState.RECEIVED}))

    with ThreadPoolExecutor(max_workers=request.max_concurrency) as pool:
        futures = {pool.submit(run, item): index for index, item in enumerate(items)}
        for future in as_completed(futures):
            index = futures[future]
            try:
                items[index] = future.result()
            except Exception as exc:
                items[index] = items[index].model_copy(
                    update={"state": WorkflowState.FAILED, "issues": [{"code": "ITEM_FAILED", "message": str(exc), "retryable": True}]}
                )

    counts = {"PAGAR": 0, "FRENAR": 0, "ESCALAR": 0}
    for item in items:
        state = item.result.get("state") if item.result else None
        if state in counts:
            counts[state] += 1
    failed = sum(item.state == WorkflowState.FAILED for item in items)
    completed = len(items) - failed
    state = BatchState.COMPLETED_WITH_ERRORS if failed else BatchState.COMPLETED
    return BatchResult(
        batch_id=request.batch_id,
        state=state,
        total_documents=len(items),
        completed_documents=completed,
        pagar=counts["PAGAR"],
        frenar=counts["FRENAR"],
        escalar=counts["ESCALAR"],
        failed=failed,
        items=items,
        completed_at=datetime.now(timezone.utc),
    )


def process_and_persist_batch(request: BatchRequest, processor: ItemProcessor, store: BatchStore) -> BatchResult:
    """Registra el lote antes de procesarlo y persiste el resultado agregado."""
    store.initialize()
    existing = store.get(request.batch_id)
    if existing is not None and existing.state in {BatchState.COMPLETED, BatchState.COMPLETED_WITH_ERRORS}:
        return existing
    created = store.create(request)
    processing = created.model_copy(update={"state": BatchState.PROCESSING})
    store.save(processing)
    return store.save(process_batch(request, processor))
