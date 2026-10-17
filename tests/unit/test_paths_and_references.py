import json
import pathlib
import shutil

import pytest

from blinka.adapters import fixture_reader
from blinka.adapters.fixture_reader import read_source_file, resolve_allowed_path
from blinka.adapters.reference_files import JsonReferenceSource
from blinka.errors import ConfigurationError, PathNotAllowedError, SourceNotFoundError, SourceTooLargeError

REPO = pathlib.Path(__file__).resolve().parents[2]


@pytest.fixture
def sandbox(tmp_path):
    inv = tmp_path / "facturas"
    inv.mkdir()
    (inv / "ok.txt").write_text("Beneficiario: PROV-A\n", encoding="utf-8")
    outside = tmp_path / "secreto.txt"
    outside.write_text("CONTENIDO CONFIDENCIAL", encoding="utf-8")
    return tmp_path, inv, outside


def test_path_outside_directory_is_rejected_without_reading_it(sandbox, monkeypatch):
    root, inv, outside = sandbox
    reads = []
    original = pathlib.Path.read_bytes

    def spy(self):
        reads.append(str(self))
        return original(self)

    monkeypatch.setattr(pathlib.Path, "read_bytes", spy)
    for attempt in (outside, "../secreto.txt", "/etc/passwd", "facturas/../secreto.txt"):
        with pytest.raises(PathNotAllowedError):
            read_source_file(inv, root, attempt, max_bytes=1000)
    assert reads == []  # nunca se abrio nada


def test_symlink_escaping_the_directory_is_rejected(sandbox, monkeypatch):
    root, inv, outside = sandbox
    link = inv / "enlace.txt"
    try:
        link.symlink_to(outside)
    except (OSError, NotImplementedError) as exc:
        # Windows requires the SeCreateSymbolicLink privilege unless
        # Developer Mode is enabled. The product behavior is covered on
        # systems that can create the fixture; skip only this setup case.
        if isinstance(exc, NotImplementedError) or getattr(exc, "winerror", None) == 1314:
            pytest.skip("El entorno no permite crear symlinks sin privilegios.")
        raise
    monkeypatch.setattr(pathlib.Path, "read_bytes", lambda self: pytest.fail("no debio leerse"))
    with pytest.raises(PathNotAllowedError):
        read_source_file(inv, root, link, max_bytes=1000)


def test_only_txt_inside_directory_and_missing_file(sandbox):
    root, inv, _ = sandbox
    (inv / "datos.json").write_text("{}", encoding="utf-8")
    with pytest.raises(PathNotAllowedError):
        resolve_allowed_path(inv, root, inv / "datos.json")
    with pytest.raises(SourceNotFoundError):
        read_source_file(inv, root, inv / "no_existe.txt", max_bytes=1000)


def test_allowed_relative_and_absolute_paths_work(sandbox):
    root, inv, _ = sandbox
    a = read_source_file(inv, root, "facturas/ok.txt", max_bytes=1000)
    b = read_source_file(inv, root, inv / "ok.txt", max_bytes=1000)
    assert a.sha256 == b.sha256 and a.origin == "ok.txt" and a.ingest_key == "file:ok.txt"


def test_oversized_file_rejected(sandbox):
    root, inv, _ = sandbox
    (inv / "grande.txt").write_bytes(b"x" * 50)
    with pytest.raises(SourceTooLargeError):
        read_source_file(inv, root, inv / "grande.txt", max_bytes=10)


def test_policy_and_references_load_with_identifiers_and_versions():
    refs = JsonReferenceSource(REPO / "data" / "reference")
    policy, sha = refs.get_policy()
    assert policy.version == "DEMO-v1" and len(sha) == 64
    assert str(policy.auto_threshold) == "1000.00" and str(policy.max_per_invoice) == "3000.00"
    assert refs.get_beneficiary("prov-a").name == "Proveedor Ficticio A"  # sin distinguir mayusculas
    assert refs.get_agreement("AC-A-001").beneficiary_id == "PROV-A"
    assert refs.get_agreement("AC-X-999") is None and refs.get_beneficiary("NADIE") is None


def _copy_refs(tmp_path, **overrides):
    dst = tmp_path / "ref"
    shutil.copytree(REPO / "data" / "reference", dst)
    policy = json.loads((dst / "policy.json").read_text(encoding="utf-8"))
    policy.update(overrides)
    (dst / "policy.json").write_text(json.dumps(policy), encoding="utf-8")
    return JsonReferenceSource(dst)


@pytest.mark.parametrize(
    "override",
    [{"auto_threshold": "4000.00"}, {"period_budget": "-1"}, {"synthetic": False}],
)
def test_invalid_policy_is_refused(tmp_path, override):
    with pytest.raises(ConfigurationError):
        _copy_refs(tmp_path, **override).get_policy()


def test_broken_reference_file_is_a_configuration_error(tmp_path):
    refs = _copy_refs(tmp_path)
    (tmp_path / "ref" / "agreements.json").write_text("{no es json", encoding="utf-8")
    with pytest.raises(ConfigurationError):
        refs.get_agreement("AC-A-001")
