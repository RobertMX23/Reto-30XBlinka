"""Tools de clasificación y normalización de entradas. No usan LLM ni mueven dinero."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from blinka.domain.input_models import InputRequest, SourceType


SUPPORTED_SOURCE_TYPES = {SourceType.TEXT, SourceType.TXT_FILE, SourceType.PDF_TEXT}


def classify_input(value: Any) -> InputRequest:
    """Convierte texto ADK o un objeto JSON en el contrato de entrada."""
    if isinstance(value, InputRequest):
        request = value
    elif isinstance(value, dict):
        request = InputRequest.model_validate(value)
    else:
        text = value
        if hasattr(value, "parts"):
            text = "".join(getattr(part, "text", "") or "" for part in value.parts)
        raw_text = str(text or "")
        try:
            decoded = json.loads(raw_text)
        except json.JSONDecodeError:
            decoded = None
        request = InputRequest.model_validate(decoded) if isinstance(decoded, dict) else InputRequest(content=raw_text, origin="CHAT")
    if request.source_type is None:
        if request.path:
            request = request.model_copy(update={"source_type": SourceType.TXT_FILE})
        else:
            request = request.model_copy(update={"source_type": SourceType.TEXT})
    if request.source_type == SourceType.TXT_FILE and request.mime_type is None:
        request = request.model_copy(update={"mime_type": "text/plain"})
    if request.source_type == SourceType.PDF_TEXT and request.mime_type is None:
        request = request.model_copy(update={"mime_type": "application/pdf"})
    return request


def validate_supported_input(request: InputRequest) -> list[dict[str, Any]]:
    """Devuelve incidencias de clasificación sin abrir ni interpretar la fuente."""
    issues: list[dict[str, Any]] = []
    if request.source_type not in SUPPORTED_SOURCE_TYPES:
        issues.append({"code": "SOURCE_TYPE_UNSUPPORTED", "message": f"Aún no existe un adaptador para {request.source_type}.", "retryable": False})
    elif request.source_type == SourceType.TEXT and not (request.content or "").strip():
        issues.append({"code": "EMPTY_INPUT", "message": "El texto de entrada está vacío.", "retryable": False})
    elif request.source_type in {SourceType.TXT_FILE, SourceType.PDF_TEXT} and not request.path:
        issues.append({"code": "PATH_REQUIRED", "message": f"Una entrada {request.source_type} requiere path.", "retryable": False})
    return issues


def preserve_input(request: InputRequest) -> dict[str, Any]:
    """Devuelve la solicitud lista para IntakeService; la persistencia la hace el servicio existente."""
    if request.source_type == SourceType.TEXT:
        return {"text": request.content or "", **({"ingest_key": request.ingest_key} if request.ingest_key else {})}
    if request.source_type == SourceType.TXT_FILE:
        return {"path": request.path, **({"ingest_key": request.ingest_key} if request.ingest_key else {})}
    if request.source_type == SourceType.PDF_TEXT:
        return {"path": request.path, **({"ingest_key": request.ingest_key} if request.ingest_key else {})}
    raise ValueError(f"No existe adaptador para {request.source_type}")
