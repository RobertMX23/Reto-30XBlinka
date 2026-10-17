"""Lectura de facturas sinteticas: acceso restringido al directorio autorizado + parser del formato con etiquetas.

Formato admitido (texto UTF-8, una etiqueta por linea, `Etiqueta: valor`):

    Beneficiario: PROV-A
    Numero de factura: A-001
    Importe: 800.00
    Moneda: USD
    Vencimiento: 2026-10-25
    Acuerdo: AC-A-001
    Notas: texto libre (se conserva en la fuente; nunca se interpreta)

Las etiquetas ignoran mayusculas y acentos. Etiquetas desconocidas se ignoran. El parser solo mira el CONTENIDO:
no usa el nombre del archivo ni ninguna tabla de resultados esperados.
"""

from __future__ import annotations

import hashlib
import unicodedata
from pathlib import Path
from typing import Dict, List, Union

from blinka.domain.models import ExtractionCandidate, RawField, SourceDocument
from blinka.errors import PathNotAllowedError, SourceNotFoundError, SourceTooLargeError

ALLOWED_SUFFIX = ".txt"

_LABELS: Dict[str, str] = {
    "beneficiario": "beneficiary",
    "numero de factura": "invoice_number",
    "importe": "amount",
    "moneda": "currency",
    "vencimiento": "due_date",
    "acuerdo": "agreement_ref",
}


def _fold(label: str) -> str:
    decomposed = unicodedata.normalize("NFKD", label)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return " ".join(stripped.lower().split())


def parse_labeled_invoice(text: str) -> ExtractionCandidate:
    """Devuelve TODAS las apariciones de cada campo reconocido; la validacion decide que hacer con ellas."""
    fields: Dict[str, List[RawField]] = {}
    for line_no, line in enumerate(text.splitlines(), start=1):
        if ":" not in line:
            continue
        label, _, value = line.partition(":")
        name = _LABELS.get(_fold(label))
        if name is None:
            continue
        fields.setdefault(name, []).append(RawField(label=label.strip(), value=value.strip(), line_no=line_no, line=line))
    return ExtractionCandidate(fields=fields)


def resolve_allowed_path(invoices_dir: Path, root: Path, requested: Union[str, Path]) -> Path:
    """Valida la ruta ANTES de abrirla. Rutas relativas se interpretan desde la raiz del repositorio."""
    base = invoices_dir.resolve()
    candidate = Path(requested)
    if not candidate.is_absolute():
        candidate = root / candidate
    resolved = candidate.resolve()  # sigue enlaces simbolicos; no lee contenido
    if resolved != base and base not in resolved.parents:
        raise PathNotAllowedError("La ruta queda fuera del directorio de facturas autorizado.")
    if resolved.suffix.lower() != ALLOWED_SUFFIX:
        raise PathNotAllowedError(f"Solo se admiten archivos {ALLOWED_SUFFIX}.")
    return resolved


def read_source_file(
    invoices_dir: Path,
    root: Path,
    requested: Union[str, Path],
    *,
    max_bytes: int,
    ingest_key: str | None = None,
) -> SourceDocument:
    path = resolve_allowed_path(invoices_dir, root, requested)
    if not path.is_file():
        raise SourceNotFoundError("El archivo solicitado no existe dentro del directorio autorizado.")
    if path.stat().st_size > max_bytes:
        raise SourceTooLargeError(f"El archivo excede {max_bytes} bytes.")
    data = path.read_bytes()
    origin = path.relative_to(invoices_dir.resolve()).as_posix()
    return build_source(data, origin=origin, ingest_key=ingest_key or f"file:{origin}")


def build_source(data: bytes, *, origin: str, ingest_key: str) -> SourceDocument:
    """Conserva los bytes originales (huella) y su texto. latin-1 es una decodificacion sin perdida como respaldo."""
    try:
        text, encoding = data.decode("utf-8"), "utf-8"
    except UnicodeDecodeError:
        text, encoding = data.decode("latin-1"), "latin-1"
    return SourceDocument(
        ingest_key=ingest_key,
        origin=origin,
        text=text,
        encoding=encoding,  # type: ignore[arg-type]
        sha256=hashlib.sha256(data).hexdigest(),
        byte_length=len(data),
    )
