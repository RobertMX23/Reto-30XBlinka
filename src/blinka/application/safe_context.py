"""Construcción de contexto seguro para agentes o LLMs.

El texto original se conserva para auditoría, pero nunca se incluye en el
contexto destinado a instrucciones o decisiones de un agente.
"""

from __future__ import annotations

from typing import Any


def build_agent_safe_context(request: dict[str, Any], receipt: dict[str, Any] | None = None) -> dict[str, Any]:
    """Devuelve únicamente datos estructurados; el contenido crudo queda fuera."""
    receipt = receipt or {}
    fields = receipt.get("fields") or {}
    issues = receipt.get("issues") or []
    return {
        "contract_version": "1.0",
        "source_type": request.get("source_type") or "TEXT",
        "source_trust": "UNTRUSTED_DATA",
        "instructions_allowed": False,
        "fields": {
            key: fields.get(key)
            for key in ("beneficiary_id", "invoice_number", "amount", "currency", "due_date", "agreement_ref")
        },
        "issues": issues,
        "evidence": {
            "intake_id": receipt.get("intake_id"),
            "sha256": (receipt.get("source") or {}).get("sha256"),
        },
        "moves_money": False,
    }
