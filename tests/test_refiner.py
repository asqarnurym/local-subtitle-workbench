"""Tests for the BRQE refiner, its constant rival and the refined benchmark modes."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("torchaudio")

from subtitle_workbench.models import PhonemeCue, WordToken  # noqa: E402
from subtitle_workbench.refiner import (  # noqa: E402
    HALF_WINDOW,
    N_MELS,
    WINDOW,
    Boundary,
    BRQERefiner,
    ConstantRefiner,
    MelExtractor,
    TrainConfig,
    boundaries_for_utterance,
    pr_auc,
    refine_prediction,
    roc_auc,
    window_at,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def _word(i: int, s: float, e: float, text: str = "w") -> WordToken:
    return WordToken(f"w{i}", text, text, s, e, 1.0)


def test_window_at_pads_edges_and_reports_subframe_offset() -> None:
    mel = np.arange(N_MELS * 10, dtype=np.float32).reshape(N_MELS, 10)
    win, off = window_at(mel, 0.0)
    assert win.shape == (N_MELS, WINDOW)
    assert np.all(win[:, :HALF_WINDOW] == 0) and np.array_equal(win[:, HALF_WINDOW:30], mel)
    _, off = window_at(mel, 0.0074)  # 1.48 frames of 5 ms -> nearest frame 1, offset +0.48
    assert off == pytest.approx(0.48, abs=1e-6)


def test_constant_refiner_learns_median_shift_per_kind_and_scenario() -> None:
    bs = [Boundary("u", 1.0, "word_start", "A", 0.2, 1.0 + d) for d in (0.01, 0.02, 0.03)]
    bs += [Boundary("u", 1.0, "word_end", "A", 0.2, 1.0 - 0.01)]
    bs += [Boundary("u", 1.0, "word_start", "A", 0.2, 1.5)]  # beyond 100 ms: ignored
    c = ConstantRefiner().fit(bs)
    assert c.offsets == pytest.approx({"word_start|A": 0.02, "word_end|A": -0.01})
    shift, prob = c.predict(
        [Boundary("v", 2.0, "word_start", "A", 0.1), Boundary("v", 2.0, "phone_end", "B", 0.1)]
    )
    assert shift.tolist() == pytest.approx([0.02, 0.0]) and np.all(np.isnan(prob))


def test_boundaries_for_utterance_pairs_words_and_folded_phones() -> None:
    pred = [WordToken("p0", "don't", "don't", 0.1, 0.4, 1.0), _word(1, 0.4, 0.7, "go")]
    ref = [WordToken("r0", "don't", "do not", 0.12, 0.41, 1.0), _word(1, 0.42, 0.69, "go")]
    phones = [PhonemeCue("D", 0.1, 0.2, 1.0), PhonemeCue("OW1", 0.2, 0.4, 1.0)]
    ref_ph = [PhonemeCue("d", 0.11, 0.21, 1.0), PhonemeCue("ow", 0.21, 0.4, 1.0)]
    bs = boundaries_for_utterance("u", "A", pred, phones, ref, ref_ph, "s01")
    assert [b.kind for b in bs[:4]] == ["word_start", "word_end", "word_start", "word_end"]
    assert [b.ref for b in bs[:4]] == pytest.approx([0.12, 0.41, 0.42, 0.69])
    assert len(bs) == 8 and all(b.ref is not None for b in bs[4:])


def _tone_burst_corpus(n: int, rng: np.random.Generator):
    """Silence then a tone; the true onset is known, the 'MFA' boundary is 30 ms late."""
    mels, bounds = {}, []
    extractor = MelExtractor()
    for k in range(n):
        onset = 0.3 + 0.4 * rng.random()
        t = np.arange(16000) / 16000
        x = 0.001 * rng.standard_normal(16000)
        x[t >= onset] += 0.3 * np.sin(2 * np.pi * (300 + 200 * rng.random()) * t[t >= onset])
        mels[f"u{k}"] = extractor(x.astype(np.float32))
        bounds.append(Boundary(f"u{k}", onset + 0.03, "word_start", "A", 0.3, onset, f"s{k % 4}"))
    return mels, bounds


def test_brqe_learns_systematic_shift_and_round_trips(tmp_path: Path) -> None:
    rng = np.random.default_rng(0)
    mels, bounds = _tone_burst_corpus(160, rng)
    model = BRQERefiner(TrainConfig(epochs=25, batch_size=32, lr=3e-3)).fit(bounds[:120], mels)
    shift, prob = model.predict(bounds[120:], mels)
    before = np.mean([abs(b.time - b.ref) for b in bounds[120:]]) * 1000
    after = (
        np.mean([abs(b.time + d - b.ref) for b, d in zip(bounds[120:], shift, strict=True)]) * 1000
    )
    assert before == pytest.approx(30.0, abs=1e-6)
    assert after < 15.0
    assert prob.shape == (40,) and np.all((prob >= 0) & (prob <= 1))

    sha = model.save(tmp_path / "brqe.pt", extra={"trained_on": {"n": 120}})
    loaded = BRQERefiner.load(tmp_path / "brqe.pt")
    assert json.loads((tmp_path / "brqe.json").read_text())["weights_sha256"] == sha
    assert np.allclose(loaded.predict(bounds[120:], mels)[0], shift)
    (tmp_path / "brqe.pt").write_bytes(b"tampered")
    with pytest.raises(ValueError, match="sha256"):
        BRQERefiner.load(tmp_path / "brqe.pt")


class _FixedShift:
    def __init__(self, shift: float, prob: float = 0.25) -> None:
        self.shift, self.prob = shift, prob

    def predict(self, boundaries, mels=None):
        return np.full(len(boundaries), self.shift), np.full(len(boundaries), self.prob)


def test_refine_prediction_keeps_order_and_sets_word_confidence() -> None:
    words = [_word(0, 0.10, 0.30), _word(1, 0.30, 0.31), _word(2, 0.31, 0.60)]
    phones = [PhonemeCue("AA1", 0.10, 0.30, 1.0), PhonemeCue("B", 0.30, 0.31, 1.0)]
    new_w, new_p = refine_prediction(_FixedShift(0.02), "u", "A", words, phones, {})
    assert [w.start for w in new_w] == pytest.approx([0.12, 0.32, 0.33])
    for a, b in zip(new_w, new_w[1:], strict=False):
        assert a.end <= b.start and a.start < a.end
    assert all(w.confidence == pytest.approx(0.75) for w in new_w)
    assert [p.phoneme for p in new_p] == ["aa", "b"]
    # A shift that would invert a token keeps that token's original times
    bad_w, _ = refine_prediction(_FixedShift(-0.5), "u", "A", words[:1], None, {})
    assert (bad_w[0].start, bad_w[0].end) == (0.10, 0.30)


def test_roc_and_pr_auc_on_known_values() -> None:
    y = np.array([0, 0, 1, 1])
    assert roc_auc(y, np.array([0.1, 0.4, 0.35, 0.8])) == pytest.approx(0.75)
    assert roc_auc(y, np.array([0.5, 0.5, 0.5, 0.5])) == pytest.approx(0.5)
    assert roc_auc(np.array([1, 1]), np.array([0.2, 0.3])) is None
    assert pr_auc(y, np.array([0.1, 0.4, 0.35, 0.8])) == pytest.approx((1 + 2 / 3) / 2)


def _write_refiners(d: Path) -> None:
    rng = np.random.default_rng(1)
    mels, bounds = _tone_burst_corpus(16, rng)
    BRQERefiner(TrainConfig(epochs=1, batch_size=8)).fit(bounds, mels).save(d / "brqe.pt")
    (d / "const_offsets.json").write_text(
        json.dumps({"offsets": {"word_start|A": -0.005, "word_end|A": -0.005}}), encoding="utf-8"
    )


def test_benchmark_refined_modes_reuse_base_alignments(tmp_path: Path) -> None:
    from scripts.speech_benchmark import BenchmarkError, run_benchmark
    from subtitle_workbench.corpora import stage_synthetic_benchmark
    from tests.test_benchmark import _OracleAligner, _OracleTranscriber

    _write_refiners(tmp_path / "ref")
    aligner = _OracleAligner()
    res = run_benchmark(
        corpus="synthetic",
        data_dir=stage_synthetic_benchmark(tmp_path / "synth"),
        output_dir=tmp_path / "out",
        bootstrap_resamples=20,
        transcriber=_OracleTranscriber(),
        aligner=aligner,
        vad_backend=lambda *a, **k: [],
        refiner_dir=tmp_path / "ref",
    )
    assert set(res["modes"]) >= {"A2_const", "A2_brqe", "B2_const", "B2_brqe"}
    # Refined modes add no aligner calls: still 2 x ctc + 2 x mfa
    assert sorted(aligner.calls) == [("ctc", 10), ("ctc", 10), ("mfa", 10), ("mfa", 10)]
    # Oracle MFA is +5 ms late; the constant rival (-5 ms on A word boundaries) removes it
    assert res["modes"]["A2_const"]["word_metrics"]["mae_ms"] == pytest.approx(0.0, abs=0.01)
    assert res["modes"]["A2_brqe"]["quality_estimation"]["n_words"] > 0
    assert "A2brqe_vs_A2const" in res["statistical_significance"]
    assert res["config"]["refiners"]["brqe_weights_sha256"]
    assert "refine_A2_brqe" in res["runtime"]["stages"]
    with pytest.raises(BenchmarkError, match="base mode"):
        run_benchmark(
            corpus="synthetic",
            output_dir=tmp_path / "o2",
            modes=["A2_brqe"],
            refiner_dir=tmp_path / "ref",
        )
    with pytest.raises(BenchmarkError, match="refiner_dir"):
        run_benchmark(
            corpus="synthetic", output_dir=tmp_path / "o3", modes=["A2_proposed", "A2_brqe"]
        )
