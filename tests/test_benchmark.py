"""Unit tests for speech benchmark corpora loaders, metrics, and statistical analysis."""

from __future__ import annotations

import math
import subprocess
import sys
from pathlib import Path

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
from subtitle_workbench.models import Config, PhonemeCue, WordToken

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

    non_mono_file = tmp_path / "non_mono.wrd"
    non_mono_file.write_text("1600 6400 she\n6000 8000 had\n", encoding="utf-8")
    with pytest.raises(CorpusFormatError, match="Non-monotonic timestamp"):
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
    assert math.isclose(eval_res.medae, 15.0, abs_tol=1e-5)
    assert math.isclose(eval_res.rmse, 15.0, abs_tol=1e-5)
    assert math.isclose(eval_res.acc_20ms, 100.0, abs_tol=1e-5)
    assert math.isclose(eval_res.acc_50ms, 100.0, abs_tol=1e-5)
    assert math.isclose(eval_res.acc_100ms, 100.0, abs_tol=1e-5)
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
    assert math.isclose(eval_res.medae, 25.0, abs_tol=1e-5)
    assert math.isclose(eval_res.rmse, 25.0, abs_tol=1e-5)
    assert math.isclose(eval_res.acc_20ms, 0.0, abs_tol=1e-5)
    assert math.isclose(eval_res.acc_50ms, 100.0, abs_tol=1e-5)
    assert math.isclose(eval_res.acc_100ms, 100.0, abs_tol=1e-5)


def test_boundary_evaluation_oracle_offsets_60ms() -> None:
    """Fixed offset +60 ms -> MAE == 60.0, Acc@20ms == 0.0%, Acc@50ms == 0.0%, Acc@100ms == 100%."""
    base_intervals = [(0.1, 0.4), (0.5, 0.8), (0.9, 1.3)]
    ref = _make_dummy_word_tokens(base_intervals, shift_ms=0.0)
    pred = _make_dummy_word_tokens(base_intervals, shift_ms=60.0)

    eval_res = evaluate_alignment_boundaries(pred, ref)
    assert isinstance(eval_res, BoundaryEvaluation)
    assert math.isclose(eval_res.mae, 60.0, abs_tol=1e-5)
    assert math.isclose(eval_res.medae, 60.0, abs_tol=1e-5)
    assert math.isclose(eval_res.rmse, 60.0, abs_tol=1e-5)
    assert math.isclose(eval_res.acc_20ms, 0.0, abs_tol=1e-5)
    assert math.isclose(eval_res.acc_50ms, 0.0, abs_tol=1e-5)
    assert math.isclose(eval_res.acc_100ms, 100.0, abs_tol=1e-5)


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
    assert eval_exact.acc_50ms == 100.0
    assert eval_exact.acc_100ms == 100.0

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
    assert eval_excess.acc_50ms == 100.0
    assert eval_excess.acc_100ms == 100.0


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
        medae=14.0,
        rmse=16.0,
        acc_20ms=100.0,
        acc_50ms=100.0,
        acc_100ms=100.0,
        boundary_errors_ms=[15.0, 15.0],
        num_matched=1,
        num_unmatched=0,
    )
    result = AlignmentEvaluationResult(
        word_metrics=word_eval,
        phone_metrics=None,
        rtf=0.08,
        peak_vram_mb=1850.0,
        peak_ram_mb=420.0,
        bootstrap_ci_95={"word_mae": (13.5, 16.5)},
        metadata={"corpus": "timit_core"},
    )
    d = result.to_dict()
    assert d["word_mae"] == 15.0
    assert d["phone_mae"] is None
    assert d["rtf"] == 0.08
    assert d["peak_vram_mb"] == 1850.0
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
