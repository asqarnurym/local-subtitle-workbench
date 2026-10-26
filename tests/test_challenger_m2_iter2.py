"""Adversarial challenge test harness for Milestone 2 Iteration 2.

Authored by challenger_m2_iter2_1.
Verifies:
1. Robustness of _deserialize_raw_alignment on missing file, malformed JSON,
   empty words, empty phonemes, missing keys, and invalid types.
2. Error handling in run_benchmark when _deserialize_raw_alignment fails
   (wrapped in BenchmarkError).
3. End-to-end execution of run_benchmark(corpus="synthetic", offline_synthetic=False)
   with mock pipeline generating real alignments.
4. Word and phoneme boundary error computation without empty array errors.
5. Edge cases: empty phonemes in real mode, empty words in real mode,
   single utterance cluster handling, mismatched word counts between modes.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

# Ensure project root is on sys.path for importing scripts
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pytest  # noqa: E402

from scripts.speech_benchmark import (  # noqa: E402
    _deserialize_raw_alignment,
    run_benchmark,
)
from subtitle_workbench.corpora import parse_timit_phn, parse_timit_wrd  # noqa: E402
from subtitle_workbench.metrics import BenchmarkError  # noqa: E402
from subtitle_workbench.models import ASRSegment, PhonemeCue, WordToken  # noqa: E402

# ---------------------------------------------------------------------------
# 1. Stress Tests: _deserialize_raw_alignment
# ---------------------------------------------------------------------------


def test_deserialize_missing_file_raises_filenotfound(tmp_path: Path) -> None:
    """Missing alignment_raw.json must raise FileNotFoundError."""
    missing = tmp_path / "non_existent_alignment.json"
    with pytest.raises(FileNotFoundError):
        _deserialize_raw_alignment(missing)


def test_deserialize_malformed_json_raises_decode_error(tmp_path: Path) -> None:
    """Malformed or truncated JSON must raise json.JSONDecodeError."""
    bad_json = tmp_path / "malformed.json"
    bad_json.write_text('{ "schema_version": 1, "words": [', encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        _deserialize_raw_alignment(bad_json)

    bad_json.write_text("NOT_JSON_AT_ALL", encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        _deserialize_raw_alignment(bad_json)


def test_deserialize_empty_json_or_missing_words(tmp_path: Path) -> None:
    """JSON with no 'words' key or empty JSON dictionary returns empty list."""
    empty_dict_file = tmp_path / "empty_dict.json"
    empty_dict_file.write_text("{}", encoding="utf-8")
    assert _deserialize_raw_alignment(empty_dict_file) == []

    no_words_file = tmp_path / "no_words.json"
    no_words_file.write_text('{"schema_version": 1, "alignment_method": "ctc"}', encoding="utf-8")
    assert _deserialize_raw_alignment(no_words_file) == []


def test_deserialize_empty_words_list(tmp_path: Path) -> None:
    """Explicit empty 'words' list returns empty list."""
    empty_words_file = tmp_path / "empty_words.json"
    payload = {"schema_version": 1, "alignment_method": "mfa", "words": []}
    empty_words_file.write_text(json.dumps(payload), encoding="utf-8")
    assert _deserialize_raw_alignment(empty_words_file) == []


def test_deserialize_words_with_empty_phonemes_list(tmp_path: Path) -> None:
    """Words with empty 'phonemes' list deserialize properly with phonemes=[]."""
    test_file = tmp_path / "empty_phonemes.json"
    payload = {
        "words": [
            {
                "id": "w_0",
                "text": "hello",
                "normalized": "hello",
                "start": 0.1,
                "end": 0.5,
                "confidence": 0.98,
                "phonemes": [],
            }
        ]
    }
    test_file.write_text(json.dumps(payload), encoding="utf-8")
    tokens = _deserialize_raw_alignment(test_file)
    assert len(tokens) == 1
    w = tokens[0]
    assert isinstance(w, WordToken)
    assert w.id == "w_0"
    assert w.text == "hello"
    assert w.normalized == "hello"
    assert w.start == 0.1
    assert w.end == 0.5
    assert w.confidence == 0.98
    assert w.phonemes == []


def test_deserialize_words_missing_optional_phonemes_key(tmp_path: Path) -> None:
    """Word missing 'phonemes' key defaults safely to empty phonemes list."""
    test_file = tmp_path / "no_phonemes_key.json"
    payload = {
        "words": [
            {
                "id": "w_1",
                "text": "world",
                "normalized": "world",
                "start": 0.6,
                "end": 1.0,
            }
        ]
    }
    test_file.write_text(json.dumps(payload), encoding="utf-8")
    tokens = _deserialize_raw_alignment(test_file)
    assert len(tokens) == 1
    w = tokens[0]
    assert w.phonemes == []
    assert w.confidence == 1.0
    assert w.char_start is None
    assert w.char_end is None


def test_deserialize_nested_phonemes_parsing(tmp_path: Path) -> None:
    """Word with nested phonemes correctly constructs typed PhonemeCue instances."""
    test_file = tmp_path / "nested_phonemes.json"
    payload = {
        "words": [
            {
                "id": "w_0",
                "text": "cat",
                "normalized": "cat",
                "start": 0.2,
                "end": 0.6,
                "confidence": 0.95,
                "phonemes": [
                    {"phoneme": "k", "start": 0.2, "end": 0.3, "confidence": 0.9},
                    {"phoneme": "ae", "start": 0.3, "end": 0.5, "confidence": 0.95},
                    {"phoneme": "t", "start": 0.5, "end": 0.6, "confidence": 0.99},
                ],
            }
        ]
    }
    test_file.write_text(json.dumps(payload), encoding="utf-8")
    tokens = _deserialize_raw_alignment(test_file)
    assert len(tokens) == 1
    w = tokens[0]
    assert len(w.phonemes) == 3
    for p in w.phonemes:
        assert isinstance(p, PhonemeCue)
    assert w.phonemes[0].phoneme == "k"
    assert w.phonemes[0].start == 0.2
    assert w.phonemes[0].end == 0.3
    assert w.phonemes[0].confidence == 0.9
    assert w.phonemes[2].phoneme == "t"
    assert w.phonemes[2].end == 0.6


def test_deserialize_missing_required_word_keys_raises_keyerror(tmp_path: Path) -> None:
    """Missing required word keys (id, text, normalized, start, or end) raises KeyError."""
    test_file = tmp_path / "missing_word_id.json"
    payload = {"words": [{"text": "cat", "normalized": "cat", "start": 0.1, "end": 0.5}]}
    test_file.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(KeyError, match="id"):
        _deserialize_raw_alignment(test_file)


def test_deserialize_missing_required_phoneme_keys_raises_keyerror(tmp_path: Path) -> None:
    """Missing required phoneme keys (phoneme, start, or end) raises KeyError."""
    test_file = tmp_path / "missing_phoneme_start.json"
    payload = {
        "words": [
            {
                "id": "w_0",
                "text": "cat",
                "normalized": "cat",
                "start": 0.1,
                "end": 0.5,
                "phonemes": [{"phoneme": "k", "end": 0.3}],
            }
        ]
    }
    test_file.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(KeyError, match="start"):
        _deserialize_raw_alignment(test_file)


def test_deserialize_invalid_numeric_values_raises_valueerror(tmp_path: Path) -> None:
    """Non-numeric string in start/end raises ValueError."""
    test_file = tmp_path / "invalid_float.json"
    payload = {
        "words": [
            {
                "id": "w_0",
                "text": "cat",
                "normalized": "cat",
                "start": "not_a_number",
                "end": 0.5,
            }
        ]
    }
    test_file.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError):
        _deserialize_raw_alignment(test_file)


def test_deserialize_inverted_word_interval_raises_valueerror(tmp_path: Path) -> None:
    """Word with start >= end violates WordToken invariant and raises ValueError."""
    test_file = tmp_path / "inverted_word.json"
    payload = {
        "words": [
            {
                "id": "w_0",
                "text": "cat",
                "normalized": "cat",
                "start": 0.8,
                "end": 0.5,
            }
        ]
    }
    test_file.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="strictly less than end"):
        _deserialize_raw_alignment(test_file)


def test_deserialize_inverted_phoneme_interval_raises_valueerror(tmp_path: Path) -> None:
    """Phoneme with start >= end violates PhonemeCue invariant and raises ValueError."""
    test_file = tmp_path / "inverted_phone.json"
    payload = {
        "words": [
            {
                "id": "w_0",
                "text": "cat",
                "normalized": "cat",
                "start": 0.1,
                "end": 0.5,
                "phonemes": [{"phoneme": "k", "start": 0.4, "end": 0.2}],
            }
        ]
    }
    test_file.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="strictly less than end"):
        _deserialize_raw_alignment(test_file)


def test_deserialize_nan_time_raises_valueerror(tmp_path: Path) -> None:
    """NaN or Inf in timing raises ValueError via finite_number check."""
    test_file = tmp_path / "nan_time.json"
    payload = {
        "words": [
            {
                "id": "w_0",
                "text": "cat",
                "normalized": "cat",
                "start": float("nan"),
                "end": 0.5,
            }
        ]
    }
    test_file.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="must be a finite number"):
        _deserialize_raw_alignment(test_file)


# ---------------------------------------------------------------------------
# 2. Production Mode Error Propagation Tests
# ---------------------------------------------------------------------------


def test_real_mode_pipeline_missing_output_raises_benchmark_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If run_speech_pipeline succeeds but alignment_raw.json missing, BenchmarkError raised."""
    mock_transcriber = MagicMock()
    mock_transcriber.return_value.transcribe.return_value = [
        ASRSegment(
            id="s0",
            start=0.1,
            end=0.5,
            text="hello",
            words=[
                WordToken(
                    id="w0",
                    text="hello",
                    normalized="hello",
                    start=0.1,
                    end=0.5,
                    confidence=1.0,
                )
            ],
        )
    ]
    monkeypatch.setattr(
        "subtitle_workbench.asr.WhisperTranscriber", mock_transcriber, raising=False
    )

    def bad_pipeline(audio_path, output_dir=None, engine="ctc", **kwargs):
        return {"status": "empty"}

    monkeypatch.setattr("subtitle_workbench.pipeline.run_speech_pipeline", bad_pipeline)

    with pytest.raises(BenchmarkError, match="Mode 2 production execution failed"):
        run_benchmark(
            corpus="synthetic",
            output_dir=tmp_path / "out",
            offline_synthetic=False,
            max_utterances=1,
            modes=["mode2_ctc"],
        )


def test_real_mode_pipeline_malformed_json_raises_benchmark_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If alignment_raw.json contains malformed JSON, BenchmarkError is raised."""

    def corrupt_pipeline(audio_path, output_dir=None, engine="ctc", **kwargs):
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        (out / "alignment_raw.json").write_text("{CORRUPT_JSON", encoding="utf-8")
        return {"status": "ok"}

    monkeypatch.setattr("subtitle_workbench.pipeline.run_speech_pipeline", corrupt_pipeline)

    with pytest.raises(BenchmarkError, match="Mode 2 production execution failed"):
        run_benchmark(
            corpus="synthetic",
            output_dir=tmp_path / "out",
            offline_synthetic=False,
            max_utterances=1,
            modes=["mode2_ctc"],
        )


# ---------------------------------------------------------------------------
# 3. Comprehensive Verification: run_benchmark(corpus="synthetic", offline_synthetic=False)
# ---------------------------------------------------------------------------


def _setup_mock_speech_environment(
    monkeypatch: pytest.MonkeyPatch,
    include_phonemes: bool = True,
    word_shift_ms: float = 15.0,
    phone_shift_ms: float = 12.0,
) -> None:
    """Setup mock WhisperTranscriber and run_speech_pipeline with realistic alignments."""

    class MockWhisper:
        def __init__(self, device: str | None = None, compute_type: str = "int8") -> None:
            self.device = device
            self.compute_type = compute_type

        def transcribe(self, audio_path: Path) -> list[ASRSegment]:
            wrd_path = Path(audio_path).with_suffix(".wrd")
            ref_words = parse_timit_wrd(wrd_path)
            shift_sec = 0.080  # Mode 1 shift: 80 ms
            pred_words = [
                WordToken(
                    id=f"m1_{w.id}",
                    text=w.text,
                    normalized=w.normalized,
                    start=round(w.start + shift_sec, 4),
                    end=round(w.end + shift_sec, 4),
                    confidence=0.88,
                )
                for w in ref_words
            ]
            return [
                ASRSegment(
                    id=f"seg_{audio_path.stem}",
                    start=pred_words[0].start,
                    end=pred_words[-1].end,
                    text=" ".join(w.text for w in pred_words),
                    words=pred_words,
                )
            ]

        def unload(self) -> None:
            pass

    monkeypatch.setattr("subtitle_workbench.asr.WhisperTranscriber", MockWhisper, raising=False)

    def mock_speech_pipeline(audio_path, output_dir=None, engine="ctc", **kwargs):
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        wrd_path = Path(audio_path).with_suffix(".wrd")
        phn_path = Path(audio_path).with_suffix(".phn")
        ref_words = parse_timit_wrd(wrd_path)
        ref_phones = parse_timit_phn(phn_path) if phn_path.is_file() else []

        w_shift = (word_shift_ms if engine == "ctc" else (word_shift_ms / 2.0)) / 1000.0
        p_shift = (phone_shift_ms if engine == "ctc" else (phone_shift_ms / 2.0)) / 1000.0

        words_data = []
        for i, w in enumerate(ref_words):
            w_start = round(w.start + w_shift, 4)
            w_end = round(w.end + w_shift, 4)
            if include_phonemes:
                w_phones = [
                    {
                        "phoneme": p.phoneme,
                        "start": round(p.start + p_shift, 4),
                        "end": round(p.end + p_shift, 4),
                        "confidence": 0.95,
                    }
                    for p in ref_phones
                    if p.start >= w.start - 0.02 and p.end <= w.end + 0.02
                ]
            else:
                w_phones = []

            words_data.append(
                {
                    "id": f"p_{i}",
                    "text": w.text,
                    "normalized": w.normalized,
                    "start": w_start,
                    "end": w_end,
                    "confidence": 0.96,
                    "char_start": 0,
                    "char_end": len(w.text),
                    "phonemes": w_phones,
                }
            )

        raw_payload = {
            "schema_version": 1,
            "alignment_method": engine,
            "words": words_data,
        }
        (out / "alignment_raw.json").write_text(json.dumps(raw_payload), encoding="utf-8")
        return {"status": "success"}

    monkeypatch.setattr("subtitle_workbench.pipeline.run_speech_pipeline", mock_speech_pipeline)


def test_real_production_execution_all_modes_verified(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify run_benchmark in real mode computes all word and phone metrics without errors."""
    _setup_mock_speech_environment(
        monkeypatch, include_phonemes=True, word_shift_ms=30.0, phone_shift_ms=25.0
    )

    out_dir = tmp_path / "real_benchmark"
    res = run_benchmark(
        corpus="synthetic",
        output_dir=out_dir,
        offline_synthetic=False,
        max_utterances=4,
        bootstrap_resamples=100,
        seed=123,
    )

    # 1. Top level metadata
    assert res["corpus"] == "synthetic"
    assert res["offline_synthetic"] is False
    assert res["utterance_count"] == 4
    assert res["total_audio_duration_seconds"] > 0.0

    # 2. Modes verification
    modes = res["modes"]
    assert "mode1_whisper" in modes
    assert "mode2_ctc" in modes
    assert "mode3_hybrid" in modes

    m1 = modes["mode1_whisper"]
    m2 = modes["mode2_ctc"]
    m3 = modes["mode3_hybrid"]

    # Mode 1: Word metrics populated, phone metrics None
    assert m1["word_metrics"]["num_matched"] > 0
    assert m1["word_metrics"]["mae_ms"] > 0.0
    assert m1["word_metrics"]["acc_20ms"] >= 0.0
    assert len(m1["word_metrics"]["ci_95"]) == 2
    assert m1["phone_metrics"] is None

    # Mode 2 & Mode 3: Word AND Phone metrics populated
    for mode_dict in (m2, m3):
        wm = mode_dict["word_metrics"]
        assert wm["num_matched"] > 0
        assert wm["mae_ms"] > 0.0
        assert wm["medae_ms"] > 0.0
        assert wm["rmse_ms"] > 0.0
        assert 0.0 <= wm["acc_20ms"] <= 100.0
        assert 0.0 <= wm["acc_50ms"] <= 100.0
        assert 0.0 <= wm["acc_100ms"] <= 100.0
        assert len(wm["ci_95"]) == 2

        pm = mode_dict["phone_metrics"]
        assert pm is not None
        assert pm["num_matched"] > 0
        assert pm["mae_ms"] > 0.0
        assert pm["medae_ms"] > 0.0
        assert pm["rmse_ms"] > 0.0
        assert 0.0 <= pm["acc_20ms"] <= 100.0
        assert 0.0 <= pm["acc_50ms"] <= 100.0
        assert 0.0 <= pm["acc_100ms"] <= 100.0
        assert len(pm["ci_95"]) == 2

    # Accuracy invariant: Mode 3 has smaller MAE than Mode 2 and Mode 1
    assert m3["word_metrics"]["mae_ms"] < m2["word_metrics"]["mae_ms"]
    assert m2["word_metrics"]["mae_ms"] < m1["word_metrics"]["mae_ms"]

    # 3. Statistical significance
    sig = res["statistical_significance"]
    assert "proposed_vs_whisper" in sig
    assert "proposed_vs_ctc" in sig

    w_whisper = sig["proposed_vs_whisper"]
    assert w_whisper["metric"] == "word_mae"
    assert "wilcoxon_w" in w_whisper
    assert 0.0 <= w_whisper["p_value"] <= 1.0
    assert -1.0 <= w_whisper["cliffs_delta"] <= 1.0

    # 4. Artifact integrity
    results_file = out_dir / "benchmark_results.json"
    manifest_file = out_dir / "manifest.json"
    assert results_file.is_file()
    assert manifest_file.is_file()
    loaded_results = json.loads(results_file.read_text(encoding="utf-8"))
    assert loaded_results == res


def test_real_production_execution_empty_phonemes_graceful_handling(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When pipeline produces words with empty phonemes, phone_metrics is None."""
    _setup_mock_speech_environment(monkeypatch, include_phonemes=False)

    out_dir = tmp_path / "empty_phone_bench"
    res = run_benchmark(
        corpus="synthetic",
        output_dir=out_dir,
        offline_synthetic=False,
        max_utterances=2,
        bootstrap_resamples=50,
        seed=42,
    )

    modes = res["modes"]
    # Words are still evaluated
    assert modes["mode2_ctc"]["word_metrics"]["num_matched"] > 0
    assert modes["mode3_hybrid"]["word_metrics"]["num_matched"] > 0

    # Phone metrics are gracefully None for all modes
    assert modes["mode1_whisper"]["phone_metrics"] is None
    assert modes["mode2_ctc"]["phone_metrics"] is None
    assert modes["mode3_hybrid"]["phone_metrics"] is None


def test_real_production_execution_empty_words_graceful_handling(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When pipeline produces empty words list for all utterances, metrics default to zeros."""
    mock_transcriber = MagicMock()
    mock_transcriber.return_value.transcribe.return_value = []
    monkeypatch.setattr(
        "subtitle_workbench.asr.WhisperTranscriber", mock_transcriber, raising=False
    )

    def empty_pipeline(audio_path, output_dir=None, engine="ctc", **kwargs):
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        (out / "alignment_raw.json").write_text('{"words": []}', encoding="utf-8")
        return {"status": "ok"}

    monkeypatch.setattr("subtitle_workbench.pipeline.run_speech_pipeline", empty_pipeline)

    out_dir = tmp_path / "zero_words_bench"
    res = run_benchmark(
        corpus="synthetic",
        output_dir=out_dir,
        offline_synthetic=False,
        max_utterances=2,
        bootstrap_resamples=50,
        seed=42,
    )

    modes = res["modes"]
    for m in ("mode1_whisper", "mode2_ctc", "mode3_hybrid"):
        wm = modes[m]["word_metrics"]
        assert wm["num_matched"] == 0
        assert wm["mae_ms"] == 0.0
        assert wm["ci_95"] == [0.0, 0.0]
        assert modes[m]["phone_metrics"] is None

    # Statistical significance is empty because errors list is empty
    assert res["statistical_significance"] == {}


def test_real_production_execution_single_utterance_cluster_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When only 1 utterance (1 cluster) is evaluated, bootstrap falls back to [mae, mae]."""
    _setup_mock_speech_environment(monkeypatch, include_phonemes=True)

    out_dir = tmp_path / "single_utt_bench"
    res = run_benchmark(
        corpus="synthetic",
        output_dir=out_dir,
        offline_synthetic=False,
        max_utterances=1,
        bootstrap_resamples=50,
        seed=42,
    )

    assert res["utterance_count"] == 1
    m3 = res["modes"]["mode3_hybrid"]
    mae = m3["word_metrics"]["mae_ms"]
    ci = m3["word_metrics"]["ci_95"]
    assert ci == [mae, mae]


def test_real_production_execution_mismatched_mode_word_counts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When different modes produce different counts of words, Wilcoxon safely skipped."""

    class MockWhisper:
        def __init__(self, **kwargs: Any) -> None:
            pass

        def transcribe(self, audio_path: Path) -> list[ASRSegment]:
            # Returns 1 word
            return [
                ASRSegment(
                    id="s0",
                    start=0.1,
                    end=0.5,
                    text="she",
                    words=[
                        WordToken(
                            id="w0",
                            text="she",
                            normalized="she",
                            start=0.1,
                            end=0.5,
                            confidence=1.0,
                        )
                    ],
                )
            ]

        def unload(self) -> None:
            pass

    monkeypatch.setattr("subtitle_workbench.asr.WhisperTranscriber", MockWhisper, raising=False)

    def mock_speech_pipeline(audio_path, output_dir=None, engine="ctc", **kwargs):
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)
        # Returns 3 words
        words_data = [
            {
                "id": f"p_{i}",
                "text": t,
                "normalized": t,
                "start": 0.1 * (i + 1),
                "end": 0.1 * (i + 2),
                "phonemes": [],
            }
            for i, t in enumerate(["she", "had", "dark"])
        ]
        (out / "alignment_raw.json").write_text(json.dumps({"words": words_data}), encoding="utf-8")
        return {"status": "ok"}

    monkeypatch.setattr("subtitle_workbench.pipeline.run_speech_pipeline", mock_speech_pipeline)

    out_dir = tmp_path / "mismatch_bench"
    res = run_benchmark(
        corpus="synthetic",
        output_dir=out_dir,
        offline_synthetic=False,
        max_utterances=1,
        bootstrap_resamples=50,
        seed=42,
    )

    # Mode 1 has 1 matched word error, Mode 3 has 3 matched word errors -> length mismatch
    # Invariant: Wilcoxon test between Mode 1 and Mode 3 is safely omitted
    assert "proposed_vs_whisper" not in res["statistical_significance"]
    # But Mode 2 and Mode 3 have equal counts (both 3) -> Wilcoxon test between Mode 2 and 3 runs
    assert "proposed_vs_ctc" in res["statistical_significance"]


def test_cli_real_mode_uninstalled_dependencies_clean_exit_code_1() -> None:
    """Verify CLI exits with code 1 and clean ASCII error when optional deps are missing."""
    cmd = [
        sys.executable,
        "scripts/speech_benchmark.py",
        "--corpus",
        "synthetic",
        "--max-utterances",
        "1",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    assert proc.returncode == 1
    assert "[-] Benchmark Error: Mode 1 production execution failed" in proc.stderr
    assert "Traceback (most recent call last)" not in proc.stderr
    # Zero-emoji rule verification
    assert all(ord(c) < 128 for c in proc.stdout)
    assert all(ord(c) < 128 for c in proc.stderr)
