from blinka.adapters.sqlite_batch_store import SqliteBatchStore
from blinka.application.batch import resume_persisted_batch
from blinka.domain.batch_models import BatchItem, BatchRequest, BatchState
from blinka.domain.input_models import InputRequest, WorkflowState


def test_resume_retries_only_failed_items(tmp_path):
    store = SqliteBatchStore(tmp_path / "batches.db")
    request = BatchRequest(batch_id="BATCH-RESUME", items=[
        BatchItem(document_id="DONE", request=InputRequest(content="done"), state=WorkflowState.PAGAR, result={"state": "PAGAR"}),
        BatchItem(document_id="RETRY", request=InputRequest(content="retry"), state=WorkflowState.FAILED),
    ])
    store.create(request)
    calls = []
    def processor(item):
        calls.append(item.document_id)
        return item.model_copy(update={"state": WorkflowState.ESCALAR, "result": {"state": "ESCALAR"}})
    result = resume_persisted_batch(request.batch_id, processor, store)
    assert calls == ["RETRY"]
    assert result.state == BatchState.COMPLETED
    assert result.pagar == 1 and result.escalar == 1
