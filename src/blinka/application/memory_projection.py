from __future__ import annotations
import hashlib
from typing import Any
from blinka.domain.memory_models import MemoryFact


def project_invoice_to_memory(receipt: dict[str, Any], decision: dict[str, Any] | None = None, *, tenant_id: str = "default") -> MemoryFact:
    fields = receipt.get("fields") or {}
    decision = decision or {}
    invoice = fields.get("invoice_number") or receipt.get("intake_id") or "unknown"
    content = {
        "beneficiary_id": fields.get("beneficiary_id"), "invoice_number": fields.get("invoice_number"),
        "agreement_ref": fields.get("agreement_ref"), "amount": fields.get("amount"),
        "currency": fields.get("currency"), "decision": decision.get("decision"),
        "reasons": decision.get("reasons", []),
    }
    return MemoryFact(
        fact_id="fact-" + hashlib.sha256(f"{tenant_id}:{invoice}".encode()).hexdigest()[:16],
        fact_type="invoice_decision", tenant_id=tenant_id, beneficiary_id=fields.get("beneficiary_id"),
        invoice_number=fields.get("invoice_number"), agreement_ref=fields.get("agreement_ref"),
        content=content, source_type="STRUCTURED_RECEIPT", evidence_ids=[receipt.get("intake_id", "")],
        policy_version=decision.get("policy_version"),
    )
