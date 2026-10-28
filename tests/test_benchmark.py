"""Unit tests for speech benchmark corpora loaders, metrics, and statistical analysis."""

from __future__ import annotations

import json
import math
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from subtitle_workbench.audio import load_wav, validate_wav
from subtitle_workbench.corpora import (
    TIMIT_SILENCE_TOKENS,
    parse_buckeye_textgrid,
    parse_timit_phn,
    parse_timit_wrd,
    stage_synthetic_benchmark,
)
from subtitle_workbench.metrics import (
    AlignmentEvaluationResult,
    BenchmarkError,
    BoundaryEvaluation,
    CorpusFormatError,
    MetricComputationError,
    WilcoxonTestResult,
    clustered_bootstrap_ci,
    evaluate_alignment_boundaries,
    paired_wilcoxon_test,
)
from subtitle_workbench.models import ASRSegment, Config, PhonemeCue, WordToken
from subtitle_workbench.provenance import sha256

# Ensure project root is on sys.path for importing scripts in test suite
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# ---------------------------------------------------------------------------
# Corpora Loader Tests (TIMIT .phn, TIMIT .wrd, Buckeye TextGrid)
# ---------------------------------------------------------------------------


def test_timit_phn_parser_silence_filtering(tmp_path: Path) -> None:
    """Verify TIMIT .phn parser converts samples to seconds and strips silence."""
    phn_file = tmp_path / "test_utt.phn"
    phn_content = (
        "0 1600 h#\n"
        "1600 4000 sh\n"
        "4000 6400 iy\n"
        "6400 7200 pau\n"
        "7200 8800 hh\n"
        "8800 10400 ae\n"
        "10400 12000 d\n"
        "12000 12800 epi\n"
        "12800 16000 s\n"
        "16000 17600 h#\n"
    )
    phn_file.write_text(phn_content, encoding="utf-8")

    cues = parse_timit_phn(phn_file, sample_rate=16000)

    # 10 lines, but 'h#', 'pau', 'epi' must be filtered out
    # Remaining: sh, iy, hh, ae, d, s (6 phones)
    expected_phones = ["sh", "iy", "hh", "ae", "d", "s"]
    assert [c.phoneme for c in cues] == expected_phones

    # Check timestamps: 1600 / 16000 = 0.1, 4000 / 16000 = 0.25
    assert math.isclose(cues[0].start, 0.1, abs_tol=1e-5)
    assert math.isclose(cues[0].end, 0.25, abs_tol=1e-5)
    assert cues[0].confidence == 1.0

    # Ensure all cues are monotonic and valid
    for c in cues:
        assert c.start < c.end
        assert c.confidence == 1.0
        assert c.phoneme.lower() not in TIMIT_SILENCE_TOKENS


def test_timit_phn_parser_malformed_and_monotonicity(tmp_path: Path) -> None:
    """Verify TIMIT .phn parser raises CorpusFormatError on invalid inputs."""
    # Malformed line (fewer than 3 tokens)
    bad_line_file = tmp_path / "bad_line.phn"
    bad_line_file.write_text("0 1600\n", encoding="utf-8")
    with pytest.raises(CorpusFormatError, match="Malformed TIMIT .phn.*expected 3 tokens, got 2"):
        parse_timit_phn(bad_line_file)

    # Malformed line (more than 3 tokens)
    extra_tokens_file = tmp_path / "extra_tokens.phn"
    extra_tokens_file.write_text("0 1600 sh extra\n", encoding="utf-8")
    with pytest.raises(CorpusFormatError, match="Malformed TIMIT .phn.*expected 3 tokens, got 4"):
        parse_timit_phn(extra_tokens_file)

    # Non-integer sample boundaries
    bad_int_file = tmp_path / "bad_int.phn"
    bad_int_file.write_text("start end sh\n", encoding="utf-8")
    with pytest.raises(CorpusFormatError, match="Non-integer"):
        parse_timit_phn(bad_int_file)

    # Negative start sample
    neg_file = tmp_path / "neg.phn"
    neg_file.write_text("-100 1600 sh\n", encoding="utf-8")
    with pytest.raises(CorpusFormatError, match="Negative start sample"):
        parse_timit_phn(neg_file)

    # Non-positive interval (start >= end)
    inv_file = tmp_path / "inv.phn"
    inv_file.write_text("1600 1600 sh\n", encoding="utf-8")
    with pytest.raises(CorpusFormatError, match="Non-positive interval"):
        parse_timit_phn(inv_file)

    # Non-monotonic timestamps (start < prev_end)
    non_mono_file = tmp_path / "non_mono.phn"
    non_mono_file.write_text("0 1600 h#\n1200 3200 sh\n", encoding="utf-8")
    with pytest.raises(CorpusFormatError, match="Non-monotonic timestamp"):
        parse_timit_phn(non_mono_file)

    # Non-existent file
    with pytest.raises(FileNotFoundError):
        parse_timit_phn(tmp_path / "non_existent.phn")

    # Invalid sample rate
    with pytest.raises(CorpusFormatError, match="sample_rate must be positive"):
        parse_timit_phn(bad_line_file, sample_rate=-16000)


def test_timit_wrd_parser_properties(tmp_path: Path) -> None:
    """Verify TIMIT .wrd parser creates WordTokens with normalized text and timestamps."""
    wrd_file = tmp_path / "test_utt.wrd"
    wrd_content = "1600 6400 she\n7200 12000 had\n12800 19200 dark\n20000 26400 suit\n"
    wrd_file.write_text(wrd_content, encoding="utf-8")

    words = parse_timit_wrd(wrd_file, sample_rate=16000)

    assert len(words) == 4
    assert [w.text for w in words] == ["she", "had", "dark", "suit"]
    assert [w.normalized for w in words] == ["she", "had", "dark", "suit"]
    assert [w.id for w in words] == ["w_0000", "w_0001", "w_0002", "w_0003"]

    # Check times
    assert math.isclose(words[0].start, 0.1, abs_tol=1e-5)
    assert math.isclose(words[0].end, 0.4, abs_tol=1e-5)
    assert math.isclose(words[1].start, 0.45, abs_tol=1e-5)
    assert math.isclose(words[1].end, 0.75, abs_tol=1e-5)


def test_timit_wrd_parser_malformed_and_monotonicity(tmp_path: Path) -> None:
    """Verify TIMIT .wrd parser raises CorpusFormatError on invalid syntax."""
    bad_file = tmp_path / "bad.wrd"
    bad_file.write_text("1600 she\n", encoding="utf-8")
    with pytest.raises(CorpusFormatError, match="Malformed TIMIT .wrd.*expected 3 tokens, got 2"):
        parse_timit_wrd(bad_file)

    # Malformed line (more than 3 tokens)
    extra_file = tmp_path / "extra.wrd"
    extra_file.write_text("0 1600 she pronoun extra\n", encoding="utf-8")
    with pytest.raises(CorpusFormatError, match="Malformed TIMIT .wrd.*expected 3 tokens, got 5"):
        parse_timit_wrd(extra_file)

    # Overlapping words (shared phone) are valid TIMIT annotation and must be kept
    overlap_file = tmp_path / "overlap.wrd"
    overlap_file.write_text("1600 6400 she\n6000 8000 had\n", encoding="utf-8")
    assert [w.text for w in parse_timit_wrd(overlap_file)] == ["she", "had"]

    non_mono_file = tmp_path / "non_mono.wrd"
    non_mono_file.write_text("6000 8000 had\n1600 6400 she\n", encoding="utf-8")
    with pytest.raises(CorpusFormatError, match="Non-monotonic word onset"):
        parse_timit_wrd(non_mono_file)


def test_timit_parsers_preserve_blank_lines(tmp_path: Path) -> None:
    """Verify TIMIT parsers skip empty and whitespace-only lines without error."""
    phn_file = tmp_path / "blanks.phn"
    phn_file.write_text("\n\n0 1600 sh\n   \n1600 3200 iy\n\n", encoding="utf-8")
    cues = parse_timit_phn(phn_file)
    assert len(cues) == 2

    wrd_file = tmp_path / "blanks.wrd"
    wrd_file.write_text("\n\n0 1600 she\n  \t \n1600 3200 had\n\n", encoding="utf-8")
    words = parse_timit_wrd(wrd_file)
    assert len(words) == 2


def test_buckeye_textgrid_parser_filters_non_speech(tmp_path: Path) -> None:
    """Verify Buckeye Praat TextGrid parser filters non-speech artifacts."""
    tg_file = tmp_path / "buckeye_sample.TextGrid"
    content = (
        'File type = "ooTextFile"\n'
        'Object class = "TextGrid"\n\n'
        "xmin = 0.0\n"
        "xmax = 2.0\n"
        "tiers? <exists>\n"
        "size = 2\n"
        "item []:\n"
        "    item [1]:\n"
        '        class = "IntervalTier"\n'
        '        name = "words"\n'
        "        xmin = 0.0\n"
        "        xmax = 2.0\n"
        "        intervals: size = 4\n"
        "        intervals [1]:\n"
        "            xmin = 0.0\n"
        "            xmax = 0.2\n"
        '            text = "{B_TRANS}"\n'
        "        intervals [2]:\n"
        "            xmin = 0.2\n"
        "            xmax = 0.8\n"
        '            text = "hello"\n'
        "        intervals [3]:\n"
        "            xmin = 0.8\n"
        "            xmax = 1.2\n"
        '            text = "<LAUGH>"\n'
        "        intervals [4]:\n"
        "            xmin = 1.2\n"
        "            xmax = 1.8\n"
        '            text = "world"\n'
        "    item [2]:\n"
        '        class = "IntervalTier"\n'
        '        name = "phones"\n'
        "        xmin = 0.0\n"
        "        xmax = 2.0\n"
        "        intervals: size = 4\n"
        "        intervals [1]:\n"
        "            xmin = 0.2\n"
        "            xmax = 0.5\n"
        '            text = "hh"\n'
        "        intervals [2]:\n"
        "            xmin = 0.5\n"
        "            xmax = 0.8\n"
        '            text = "ah"\n'
        "        intervals [3]:\n"
        "            xmin = 1.2\n"
        "            xmax = 1.5\n"
        '            text = "w"\n'
        "        intervals [4]:\n"
        "            xmin = 1.5\n"
        "            xmax = 1.8\n"
        '            text = "er"\n'
    )
    tg_file.write_text(content, encoding="utf-8")

    words = parse_buckeye_textgrid(tg_file)

    # '{B_TRANS}' and '<LAUGH>' must be stripped
    assert len(words) == 2
    assert words[0].text == "hello"
    assert words[1].text == "world"
    assert len(words[0].phonemes) == 2
    assert [p.phoneme for p in words[0].phonemes] == ["hh", "ah"]


# ---------------------------------------------------------------------------
# Synthetic Benchmark Staging Tests
# ---------------------------------------------------------------------------


def test_stage_synthetic_benchmark_creates_valid_corpora(tmp_path: Path) -> None:
    """Verify stage_synthetic_benchmark creates 10 paired utterances loadable offline."""
    out_dir = tmp_path / "synthetic_corpora"
    result_path = stage_synthetic_benchmark(out_dir)

    assert result_path == out_dir
    wav_files = sorted(out_dir.glob("*.wav"))
    phn_files = sorted(out_dir.glob("*.phn"))
    wrd_files = sorted(out_dir.glob("*.wrd"))
    tg_files = sorted(out_dir.glob("*.TextGrid"))

    assert len(wav_files) == 10
    assert len(phn_files) == 10
    assert len(wrd_files) == 10
    assert len(tg_files) == 10

    # Test that each utterance parses correctly
    cfg = Config()
    for wav_f, phn_f, wrd_f, tg_f in zip(wav_files, phn_files, wrd_files, tg_files, strict=True):
        # 1. Validate audio format and loadability
        validate_wav(wav_f)
        audio = load_wav(wav_f, cfg)
        assert audio.duration > 0.5
        assert audio.sample_rate == 16000

        # 2. Parse TIMIT .phn and .wrd
        phones = parse_timit_phn(phn_f)
        words = parse_timit_wrd(wrd_f)
        assert len(phones) >= 3
        assert len(words) >= 2

        # 3. Parse TextGrid
        tg_words = parse_buckeye_textgrid(tg_f)
        assert len(tg_words) == len(words)
        assert [w.text for w in tg_words] == [w.text for w in words]


# ---------------------------------------------------------------------------
# Boundary Evaluation Metrics and Oracle Tests
# ---------------------------------------------------------------------------


def _make_dummy_word_tokens(
    offsets_sec: list[tuple[float, float]],
    shift_ms: float = 0.0,
) -> list[WordToken]:
    """Helper to generate word tokens with an optional fixed boundary shift in ms."""
    shift_sec = shift_ms / 1000.0
    tokens: list[WordToken] = []
    for idx, (s, e) in enumerate(offsets_sec):
        tokens.append(
            WordToken(
                id=f"w_{idx:04d}",
                text=f"word_{idx}",
                normalized=f"word_{idx}",
                start=round(s + shift_sec, 6),
                end=round(e + shift_sec, 6),
                confidence=1.0,
            )
        )
    return tokens


def test_boundary_evaluation_oracle_offsets_15ms() -> None:
    """Fixed offset +15 ms -> MAE == 15.0, Acc@20ms == 100.0%, Acc@50ms == 100.0%."""
    base_intervals = [(0.1, 0.4), (0.5, 0.8), (0.9, 1.3), (1.4, 1.8)]
    ref = _make_dummy_word_tokens(base_intervals, shift_ms=0.0)
    pred = _make_dummy_word_tokens(base_intervals, shift_ms=15.0)

    eval_res = evaluate_alignment_boundaries(pred, ref)
    assert isinstance(eval_res, BoundaryEvaluation)
    assert math.isclose(eval_res.mae, 15.0, abs_tol=1e-5)
    assert math.isclose(eval_res.acc_20ms, 100.0, abs_tol=1e-5)
    assert eval_res.num_matched == 4
    assert eval_res.num_unmatched == 0


def test_boundary_evaluation_oracle_offsets_25ms() -> None:
    """Fixed offset +25 ms -> MAE == 25.0, Acc@20ms == 0.0%, Acc@50ms == 100.0%."""
    base_intervals = [(0.1, 0.4), (0.5, 0.8), (0.9, 1.3)]
    ref = _make_dummy_word_tokens(base_intervals, shift_ms=0.0)
    pred = _make_dummy_word_tokens(base_intervals, shift_ms=25.0)

    eval_res = evaluate_alignment_boundaries(pred, ref)
    assert isinstance(eval_res, BoundaryEvaluation)
    assert math.isclose(eval_res.mae, 25.0, abs_tol=1e-5)
    assert math.isclose(eval_res.acc_20ms, 0.0, abs_tol=1e-5)


def test_boundary_evaluation_oracle_offsets_60ms() -> None:
    """Fixed offset +60 ms -> MAE == 60.0, Acc@20ms == 0.0%, Acc@50ms == 0.0%, Acc@100ms == 100%."""
    base_intervals = [(0.1, 0.4), (0.5, 0.8), (0.9, 1.3)]
    ref = _make_dummy_word_tokens(base_intervals, shift_ms=0.0)
    pred = _make_dummy_word_tokens(base_intervals, shift_ms=60.0)

    eval_res = evaluate_alignment_boundaries(pred, ref)
    assert isinstance(eval_res, BoundaryEvaluation)
    assert math.isclose(eval_res.mae, 60.0, abs_tol=1e-5)
    assert math.isclose(eval_res.acc_20ms, 0.0, abs_tol=1e-5)


def test_boundary_evaluation_phoneme_cues() -> None:
    """Verify evaluate_alignment_boundaries handles PhonemeCue sequences."""
    ref_phones = [
        PhonemeCue(phoneme="sh", start=0.100, end=0.250, confidence=1.0),
        PhonemeCue(phoneme="iy", start=0.250, end=0.400, confidence=1.0),
    ]
    pred_phones = [
        PhonemeCue(phoneme="sh", start=0.110, end=0.260, confidence=1.0),
        PhonemeCue(phoneme="iy", start=0.260, end=0.410, confidence=1.0),
    ]
    eval_res = evaluate_alignment_boundaries(pred_phones, ref_phones)
    assert math.isclose(eval_res.mae, 10.0, abs_tol=1e-4)
    assert eval_res.acc_20ms == 100.0


def test_boundary_evaluation_dp_sequence_matching() -> None:
    """Verify dynamic programming matches text tokens across insertions and deletions."""
    ref = [
        WordToken(id="w0", text="she", normalized="she", start=0.1, end=0.4, confidence=1.0),
        WordToken(id="w1", text="had", normalized="had", start=0.5, end=0.8, confidence=1.0),
        WordToken(id="w2", text="dark", normalized="dark", start=0.9, end=1.2, confidence=1.0),
        WordToken(id="w3", text="suit", normalized="suit", start=1.3, end=1.6, confidence=1.0),
    ]
    pred = [
        WordToken(id="p0", text="she", normalized="she", start=0.11, end=0.41, confidence=1.0),
        WordToken(
            id="p1", text="really", normalized="really", start=0.42, end=0.49, confidence=1.0
        ),
        WordToken(id="p2", text="had", normalized="had", start=0.51, end=0.81, confidence=1.0),
        WordToken(id="p3", text="suit", normalized="suit", start=1.31, end=1.61, confidence=1.0),
    ]

    eval_res = evaluate_alignment_boundaries(pred, ref)
    assert eval_res.num_matched == 3
    assert eval_res.num_unmatched >= 2
    assert math.isclose(eval_res.mae, 10.0, abs_tol=1e-4)


def test_boundary_evaluation_matches_contractions_across_normalizations() -> None:
    """Reference loaders expand contractions; aligners keep surface forms. Both must match."""
    ref = [
        WordToken(id="r0", text="don't", normalized="do not", start=0.1, end=0.3, confidence=1.0),
        WordToken(id="r1", text="ask", normalized="ask", start=0.3, end=0.6, confidence=1.0),
        WordToken(id="r2", text="he'd", normalized="he would", start=0.7, end=0.9, confidence=1.0),
    ]
    pred = [
        WordToken(id="p0", text="don't", normalized="don't", start=0.11, end=0.31, confidence=1.0),
        WordToken(id="p1", text="Ask,", normalized="ask,", start=0.31, end=0.61, confidence=1.0),
        WordToken(id="p2", text="he'd", normalized="he'd", start=0.71, end=0.91, confidence=1.0),
    ]
    res = evaluate_alignment_boundaries(pred, ref)
    assert res.num_matched == 3 and res.num_unmatched == 0
    assert math.isclose(res.mae, 10.0, abs_tol=1e-4)


def test_boundary_evaluation_division_by_zero_protection() -> None:
    """Verify empty inputs or zero matches raise MetricComputationError."""
    valid_tokens = [
        WordToken(id="w0", text="test", normalized="test", start=0.1, end=0.5, confidence=1.0)
    ]
    other_tokens = [
        WordToken(id="w0", text="other", normalized="other", start=0.1, end=0.5, confidence=1.0)
    ]

    with pytest.raises(MetricComputationError, match="pred_tokens list is empty"):
        evaluate_alignment_boundaries([], valid_tokens)

    with pytest.raises(MetricComputationError, match="ref_tokens list is empty"):
        evaluate_alignment_boundaries(valid_tokens, [])

    with pytest.raises(MetricComputationError, match="Zero matching tokens"):
        evaluate_alignment_boundaries(valid_tokens, other_tokens)

    with pytest.raises(MetricComputationError, match="tolerance_ms must be positive"):
        evaluate_alignment_boundaries(valid_tokens, valid_tokens, tolerance_ms=-5.0)


def test_boundary_evaluation_exact_sample_boundaries_precision() -> None:
    """Verify IEEE-754 precision tolerance allows exact sample boundaries to pass Acc@20ms."""
    # 320 samples at 16000 Hz is exactly 20.0 ms. At t=1.0s, (16320/16000 - 1.0) * 1000.0 ms
    # produces 20.000000000000018 ms in binary64 arithmetic.
    ref = [
        WordToken(
            id="w0",
            text="word",
            normalized="word",
            start=16000 / 16000,
            end=24000 / 16000,
            confidence=1.0,
        )
    ]
    pred_exact = [
        WordToken(
            id="w0",
            text="word",
            normalized="word",
            start=16320 / 16000,
            end=24320 / 16000,
            confidence=1.0,
        )
    ]
    eval_exact = evaluate_alignment_boundaries(pred_exact, ref)
    assert eval_exact.acc_20ms == 100.0

    # 321 samples at 16000 Hz is 20.0625 ms (> 20.0 ms), must be rejected by Acc@20ms
    pred_excess = [
        WordToken(
            id="w0",
            text="word",
            normalized="word",
            start=16321 / 16000,
            end=24321 / 16000,
            confidence=1.0,
        )
    ]
    eval_excess = evaluate_alignment_boundaries(pred_excess, ref)
    assert eval_excess.acc_20ms == 0.0


# ---------------------------------------------------------------------------
# Statistical Analysis Tests (Clustered Bootstrap, Wilcoxon)
# ---------------------------------------------------------------------------


def test_clustered_bootstrap_determinism_and_bounds() -> None:
    """Verify clustered bootstrap produces deterministic 95% CI with seed."""
    rng = np.random.default_rng(123)
    errors = rng.normal(loc=20.0, scale=4.0, size=200)
    clusters = np.repeat(["spk01", "spk02", "spk03", "spk04"], 50)

    ci1 = clustered_bootstrap_ci(errors, clusters, num_resamples=500, seed=42)
    ci2 = clustered_bootstrap_ci(errors, clusters, num_resamples=500, seed=42)

    assert ci1 == ci2
    assert ci1[0] < ci1[1]
    assert 15.0 < ci1[0] < 22.0
    assert 18.0 < ci1[1] < 25.0


def test_paired_wilcoxon_test_significance() -> None:
    """Verify paired Wilcoxon test detects significant difference and Cliff's Delta."""
    rng = np.random.default_rng(999)
    base = rng.normal(loc=45.0, scale=5.0, size=100)
    prop = rng.normal(loc=15.0, scale=3.0, size=100)

    res = paired_wilcoxon_test(base, prop)
    assert isinstance(res, WilcoxonTestResult)
    assert res.p_value < 0.001
    assert res.cliffs_delta > 0.474
    assert res.effect_size == "large"
    assert res.n_pairs == 100

    identical_res = paired_wilcoxon_test(base, base)
    assert identical_res.statistic == 0.0
    assert identical_res.p_value == 1.0
    assert identical_res.cliffs_delta == 0.0
    assert identical_res.effect_size == "negligible"


def test_paired_wilcoxon_symmetric_differences_exact_null() -> None:
    """Verify symmetric non-zero paired differences evaluate to p-value == 1.0."""
    # 4 pairs with symmetric differences: diffs [+1, -1, +2, -2]
    # W+ = 1.5 + 3.5 = 5.0, W- = 1.5 + 3.5 = 5.0 -> W_stat = 5.0, mean_w = 5.0
    # Deviation from mean is 0.0. Under H0, p-value must be exactly 1.0
    base_4 = [11.0, 9.0, 12.0, 8.0]
    prop_4 = [10.0, 10.0, 10.0, 10.0]
    res_4 = paired_wilcoxon_test(base_4, prop_4)
    assert res_4.statistic == 5.0
    assert res_4.p_value == 1.0
    assert res_4.cliffs_delta == 0.0
    assert res_4.effect_size == "negligible"
    assert res_4.n_pairs == 4
    assert res_4.n_non_zero == 4

    # 6 pairs with symmetric differences: diffs [+1, -1, +2, -2, +3, -3]
    # W_stat = 10.5, mean_w = 10.5 -> deviation = 0.0 -> p = 1.0
    base_6 = [11.0, 9.0, 12.0, 8.0, 13.0, 7.0]
    prop_6 = [10.0, 10.0, 10.0, 10.0, 10.0, 10.0]
    res_6 = paired_wilcoxon_test(base_6, prop_6)
    assert res_6.statistic == 10.5
    assert res_6.p_value == 1.0
    assert res_6.cliffs_delta == 0.0
    assert res_6.effect_size == "negligible"

    # Near-null symmetry where |W - mean_w| == 0.5: diffs [+1, +2, -3, +4, -5]
    # W_stat = 7.0, mean_w = 7.5 -> deviation = max(0.0, 0.5 - 0.5) = 0.0 -> p = 1.0
    base_5 = [11.0, 12.0, 7.0, 14.0, 5.0]
    prop_5 = [10.0, 10.0, 10.0, 10.0, 10.0]
    res_5 = paired_wilcoxon_test(base_5, prop_5)
    assert res_5.statistic == 7.0
    assert res_5.p_value == 1.0

    # Asymmetric distribution where |W - mean_w| > 0.5: p-value must be < 1.0
    base_asym = [15.0, 16.0, 17.0, 18.0, 10.0]
    prop_asym = [10.0, 10.0, 10.0, 10.0, 10.0]
    res_asym = paired_wilcoxon_test(base_asym, prop_asym)
    assert res_asym.p_value < 1.0


def test_benchmark_contracts_and_exception_hierarchy() -> None:
    """Verify exception hierarchy and AlignmentEvaluationResult serialization."""
    assert issubclass(CorpusFormatError, BenchmarkError)
    assert issubclass(MetricComputationError, BenchmarkError)

    word_eval = BoundaryEvaluation(
        mae=15.0,
        acc_20ms=100.0,
        boundary_errors_ms=[15.0, 15.0],
        num_matched=1,
        num_unmatched=0,
    )
    result = AlignmentEvaluationResult(
        word_metrics=word_eval,
        phone_metrics=None,
        bootstrap_ci_95={"word_mae": (13.5, 16.5)},
        metadata={"corpus": "timit_core"},
    )
    d = result.to_dict()
    assert d["word_mae"] == 15.0
    assert d["phone_mae"] is None
    assert d["bootstrap_ci_95"]["word_mae"] == [13.5, 16.5]
    assert d["metadata"]["corpus"] == "timit_core"


# ---------------------------------------------------------------------------
# CLI Script Verification
# ---------------------------------------------------------------------------


def test_cli_download_reference_corpora_offline(tmp_path: Path) -> None:
    """Verify scripts/download_reference_corpora.py executes offline with --offline-synthetic."""
    target_dir = tmp_path / "cli_synth"
    cmd = [
        sys.executable,
        "scripts/download_reference_corpora.py",
        "--offline-synthetic",
        "--target-dir",
        str(target_dir),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
    assert proc.returncode == 0
    assert "[+] Successfully staged 10 synthetic utterances" in proc.stdout
    assert (target_dir / "spk01_utt01.wav").exists()
    assert (target_dir / "spk01_utt01.phn").exists()
    assert (target_dir / "spk01_utt01.wrd").exists()
    assert (target_dir / "spk01_utt01.TextGrid").exists()


# ---------------------------------------------------------------------------
# Benchmark Suite Runner Tests (scripts/speech_benchmark.py)
# ---------------------------------------------------------------------------


def test_speech_benchmark_simulation_profiles() -> None:
    """Verify simulated self-test predictions have mode-specific noise and phone tiers."""
    from scripts.speech_benchmark import simulate_predictions_for_pipeline_selftest

    rng = np.random.default_rng(42)
    ref_phones = [
        PhonemeCue(phoneme="sh", start=0.1, end=0.25, confidence=1.0),
        PhonemeCue(phoneme="iy", start=0.25, end=0.4, confidence=1.0),
    ]
    ref_words = [
        WordToken(
            id="w1",
            text="she",
            normalized="she",
            start=0.1,
            end=0.4,
            confidence=1.0,
            phonemes=ref_phones,
        )
    ]
    b0_words, b0_phones = simulate_predictions_for_pipeline_selftest(
        ref_words, ref_phones, "B0_whisper", rng
    )
    assert b0_phones is None
    assert 0.16 <= b0_words[0].start <= 0.6

    a1_words, a1_phones = simulate_predictions_for_pipeline_selftest(
        ref_words, ref_phones, "A1_ctc", rng
    )
    assert a1_phones is None  # CTC (MMS_FA) has no phone tier
    assert a1_words[0].start < a1_words[0].end

    a2_words, a2_phones = simulate_predictions_for_pipeline_selftest(
        ref_words, ref_phones, "A2_proposed", rng
    )
    assert a2_phones is not None and len(a2_phones) == 2
    assert 0.1 < a2_words[0].start <= 0.15

    with pytest.raises(BenchmarkError, match="Unsupported ablation mode"):
        simulate_predictions_for_pipeline_selftest(ref_words, ref_phones, "invalid_mode", rng)


def test_speech_benchmark_programmatic_offline_synthetic(tmp_path: Path) -> None:
    """Simulated self-test produces the v2 schema, per-utterance rows and paired tests."""
    from scripts.speech_benchmark import run_benchmark

    bench_dir = tmp_path / "bench_report"
    res = run_benchmark(
        corpus="timit",
        output_dir=bench_dir,
        offline_synthetic=True,
        seed=42,
        bootstrap_resamples=500,
    )

    assert res["schema_version"] == 2
    assert res["offline_synthetic"] is True
    assert res["corpus"] == "synthetic"
    assert res["reference_type"] == "synthetic"
    assert res["data_provenance"] == "SIMULATED_PREDICTIONS"
    assert "Predictions are simulated" in res["warning"]
    assert res["n_utterances"] == 10
    assert res["n_speakers"] == 3
    # Fewer than 10 speakers: CI resamples utterances, not speakers
    assert res["config"]["ci_unit"] == "utterance"

    modes = res["modes"]
    assert list(modes) == ["B0_whisper", "B1_whisper_ctc", "B2_proposed", "A1_ctc", "A2_proposed"]
    b0, b1, b2 = modes["B0_whisper"], modes["B1_whisper_ctc"], modes["B2_proposed"]
    a1, a2 = modes["A1_ctc"], modes["A2_proposed"]
    assert (
        b2["word_metrics"]["mae_ms"] < b1["word_metrics"]["mae_ms"] < b0["word_metrics"]["mae_ms"]
    )
    assert a2["word_metrics"]["mae_ms"] < a1["word_metrics"]["mae_ms"]
    for m in (b0, b1, a1):
        assert m["phone_metrics"] is None
    for m in (b2, a2):
        assert m["phone_metrics"] is not None
        assert m["word_metrics"]["ci_unit"] == "utterance"
        assert m["word_metrics"]["n_clusters"] == 10
        assert m["word_metrics"]["coverage"] == 1.0
    for m in modes.values():
        assert "performance" not in m
        assert set(m["word_metrics"]) >= {"mae_ms", "acc_20ms", "ci_95", "coverage"}
        assert "medae_ms" not in m["word_metrics"]

    sig = res["statistical_significance"]
    assert set(sig) == {"B2_vs_B0", "B2_vs_B1", "A2_vs_A1"}
    for test in sig.values():
        assert test["pairing"] == "utterance_id"
        assert test["n_pairs"] == 10
        assert test["n_unpaired_excluded"] == 0
        assert test["p_value_holm"] < 0.05
        assert test["effect_size"] == "large"

    results_path = bench_dir / "benchmark_results.json"
    utt_path = bench_dir / "benchmark_utterances.json"
    manifest_path = bench_dir / "manifest.json"
    assert json.loads(results_path.read_text(encoding="utf-8")) == res
    rows = json.loads(utt_path.read_text(encoding="utf-8"))
    assert len(rows) == 50 and all(r["status"] == "ok" for r in rows)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["schema_version"] == 2
    assert len(manifest["code"]["source_sha256"]) == 64
    assert manifest["outputs"]["benchmark_results.json"]["sha256"] == sha256(results_path)
    assert manifest["outputs"]["benchmark_utterances.json"]["sha256"] == sha256(utt_path)


def test_speech_benchmark_cli_offline_synthetic(tmp_path: Path) -> None:
    """Verify scripts/speech_benchmark.py executes via CLI with clean ASCII output."""
    out_dir = tmp_path / "cli_benchmark"
    cmd = [
        sys.executable,
        "scripts/speech_benchmark.py",
        "--offline-synthetic",
        "--output-dir",
        str(out_dir),
        "--bootstrap-resamples",
        "500",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
    stdout = proc.stdout
    assert "[*] Corpus synthetic: 10 utterances, 3 speakers" in stdout
    for mode in ("B0_whisper", "B1_whisper_ctc", "B2_proposed", "A1_ctc", "A2_proposed"):
        assert f"[+] {mode}: word MAE" in stdout
    assert "[OK] Results written to" in stdout
    assert all(ord(char) < 128 for char in stdout)
    assert all(ord(char) < 128 for char in proc.stderr)
    assert (out_dir / "benchmark_results.json").is_file()
    assert (out_dir / "manifest.json").is_file()


def test_speech_benchmark_cli_help_and_options(tmp_path: Path) -> None:
    """Verify CLI argument parsing, help flags, and subset filtering."""
    help_proc = subprocess.run(
        [sys.executable, "scripts/speech_benchmark.py", "--help"],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "--corpus" in help_proc.stdout
    assert "--offline-synthetic" in help_proc.stdout
    assert "--device" in help_proc.stdout

    bad_proc = subprocess.run(
        [
            sys.executable,
            "scripts/speech_benchmark.py",
            "--data-dir",
            str(tmp_path / "non_existent"),
            "--output-dir",
            str(tmp_path / "bad_out"),
        ],
        capture_output=True,
        text=True,
    )
    assert bad_proc.returncode == 1
    assert "[-] Benchmark Error" in bad_proc.stderr

    limited_out = tmp_path / "limited_out"
    lim_proc = subprocess.run(
        [
            sys.executable,
            "scripts/speech_benchmark.py",
            "--offline-synthetic",
            "--output-dir",
            str(limited_out),
            "--max-utterances",
            "3",
            "--bootstrap-resamples",
            "200",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "3 utterances" in lim_proc.stdout

    a2_out = tmp_path / "a2_only"
    subprocess.run(
        [
            sys.executable,
            "scripts/speech_benchmark.py",
            "--offline-synthetic",
            "--output-dir",
            str(a2_out),
            "--modes",
            "A2_proposed",
            "--bootstrap-resamples",
            "200",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    res = json.loads((a2_out / "benchmark_results.json").read_text(encoding="utf-8"))
    assert list(res["modes"]) == ["A2_proposed"]
    assert res["statistical_significance"] == {}

    bad_mode = subprocess.run(
        [
            sys.executable,
            "scripts/speech_benchmark.py",
            "--offline-synthetic",
            "--output-dir",
            str(tmp_path / "bm"),
            "--modes",
            "mode3_hybrid",
        ],
        capture_output=True,
        text=True,
    )
    assert bad_mode.returncode == 1
    assert "Unknown mode" in bad_mode.stderr


def test_speech_benchmark_corpus_synthetic_offline(tmp_path: Path) -> None:
    """Verify synthetic corpus runs with offline simulation when offline_synthetic=True."""
    from scripts.speech_benchmark import run_benchmark

    res = run_benchmark(
        corpus="synthetic",
        output_dir=tmp_path / "synth_corpus",
        offline_synthetic=True,
        bootstrap_resamples=200,
    )
    assert res["corpus"] == "synthetic"
    assert res["n_utterances"] == 10


class _OracleTranscriber:
    """Fake Whisper: returns the reference words shifted by +25 ms (counts calls)."""

    def __init__(self) -> None:
        self.model_size_or_path = "fake"
        self.device = "cpu"
        self.compute_type = "int8"
        self.calls: list[str] = []
        self.unloaded = 0

    def transcribe(self, audio_path: Path) -> list[ASRSegment]:
        self.calls.append(Path(audio_path).name)
        ref = parse_timit_wrd(Path(audio_path).with_suffix(".wrd"))
        words = [
            WordToken(
                id=f"h{i}",
                text=w.text,
                normalized=w.normalized,
                start=round(w.start + 0.025, 4),
                end=round(w.end + 0.025, 4),
                confidence=0.9,
            )
            for i, w in enumerate(ref)
        ]
        return [ASRSegment(id="s0", start=words[0].start, end=words[-1].end, text="x", words=words)]

    def unload(self) -> None:
        self.unloaded += 1


class _OracleAligner:
    """Fake aligner: reference words (+offset); MFA adds phones; one call per engine."""

    def __init__(self, fail_audio: str | None = None) -> None:
        self.calls: list[tuple[str, int]] = []
        self.fail_audio = fail_audio

    def describe(self, engine: str) -> dict[str, str]:
        return {"engine": engine}

    def align_requests(self, requests, engine="mfa"):  # type: ignore[no-untyped-def]
        from subtitle_workbench.aligner import AlignmentFailure

        self.calls.append((engine, len(requests)))
        out = []
        for req in requests:
            if self.fail_audio and Path(req.audio_path).name == self.fail_audio:
                out.append(AlignmentFailure("simulated beam failure"))
                continue
            ref_w = parse_timit_wrd(Path(req.audio_path).with_suffix(".wrd"))
            ref_p = parse_timit_phn(Path(req.audio_path).with_suffix(".phn"))
            off = 0.005 if engine == "mfa" else 0.03
            words = []
            for i, w in enumerate(ref_w):
                phones = [
                    PhonemeCue(p.phoneme, round(p.start + off, 4), round(p.end + off, 4), 1.0)
                    for p in ref_p
                    if engine == "mfa" and p.start >= w.start - 1e-6 and p.end <= w.end + 1e-6
                ]
                words.append(
                    WordToken(
                        id=f"a{i}",
                        text=w.text,
                        normalized=w.normalized,
                        start=round(w.start + off, 4),
                        end=round(w.end + off, 4),
                        confidence=1.0,
                        phonemes=phones,
                    )
                )
            out.append(words)
        return out


def _staged_synthetic(tmp_path: Path) -> Path:
    from subtitle_workbench.corpora import stage_synthetic_benchmark

    return stage_synthetic_benchmark(tmp_path / "synth")


def test_speech_benchmark_real_execution_stages_and_batching(tmp_path: Path) -> None:
    """Real path: one ASR model for all utterances (A and B share one transcription),
    one aligner batch per (scenario, engine), complete pipeline for every mode."""
    from scripts.speech_benchmark import run_benchmark

    data = _staged_synthetic(tmp_path)
    transcriber, aligner = _OracleTranscriber(), _OracleAligner()
    res = run_benchmark(
        corpus="synthetic",
        data_dir=data,
        output_dir=tmp_path / "real",
        offline_synthetic=False,
        bootstrap_resamples=50,
        transcriber=transcriber,
        aligner=aligner,
        vad_backend=lambda *a, **k: [],
    )
    assert res["data_provenance"] == "MODEL_EXECUTION"
    # Whisper ran exactly once per utterance and was unloaded once
    assert len(transcriber.calls) == 10 and len(set(transcriber.calls)) == 10
    assert transcriber.unloaded == 1
    # B1, B2, A1, A2 -> four batched aligner calls, each with all 10 utterances
    assert sorted(aligner.calls) == [("ctc", 10), ("ctc", 10), ("mfa", 10), ("mfa", 10)]

    modes = res["modes"]
    assert modes["B0_whisper"]["word_metrics"]["mae_ms"] == pytest.approx(25.0, abs=0.01)
    assert modes["A2_proposed"]["word_metrics"]["mae_ms"] == pytest.approx(5.0, abs=0.01)
    assert modes["A2_proposed"]["phone_metrics"]["mae_ms"] == pytest.approx(5.0, abs=0.01)
    assert modes["A1_ctc"]["phone_metrics"] is None
    assert res["config"]["asr"]["model"] == "fake"


def test_speech_benchmark_pins_mfa_num_jobs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The default aligner runs MFA with one job, and the value is recorded in the config."""
    import subtitle_workbench.aligner as aligner_mod
    from scripts.speech_benchmark import MFA_NUM_JOBS, run_benchmark

    real_cls = aligner_mod.ForcedAligner
    created: list[dict[str, Any]] = []

    class _RecordingAligner(_OracleAligner):
        """Oracle alignments, but the real configuration record."""

        def __init__(self, **kwargs: Any) -> None:
            super().__init__()
            created.append(kwargs)
            self.real = real_cls(**kwargs)

        def describe(self, engine: str) -> dict[str, Any]:
            return self.real.describe(engine)

    monkeypatch.setattr(aligner_mod, "ForcedAligner", _RecordingAligner)
    res = run_benchmark(
        corpus="synthetic",
        data_dir=_staged_synthetic(tmp_path),
        output_dir=tmp_path / "jobs",
        offline_synthetic=False,
        bootstrap_resamples=10,
        transcriber=_OracleTranscriber(),
        vad_backend=lambda *a, **k: [],
    )
    assert MFA_NUM_JOBS == 1
    assert created == [{"mfa_num_jobs": 1}]
    assert res["config"]["aligners"]["mfa"]["num_jobs"] == 1
    manifest = json.loads((tmp_path / "jobs" / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["config"]["aligners"]["mfa"]["num_jobs"] == 1


def test_forced_aligner_describe_records_resolved_num_jobs() -> None:
    from subtitle_workbench.aligner import ForcedAligner
    from subtitle_workbench.mfa_wrapper import default_num_jobs

    assert ForcedAligner(mfa_num_jobs=1).describe("mfa")["num_jobs"] == 1
    assert ForcedAligner().describe("mfa")["num_jobs"] == default_num_jobs()
    assert "num_jobs" not in ForcedAligner().describe("ctc")


def test_speech_benchmark_failures_are_recorded_and_pairs_stay_aligned(tmp_path: Path) -> None:
    """A failed utterance is reported (not dropped) and excluded from pairs by ID."""
    from scripts.speech_benchmark import run_benchmark

    data = _staged_synthetic(tmp_path)
    failing = sorted(data.glob("*.wav"))[3].name
    res = run_benchmark(
        corpus="synthetic",
        data_dir=data,
        output_dir=tmp_path / "real_fail",
        offline_synthetic=False,
        bootstrap_resamples=50,
        transcriber=_OracleTranscriber(),
        aligner=_OracleAligner(fail_audio=failing),
        vad_backend=lambda *a, **k: [],
    )
    a2 = res["modes"]["A2_proposed"]
    assert a2["n_utterances_failed"] == 1 and a2["n_utterances_ok"] == 9
    test = res["statistical_significance"]["A2_vs_A1"]
    assert test["n_pairs"] == 9
    rows = json.loads((tmp_path / "real_fail" / "benchmark_utterances.json").read_text())
    failed = [r for r in rows if r["status"] == "failed"]
    assert {r["mode"] for r in failed} == {"B1_whisper_ctc", "B2_proposed", "A1_ctc", "A2_proposed"}
    assert all("simulated beam failure" in r["error"] for r in failed)


def test_speech_benchmark_real_execution_requires_unique_ids(tmp_path: Path) -> None:
    import wave

    from scripts.speech_benchmark import BenchmarkUtterance, load_timit_utterances

    for spk in ("dr1-a", "dr2-b"):
        d = tmp_path / spk
        d.mkdir()
        with wave.open(str(d / "sa1.wav"), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(16000)
            w.writeframes(b"\x00\x01" * 16000)
        (d / "sa1.wrd").write_text("1600 8000 she\n", encoding="utf-8")
        (d / "sa1.phn").write_text("1600 4000 sh\n4000 8000 iy\n", encoding="utf-8")
    utts = load_timit_utterances(tmp_path)
    assert sorted(u.id for u in utts) == ["dr1-a_sa1", "dr2-b_sa1"]
    assert isinstance(utts[0], BenchmarkUtterance)


def test_speech_benchmark_cli_seed_negative_exits_one(tmp_path: Path) -> None:
    """Verify CLI exits with code 1 when negative seed is passed."""
    proc = subprocess.run(
        [
            sys.executable,
            "scripts/speech_benchmark.py",
            "--offline-synthetic",
            "--seed",
            "-1",
            "--output-dir",
            str(tmp_path / "neg_seed"),
        ],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 1
    assert "[-] Benchmark Error" in proc.stderr
    assert "non-negative" in proc.stderr


def test_speech_benchmark_negative_seed_validation(tmp_path: Path) -> None:
    """Verify run_benchmark raises BenchmarkError for negative seed."""
    from scripts.speech_benchmark import run_benchmark

    with pytest.raises(BenchmarkError, match="non-negative"):
        run_benchmark(
            corpus="synthetic",
            output_dir=tmp_path / "bad_seed",
            seed=-1,
        )


def test_speech_benchmark_invalid_resamples_validation(tmp_path: Path) -> None:
    """Verify run_benchmark raises BenchmarkError for bootstrap_resamples < 1."""
    from scripts.speech_benchmark import run_benchmark

    with pytest.raises(BenchmarkError, match="bootstrap_resamples"):
        run_benchmark(
            corpus="synthetic",
            output_dir=tmp_path / "bad_resamples",
            bootstrap_resamples=0,
        )


# ---------------------------------------------------------------------------
# Publication LaTeX Table Generator Tests (scripts/generate_paper_tables.py)
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_benchmark_payload() -> dict[str, Any]:
    """Schema-v2 payload with arbitrary illustrative numbers (not results)."""

    def tier(mae: float, acc: float, ci: list[float]) -> dict[str, Any]:
        return {"mae_ms": mae, "acc_20ms": acc, "ci_95": ci, "num_matched": 33}

    return {
        "schema_version": 2,
        "corpus": "timit",
        "reference_type": "gold",
        "data_provenance": "MODEL_EXECUTION",
        "offline_synthetic": False,
        "n_utterances": 160,
        "n_speakers": 16,
        "modes": {
            "B0_whisper": {
                "word_metrics": tier(101.04, 1.5, [95.02, 108.33]),
                "phone_metrics": None,
            },
            "B1_whisper_ctc": {
                "word_metrics": tier(44.44, 21.0, [40.0, 49.9]),
                "phone_metrics": None,
            },
            "B2_proposed": {
                "word_metrics": tier(22.22, 61.25, [20.1, 24.4]),
                "phone_metrics": tier(19.37, 66.0, [18.0, 20.5]),
            },
            "A1_ctc": {"word_metrics": tier(40.06, 25.0, [37.0, 43.0]), "phone_metrics": None},
            "A2_proposed": {
                "word_metrics": tier(18.81, 70.5, [17.6, 19.9]),
                "phone_metrics": tier(17.45, 72.0, [16.8, 18.1]),
            },
        },
        "statistical_significance": {
            "B2_vs_B0": {
                "n_pairs": 160,
                "wilcoxon_w": 0.0,
                "p_value": 3.3e-28,
                "cliffs_delta": 1.0,
                "effect_size": "large",
            },
            "A2_vs_A1": {
                "n_pairs": 158,
                "wilcoxon_w": 812.0,
                "p_value": 0.0042,
                "cliffs_delta": 0.41,
                "effect_size": "medium",
            },
        },
    }


def test_generate_alignment_accuracy_table_mock_data(
    sample_benchmark_payload: dict[str, Any],
) -> None:
    """Verify Table 1 structure, captions with sample size, and escaping."""
    from scripts.generate_paper_tables import generate_alignment_accuracy_table

    tex = generate_alignment_accuracy_table(sample_benchmark_payload)
    assert r"\begin{tabular}{lcccc}" in tex
    assert (
        r"\caption{Boundary Error on TIMIT (read speech, manual boundaries) "
        r"(160 utterances, 16 speakers)}" in tex
    )
    assert r"\label{tab:alignment_accuracy}" in tex
    rows = [line for line in tex.splitlines() if line.startswith("(")]
    assert [r.split(" & ")[0] for r in rows] == [
        "(B0) Whisper timestamps",
        "(B1) Whisper + CTC",
        "(B2) Proposed: Whisper + MFA",
        "(A1) Known text + CTC",
        "(A2) Proposed: known text + MFA",
    ]
    assert "101.0 [95.0, 108.3]" in tex
    assert "18.8 [17.6, 19.9]" in tex
    assert r"70.5\%" in tex
    assert "17.4" in tex
    assert r"Word MAE [95\% CI] (ms)" in tex
    assert re.search(r"(?<!\\)%", tex) is None


def test_generate_alignment_accuracy_table_marks_silver_reference(
    sample_benchmark_payload: dict[str, Any],
) -> None:
    from scripts.generate_paper_tables import generate_alignment_accuracy_table

    payload = {**sample_benchmark_payload, "corpus": "librispeech"}
    tex = generate_alignment_accuracy_table(payload)
    assert "silver reference: MFA alignments" in tex


def test_generate_statistical_significance_table_mock_data(
    sample_benchmark_payload: dict[str, Any],
) -> None:
    """Verify Table 2 contains n, Wilcoxon W, Holm p-value, signed Cliff's delta."""
    from scripts.generate_paper_tables import generate_statistical_significance_table

    tex = generate_statistical_significance_table(sample_benchmark_payload)
    assert r"\begin{tabular}{lccccc}" in tex
    assert "B2 Proposed vs. B0 Whisper & 160 & 0.0 & $3.30 \\times 10^{-28}$" in tex
    assert "A2 Proposed vs. A1 CTC & 158 & 812.0 & 0.004 & +0.41 & Medium" in tex
    assert re.search(r"(?<!\\)%", tex) is None


@pytest.fixture(scope="module")
def simulated_benchmark_json(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Generate a simulated self-test benchmark JSON (no dependency on prior manual runs)."""
    from scripts.speech_benchmark import run_benchmark

    out_dir = tmp_path_factory.mktemp("benchmark_demo")
    run_benchmark(corpus="synthetic", output_dir=out_dir, offline_synthetic=True)
    return out_dir / "benchmark_results.json"


def test_generate_all_tables_from_json_file(tmp_path: Path, simulated_benchmark_json: Path) -> None:
    """Verify generate_all_tables enforces provenance guard and --allow-simulated."""
    from scripts.generate_paper_tables import generate_all_tables

    input_file = simulated_benchmark_json
    assert input_file.is_file()

    out_dir = tmp_path / "paper_tables"

    # Must refuse without allow_simulated=True on simulated data
    with pytest.raises(ValueError, match="Refusing to generate publication tables"):
        generate_all_tables(input_file, out_dir, allow_simulated=False)

    # Must succeed with allow_simulated=True
    result_paths = generate_all_tables(input_file, out_dir, allow_simulated=True)

    assert set(result_paths.keys()) == {
        "alignment_accuracy",
        "statistical_significance",
    }

    t1_file = out_dir / "table_alignment_accuracy.tex"
    t3_file = out_dir / "table_statistical_significance.tex"

    for f in (t1_file, t3_file):
        assert f.is_file()
        content = f.read_text(encoding="utf-8")
        assert len(content) > 100
        assert r"\begin{table}" in content
        assert r"\begin{tabular}" in content
        assert r"\toprule" in content
        assert r"\midrule" in content
        assert r"\bottomrule" in content
        assert r"\end{tabular}" in content
        assert r"\end{table}" in content
        assert "SIMULATED SELF-TEST" in content
        # Zero unescaped percent signs
        assert re.search(r"(?<!\\)%", content) is None


def test_generate_paper_tables_cli_execution(
    tmp_path: Path, simulated_benchmark_json: Path
) -> None:
    """Verify scripts/generate_paper_tables.py CLI refuses simulated data without flag."""
    input_file = simulated_benchmark_json
    out_dir = tmp_path / "cli_tables"

    # Without --allow-simulated: exits 1 with refusal error
    cmd_refuse = [
        sys.executable,
        "scripts/generate_paper_tables.py",
        "--input",
        str(input_file),
        "--output-dir",
        str(out_dir),
    ]
    proc_refuse = subprocess.run(cmd_refuse, capture_output=True, text=True)
    assert proc_refuse.returncode == 1
    assert "Refusing to generate publication tables" in proc_refuse.stderr

    # With --allow-simulated: succeeds with code 0
    cmd_allow = [
        sys.executable,
        "scripts/generate_paper_tables.py",
        "--input",
        str(input_file),
        "--output-dir",
        str(out_dir),
        "--allow-simulated",
    ]
    proc_allow = subprocess.run(cmd_allow, capture_output=True, text=True, check=True)

    assert proc_allow.returncode == 0
    stdout = proc_allow.stdout
    assert "[+] Generated alignment_accuracy table" in stdout
    assert "[+] Generated statistical_significance table" in stdout
    assert "[OK] All publication LaTeX tables generated successfully." in stdout

    # Zero-Emoji discipline: pure ASCII on stdout and stderr
    assert all(ord(c) < 128 for c in stdout)
    assert all(ord(c) < 128 for c in proc_allow.stderr)

    assert (out_dir / "table_alignment_accuracy.tex").is_file()
    assert (out_dir / "table_statistical_significance.tex").is_file()
    assert "SIMULATED SELF-TEST" in (out_dir / "table_alignment_accuracy.tex").read_text(
        encoding="utf-8"
    )


def test_generate_paper_tables_cli_arg_error(tmp_path: Path) -> None:
    """Verify CLI exits with code 2 on unknown flags."""
    cmd = [
        sys.executable,
        "scripts/generate_paper_tables.py",
        "--unrecognized-flag",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    assert proc.returncode == 2
    assert "error" in proc.stderr.lower() or "unrecognized" in proc.stderr.lower()


def test_generate_paper_tables_cli_missing_input_file(tmp_path: Path) -> None:
    """Verify CLI exits with code 1 when input JSON is missing."""
    cmd = [
        sys.executable,
        "scripts/generate_paper_tables.py",
        "--input",
        str(tmp_path / "missing_benchmark.json"),
        "--output-dir",
        str(tmp_path / "out"),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    assert proc.returncode == 1
    assert "[-] Error:" in proc.stderr
    assert "not found" in proc.stderr.lower()


def test_generate_paper_tables_cli_invalid_json_file(tmp_path: Path) -> None:
    """Verify CLI exits with code 1 on malformed JSON input."""
    bad_json = tmp_path / "bad.json"
    bad_json.write_text("{ corrupt json: [", encoding="utf-8")

    cmd = [
        sys.executable,
        "scripts/generate_paper_tables.py",
        "--input",
        str(bad_json),
        "--output-dir",
        str(tmp_path / "out"),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    assert proc.returncode == 1
    assert "[-] Error:" in proc.stderr


def test_generate_paper_tables_missing_required_keys() -> None:
    """Verify validation errors when required JSON structures are missing."""
    from scripts.generate_paper_tables import (
        generate_alignment_accuracy_table,
        generate_statistical_significance_table,
    )

    valid_prov = {"data_provenance": "MODEL_EXECUTION", "offline_synthetic": False}

    with pytest.raises(ValueError, match="missing 'modes'"):
        generate_alignment_accuracy_table(valid_prov)

    with pytest.raises(ValueError, match="missing 'statistical_tests'"):
        generate_statistical_significance_table({**valid_prov, "modes": {}})

    with pytest.raises(ValueError, match="Unsupported table format"):
        generate_alignment_accuracy_table(
            {**valid_prov, "modes": {"m1": {}}}, table_format="markdown"
        )


def test_generate_paper_tables_buckeye_corpus_caption(
    sample_benchmark_payload: dict[str, Any],
) -> None:
    """Verify caption updates cleanly when corpus is buckeye."""
    from scripts.generate_paper_tables import generate_alignment_accuracy_table

    payload = dict(sample_benchmark_payload)
    payload["corpus"] = "buckeye"
    tex = generate_alignment_accuracy_table(payload)
    assert "Buckeye (spontaneous speech, manual boundaries)" in tex


def test_generate_paper_tables_synthetic_corpus_caption(
    sample_benchmark_payload: dict[str, Any],
) -> None:
    """Verify caption updates cleanly when corpus is synthetic."""
    from scripts.generate_paper_tables import generate_alignment_accuracy_table

    payload = dict(sample_benchmark_payload)
    payload["corpus"] = "synthetic"
    tex = generate_alignment_accuracy_table(payload)
    assert "Synthetic self-test" in tex


def test_bonferroni_holm_adjustment_properties() -> None:
    """Verify Bonferroni-Holm step-down adjustments match theoretical bounds."""
    from subtitle_workbench.metrics import bonferroni_holm_adjustment

    # Empty
    assert bonferroni_holm_adjustment([]) == []

    # Single p-value
    assert bonferroni_holm_adjustment([0.04]) == [0.04]

    # Two p-values: [0.02, 0.04] -> rank1 = min(1, 2 * 0.02) = 0.04; rank2 = min(1, max(0.04, 1 * 0.04)) = 0.04
    adj = bonferroni_holm_adjustment([0.02, 0.04])
    assert math.isclose(adj[0], 0.04, abs_tol=1e-7)
    assert math.isclose(adj[1], 0.04, abs_tol=1e-7)

    # Order preservation: larger p-value first
    adj_rev = bonferroni_holm_adjustment([0.04, 0.02])
    assert math.isclose(adj_rev[0], 0.04, abs_tol=1e-7)
    assert math.isclose(adj_rev[1], 0.04, abs_tol=1e-7)

    # Extreme values clamp at 1.0
    adj_large = bonferroni_holm_adjustment([0.6, 0.8])
    assert adj_large == [1.0, 1.0]

    # Invalid input validation
    with pytest.raises(ValueError, match="between 0.0 and 1.0"):
        bonferroni_holm_adjustment([-0.1, 0.5])
    with pytest.raises(ValueError, match="between 0.0 and 1.0"):
        bonferroni_holm_adjustment([0.1, 1.5])


def test_generate_paper_tables_escape_latex_edge_cases() -> None:
    """Verify escape_latex handles unescaped %, _, and already escaped sequences."""
    from scripts.generate_paper_tables import escape_latex

    assert escape_latex("") == ""
    assert escape_latex("test_word") == r"test\_word"
    assert escape_latex("100% accuracy") == r"100\% accuracy"
    assert escape_latex(r"already\_escaped and \% safe") == r"already\_escaped and \% safe"
    assert escape_latex("AT&T_model_v1") == r"AT&T\_model\_v1"


def test_generate_paper_tables_alternative_schema_keys() -> None:
    """Verify generator supports schema variants (statistical_tests)."""
    from scripts.generate_paper_tables import (
        generate_alignment_accuracy_table,
        generate_statistical_significance_table,
    )

    alt_payload = {
        "data_provenance": "MODEL_EXECUTION",
        "offline_synthetic": False,
        "modes": {
            "mode1_whisper": {
                "description": "Whisper Baseline",
                "word_metrics": {"mae_ms": 110.0},
            }
        },
        "statistical_tests": {
            "B2_vs_B0": {
                "w_statistic": 4.5,
                "p_value": 0.042,
                "cliffs_delta": 0.75,
                "effect_size": "medium",
            }
        },
    }

    t1 = generate_alignment_accuracy_table(alt_payload)
    assert "Whisper Baseline" in t1
    assert "110.0" in t1

    t3 = generate_statistical_significance_table(alt_payload)
    assert "B2 Proposed vs. B0 Whisper" in t3
    assert "4.5" in t3
    assert "0.042" in t3
    assert "+0.75" in t3
    assert "Medium" in t3


def test_generate_paper_tables_programmatic_main_dispatch(
    tmp_path: Path, simulated_benchmark_json: Path
) -> None:
    """Verify main() return codes in-process for 0, 1, and 2."""
    from scripts.generate_paper_tables import main

    input_file = simulated_benchmark_json
    out_dir = tmp_path / "main_dispatch"

    # Exit code 1 when attempting to generate tables on simulated input without --allow-simulated
    code_refuse = main(["--input", str(input_file), "--output-dir", str(out_dir)])
    assert code_refuse == 1

    # Exit code 0 on valid run with --allow-simulated
    code0 = main(
        [
            "--input",
            str(input_file),
            "--output-dir",
            str(out_dir),
            "--allow-simulated",
        ]
    )
    assert code0 == 0

    # Exit code 1 on missing file
    code1 = main(["--input", str(tmp_path / "not_found.json")])
    assert code1 == 1

    # Exit code 2 on invalid flag
    code2 = main(["--bogus-option"])
    assert code2 == 2
