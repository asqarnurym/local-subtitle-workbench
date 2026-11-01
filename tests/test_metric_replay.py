"""Saved prediction replay must preserve failures, confidences and boundary values."""

import copy
import sys
from dataclasses import replace
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.replay_frozen_metrics import deserialize_predictions, differences  # noqa: E402
from scripts.speech_benchmark import (  # noqa: E402
    evaluate_mode,
    load_synthetic_utterances,
    serialize_predictions,
)
from subtitle_workbench.corpora import stage_synthetic_benchmark  # noqa: E402


def test_prediction_replay_preserves_metrics_and_failures(tmp_path: Path):
    utterances = load_synthetic_utterances(stage_synthetic_benchmark(tmp_path / "data"))
    original = {u.id: (u.ref_words, u.ref_phones) for u in utterances}
    original[utterances[0].id] = "AlignmentFailure: recorded failure"
    words, phones = original[utterances[1].id]
    original[utterances[1].id] = ([replace(words[0], confidence=0.375), *words[1:]], phones)
    mode = "A2_proposed"
    saved = serialize_predictions({mode: original}, [mode])
    restored = deserialize_predictions(saved)[mode]
    expected = evaluate_mode(mode, utterances, original, "speaker", 20, 42)
    actual = evaluate_mode(mode, utterances, restored, "speaker", 20, 42)
    assert expected == actual
    for u in utterances[1:]:
        assert [(w.start, w.end, w.confidence) for w in restored[u.id][0]] == [
            (w.start, w.end, w.confidence) for w in original[u.id][0]
        ]


def test_replay_requires_saved_confidence():
    payload = {
        "schema_version": 1,
        "fields": {"word": "text,normalized,start,end", "phone": "phoneme,start,end"},
        "modes": {},
    }
    with pytest.raises(ValueError, match="confidence"):
        deserialize_predictions(payload)


def test_comparison_detects_small_numeric_changes_missing_fields_and_extra_rows():
    original = {"rows": [{"mae_ms": 17.0, "coverage": 0.89}], "ci": [15.2, 18.9]}
    changed = copy.deepcopy(original)
    changed["rows"][0]["mae_ms"] += 1e-12
    del changed["rows"][0]["coverage"]
    changed["rows"].append({"mae_ms": 1.0})
    changed["ci"][1] = 19.0
    paths = {entry["path"] for entry in differences(original, changed)}
    assert paths == {"$.rows[0].mae_ms", "$.rows[0].coverage", "$.rows", "$.ci[1]"}
