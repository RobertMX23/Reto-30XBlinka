from blinka.adapters.sqlite_batch_store import SqliteBatchStore
from blinka.domain.batch_models import BatchItem, BatchRequest
from blinka.domain.input_models import InputRequest
from blinka.tools.batch_tools import get_batch_status


def test_get_batch_status_returns_aggregate_and_items(tmp_path):
    store = SqliteBatchStore(tmp_path / "batch.db")
    request = BatchRequest(batch_id="BATCH-STATUS", items=[BatchItem(document_id="D-1", request=InputRequest(content="x"))])
    store.create(request)
    response = get_batch_status(request.batch_id, tmp_path / "batch.db")
    assert response["ok"] is True
    assert response["result"]["batch_id"] == "BATCH-STATUS"
    assert len(response["result"]["items"]) == 1


def test_get_batch_status_reports_missing_batch(tmp_path):
    response = get_batch_status("BATCH-MISSING", tmp_path / "batch.db")
    assert response == {"ok": False, "code": "BATCH_NOT_FOUND", "message": "No existe el lote BATCH-MISSING."}
