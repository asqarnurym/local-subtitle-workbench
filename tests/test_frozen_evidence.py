"""Integrity failures must be detected without loading any speech model."""

import hashlib
import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts import verify_frozen_evidence as evidence  # noqa: E402


def test_digest_rejects_line_ending_changes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(evidence, "ROOT", tmp_path)
    path = tmp_path / "result.json"
    original = b'{"mae_ms": 17.0}\r\n'
    path.write_bytes(original)
    expected = hashlib.sha256(original).hexdigest()
    assert evidence.verify_digest("result.json", expected) == expected

    # The JSON is identical, but its recorded byte-level fingerprint is not.
    path.write_bytes(original.replace(b"\r\n", b"\n"))
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        evidence.verify_digest("result.json", expected)


def test_manifest_path_cannot_escape_repository(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(evidence, "ROOT", tmp_path)
    with pytest.raises(ValueError, match="Path outside repository"):
        evidence.local_path("../outside.json")


def test_audit_output_cannot_overwrite_a_sample(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(evidence, "ROOT", tmp_path)
    baseline = {"reference_snapshot": {"files": {}}}
    monkeypatch.setattr(evidence, "audit", lambda: baseline)
    target = tmp_path / "reports" / "sample.json"
    target.parent.mkdir()
    (target.parent / "frozen_evidence_audit_20261101.json").write_text(json.dumps(baseline))
    original = b'{"utterance_ids": ["u1"]}\r\n'
    target.write_bytes(original)
    monkeypatch.setattr(
        sys, "argv", ["verify_frozen_evidence.py", "--output", "reports/sample.json"]
    )

    with pytest.raises(ValueError, match="Refusing to overwrite"):
        evidence.main()
    assert target.read_bytes() == original


def test_recheck_rejects_changed_reference_without_overwriting_baseline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(evidence, "ROOT", tmp_path)
    reference = tmp_path / "gold.TextGrid"
    reference.write_bytes(b"original reference\n")
    baseline = tmp_path / "reports" / "frozen_evidence_audit_20261101.json"
    baseline.parent.mkdir()
    original = json.dumps(
        {"reference_snapshot": {"files": {"gold.TextGrid": evidence.digest(reference)}}}
    ).encode()
    baseline.write_bytes(original)
    reference.write_bytes(b"changed reference\n")
    monkeypatch.setattr(
        evidence,
        "audit",
        lambda: {"reference_snapshot": {"files": {"gold.TextGrid": evidence.digest(reference)}}},
    )
    monkeypatch.setattr(sys, "argv", ["verify_frozen_evidence.py"])

    with pytest.raises(ValueError, match="Reference snapshot mismatch"):
        evidence.main()
    assert baseline.read_bytes() == original
