"""Fallos tecnicos y rechazos de entrada.

Se distinguen de los resultados de negocio: una factura con incidencias se REGISTRA (no es un error);
una ruta no autorizada o una clave en conflicto SI son errores explicitos y nunca se convierten en exito.
"""

from __future__ import annotations


class BlinkaError(Exception):
    """Base de los errores esperados. Cualquier otra excepcion se considera fallo tecnico inesperado."""

    code = "BLINKA_ERROR"
    kind = "TECHNICAL"  # TECHNICAL | REJECTED | CONFLICT


class ConfigurationError(BlinkaError):
    code = "CONFIGURATION_ERROR"
    kind = "TECHNICAL"


class PathNotAllowedError(BlinkaError):
    code = "PATH_NOT_ALLOWED"
    kind = "REJECTED"


class SourceNotFoundError(BlinkaError):
    code = "SOURCE_NOT_FOUND"
    kind = "REJECTED"


class SourceTooLargeError(BlinkaError):
    code = "SOURCE_TOO_LARGE"
    kind = "REJECTED"


class InvalidRequestError(BlinkaError):
    code = "INVALID_REQUEST"
    kind = "REJECTED"


class IngestConflictError(BlinkaError):
    code = "INGEST_CONFLICT"
    kind = "CONFLICT"

    def __init__(self, message: str, *, intake_id: str, existing_sha256: str, new_sha256: str):
        super().__init__(message)
        self.intake_id = intake_id
        self.existing_sha256 = existing_sha256
        self.new_sha256 = new_sha256


class StorageError(BlinkaError):
    code = "STORAGE_ERROR"
    kind = "TECHNICAL"
