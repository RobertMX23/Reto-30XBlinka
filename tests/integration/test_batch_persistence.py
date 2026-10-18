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
