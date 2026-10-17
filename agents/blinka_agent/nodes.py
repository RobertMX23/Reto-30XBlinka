"""Adaptadores finos entre ADK y el servicio de ingreso. Aqui NO hay logica de negocio ni llamadas a un modelo.

Cada nodo recibe y devuelve diccionarios JSON. Un rechazo o conflicto viaja como {"error": {...}} y los nodos
siguientes lo dejan pasar sin tocarlo: nunca se convierte en exito ni se registra una aprobacion por defecto.
Solo se capturan errores ESPERADOS de Blinka (BlinkaError); cualquier otra excepcion se propaga como fallo tecnico.
"""

from __future__ import annotations

import json
from typing import Any

from blinka.application.intake import conflict_error  # noqa: F401  (reutilizado por pruebas)
from blinka.domain.models import ExtractionResult, ReferenceLookup, SourceDocument
from blinka.errors import BlinkaError, IngestConflictError, InvalidRequestError
from blinka.ports.storage import SaveResult
from blinka.wiring import build_service


def _error(exc: BlinkaError) -> dict:
    payload = {"code": exc.code, "kind": exc.kind, "message": str(exc)}
    if isinstance(exc, IngestConflictError):
        payload.update(intake_id=exc.intake_id, existing_sha256=exc.existing_sha256, new_sha256=exc.new_sha256)
    return {"error": payload}


def _request_from_input(node_input: Any) -> dict:
    """El mensaje de usuario es un JSON: {"path": ...} o {"text": ...}, con "ingest_key" opcional."""
    if isinstance(node_input, dict):
        return node_input
    if isinstance(node_input, str):
        text = node_input
    elif hasattr(node_input, "parts"):
        text = "".join(getattr(p, "text", "") or "" for p in node_input.parts)
    else:
        raise InvalidRequestError("Entrada no reconocida.")
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise InvalidRequestError(f"La solicitud debe ser JSON ({{'path': ...}} o {{'text': ...}}): {exc}") from exc
    if not isinstance(data, dict):
        raise InvalidRequestError("La solicitud debe ser un objeto JSON.")
    return data


# 1. Leer y conservar ---------------------------------------------------------------------------
def read_source(node_input: Any) -> dict:
    try:
        source = build_service().read_source(_request_from_input(node_input))
    except BlinkaError as exc:
        return _error(exc)
    return {"source": source.model_dump(mode="json")}


# 2. Parsear y validar --------------------------------------------------------------------------
def parse_and_validate(node_input: dict) -> dict:
    if "error" in node_input:
        return node_input
    source = SourceDocument.model_validate(node_input["source"])
    extraction = build_service().extract(source)
    return {**node_input, "extraction": extraction.model_dump(mode="json")}


# 3. Cargar referencias -------------------------------------------------------------------------
def load_references(node_input: dict) -> dict:
    if "error" in node_input:
        return node_input
    extraction = ExtractionResult.model_validate(node_input["extraction"])
    try:
        lookup = build_service().load_references(extraction)
    except BlinkaError as exc:
        return _error(exc)
    return {**node_input, "references": lookup.model_dump(mode="json")}


# 4. Guardar ------------------------------------------------------------------------------------
def save_intake(node_input: dict) -> dict:
    if "error" in node_input:
        return node_input
    source = SourceDocument.model_validate(node_input["source"])
    extraction = ExtractionResult.model_validate(node_input["extraction"])
    lookup = ReferenceLookup.model_validate(node_input["references"])
    try:
        saved: SaveResult = build_service().save(source, extraction, lookup)
    except BlinkaError as exc:
        return _error(exc)
    if saved.outcome == "CONFLICT":
        return _error(conflict_error(saved))
    return {"saved": {"intake_id": saved.record.intake_id, "outcome": saved.outcome}}


# 5. Recuperar y emitir recibo --------------------------------------------------------------------
def recover_receipt(node_input: dict) -> dict:
    if "error" in node_input:
        return node_input
    try:
        receipt = build_service().receipt_for(node_input["saved"]["intake_id"])  # se LEE de la base, no de memoria
    except BlinkaError as exc:
        return _error(exc)
    if receipt is None:
        return {"error": {"code": "STORAGE_ERROR", "kind": "TECHNICAL", "message": "El ingreso guardado no pudo recuperarse."}}
    return {"ingest_outcome": node_input["saved"]["outcome"], "receipt": receipt.model_dump(mode="json")}


# F2: decision determinista ---------------------------------------------------------------
def evaluate_decision(node_input: Any) -> dict:
    """Evalua y persiste una decision por intake_id; nunca mueve dinero."""
    if isinstance(node_input, dict) and "error" in node_input:
        return node_input
    try:
        request = _request_from_input(node_input)
    except BlinkaError as exc:
        return _error(exc)
    intake_id = request.get("intake_id")
    if not isinstance(intake_id, str) or not intake_id:
        return {"error": {"code": "INVALID_REQUEST", "kind": "REJECTED", "message": "Se requiere intake_id."}}
    try:
        service = build_service()
        decision = service.decide(intake_id)
        if decision is None:
            return {"error": {"code": "NOT_FOUND", "kind": "REJECTED", "message": f"No existe {intake_id}"}}
        return {"intake_id": intake_id, "decision": decision.model_dump(mode="json")}
    except BlinkaError as exc:
        return _error(exc)


def recover_decision(node_input: dict) -> dict:
    if "error" in node_input:
        return node_input
    try:
        receipt = build_service().receipt_for(node_input["intake_id"])
    except BlinkaError as exc:
        return _error(exc)
    if receipt is None:
        return {"error": {"code": "STORAGE_ERROR", "kind": "TECHNICAL", "message": "La decision no pudo recuperarse."}}
    return {"decision": node_input["decision"], "receipt": receipt.model_dump(mode="json")}
