"""S1: long recordings built from consecutive Buckeye test-speaker clips.

Pre-registered in docs/S1_LONG_RECORDINGS_PROTOCOL.md. A thin wrapper over the frozen
benchmark (``speech_benchmark.run_benchmark``); the pipeline core is not changed.

  python scripts/s1_long_recordings.py build   --output-dir reports/s1_long_20261103
  python scripts/s1_long_recordings.py run     --output-dir reports/s1_long_20261103
  python scripts/s1_long_recordings.py analyze --output-dir reports/s1_long_20261103
  python scripts/s1_long_recordings.py verify  --output-dir reports/s1_long_20261103

Derived audio goes to ``data/derived/<output-dir name>`` (ignored by Git); finished
runs are never recomputed or overwritten.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import subprocess
import sys
import time
import wave
from pathlib import Path
from typing import Any

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts import speech_benchmark as benchmark  # noqa: E402
from scripts.analyze_speaker_errors import exact_signed_rank  # noqa: E402
from scripts.replay_frozen_metrics import deserialize_predictions  # noqa: E402
from subtitle_workbench.buckeye import Interval, _textgrid  # noqa: E402
from subtitle_workbench.corpora import parse_buckeye_textgrid  # noqa: E402
from subtitle_workbench.metrics import (  # noqa: E402
    _align_token_sequences,
    bonferroni_holm_adjustment,
)

SCHEMA_VERSION = 1
CLIPS = Path("data/corpora/buckeye")
SPLIT = Path("reports/buckeye_split_20260401.json")
REFINER_DIR = Path("models/brqe")
LENGTHS: dict[str, float] = {"L01": 60.0, "L05": 300.0, "L10": 600.0}
VARIANTS: dict[str, list[str] | None] = {
    "anchored": None,  # all nine benchmark modes, Whisper large-v3
    "noanchor": ["A2_proposed", "A2_const", "A2_brqe"],
}
TESTS: list[tuple[str, str]] = [
    ("H1_drift_A2", "A2_proposed"),
    ("H2_drift_B2", "B2_proposed"),
    ("H3_length_A2", "A2_proposed"),
    ("H4_length_B2", "B2_proposed"),
    ("H5_anchoring_A2", "A2_proposed"),
]
DRIFT_EARLY, DRIFT_LATE = (0.0, 120.0), (480.0, 600.0)
POSITION_MODES = ["A2_proposed", "A2_brqe", "B2_proposed", "B2_brqe"]
CODE_FILES = (
    "scripts/s1_long_recordings.py",
    "scripts/speech_benchmark.py",
    "scripts/analyze_speaker_errors.py",
    "src/subtitle_workbench/pipeline.py",
    "src/subtitle_workbench/anchoring.py",
    "src/subtitle_workbench/chunker.py",
    "src/subtitle_workbench/aligner.py",
    "src/subtitle_workbench/metrics.py",
    "src/subtitle_workbench/refiner.py",
    "uv.lock",
    "pyproject.toml",
)
# The frozen TextGrid parser rounds times to 0.1 ms; clip and long-recording references
# are each rounded once, so they may differ by up to two half-steps.
TIME_TOLERANCE_S = 1e-4 + 1e-6
MAE_TOLERANCE_MS = 5e-4 + 1e-9  # benchmark rows are rounded to 0.001 ms
MIN_PAIRS = 6


class S1Error(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise S1Error(message)


def sha_file(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=PROJECT_ROOT, capture_output=True, text=True, check=True
    ).stdout.strip()


def git_state() -> dict[str, Any]:
    return {"revision": _git("rev-parse", "HEAD"), "dirty": bool(_git("status", "--porcelain"))}


def code_hashes() -> dict[str, str]:
    return {p: sha_file(PROJECT_ROOT / p) for p in CODE_FILES}


def write_json(path: Path, value: Any) -> None:
    path.write_bytes((json.dumps(value, indent=2, allow_nan=False) + "\n").encode("utf-8"))


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def derived_root(out: Path) -> Path:
    return PROJECT_ROOT / "data" / "derived" / out.name


# ---------------------------------------------------------------------------
# Build: concatenate consecutive clips into nested long recordings
# ---------------------------------------------------------------------------


class NullTranscriber:
    """No ASR: scenario A then spreads the known text over the recording (no anchors)."""

    model_size_or_path = "none (no ASR anchors)"
    device = "none"
    compute_type = None

    def transcribe(self, audio_path: Path | str, **kwargs: Any) -> list:
        return []


def read_pcm(path: Path) -> tuple[int, bytes]:
    with wave.open(str(path), "rb") as src:
        require(src.getnchannels() == 1 and src.getsampwidth() == 2, f"{path}: expected mono PCM16")
        return src.getframerate(), src.readframes(src.getnframes())


def shifted(words: list, offset: float) -> tuple[list[Interval], list[Interval]]:
    w = [Interval(x.start + offset, x.end + offset, x.text) for x in words]
    p = [Interval(c.start + offset, c.end + offset, c.phoneme) for x in words for c in x.phonemes]
    return w, p


def same_references(parsed: list, expected: list[Interval], phones: list[Interval]) -> bool:
    """Parsed long-recording references equal the shifted clip references (1 us)."""
    got_phones = [c for w in parsed for c in w.phonemes]
    return (
        len(parsed) == len(expected)
        and len(got_phones) == len(phones)
        and all(
            a.text == b.label
            and abs(a.start - b.start) <= TIME_TOLERANCE_S
            and abs(a.end - b.end) <= TIME_TOLERANCE_S
            for a, b in zip(parsed, expected, strict=True)
        )
        and all(
            a.phoneme == b.label
            and abs(a.start - b.start) <= TIME_TOLERANCE_S
            and abs(a.end - b.end) <= TIME_TOLERANCE_S
            for a, b in zip(got_phones, phones, strict=True)
        )
    )


def build_speaker(
    clip_dir: Path, speaker: str, dest: Path, lengths: dict[str, float]
) -> dict[str, Any]:
    """Write the nested recordings of one speaker; returns their manifest entries."""
    target = max(lengths.values())
    clips: list[tuple[str, bytes, list]] = []
    skipped: dict[str, str] = {}
    sr_all: set[int] = set()
    total = 0.0
    for wav in sorted(clip_dir.glob(f"{speaker}*.wav")):
        sr, frames = read_pcm(wav)
        if not frames:
            skipped[wav.stem] = "empty audio"
            continue
        sr_all.add(sr)
        clips.append((wav.stem, frames, parse_buckeye_textgrid(wav.with_suffix(".TextGrid"))))
        total += len(frames) / (2 * sr)
        if total >= target:
            break
    require(total >= target, f"{speaker}: only {total:.1f} s of usable clips")
    require(len(sr_all) == 1, f"{speaker}: mixed sample rates {sr_all}")
    sr = sr_all.pop()

    out: dict[str, Any] = {"skipped_clips": skipped, "recordings": {}}
    n_words_by_length: list[tuple[float, int, list]] = []
    for name, seconds in sorted(lengths.items(), key=lambda kv: kv[1]):
        audio, words, phones, ids = bytearray(), [], [], []
        for clip_id, frames, refs in clips:
            offset = len(audio) / (2 * sr)
            w, p = shifted(refs, offset)
            words += w
            phones += p
            audio += frames
            ids.append(clip_id)
            if len(audio) / (2 * sr) >= seconds:
                break
        duration = len(audio) / (2 * sr)
        stem = f"{speaker}_{name}"
        (dest / name).mkdir(parents=True, exist_ok=True)
        wav_path, tg_path = dest / name / f"{stem}.wav", dest / name / f"{stem}.TextGrid"
        require(not wav_path.exists() and not tg_path.exists(), f"{wav_path} already exists")
        with wave.open(str(wav_path), "wb") as dst:
            dst.setnchannels(1)
            dst.setsampwidth(2)
            dst.setframerate(sr)
            dst.writeframes(bytes(audio))
        tg_path.write_text(_textgrid(words, phones, 0.0, round(duration, 6)), encoding="utf-8")
        (dest / name / f"{stem}.txt").write_text(
            " ".join(w.label for w in words) + "\n", encoding="utf-8"
        )
        # Validation 1: audio bytes and references survive the round trip
        require(read_pcm(wav_path)[1] == bytes(audio), f"{stem}: audio round trip differs")
        parsed = parse_buckeye_textgrid(tg_path)
        require(same_references(parsed, words, phones), f"{stem}: reference round trip differs")
        for shorter_seconds, n, shorter_words in n_words_by_length:
            require(parsed[:n] == shorter_words, f"{stem}: not a prefix of {shorter_seconds} s")
        n_words_by_length.append((seconds, len(parsed), parsed))
        out["recordings"][name] = {
            "utterance": stem,
            "duration_s": round(duration, 6),
            "n_clips": len(ids),
            "first_clip": ids[0],
            "last_clip": ids[-1],
            "clip_ids": ids,
            "n_words": len(parsed),
            "wav_sha256": sha_file(wav_path),
            "textgrid_sha256": sha_file(tg_path),
        }
    out["source_sha256"] = sha_bytes(
        b"".join(
            f"{cid}\0{sha_file(clip_dir / f'{cid}.wav')}\0"
            f"{sha_file(clip_dir / f'{cid}.TextGrid')}\n".encode()
            for cid, _, _ in clips
        )
    )
    return out


def build(out: Path) -> int:
    before = git_state()
    require(not before["dirty"], "Worktree is dirty; commit before building")
    build_file = out / "build.json"
    require(not build_file.exists(), f"{build_file} exists; builds are never overwritten")
    dest = derived_root(out)
    require(not dest.exists(), f"{dest} exists; use a fresh output directory")
    out.mkdir(parents=True, exist_ok=True)
    speakers = read_json(PROJECT_ROOT / SPLIT)["test_speakers"]
    t0 = time.perf_counter()
    entries = {}
    for spk in speakers:
        entries[spk] = build_speaker(PROJECT_ROOT / CLIPS, spk, dest, LENGTHS)
        lens = ", ".join(
            f"{k} {v['duration_s']:.1f} s/{v['n_words']} w"
            for k, v in entries[spk]["recordings"].items()
        )
        print(f"[+] {spk}: {lens}", flush=True)
    write_json(
        build_file,
        {
            "schema_version": SCHEMA_VERSION,
            "protocol": "docs/S1_LONG_RECORDINGS_PROTOCOL.md",
            "protocol_sha256": sha_file(PROJECT_ROOT / "docs/S1_LONG_RECORDINGS_PROTOCOL.md"),
            "created_utc": datetime.datetime.now(datetime.UTC).isoformat(),
            "derived_dir": dest.relative_to(PROJECT_ROOT).as_posix(),
            "lengths_s": LENGTHS,
            "split": {"path": SPLIT.as_posix(), "sha256": sha_file(PROJECT_ROOT / SPLIT)},
            "speakers": entries,
            "code": code_hashes(),
            "git_before": before,
            "git_after": git_state(),
            "seconds": round(time.perf_counter() - t0, 1),
        },
    )
    print(f"[OK] {len(speakers)} speakers x {len(LENGTHS)} lengths -> {dest}")
    return 0


def check_build(out: Path) -> dict[str, Any]:
    """Re-hash every derived file against build.json."""
    meta = read_json(out / "build.json")
    dest = PROJECT_ROOT / meta["derived_dir"]
    for spk, entry in meta["speakers"].items():
        for name, rec in entry["recordings"].items():
            stem = rec["utterance"]
            require(
                sha_file(dest / name / f"{stem}.wav") == rec["wav_sha256"]
                and sha_file(dest / name / f"{stem}.TextGrid") == rec["textgrid_sha256"],
                f"{spk}/{name}: derived file changed since build",
            )
    return meta


# ---------------------------------------------------------------------------
# Run: the frozen benchmark on each length and variant
# ---------------------------------------------------------------------------


def run(out: Path) -> int:
    meta = check_build(out)
    dest = PROJECT_ROOT / meta["derived_dir"]
    for length in LENGTHS:
        for variant, modes in VARIANTS.items():
            run_dir = out / "runs" / f"{length}_{variant}"
            if (run_dir / "run_record.json").exists():
                print(f"[=] {run_dir.name}: done, skipped", flush=True)
                continue
            require(
                not (run_dir / "benchmark_results.json").exists(),
                f"{run_dir}: results without run record; inspect before rerunning",
            )
            before = git_state()
            require(not before["dirty"], "Worktree is dirty; commit before running")
            print(f"[*] {run_dir.name}: start {time.strftime('%H:%M:%S')}", flush=True)
            t0 = time.perf_counter()
            benchmark.run_benchmark(
                corpus="buckeye",
                data_dir=dest / length,
                output_dir=run_dir,
                modes=modes,
                refiner_dir=PROJECT_ROOT / REFINER_DIR,
                transcriber=NullTranscriber() if variant == "noanchor" else None,
            )
            write_json(
                run_dir / "run_record.json",
                {
                    "length": length,
                    "variant": variant,
                    "seconds": round(time.perf_counter() - t0, 1),
                    "git_before": before,
                    "git_after": git_state(),
                    "code": code_hashes(),
                    "build_sha256": sha_file(out / "build.json"),
                    "refiner_files": {
                        f.name: sha_file(f) for f in sorted((PROJECT_ROOT / REFINER_DIR).glob("*"))
                    },
                },
            )
            print(f"[+] {run_dir.name}: {time.perf_counter() - t0:.0f} s", flush=True)
    return 0


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------


def word_errors(words: list, refs: list) -> list[tuple[int, float, float, float]]:
    """(reference index, reference start s, |start error| ms, |end error| ms) per matched word."""
    index = {id(r): i for i, r in enumerate(refs)}
    pairs, _ = _align_token_sequences(words, refs)
    return [
        (index[id(r)], r.start, abs(p.start - r.start) * 1000.0, abs(p.end - r.end) * 1000.0)
        for p, r in pairs
    ]


def load_run(out: Path, meta: dict[str, Any], length: str, variant: str) -> dict[str, Any]:
    """Per mode and speaker: word errors, or the failure text. Checks MAE against rows."""
    run_dir = out / "runs" / f"{length}_{variant}"
    preds = deserialize_predictions(read_json(run_dir / "benchmark_predictions.json"))
    rows = {
        (r["mode"], r["utterance"]): r for r in read_json(run_dir / "benchmark_utterances.json")
    }
    utts = benchmark.load_textgrid_utterances(
        PROJECT_ROOT / meta["derived_dir"] / length, "buckeye"
    )
    errors: dict[str, dict[str, Any]] = {}
    for mode, per_utt in preds.items():
        errors[mode] = {}
        for utt in utts:
            pred = per_utt[utt.id]
            row = rows[(mode, utt.id)]
            if isinstance(pred, str):
                require(row["status"] == "failed", f"{run_dir.name}/{mode}/{utt.id}: status")
                errors[mode][utt.speaker_id] = pred
                continue
            werr = word_errors(pred[0], utt.ref_words)
            if not werr:
                errors[mode][utt.speaker_id] = "zero matched words"
                continue
            mae = float(np.mean([e for _, _, es, ee in werr for e in (es, ee)]))
            # Validation 2: the recomputed MAE equals the benchmark's row
            require(
                row["status"] == "ok" and abs(mae - row["word_mae_ms"]) <= MAE_TOLERANCE_MS,
                f"{run_dir.name}/{mode}/{utt.id}: MAE {mae} != row {row.get('word_mae_ms')}",
            )
            errors[mode][utt.speaker_id] = werr
    return errors


def subset_mae(werr: Any, keep) -> float | None:
    if isinstance(werr, str):
        return None
    vals = [e for i, s, es, ee in werr if keep(i, s) for e in (es, ee)]
    return float(np.mean(vals)) if vals else None


def bootstrap_mean_ci(values: list[float], seed: int = 42, n: int = 2000) -> list[float]:
    arr = np.asarray(values, dtype=np.float64)
    draws = np.random.default_rng(seed).integers(0, len(arr), size=(n, len(arr)))
    return np.percentile(arr[draws].mean(axis=1), [2.5, 97.5]).tolist()


def paired_test(base: dict[str, float | None], cond: dict[str, float | None]) -> dict[str, Any]:
    speakers = sorted(base)
    pairs = [(s, base[s], cond[s]) for s in speakers if base[s] is not None and cond[s] is not None]
    excluded = [s for s in speakers if base[s] is None or cond[s] is None]
    diffs = [c - b for _, b, c in pairs]
    out: dict[str, Any] = {
        "n_pairs": len(pairs),
        "excluded_speakers": excluded,
        "per_speaker_difference_ms": {s: round(c - b, 6) for s, b, c in pairs},
    }
    if len(pairs) < MIN_PAIRS:
        out.update({"testable": False, "p_value_raw": None})
        return out
    test = exact_signed_rank(diffs)
    out.update(
        {
            "testable": True,
            "mean_difference_ms": float(np.mean(diffs)),
            "median_difference_ms": float(np.median(diffs)),
            "mean_difference_ci_95_ms": bootstrap_mean_ci(diffs),
            "n_worse": int(sum(d > 0 for d in diffs)),
            "w": test["w"],
            "n_nonzero": test["n_nonzero"],
            "p_value_raw": test["p_value_raw"],
        }
    )
    return out


def analyze_runs(out: Path) -> dict[str, Any]:
    meta = check_build(out)
    data = {(L, v): load_run(out, meta, L, v) for L in LENGTHS for v in VARIANTS}
    first_minute = {spk: e["recordings"]["L01"]["n_words"] for spk, e in meta["speakers"].items()}

    def per_speaker(L, v, mode, keep=lambda i, s: True):
        return {spk: subset_mae(w, keep) for spk, w in data[(L, v)][mode].items()}

    tests: dict[str, Any] = {}
    for key, mode in TESTS:
        if key.startswith(("H1", "H2")):
            base = per_speaker(
                "L10", "anchored", mode, lambda i, s: DRIFT_EARLY[0] <= s < DRIFT_EARLY[1]
            )
            cond = per_speaker(
                "L10", "anchored", mode, lambda i, s: DRIFT_LATE[0] <= s < DRIFT_LATE[1]
            )
        elif key.startswith(("H3", "H4")):
            base = per_speaker("L01", "anchored", mode)
            cond = {
                spk: subset_mae(w, lambda i, s, n=first_minute[spk]: i < n)
                for spk, w in data[("L10", "anchored")][mode].items()
            }
        else:
            base = per_speaker("L10", "anchored", mode)
            cond = per_speaker("L10", "noanchor", mode)
        tests[key] = {"mode": mode, **paired_test(base, cond)}
    testable = [k for k, t in tests.items() if t["testable"]]
    for k, p in zip(
        testable,
        bonferroni_holm_adjustment([tests[k]["p_value_raw"] for k in testable]),
        strict=True,
    ):
        tests[k]["p_value_holm"] = float(p)
        tests[k]["significant_0_05"] = bool(p < 0.05)

    position: dict[str, Any] = {}
    for v in VARIANTS:
        for mode in POSITION_MODES:
            if mode not in data[("L10", v)]:
                continue
            bins = []
            for m in range(10):
                vals = [
                    e
                    for w in data[("L10", v)][mode].values()
                    if not isinstance(w, str)
                    for _, s, es, ee in w
                    if 60 * m <= s < 60 * (m + 1)
                    for e in (es, ee)
                ]
                bins.append(
                    {
                        "minute": m,
                        "n_boundaries": len(vals),
                        "mae_ms": float(np.mean(vals)) if vals else None,
                        "acc_20ms": float(np.mean(np.asarray(vals) <= 20.0) * 100)
                        if vals
                        else None,
                    }
                )
            position[f"{v}/{mode}"] = bins

    summary: dict[str, Any] = {}
    inputs: dict[str, str] = {}
    for L, v in data:
        run_dir = out / "runs" / f"{L}_{v}"
        res = read_json(run_dir / "benchmark_results.json")
        for f in (
            "benchmark_results.json",
            "benchmark_utterances.json",
            "benchmark_predictions.json",
            "manifest.json",
            "run_record.json",
        ):
            inputs[f"{run_dir.name}/{f}"] = sha_file(run_dir / f)
        summary[f"{L}_{v}"] = {
            "n_utterances": res["n_utterances"],
            "audio_seconds": res["total_audio_duration_seconds"],
            "rtf_total": res["runtime"]["rtf_total"],
            "mfa_retries": len(res["config"].get("mfa_retries", [])),
            "modes": {
                m: {
                    "failed": s["n_utterances_failed"],
                    "word": s["word_metrics"],
                    "phone": s["phone_metrics"],
                    "qe_roc_auc": (s.get("quality_estimation") or {}).get("roc_auc"),
                }
                for m, s in res["modes"].items()
            },
        }
    return {
        "schema_version": SCHEMA_VERSION,
        "protocol_sha256": sha_file(PROJECT_ROOT / "docs/S1_LONG_RECORDINGS_PROTOCOL.md"),
        "build_sha256": sha_file(out / "build.json"),
        "inputs": inputs,
        "tests": tests,
        "position_L10": position,
        "runs": summary,
    }


def analyze(out: Path) -> int:
    before = git_state()
    require(not before["dirty"], "Worktree is dirty; commit before analysis")
    result = analyze_runs(out)
    result["code"] = code_hashes()
    result["git"] = before
    write_json(out / "analysis.json", result)
    for key, t in result["tests"].items():
        if t["testable"]:
            print(
                f"[+] {key}: mean diff {t['mean_difference_ms']:+.2f} ms, "
                f"{t['n_worse']}/{t['n_pairs']} worse, p_holm {t['p_value_holm']:.3g}"
            )
        else:
            print(f"[!] {key}: not testable ({t['n_pairs']} pairs)")
    return 0


# ---------------------------------------------------------------------------
# Verify (separate process)
# ---------------------------------------------------------------------------


def brute_force_p(diffs: list[float]) -> float:
    """Two-sided exact signed-rank p by enumerating all 2^n sign vectors (n <= 20)."""
    d = np.round(np.asarray(diffs, dtype=np.float64), 9)
    d = d[d != 0]
    n = len(d)
    if n == 0:
        return 1.0
    require(n <= 20, "brute force limited to 20 pairs")
    absd = np.abs(d)
    ranks = np.array([np.mean(np.flatnonzero(np.sort(absd) == a) + 1) for a in absd])
    observed = ranks[d > 0].sum()
    total = ranks.sum()
    stat = min(observed, total - observed)
    hits = 0
    for lo in range(0, 2**n, 1 << 16):  # chunks keep memory small
        block = np.arange(lo, min(lo + (1 << 16), 2**n))
        pos = ((block[:, None] >> np.arange(n)) & 1).astype(np.float64) @ ranks
        hits += int(np.count_nonzero(np.minimum(pos, total - pos) <= stat + 1e-9))
    return float(min(1.0, hits / 2**n))


def verify(out: Path) -> int:
    problems: list[str] = []
    recorded = read_json(out / "analysis.json")
    try:
        fresh = analyze_runs(out)
    except S1Error as err:
        problems.append(f"re-analysis failed: {err}")
        fresh = {}
    for key in ("protocol_sha256", "build_sha256", "inputs", "tests", "position_L10", "runs"):
        if fresh and fresh.get(key) != recorded.get(key):
            problems.append(f"{key}: re-analysis differs from analysis.json")
    if recorded.get("code") != code_hashes():
        problems.append("code changed since analysis")
    for key, t in recorded["tests"].items():
        if t["testable"]:
            p = brute_force_p(list(t["per_speaker_difference_ms"].values()))
            if abs(p - t["p_value_raw"]) > 1e-12:
                problems.append(f"{key}: exact p {t['p_value_raw']} != brute force {p}")
    report = {
        "verified": not problems,
        "problems": problems,
        "checked_utc": datetime.datetime.now(datetime.UTC).isoformat(),
    }
    write_json(out / "verify.json", report)
    print(json.dumps(report, indent=2))
    return 0 if not problems else 1


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("command", choices=["build", "run", "analyze", "verify"])
    p.add_argument("--output-dir", type=Path, required=True)
    args = p.parse_args(argv)
    out = args.output_dir if args.output_dir.is_absolute() else PROJECT_ROOT / args.output_dir
    commands = {"build": build, "run": run, "analyze": analyze, "verify": verify}
    try:
        return commands[args.command](out)
    except S1Error as err:
        print(f"[ERROR] {err}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
