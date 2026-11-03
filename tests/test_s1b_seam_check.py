"""Tests for the S1b seam check report (scripts/s1b_seam_check.py)."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts import s1b_seam_check as check  # noqa: E402
from subtitle_workbench.models import AudioChunk, WordToken  # noqa: E402


def _words(n: int) -> list[WordToken]:
    return [WordToken(f"w{i}", "word", "word", i * 1.0, i * 1.0 + 0.5, 0.9) for i in range(n)]


def test_compare_with_one_layout_failed_is_json_serializable() -> None:
    utts = [
        SimpleNamespace(id="u1", speaker_id="s01", ref_words=_words(4)),
        SimpleNamespace(id="u2", speaker_id="s02", ref_words=_words(4)),
    ]
    chunks = [
        AudioChunk("c0", 0, 0.0, 2.0, 0.0, 2.5, "a"),
        AudioChunk("c1", 1, 2.0, 4.0, 1.5, 4.0, "b"),
    ]
    jobs = {("A", "multi"): {u.id: SimpleNamespace(chunks=chunks) for u in utts}}
    aligned = {
        ("A", "multi"): {"u1": _words(4), "u2": "AlignmentFailure: no TextGrid"},
        ("A", "single"): {"u1": _words(4), "u2": _words(4)},
    }
    res = check.compare(utts, jobs, aligned, "A")
    json.dumps(res, allow_nan=False)
    assert res["per_speaker"]["s02"] == {
        "failed": {"multi": "AlignmentFailure: no TextGrid", "single": None}
    }
    assert res["failed"] == {"multi": ["s02"], "single": []}
    assert res["near_excess_ms"] == 0.0 and res["pass"]
