from blinka.domain.batch_models import BatchItem, BatchRequest, BatchState
from blinka.domain.input_models import InputRequest
from agents.blinka_orchestrator.nodes import process_batch_request


def _invoice(number: str, amount: str = "800.00", agreement: str = "AC-A-001") -> str:
    return "\n".join(
        [
            "Beneficiario: PROV-A",
            f"Numero de factura: {number}",
            f"Importe: {amount}",
            "Moneda: USD",
            "Vencimiento: 2026-10-25",
            f"Acuerdo: {agreement}",
        ]
    )


def test_orchestrator_processes_batch_through_real_decision_flow(service, monkeypatch):
    monkeypatch.setenv("BLINKA_DB_PATH", str(service._settings.db_path))
    request = BatchRequest(
        batch_id="BATCH-ORCH-001",
        max_concurrency=2,
        items=[
            BatchItem(document_id="DOC-001", request=InputRequest(content=_invoice("B-001"))),
            BatchItem(document_id="DOC-002", request=InputRequest(content=_invoice("B-002", "1500.00", "AC-A-002"))),
            BatchItem(document_id="DOC-003", request=InputRequest(content=_invoice("B-003", "800.00"))),
        ],
    )
    result = process_batch_request(request)
    assert result.state == BatchState.COMPLETED
    assert (result.pagar, result.escalar, result.frenar) == (2, 1, 0)
    assert all(item.result["moves_money"] is False for item in result.items)
    assert all(item.attempt == 1 for item in result.items)


def test_orchestrator_batch_is_idempotent_for_same_documents(service, monkeypatch):
    monkeypatch.setenv("BLINKA_DB_PATH", str(service._settings.db_path))
    request = BatchRequest(
        batch_id="BATCH-ORCH-REPLAY",
        items=[BatchItem(document_id="DOC-001", request=InputRequest(content=_invoice("REPLAY-001")))],
    )
    first = process_batch_request(request)
    second = process_batch_request(request)
    assert first.items[0].result["ingest_outcome"] == "CREATED"
    assert second.items[0].result["ingest_outcome"] == "REPLAYED"
    assert first.items[0].result["intake_id"] == second.items[0].result["intake_id"]
