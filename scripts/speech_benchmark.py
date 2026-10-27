"""Speech alignment benchmark: reference pipeline vs. baselines on annotated corpora.

Modes (one row per mode in the result tables)

Scenario B - no transcript (Whisper output is aligned; the realistic lecture case)
    B0_whisper      Whisper large-v3 word timestamps (baseline)
    B1_whisper_ctc  Whisper -> MMS_FA CTC forced alignment (WhisperX-style baseline)
    B2_proposed     Whisper -> anchoring/chunking -> MFA (proposed reference pipeline)
Scenario A - transcript known (the reference transcript of the corpus is given)
    A1_ctc          anchoring/chunking -> MMS_FA CTC (baseline)
    A2_proposed     anchoring/chunking -> MFA (proposed reference pipeline)

Every mode runs the complete pipeline for its scenario (VAD and Whisper are never
skipped; Whisper supplies anchors in scenario A). Execution is staged so that each
model is loaded once: (1) one Whisper instance transcribes every utterance,
(2) Whisper is unloaded, (3) all utterances are aligned by MFA in a single batch
call and by one reused CTC model.

Metrics (Individual Master's Plan): mean absolute boundary error (word and phone
level, start and end boundaries) and the share of boundaries within 20 ms, with a
cluster bootstrap 95% CI. Methods are compared with paired Wilcoxon signed-rank
tests on utterance-level word MAE (paired by utterance ID, Holm correction).
Failures are recorded per utterance, never silently dropped.
"""

from __future__ import annotations

import argparse
import datetime
import json
import platform
import sys
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from subtitle_workbench import __version__
from subtitle_workbench.corpora import (
    parse_buckeye_textgrid,
    parse_timit_phn,
    parse_timit_wrd,
    stage_synthetic_benchmark,
)
from subtitle_workbench.metrics import (
    BOUNDARY_EPSILON_MS,
    BenchmarkError,
    MetricComputationError,
    bonferroni_holm_adjustment,
    clustered_bootstrap_ci,
    evaluate_alignment_boundaries,
    paired_wilcoxon_test,
)
from subtitle_workbench.models import PhonemeCue, WordToken
from subtitle_workbench.phone_sets import fold_phones
from subtitle_workbench.provenance import code_provenance, sha256


@dataclass(frozen=True)
class ModeSpec:
    name: str
    scenario: str  # "A" or "B"
    engine: str | None  # None -> Whisper timestamps only
    has_phones: bool


MODES: dict[str, ModeSpec] = {
    "B0_whisper": ModeSpec("Whisper word timestamps", "B", None, False),
    "B1_whisper_ctc": ModeSpec("Whisper + CTC (MMS_FA)", "B", "ctc", False),
    "B2_proposed": ModeSpec("Proposed: Whisper + anchoring + MFA", "B", "mfa", True),
    "A1_ctc": ModeSpec("Known text + CTC (MMS_FA)", "A", "ctc", False),
    "A2_proposed": ModeSpec("Proposed: known text + anchoring + MFA", "A", "mfa", True),
}
DEFAULT_MODES = list(MODES)

# Primary hypotheses: proposed vs. each baseline within the same scenario
COMPARISONS: list[tuple[str, str, str]] = [
    ("B2_vs_B0", "B0_whisper", "B2_proposed"),
    ("B2_vs_B1", "B1_whisper_ctc", "B2_proposed"),
    ("A2_vs_A1", "A1_ctc", "A2_proposed"),
]

REFERENCE_TYPES: dict[str, str] = {
    "timit": "gold",
    "buckeye": "gold",
    "synthetic": "synthetic",
    # Reference boundaries of these corpora were produced by forced alignment (MFA):
    # results measure agreement with MFA, not accuracy.
    "librispeech": "silver_mfa",
    "l2arctic": "silver_mfa",
}

MIN_SPEAKERS_FOR_SPEAKER_CLUSTERS = 10


@dataclass(frozen=True)
class BenchmarkUtterance:
    """Internal representation of a benchmark speech utterance."""

    id: str
    speaker_id: str
    wav_path: Path
    duration: float
    ref_words: list[WordToken]
    ref_phones: list[PhonemeCue]

    @property
    def transcript(self) -> str:
        return " ".join(w.text for w in self.ref_words)


# ---------------------------------------------------------------------------
# Hardware provenance
# ---------------------------------------------------------------------------


def get_hardware_info() -> dict[str, Any]:
    """Gather platform and GPU metadata (device actually usable by each model)."""
    torch_cuda = False
    cuda_name: str | None = None
    try:
        import torch

        torch_cuda = bool(torch.cuda.is_available())
        if torch_cuda:
            cuda_name = str(torch.cuda.get_device_name(0))
    except Exception:
        pass
    try:
        from subtitle_workbench.asr import whisper_cuda_available

        whisper_cuda = whisper_cuda_available()
    except Exception:
        whisper_cuda = False

    return {
        "platform": platform.platform(),
        "processor": platform.processor(),
        "python_version": platform.python_version(),
        "cuda_available": torch_cuda or whisper_cuda,
        "whisper_cuda_available": whisper_cuda,
        "torch_cuda_available": torch_cuda,
        "cuda_device_name": cuda_name,
    }


def get_audio_duration_seconds(wav_path: Path | str) -> float:
    import wave

    with wave.open(str(wav_path), "rb") as w:
        return w.getnframes() / float(w.getframerate())


# ---------------------------------------------------------------------------
# Corpus loaders (no silent skipping: malformed items raise)
# ---------------------------------------------------------------------------


def load_synthetic_utterances(data_dir: Path) -> list[BenchmarkUtterance]:
    """Load staged synthetic benchmark utterances from directory."""
    utterances: list[BenchmarkUtterance] = []
    for wrd_file in sorted(data_dir.glob("*.wrd")):
        utt_id = wrd_file.stem
        spk_id = utt_id.split("_")[0] if "_" in utt_id else utt_id
        wav_file = data_dir / f"{utt_id}.wav"
        phn_file = data_dir / f"{utt_id}.phn"
        if not wav_file.is_file():
            raise BenchmarkError(f"Missing audio for {wrd_file.name}")
        utterances.append(
            BenchmarkUtterance(
                id=utt_id,
                speaker_id=spk_id,
                wav_path=wav_file,
                duration=get_audio_duration_seconds(wav_file),
                ref_words=parse_timit_wrd(wrd_file),
                ref_phones=parse_timit_phn(phn_file) if phn_file.is_file() else [],
            )
        )
    return utterances


def load_timit_utterances(data_dir: Path) -> list[BenchmarkUtterance]:
    """Load TIMIT (full LDC layout or the NLTK sample: <speaker-dir>/<utt>.wav/.wrd/.phn).

    Utterance IDs are ``<speaker>_<utt>`` because sentence IDs (e.g. ``sa1``) repeat
    across speakers.
    """
    utterances: list[BenchmarkUtterance] = []
    wrd_files = sorted(set(data_dir.glob("**/*.wrd")) | set(data_dir.glob("**/*.WRD")))
    for wrd_file in wrd_files:
        spk_id = wrd_file.parent.name.lower()
        wav_file = next(
            (
                w
                for w in (wrd_file.with_suffix(".wav"), wrd_file.with_suffix(".WAV"))
                if w.is_file()
            ),
            None,
        )
        if wav_file is None:
            raise BenchmarkError(f"Missing audio for {wrd_file}")
        phn_file = next(
            (
                p
                for p in (wrd_file.with_suffix(".phn"), wrd_file.with_suffix(".PHN"))
                if p.is_file()
            ),
            None,
        )
        utterances.append(
            BenchmarkUtterance(
                id=f"{spk_id}_{wrd_file.stem.lower()}",
                speaker_id=spk_id,
                wav_path=wav_file,
                duration=get_audio_duration_seconds(wav_file),
                ref_words=parse_timit_wrd(wrd_file),
                ref_phones=parse_timit_phn(phn_file) if phn_file else [],
            )
        )
    return utterances


def _speaker_from_stem(stem: str, corpus: str) -> str:
    if corpus == "librispeech":
        return stem.split("-")[0]
    if corpus == "l2arctic":
        return stem.split("_")[0]
    # Buckeye clips: s0101a_0003 -> s01
    return stem[:3]


def load_textgrid_utterances(data_dir: Path, corpus: str) -> list[BenchmarkUtterance]:
    """Load ``<utt>.wav`` + ``<utt>.TextGrid`` pairs (Buckeye clips, LibriSpeech, L2-ARCTIC)."""
    utterances: list[BenchmarkUtterance] = []
    tg_files = sorted(set(data_dir.glob("**/*.TextGrid")) | set(data_dir.glob("**/*.textgrid")))
    for tg_file in tg_files:
        wav_file = next(
            (w for w in (tg_file.with_suffix(".wav"), tg_file.with_suffix(".WAV")) if w.is_file()),
            None,
        )
        if wav_file is None:
            raise BenchmarkError(f"Missing audio for {tg_file}")
        ref_words = parse_buckeye_textgrid(tg_file)
        utterances.append(
            BenchmarkUtterance(
                id=tg_file.stem,
                speaker_id=_speaker_from_stem(tg_file.stem, corpus),
                wav_path=wav_file,
                duration=get_audio_duration_seconds(wav_file),
                ref_words=ref_words,
                ref_phones=[p for w in ref_words for p in w.phonemes],
            )
        )
    return utterances


# Backwards-compatible name
def load_buckeye_utterances(data_dir: Path) -> list[BenchmarkUtterance]:
    return load_textgrid_utterances(data_dir, "buckeye")


# ---------------------------------------------------------------------------
# Simulated self-test (pipeline plumbing only; never citable)
# ---------------------------------------------------------------------------

_SIM_OFFSETS_MS: dict[str, tuple[float, float]] = {
    "B0_whisper": (120.0, 20.0),
    "B1_whisper_ctc": (36.0, 12.0),
    "A1_ctc": (35.0, 12.0),
    "B2_proposed": (13.0, 4.0),
    "A2_proposed": (12.0, 3.5),
}


def simulate_predictions_for_pipeline_selftest(
    ref_words: list[WordToken],
    ref_phones: list[PhonemeCue],
    mode: str,
    rng: np.random.Generator,
) -> tuple[list[WordToken], list[PhonemeCue] | None]:
    """Shift reference boundaries by mode-specific noise to exercise metric/table code."""
    if mode not in _SIM_OFFSETS_MS:
        raise BenchmarkError(f"Unsupported ablation mode: {mode}")
    mu, sd = _SIM_OFFSETS_MS[mode]

    def shift() -> float:
        return float(np.clip(rng.normal(mu, sd), 1.0, 4 * mu)) / 1000.0

    words = []
    for w in ref_words:
        s = round(w.start + shift(), 6)
        e = round(w.end + shift(), 6)
        words.append(
            WordToken(
                id=f"{w.id}_{mode}",
                text=w.text,
                normalized=w.normalized,
                start=s,
                end=max(e, s + 0.01),
                confidence=0.9,
            )
        )
    phones = None
    if MODES[mode].has_phones:
        phones = []
        for p in ref_phones:
            s = round(p.start + shift(), 6)
            e = round(p.end + shift(), 6)
            phones.append(PhonemeCue(p.phoneme, s, max(e, s + 0.005), 0.9))
    return words, phones


# ---------------------------------------------------------------------------
# Real execution
# ---------------------------------------------------------------------------


class CachedTranscriber:
    """Transcribe each file once even when scenarios A and B both need the ASR output."""

    def __init__(self, inner: Any) -> None:
        self.inner = inner
        self._cache: dict[str, Any] = {}

    def transcribe(self, audio_path: Path | str, **kwargs: Any) -> Any:
        key = str(Path(audio_path).resolve())
        if key not in self._cache:
            self._cache[key] = self.inner.transcribe(audio_path, **kwargs)
        return self._cache[key]

    def unload(self) -> None:
        if hasattr(self.inner, "unload"):
            self.inner.unload()


def _error_text(err: BaseException) -> str:
    return f"{type(err).__name__}: {err}"


def execute_modes(
    utterances: list[BenchmarkUtterance],
    modes: list[str],
    transcriber: Any,
    aligner: Any,
    vad_backend: Any | None = None,
    log: Callable[[str], None] = print,
) -> dict[str, dict[str, tuple[list[WordToken], list[PhonemeCue] | None] | str]]:
    """Run all requested modes; returns mode -> utterance id -> prediction or error text."""
    from subtitle_workbench.aligner import AlignmentFailure, AlignmentRequest
    from subtitle_workbench.pipeline import prepare_alignment_job

    scenarios = {MODES[m].scenario for m in modes}
    cached = CachedTranscriber(transcriber)
    jobs: dict[str, dict[str, Any]] = {"A": {}, "B": {}}

    # Stage 1: VAD + Whisper (+ anchoring + chunking), one loaded ASR model
    log(f"[*] Stage 1/2: ASR and chunking for {len(utterances)} utterances")
    try:
        for utt in utterances:
            for scenario in sorted(scenarios):
                try:
                    jobs[scenario][utt.id] = prepare_alignment_job(
                        utt.wav_path,
                        transcriber=cached,
                        transcript_text=utt.transcript if scenario == "A" else None,
                        speaker=utt.speaker_id,
                        vad_backend=vad_backend,
                    )
                except Exception as err:  # recorded, not dropped
                    jobs[scenario][utt.id] = _error_text(err)
    finally:
        cached.unload()

    results: dict[str, dict[str, Any]] = {m: {} for m in modes}

    # Whisper-only baseline
    if "B0_whisper" in modes:
        for utt in utterances:
            job = jobs["B"][utt.id]
            results["B0_whisper"][utt.id] = (
                job if isinstance(job, str) else (list(job.hypothesis_words), None)
            )

    # Stage 2: forced alignment, one batch per (scenario, engine)
    log("[*] Stage 2/2: forced alignment")
    for mode in modes:
        spec = MODES[mode]
        if spec.engine is None:
            continue
        ready = [
            (utt, jobs[spec.scenario][utt.id])
            for utt in utterances
            if not isinstance(jobs[spec.scenario][utt.id], str)
        ]
        for utt in utterances:
            job = jobs[spec.scenario][utt.id]
            if isinstance(job, str):
                results[mode][utt.id] = job
        if not ready:
            continue
        requests = [
            AlignmentRequest(audio_path=job.audio_path, chunks=job.chunks, speaker=job.speaker)
            for _, job in ready
        ]
        log(f"[*]   {mode}: {len(requests)} utterances via {spec.engine}")
        aligned = aligner.align_requests(requests, engine=spec.engine)
        for (utt, _), out in zip(ready, aligned, strict=True):
            if isinstance(out, AlignmentFailure):
                results[mode][utt.id] = _error_text(out)
            else:
                phones = [p for w in out for p in w.phonemes] if spec.has_phones else None
                results[mode][utt.id] = (out, phones)
    return results


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------


def _ci(
    errors: list[float], clusters: list[str], resamples: int, seed: int
) -> tuple[list[float] | None, int]:
    n_clusters = len(set(clusters))
    if n_clusters < 2:
        return None, n_clusters
    lo, hi = clustered_bootstrap_ci(errors, clusters, num_resamples=resamples, seed=seed)
    return [round(lo, 2), round(hi, 2)], n_clusters


def _tier_summary(
    errors: list[float],
    spk_clusters: list[str],
    utt_clusters: list[str],
    ci_unit: str,
    resamples: int,
    seed: int,
    n_matched: int,
    n_reference: int,
) -> dict[str, Any] | None:
    if not errors:
        return None
    arr = np.asarray(errors, dtype=np.float64)
    clusters = spk_clusters if ci_unit == "speaker" else utt_clusters
    ci, n_clusters = _ci(errors, clusters, resamples, seed)
    return {
        "mae_ms": round(float(arr.mean()), 2),
        "acc_20ms": round(float(np.mean(arr <= 20.0 + BOUNDARY_EPSILON_MS) * 100.0), 2),
        "ci_95": ci,
        "ci_unit": ci_unit,
        "n_clusters": n_clusters,
        "n_boundaries": int(arr.size),
        "num_matched": n_matched,
        "num_reference": n_reference,
        "coverage": round(n_matched / n_reference, 4) if n_reference else 0.0,
    }


def evaluate_mode(
    mode: str,
    utterances: list[BenchmarkUtterance],
    predictions: dict[str, Any],
    ci_unit: str,
    resamples: int,
    seed: int,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    w_err: list[float] = []
    w_spk: list[str] = []
    w_utt: list[str] = []
    p_err: list[float] = []
    p_spk: list[str] = []
    p_utt: list[str] = []
    w_match = w_ref = p_match = p_ref = 0
    rows: list[dict[str, Any]] = []

    for utt in utterances:
        row: dict[str, Any] = {"mode": mode, "utterance": utt.id, "speaker": utt.speaker_id}
        pred = predictions.get(utt.id)
        if pred is None or isinstance(pred, str):
            row.update({"status": "failed", "error": pred or "not executed"})
            rows.append(row)
            continue
        words, phones = pred
        try:
            w_eval = evaluate_alignment_boundaries(words, utt.ref_words)
        except MetricComputationError as err:
            row.update({"status": "failed", "error": _error_text(err)})
            rows.append(row)
            continue
        w_err += w_eval.boundary_errors_ms
        w_spk += [utt.speaker_id] * len(w_eval.boundary_errors_ms)
        w_utt += [utt.id] * len(w_eval.boundary_errors_ms)
        w_match += w_eval.num_matched
        w_ref += len(utt.ref_words)
        row.update(
            {
                "status": "ok",
                "word_mae_ms": round(w_eval.mae, 3),
                "word_acc_20ms": round(w_eval.acc_20ms, 2),
                "word_matched": w_eval.num_matched,
                "word_reference": len(utt.ref_words),
            }
        )
        if phones and utt.ref_phones:
            pred_ph, ref_ph = fold_phones(phones), fold_phones(utt.ref_phones)
            if pred_ph and ref_ph:
                try:
                    p_eval = evaluate_alignment_boundaries(pred_ph, ref_ph)
                    p_err += p_eval.boundary_errors_ms
                    p_spk += [utt.speaker_id] * len(p_eval.boundary_errors_ms)
                    p_utt += [utt.id] * len(p_eval.boundary_errors_ms)
                    p_match += p_eval.num_matched
                    p_ref += len(ref_ph)
                    row["phone_mae_ms"] = round(p_eval.mae, 3)
                except MetricComputationError as err:
                    row["phone_error"] = _error_text(err)
        rows.append(row)

    n_ok = sum(1 for r in rows if r["status"] == "ok")
    summary = {
        "name": MODES[mode].name,
        "scenario": MODES[mode].scenario,
        "engine": MODES[mode].engine,
        "n_utterances_ok": n_ok,
        "n_utterances_failed": len(rows) - n_ok,
        "word_metrics": _tier_summary(
            w_err, w_spk, w_utt, ci_unit, resamples, seed, w_match, w_ref
        ),
        "phone_metrics": _tier_summary(
            p_err, p_spk, p_utt, ci_unit, resamples, seed, p_match, p_ref
        ),
    }
    return summary, rows


def compare_modes(rows: list[dict[str, Any]], modes: list[str], n_speakers: int) -> dict[str, Any]:
    by_mode: dict[str, dict[str, float]] = {m: {} for m in modes}
    for r in rows:
        if r["status"] == "ok" and r["mode"] in by_mode:
            by_mode[r["mode"]][r["utterance"]] = r["word_mae_ms"]

    tests: list[tuple[str, str, str, Any, int]] = []
    for key, baseline, proposed in COMPARISONS:
        if baseline not in by_mode or proposed not in by_mode:
            continue
        common = sorted(set(by_mode[baseline]) & set(by_mode[proposed]))
        if not common:
            continue
        excluded = len(set(by_mode[baseline]) ^ set(by_mode[proposed]))
        res = paired_wilcoxon_test(
            [by_mode[baseline][u] for u in common], [by_mode[proposed][u] for u in common]
        )
        tests.append((key, baseline, proposed, res, excluded))

    out: dict[str, Any] = {}
    if not tests:
        return out
    adjusted = bonferroni_holm_adjustment([t[3].p_value for t in tests])
    for (key, baseline, proposed, res, excluded), p_adj in zip(tests, adjusted, strict=True):
        out[key] = {
            "baseline": baseline,
            "proposed": proposed,
            "metric": "word_mae",
            "aggregation": "utterance_mean",
            "pairing": "utterance_id",
            "n_pairs": res.n_pairs,
            "n_unpaired_excluded": excluded,
            "n_speakers": n_speakers,
            "wilcoxon_w": round(res.statistic, 2),
            "p_value_raw": float(res.p_value),
            "p_value_holm": float(p_adj),
            "p_value": float(p_adj),
            "cliffs_delta": round(res.cliffs_delta, 4),
            "effect_size": res.effect_size,
            "significant_0_05": bool(p_adj < 0.05),
        }
    return out


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def _resolve_utterances(
    corpus: str, data_dir: Path | str | None, offline_synthetic: bool, tmp: list[Any]
) -> tuple[list[BenchmarkUtterance], str]:
    if offline_synthetic or corpus == "synthetic":
        has_wrd = bool(data_dir and Path(data_dir).is_dir() and any(Path(data_dir).glob("*.wrd")))
        if has_wrd:
            synth_path = Path(data_dir)  # type: ignore[arg-type]
        else:
            tmp.append(tempfile.TemporaryDirectory(prefix="bench_synth_"))
            synth_path = stage_synthetic_benchmark(tmp[-1].name)
        return load_synthetic_utterances(synth_path), "synthetic" if offline_synthetic else corpus
    resolved = Path(data_dir) if data_dir else Path(f"data/corpora/{corpus}")
    if not resolved.is_dir():
        raise BenchmarkError(
            f"Corpus directory not found: {resolved}. "
            "Use --offline-synthetic for offline benchmarking without external datasets."
        )
    if corpus == "timit":
        return load_timit_utterances(resolved), corpus
    if corpus in ("buckeye", "librispeech", "l2arctic"):
        return load_textgrid_utterances(resolved, corpus), corpus
    raise BenchmarkError(f"Unsupported corpus: {corpus}")


def run_benchmark(
    corpus: str = "timit",
    data_dir: Path | str | None = None,
    output_dir: Path | str = "reports/benchmark",
    offline_synthetic: bool = False,
    seed: int = 42,
    bootstrap_resamples: int = 2000,
    device: str = "cuda",
    max_utterances: int | None = None,
    modes: list[str] | None = None,
    asr_model: str = "large-v3",
    transcriber: Any | None = None,
    aligner: Any | None = None,
    vad_backend: Any | None = None,
) -> dict[str, Any]:
    """Execute the benchmark and write benchmark_results.json, benchmark_utterances.json,
    and manifest.json into ``output_dir``."""
    if seed < 0:
        raise BenchmarkError(f"Random seed must be non-negative, got {seed}")
    if bootstrap_resamples < 1:
        raise BenchmarkError(f"bootstrap_resamples must be >= 1, got {bootstrap_resamples}")
    selected = list(modes) if modes is not None else list(DEFAULT_MODES)
    if not selected:
        raise BenchmarkError("At least one mode must be selected")
    unknown = [m for m in selected if m not in MODES]
    if unknown:
        raise BenchmarkError(f"Unknown mode(s): {unknown}; choose from {list(MODES)}")

    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    tmp: list[Any] = []
    try:
        utterances, corpus = _resolve_utterances(corpus, data_dir, offline_synthetic, tmp)
        if max_utterances is not None and max_utterances > 0:
            utterances = utterances[:max_utterances]
        if not utterances:
            raise BenchmarkError(
                f"No valid utterances found for corpus '{corpus}'. "
                "Use --offline-synthetic to generate offline benchmark data."
            )
        ids = [u.id for u in utterances]
        if len(ids) != len(set(ids)):
            raise BenchmarkError("Utterance IDs are not unique; pairing would be ambiguous")

        n_spk = len({u.speaker_id for u in utterances})
        ci_unit = "speaker" if n_spk >= MIN_SPEAKERS_FOR_SPEAKER_CLUSTERS else "utterance"
        total_audio = round(sum(u.duration for u in utterances), 3)
        print(f"[*] Corpus {corpus}: {len(utterances)} utterances, {n_spk} speakers")

        config: dict[str, Any] = {"modes": selected, "ci_unit": ci_unit}
        if offline_synthetic:
            rng = np.random.default_rng(seed)
            predictions = {
                m: {
                    u.id: simulate_predictions_for_pipeline_selftest(
                        u.ref_words, u.ref_phones, m, rng
                    )
                    for u in utterances
                }
                for m in selected
            }
        else:
            if transcriber is None:
                from subtitle_workbench.asr import WhisperTranscriber

                transcriber = WhisperTranscriber(model_size_or_path=asr_model, device=device)
            if aligner is None:
                from subtitle_workbench.aligner import ForcedAligner

                aligner = ForcedAligner()
            config["asr"] = {
                "model": getattr(transcriber, "model_size_or_path", asr_model),
                "device": getattr(transcriber, "device", device),
                "compute_type": getattr(transcriber, "compute_type", None),
            }
            describe = getattr(aligner, "describe", None)
            if callable(describe):
                config["aligners"] = {e: describe(e) for e in ("mfa", "ctc")}
            predictions = execute_modes(
                utterances, selected, transcriber, aligner, vad_backend=vad_backend
            )

        modes_output: dict[str, Any] = {}
        all_rows: list[dict[str, Any]] = []
        for m in selected:
            summary, rows = evaluate_mode(
                m, utterances, predictions[m], ci_unit, bootstrap_resamples, seed
            )
            modes_output[m] = summary
            all_rows += rows
            wm = summary["word_metrics"]
            if wm:
                print(
                    f"[+] {m}: word MAE {wm['mae_ms']:.1f} ms, Acc@20ms {wm['acc_20ms']:.1f}%, "
                    f"coverage {wm['coverage'] * 100:.1f}%, failed {summary['n_utterances_failed']}"
                )
            else:
                print(f"[!] {m}: no successful utterances")

        stats = compare_modes(all_rows, selected, n_spk)
        now_utc = datetime.datetime.now(datetime.UTC).isoformat()
        hardware = get_hardware_info()
        provenance = "SIMULATED_PREDICTIONS" if offline_synthetic else "MODEL_EXECUTION"
        results = {
            "schema_version": 2,
            "timestamp": now_utc,
            "corpus": corpus,
            "reference_type": REFERENCE_TYPES.get(corpus, "unknown"),
            "data_provenance": provenance,
            "warning": (
                "Predictions are simulated; not model output; not citable."
                if offline_synthetic
                else None
            ),
            "offline_synthetic": offline_synthetic,
            "seed": seed,
            "bootstrap_resamples": bootstrap_resamples,
            "n_utterances": len(utterances),
            "n_speakers": n_spk,
            "total_audio_duration_seconds": total_audio,
            "config": config,
            "modes": modes_output,
            "statistical_significance": stats,
            "hardware": hardware,
        }
        results_file = out_path / "benchmark_results.json"
        results_file.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
        utt_file = out_path / "benchmark_utterances.json"
        utt_file.write_text(json.dumps(all_rows, indent=2) + "\n", encoding="utf-8")

        manifest = {
            "schema_version": 2,
            "tool": {"name": "local-subtitle-workbench", "version": __version__},
            "code": code_provenance(),
            "timestamp": now_utc,
            "inputs": {
                "corpus": corpus,
                "reference_type": results["reference_type"],
                "data_provenance": provenance,
                "offline_synthetic": offline_synthetic,
                "n_utterances": len(utterances),
                "n_speakers": n_spk,
                "audio_files": {u.id: sha256(u.wav_path) for u in utterances},
            },
            "config": config,
            "outputs": {
                results_file.name: {"sha256": sha256(results_file)},
                utt_file.name: {"sha256": sha256(utt_file)},
            },
            "runtime": {
                "python": platform.python_version(),
                "numpy": np.__version__,
                "platform": platform.platform(),
            },
            "hardware": hardware,
        }
        (out_path / "manifest.json").write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
        )
        print(f"[OK] Results written to {out_path}")
        return results
    finally:
        for t in tmp:
            t.cleanup()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Speech alignment benchmark runner.")
    parser.add_argument(
        "--corpus",
        choices=["timit", "buckeye", "librispeech", "l2arctic", "synthetic"],
        default="timit",
    )
    parser.add_argument("--data-dir", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=Path("reports/benchmark"))
    parser.add_argument(
        "--offline-synthetic",
        action="store_true",
        default=False,
        help="Simulated predictions to test metric/table plumbing (never citable)",
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--bootstrap-resamples", type=int, default=2000)
    parser.add_argument(
        "--device",
        choices=["cuda", "cpu"],
        default="cuda",
        help="Whisper device (default: cuda; fails instead of silently using CPU)",
    )
    parser.add_argument("--asr-model", type=str, default="large-v3")
    parser.add_argument("--max-utterances", type=int, default=None)
    parser.add_argument(
        "--modes",
        type=str,
        default=None,
        help=f"Comma-separated subset of {','.join(MODES)} (default: all)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    modes_list = [m.strip() for m in args.modes.split(",") if m.strip()] if args.modes else None
    try:
        run_benchmark(
            corpus=args.corpus,
            data_dir=args.data_dir,
            output_dir=args.output_dir,
            offline_synthetic=args.offline_synthetic,
            seed=args.seed,
            bootstrap_resamples=args.bootstrap_resamples,
            device=args.device,
            max_utterances=args.max_utterances,
            modes=modes_list,
            asr_model=args.asr_model,
        )
        return 0
    except BenchmarkError as err:
        sys.stderr.write(f"[-] Benchmark Error: {err}\n")
        return 1
    except Exception as err:
        sys.stderr.write(f"error: {err}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
