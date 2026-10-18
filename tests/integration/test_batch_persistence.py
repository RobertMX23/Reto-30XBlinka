from blinka.adapters.sqlite_batch_store import SqliteBatchStore
from blinka.domain.batch_models import BatchItem, BatchRequest, BatchState
from blinka.domain.input_models import InputRequest


def test_batch_state_is_persisted_and_recoverable(tmp_path):
    store = SqliteBatchStore(tmp_path / "batches.db")
    request = BatchRequest(batch_id="BATCH-PERSIST", items=[BatchItem(document_id="D-1", request=InputRequest(content="x"))])
    created = store.create(request)
    assert created.state == BatchState.RECEIVED
    recovered = store.get(request.batch_id)
    assert recovered is not None
    assert recovered.total_documents == 1


def test_batch_can_be_marked_processing_before_workers_start(tmp_path):
    store = SqliteBatchStore(tmp_path / "batches.db")
    request = BatchRequest(batch_id="BATCH-PROCESSING", items=[BatchItem(document_id="D-1", request=InputRequest(content="x"))])
    created = store.create(request)
    processing = created.model_copy(update={"state": BatchState.PROCESSING})
    store.save(processing)
    assert store.get(request.batch_id).state == BatchState.PROCESSING
