from blinka.application.batch import process_batch
from blinka.domain.batch_models import BatchItem, BatchRequest, BatchState
from blinka.domain.input_models import InputRequest, WorkflowState


def _item(number: int) -> BatchItem:
    return BatchItem(
        document_id=f"DOC-{number:03d}",
        request=InputRequest(content=f"factura {number}"),
    )


def test_batch_processes_items_and_aggregates_decisions():
    request = BatchRequest(batch_id="BATCH-001", items=[_item(1), _item(2), _item(3)], max_concurrency=2)

    def processor(item: BatchItem) -> BatchItem:
        state = {"DOC-001": "PAGAR", "DOC-002": "ESCALAR", "DOC-003": "FRENAR"}[item.document_id]
        return item.model_copy(update={"state": WorkflowState(state), "result": {"state": state}})

    result = process_batch(request, processor)
    assert result.state == BatchState.COMPLETED
    assert (result.pagar, result.escalar, result.frenar) == (1, 1, 1)
    assert all(item.attempt == 1 for item in result.items)
    assert result.moves_money is False


def test_batch_limits_items_to_one_hundred():
    items = [_item(index) for index in range(100)]
    assert len(BatchRequest(batch_id="BATCH-100", items=items).items) == 100
    with pytest.raises(ValueError):
        BatchRequest(batch_id="BATCH-101", items=[_item(index) for index in range(101)])
import pytest
