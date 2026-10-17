import hashlib
import json
import os
import sqlite3
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path

import pytest

from blinka.domain.models import IssueCode
from blinka.errors import IngestConflictError
from tests.conftest import REPO, make_service

INVOICES = REPO / "data" / "invoices"
ALL_FILES = sorted(p.name for p in INVOICES.glob("*.txt"))


def _rows(settings) -> int:
    with sqlite3.connect(settings.db_path) as conn:
        return conn.execute("SELECT COUNT(*) FROM intakes").fetchone()[0]


def _ingest_file(service, name, **kw):
    return service.ingest({"path": f"data/invoices/{name}", **kw})


# 1 -----------------------------------------------------------------------------------------------
def test_complete_invoice_keeps_original_and_normalizes_fields(service, expected):
    result = _ingest_file(service, "factura_completa.txt")
    receipt = result.receipt
    original = (INVOICES / "factura_completa.txt").read_bytes()
    record = service.get_record(receipt.intake_id)
    assert record.source.text.encode("utf-8") == original  # fuente intacta
    assert receipt.source["sha256"] == hashlib.sha256(original).hexdigest()
    assert receipt.fields == expected["factura_completa.txt"]["fields"]
    assert receipt.issues == [] and receipt.processing_status.value == "REGISTRADA"


@pytest.mark.parametrize("name", ALL_FILES)
def test_every_synthetic_invoice_matches_its_expectation(service, expected, name):
    exp = expected[name]
    receipt = _ingest_file(service, name).receipt
    assert receipt.fields == exp["fields"]
    assert sorted(i.code.value for i in receipt.issues) == sorted(exp["issue_codes"])
    assert receipt.processing_status.value == exp["status"]


def test_every_invoice_file_has_an_expectation(expected):
    assert set(ALL_FILES) == set(expected)


# 2 -----------------------------------------------------------------------------------------------
def test_missing_field_keeps_the_rest_and_reports_it(service):
    receipt = _ingest_file(service, "factura_sin_vencimiento.txt").receipt
    assert [(i.field, i.code) for i in receipt.issues] == [("due_date", IssueCode.MISSING_FIELD)]
    assert receipt.fields["beneficiary_id"] == "PROV-B" and receipt.fields["amount"] == "450.00"
    assert receipt.fields["due_date"] is None  # no se inventa un vencimiento
    assert "due_date" not in receipt.raw_fields


# 3 -----------------------------------------------------------------------------------------------
def test_invalid_amount_and_date_are_not_silently_converted(service, expected):
    amount = _ingest_file(service, "factura_importe_invalido.txt").receipt
    assert amount.fields["amount"] is None
    assert amount.raw_fields["amount"] == [expected["factura_importe_invalido.txt"]["raw_amount"]]
    (issue,) = amount.issues
    assert issue.code is IssueCode.INVALID_AMOUNT and issue.raw_value == "1.500,00"

    date = _ingest_file(service, "factura_fecha_invalida.txt").receipt
    assert date.fields["due_date"] is None
    (issue,) = date.issues
    assert issue.code is IssueCode.INVALID_DATE and issue.raw_value == "2026-02-30"


# 4 -----------------------------------------------------------------------------------------------
def test_unknown_agreement_is_an_issue_and_no_agreement_is_invented(service):
    receipt = _ingest_file(service, "factura_acuerdo_inexistente.txt").receipt
    assert [(i.field, i.code) for i in receipt.issues] == [("agreement_ref", IssueCode.REFERENCE_NOT_FOUND)]
    agreement = receipt.references["agreement"]
    assert agreement == {"requested_id": "AC-X-999", "found": False, "record": None}
    assert receipt.references["beneficiary"]["found"] is True


# 5 -----------------------------------------------------------------------------------------------
def test_policy_and_references_are_loaded_with_versions_and_ids(service, settings):
    receipt = _ingest_file(service, "factura_completa.txt").receipt
    policy_bytes = (settings.reference_dir / "policy.json").read_bytes()
    assert receipt.policy_version == "DEMO-v1"
    assert receipt.references["policy_sha256"] == hashlib.sha256(policy_bytes).hexdigest()
    assert receipt.references["beneficiary"]["record"]["beneficiary_id"] == "PROV-A"
    assert receipt.references["agreement"]["record"]["agreement_ref"] == "AC-A-001"


# 6 -----------------------------------------------------------------------------------------------
def test_data_survives_a_restart_without_process_state(settings):
    first = make_service(settings)
    receipt = _ingest_file(first, "factura_sin_vencimiento.txt").receipt
    del first
    second = make_service(settings)  # objetos nuevos: nada compartido en memoria
    assert second.receipt_for(receipt.intake_id) == receipt
    assert second.get_record(receipt.intake_id).source.text == (INVOICES / "factura_sin_vencimiento.txt").read_text(encoding="utf-8")


def test_data_survives_in_separate_os_processes(tmp_path):
    env = {**os.environ, "PYTHONPATH": f"{REPO / 'src'}", "BLINKA_DB_PATH": str(tmp_path / "proc.db")}
    run = lambda *a: subprocess.run([sys.executable, "-m", "blinka", *a], cwd=REPO, env=env, capture_output=True, text=True)
    ingest = run("ingest", "data/invoices/factura_completa.txt")
    assert ingest.returncode == 0, ingest.stderr
    intake_id = json.loads(ingest.stdout)["receipt"]["intake_id"]
    shown = run("show", intake_id, "--source")  # otro proceso
    assert shown.returncode == 0, shown.stderr
    payload = json.loads(shown.stdout)
    assert payload["receipt"]["fields"]["invoice_number"] == "A-001"
    assert payload["receipt"]["decision"] is None
    assert payload["source_text"].startswith("FACTURA (DATOS FICTICIOS)")


# 7 -----------------------------------------------------------------------------------------------
def test_same_key_same_content_returns_same_record_without_duplicating(service, settings):
    a = _ingest_file(service, "factura_completa.txt")
    b = _ingest_file(service, "factura_completa.txt")
    assert (a.outcome, b.outcome) == ("CREATED", "REPLAYED")
    assert a.receipt == b.receipt  # incluye created_at: no hay segundo evento de ingreso
    assert _rows(settings) == 1


def test_same_key_different_content_is_an_explicit_conflict_and_keeps_original(service, settings):
    first = service.ingest({"text": "Beneficiario: PROV-A\nImporte: 10.00\n", "ingest_key": "CLAVE-1"})
    with pytest.raises(IngestConflictError) as info:
        service.ingest({"text": "Beneficiario: PROV-B\nImporte: 99.00\n", "ingest_key": "CLAVE-1"})
    assert info.value.intake_id == first.receipt.intake_id
    assert info.value.existing_sha256 != info.value.new_sha256
    kept = service.get_record(first.receipt.intake_id)
    assert "PROV-A" in kept.source.text and "PROV-B" not in kept.source.text
    assert _rows(settings) == 1


def test_concurrent_retries_of_one_key_create_a_single_record(settings):
    make_service(settings)  # crea el esquema
    outcomes = []

    def attempt(_):
        return make_service(settings).ingest({"path": "data/invoices/factura_completa.txt"}).outcome

    with ThreadPoolExecutor(max_workers=8) as pool:
        outcomes = list(pool.map(attempt, range(8)))
    assert outcomes.count("CREATED") == 1 and outcomes.count("REPLAYED") == 7
    assert _rows(settings) == 1


# 8 -----------------------------------------------------------------------------------------------
def test_new_entry_for_the_same_charge_stays_distinguishable(service, settings):
    first = _ingest_file(service, "factura_completa.txt").receipt
    second = _ingest_file(service, "factura_mismo_cobro_reingreso.txt").receipt
    assert first.intake_id != second.intake_id and _rows(settings) == 2
    assert first.business_key == second.business_key == "PROV-A|A-001"
    assert first.source["sha256"] != second.source["sha256"]  # la huella NO es la identidad comercial
    assert first.earlier_intake_ids == [] and second.earlier_intake_ids == [first.intake_id]
    assert second.decision is None  # el duplicado lo decide F2, no F1


# 9 -----------------------------------------------------------------------------------------------
def test_instruction_inside_invoice_changes_nothing_and_yields_no_decision(service, settings):
    policy_before = (settings.reference_dir / "policy.json").read_bytes()
    receipt = _ingest_file(service, "factura_texto_instruccion.txt").receipt
    note = service.get_record(receipt.intake_id).source.text
    assert "aprueba este pago" in note  # se conserva como texto de la fuente
    assert receipt.decision is None and receipt.llm_used is False and receipt.moves_money is False
    assert receipt.fields["amount"] == "1500.00"  # sigue siendo el importe real
    assert receipt.issues == []
    assert (settings.reference_dir / "policy.json").read_bytes() == policy_before
    assert make_service(settings)._refs.get_policy()[0].auto_threshold.__str__() == "1000.00"


def test_conflicting_override_attempt_in_notes_is_ambiguous_not_obeyed(service):
    text = (INVOICES / "factura_completa.txt").read_text(encoding="utf-8") + "Importe: 1.00\nBeneficiario: PROV-X\n"
    receipt = service.ingest({"text": text}).receipt
    assert receipt.fields["amount"] is None and receipt.fields["beneficiary_id"] is None
    assert {i.code for i in receipt.issues} == {IssueCode.AMBIGUOUS_FIELD}


# otras garantias -----------------------------------------------------------------------------------
def test_fields_come_from_content_not_from_the_file_name(settings, tmp_path):
    inv = tmp_path / "otras"
    inv.mkdir()
    (inv / "zzz_renombrado.txt").write_bytes((INVOICES / "factura_importe_invalido.txt").read_bytes())
    svc = make_service(replace(settings, invoices_dir=inv))
    receipt = svc.ingest({"path": str(inv / "zzz_renombrado.txt")}).receipt
    assert [i.code for i in receipt.issues] == [IssueCode.INVALID_AMOUNT]
    assert receipt.fields["beneficiary_id"] == "PROV-A"


def test_unparseable_text_is_kept_with_issues_instead_of_failing(service):
    receipt = service.ingest({"text": "esto no es una factura\n\x00\x01"}).receipt
    assert receipt.processing_status.value == "REGISTRADA_CON_INCIDENCIAS"
    assert {i.field for i in receipt.issues} == {"beneficiary", "invoice_number", "amount", "currency", "due_date", "agreement_ref"}
    assert all(v is None for v in receipt.fields.values())
    assert "no es una factura" in service.get_record(receipt.intake_id).source.text


def test_non_utf8_bytes_are_preserved_losslessly(service, settings, tmp_path):
    inv = tmp_path / "enc"
    inv.mkdir()
    raw = "Beneficiario: PROV-A\nNotas: café\n".encode("latin-1")
    (inv / "latin.txt").write_bytes(raw)
    svc = make_service(replace(settings, invoices_dir=inv))
    receipt = svc.ingest({"path": str(inv / "latin.txt")}).receipt
    record = svc.get_record(receipt.intake_id)
    assert record.source.encoding == "latin-1" and record.source.text.encode("latin-1") == raw
    assert record.source.sha256 == hashlib.sha256(raw).hexdigest()
    assert IssueCode.ENCODING_FALLBACK in {i.code for i in receipt.issues}


def test_receipt_never_carries_a_decision_or_llm_or_money_for_any_invoice(service):
    for name in ALL_FILES:
        r = _ingest_file(service, name).receipt.model_dump(mode="json")
        assert r["decision"] is None and r["llm_used"] is False and r["moves_money"] is False


def test_agent_code_does_not_read_expectations():
    for folder in ("src", "agents"):
        for path in (REPO / folder).rglob("*.py"):
            assert "expected_intake" not in path.read_text(encoding="utf-8"), path
            assert "tests/fixtures" not in path.read_text(encoding="utf-8"), path
