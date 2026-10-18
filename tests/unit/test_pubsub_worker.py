from blinka.application.pubsub_worker import process_batch_message
from blinka.adapters.sqlite_batch_store import SqliteBatchStore
from blinka.domain.batch_models import BatchItem, BatchRequest, BatchState
from blinka.domain.input_models import InputRequest


def test_worker_recovers_batch_and_processes_it(tmp_path):
    store = SqliteBatchStore(tmp_path / "worker.db")
    request = BatchRequest(batch_id="W-1", items=[BatchItem(document_id="D-1", request=InputRequest(content="x"))])
    store.create(request)
    result = process_batch_message('{"batch_id":"W-1"}', store, lambda item: item.model_copy(update={"result": {"state": "PAGAR"}}))
    assert result.batch_id == "W-1"
    assert result.state in {BatchState.COMPLETED, BatchState.COMPLETED_WITH_ERRORS}
