"""Referencias ficticias en archivos JSON: policy.json, beneficiaries.json, agreements.json."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Dict, Optional

from blinka.domain.models import Agreement, Beneficiary, Policy
from blinka.errors import ConfigurationError


class JsonReferenceSource:
    def __init__(self, reference_dir: Path):
        self._dir = reference_dir
        self._policy: Optional[tuple[Policy, str]] = None
        self._beneficiaries: Optional[Dict[str, Beneficiary]] = None
        self._agreements: Optional[Dict[str, Agreement]] = None

    def _read(self, name: str) -> tuple[object, str]:
        path = self._dir / name
        try:
            raw = path.read_bytes()
        except OSError as exc:
            raise ConfigurationError(f"No se pudo leer la referencia {name}: {exc}") from exc
        try:
            return json.loads(raw), hashlib.sha256(raw).hexdigest()
        except json.JSONDecodeError as exc:
            raise ConfigurationError(f"{name} no es JSON valido: {exc}") from exc

    def get_policy(self) -> tuple[Policy, str]:
        if self._policy is None:
            data, sha = self._read("policy.json")
            self._policy = (Policy.model_validate(data), sha)
        return self._policy

    def _load_beneficiaries(self) -> Dict[str, Beneficiary]:
        if self._beneficiaries is None:
            data, _ = self._read("beneficiaries.json")
            items = [Beneficiary.model_validate(x) for x in data]  # type: ignore[union-attr]
            self._beneficiaries = {b.beneficiary_id.upper(): b for b in items}
        return self._beneficiaries

    def _load_agreements(self) -> Dict[str, Agreement]:
        if self._agreements is None:
            data, _ = self._read("agreements.json")
            items = [Agreement.model_validate(x) for x in data]  # type: ignore[union-attr]
            self._agreements = {a.agreement_ref.upper(): a for a in items}
        return self._agreements

    def get_beneficiary(self, beneficiary_id: str) -> Optional[Beneficiary]:
        return self._load_beneficiaries().get(beneficiary_id.upper())

    def get_agreement(self, agreement_ref: str) -> Optional[Agreement]:
        return self._load_agreements().get(agreement_ref.upper())

    def summary(self) -> dict:
        policy, sha = self.get_policy()
        return {
            "policy_version": policy.version,
            "policy_sha256": sha,
            "beneficiaries": len(self._load_beneficiaries()),
            "agreements": len(self._load_agreements()),
        }
