"""S2 (speech tempo) and S3 (Whisper size): wrappers over the frozen benchmark.

Protocol: docs/S2_S3_PROTOCOL.md (committed before any run).

  python scripts/s2_s3_substudies.py s2-build --output-dir reports/s2_tempo_20261103
  python scripts/s2_s3_substudies.py s2-run   --output-dir reports/s2_tempo_20261103 --mfa-workers 4
  python scripts/s2_s3_substudies.py s3-run   --output-dir reports/s3_asr_size_20261103 --mfa-workers 4
  python scripts/s2_s3_substudies.py analyze  --output-dir <either>

S2: every TIMIT test utterance (160) and 10 seeded clips per Buckeye test speaker (200)
are re-rendered at tempo 0.8 / 0.9 / 1.0 / 1.1 / 1.25 (pitch kept, scripts/tempo.py;
1.0 also goes through the vocoder as the processed control); references are mapped
by t / rate. All nine benchmark modes run per corpus and tempo.
S3: the 999 frozen Buckeye test clips, scenario B modes only, with Whisper sizes other
than large-v3 (whose results are the frozen Buckeye run).
"""

from __future__ import annotations

import argparse
import datetime
import json
import random
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts import s1_long_recordings as s1  # noqa: E402
from scripts import speech_benchmark as benchmark  # noqa: E402
from scripts.tempo import stretch_pcm16  # noqa: E402
from subtitle_workbench.buckeye import Interval, _textgrid  # noqa: E402
from subtitle_workbench.corpora import parse_buckeye_textgrid  # noqa: E402

RATES = [0.8, 0.9, 1.0, 1.1, 1.25]
TIMIT_DIR = Path("data/corpora/timit")
BUCKEYE_DIR = Path("data/corpora/buckeye")
BUCKEYE_SAMPLE = Path("reports/buckeye_test_sample_20260401.json")
S2_PER_SPEAKER = 10
S2_SEED = 20261103
S3_SIZES = ["tiny", "base", "small", "medium", "large-v3-turbo"]
S3_MODES = ["B0_whisper", "B1_whisper_ctc", "B2_proposed", "B2_const", "B2_brqe"]
FROZEN_BUCKEYE = Path("reports/buckeye/benchmark_utterances.json")
KEY_MODES = ["A2_proposed", "A2_brqe", "B2_proposed", "B2_brqe"]
CODE_FILES = (
    "scripts/s2_s3_substudies.py",
    "scripts/tempo.py",
    "scripts/parallel_mfa.py",
    "docs/S2_S3_PROTOCOL.md",
    "scripts/speech_benchmark.py",
    "uv.lock",
)
require = s1.require


def code_hashes() -> dict[str, str]:
    return {p: s1.sha_file(PROJECT_ROOT / p) for p in CODE_FILES}


def tag(rate: float) -> str:
    return f"r{rate:.2f}"


# ---------------------------------------------------------------- S2 build
def _write_wav(path: Path, sr: int, frames: bytes) -> None:
    import wave

    with wave.open(str(path), "wb") as dst:
        dst.setnchannels(1)
        dst.setsampwidth(2)
        dst.setframerate(sr)
        dst.writeframes(frames)


def _scale_sample_file(src: Path, dst: Path, rate: float) -> None:
    """TIMIT .wrd/.phn: '<start sample> <end sample> <label>' per line."""
    lines = []
    for ln in src.read_text(encoding="utf-8", errors="replace").splitlines():
        parts = ln.split()
        if len(parts) >= 3:
            a, b = round(int(parts[0]) / rate), round(int(parts[1]) / rate)
            lines.append(f"{a} {b} {' '.join(parts[2:])}")
    dst.write_text("\n".join(lines) + "\n", encoding="utf-8")


def s2_buckeye_ids() -> list[str]:
    ids = s1.read_json(PROJECT_ROOT / BUCKEYE_SAMPLE)["utterance_ids"]
    rng = random.Random(S2_SEED)
    chosen = []
    for spk in sorted({i[:3] for i in ids}):
        own = sorted(i for i in ids if i[:3] == spk)
        chosen += sorted(rng.sample(own, min(S2_PER_SPEAKER, len(own))))
    return chosen


def s2_build(out: Path) -> int:
    before = s1.git_state()
    require(not before["dirty"], "Worktree is dirty; commit before building")
    require(not (out / "build.json").exists(), "build.json exists; never overwritten")
    dest = s1.derived_root(out)
    require(not dest.exists(), f"{dest} exists; use a fresh output directory")
    t0 = time.perf_counter()
    files: dict[str, str] = {}
    timit_wavs = sorted((PROJECT_ROOT / TIMIT_DIR).glob("**/*.wav"))
    bk_ids = s2_buckeye_ids()
    for rate in RATES:
        for wav in timit_wavs:
            rel = wav.relative_to(PROJECT_ROOT / TIMIT_DIR)
            target = dest / "timit" / tag(rate) / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            sr, frames = s1.read_pcm(wav)
            _write_wav(target, sr, stretch_pcm16(frames, rate))
            for ext in (".wrd", ".phn"):
                if wav.with_suffix(ext).is_file():
                    _scale_sample_file(wav.with_suffix(ext), target.with_suffix(ext), rate)
            files[target.relative_to(PROJECT_ROOT).as_posix()] = s1.sha_file(target)
        for cid in bk_ids:
            src = PROJECT_ROOT / BUCKEYE_DIR / f"{cid}.wav"
            target = dest / "buckeye" / tag(rate) / f"{cid}.wav"
            target.parent.mkdir(parents=True, exist_ok=True)
            sr, frames = s1.read_pcm(src)
            out_frames = stretch_pcm16(frames, rate)
            _write_wav(target, sr, out_frames)
            refs = parse_buckeye_textgrid(src.with_suffix(".TextGrid"))
            words = [Interval(w.start / rate, w.end / rate, w.text) for w in refs]
            phones = [
                Interval(c.start / rate, c.end / rate, c.phoneme) for w in refs for c in w.phonemes
            ]
            dur = round(len(out_frames) / (2 * sr), 6)
            tg = target.with_suffix(".TextGrid")
            tg.write_text(_textgrid(words, phones, 0.0, dur), encoding="utf-8")
            target.with_suffix(".txt").write_text(
                " ".join(w.label for w in words) + "\n", encoding="utf-8"
            )
            parsed = parse_buckeye_textgrid(tg)
            require(
                s1.max_deviation(parsed, words, phones) <= s1.TIME_TOLERANCE_S,
                f"{cid}: TextGrid round trip",
            )
            files[target.relative_to(PROJECT_ROOT).as_posix()] = s1.sha_file(target)
        print(f"[+] tempo {rate}: {len(timit_wavs)} TIMIT + {len(bk_ids)} Buckeye", flush=True)
    out.mkdir(parents=True, exist_ok=True)
    s1.write_json(
        out / "build.json",
        {
            "protocol": "docs/S2_S3_PROTOCOL.md",
            "created_utc": datetime.datetime.now(datetime.UTC).isoformat(),
            "derived_dir": dest.relative_to(PROJECT_ROOT).as_posix(),
            "rates": RATES,
            "buckeye_ids": bk_ids,
            "n_timit": len(timit_wavs),
            "audio_sha256": files,
            "code": code_hashes(),
            "git_before": before,
            "git_after": s1.git_state(),
            "seconds": round(time.perf_counter() - t0, 1),
        },
    )
    return 0


def check_s2_build(out: Path) -> dict[str, Any]:
    meta = s1.read_json(out / "build.json")
    for rel, sha in meta["audio_sha256"].items():
        require(s1.sha_file(PROJECT_ROOT / rel) == sha, f"{rel}: changed since build")
    return meta


# ---------------------------------------------------------------- runs
def _aligner(workers: int) -> Any:
    from scripts.parallel_mfa import ParallelAligner

    return ParallelAligner.build(workers, benchmark.MFA_NUM_JOBS, isolate=False)


def _run_one(run_dir: Path, workers: int, record: dict[str, Any], **kwargs: Any) -> None:
    if (run_dir / "run_record.json").exists():
        print(f"[=] {run_dir.name}: done, skipped", flush=True)
        return
    require(
        not (run_dir / "benchmark_results.json").exists(),
        f"{run_dir}: results without run record; inspect before rerunning",
    )
    before = s1.git_state()
    require(not before["dirty"], "Worktree is dirty; commit before running")
    print(f"[*] {run_dir.name}: start {time.strftime('%H:%M:%S')}", flush=True)
    t0 = time.perf_counter()
    aligner = _aligner(workers)
    benchmark.run_benchmark(
        output_dir=run_dir, refiner_dir=PROJECT_ROOT / s1.REFINER_DIR, aligner=aligner, **kwargs
    )
    s1.write_json(
        run_dir / "run_record.json",
        {
            **record,
            "mfa_workers": workers,
            "mfa_retries": aligner.mfa_retries,
            "seconds": round(time.perf_counter() - t0, 1),
            "git_before": before,
            "git_after": s1.git_state(),
            "code": code_hashes(),
            "refiner_files": {
                f.name: s1.sha_file(f) for f in sorted((PROJECT_ROOT / s1.REFINER_DIR).glob("*"))
            },
        },
    )
    print(f"[+] {run_dir.name}: {time.perf_counter() - t0:.0f} s", flush=True)


def s2_run(out: Path, workers: int) -> int:
    meta = check_s2_build(out)
    dest = PROJECT_ROOT / meta["derived_dir"]
    for corpus in ("timit", "buckeye"):
        for rate in RATES:
            _run_one(
                out / "runs" / f"{corpus}_{tag(rate)}",
                workers,
                {"study": "S2", "corpus": corpus, "rate": rate},
                corpus=corpus,
                data_dir=dest / corpus / tag(rate),
            )
    return 0


def s3_run(out: Path, workers: int) -> int:
    out.mkdir(parents=True, exist_ok=True)
    for size in S3_SIZES:
        _run_one(
            out / "runs" / f"buckeye_{size}",
            workers,
            {"study": "S3", "asr_model": size},
            corpus="buckeye",
            data_dir=PROJECT_ROOT / BUCKEYE_DIR,
            utterance_list=PROJECT_ROOT / BUCKEYE_SAMPLE,
            modes=S3_MODES,
            asr_model=size,
        )
    return 0


# ---------------------------------------------------------------- analysis
def summarize_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Per mode: speaker-level mean MAE, Acc@20, word coverage and failures."""
    out: dict[str, Any] = {}
    for mode in sorted({r["mode"] for r in rows}):
        mrows = [r for r in rows if r["mode"] == mode]
        per_spk: dict[str, list[float]] = {}
        for r in mrows:
            if r.get("word_mae_ms") is not None:
                per_spk.setdefault(r["speaker"], []).append(r["word_mae_ms"])
        spk_mae = {s: float(np.mean(v)) for s, v in per_spk.items()}
        acc = [r["word_acc_20ms"] for r in mrows if r.get("word_acc_20ms") is not None]
        matched = sum(r.get("word_matched") or 0 for r in mrows)
        reference = sum(r.get("word_reference") or 0 for r in mrows)
        out[mode] = {
            "n_utterances": len(mrows),
            "n_failed": sum(r.get("word_mae_ms") is None for r in mrows),
            "speaker_mae_ms": spk_mae,
            "mean_speaker_mae_ms": float(np.mean(list(spk_mae.values()))) if spk_mae else None,
            "mean_acc20": float(np.mean(acc)) if acc else None,
            "word_coverage": matched / reference if reference else None,
        }
    return out


def holm(pvals: dict[str, float | None]) -> dict[str, float | None]:
    items = sorted((p, k) for k, p in pvals.items() if p is not None)
    adj: dict[str, float | None] = {k: None for k in pvals}
    running = 0.0
    for i, (p, k) in enumerate(items):
        running = max(running, min(1.0, (len(items) - i) * p))
        adj[k] = running
    return adj


def compare(
    base: dict[str, Any], conds: dict[str, dict[str, Any]], modes: list[str]
) -> dict[str, Any]:
    """Speaker-paired tests of each condition against the base, Holm within each mode."""
    out: dict[str, Any] = {}
    for mode in modes:
        if mode not in base:
            continue
        tests = {
            c: s1.paired_test(
                base[mode]["speaker_mae_ms"],
                {s: v[mode]["speaker_mae_ms"].get(s) for s in base[mode]["speaker_mae_ms"]},
            )
            for c, v in conds.items()
            if mode in v
        }
        adj = holm({c: t.get("p_value_raw") for c, t in tests.items()})
        for c, t in tests.items():
            t["p_value_holm"] = adj[c]
        out[mode] = tests
    return out


def analyze(out: Path) -> int:
    runs = {
        d.name: summarize_rows(s1.read_json(d / "benchmark_utterances.json"))
        for d in sorted((out / "runs").glob("*"))
        if (d / "run_record.json").exists()
    }
    require(runs, "no finished runs")
    result: dict[str, Any] = {"runs": runs}
    if (out / "build.json").exists():  # S2
        for corpus in ("timit", "buckeye"):
            base = runs.get(f"{corpus}_{tag(1.0)}")
            conds = {
                k: v
                for k, v in runs.items()
                if k.startswith(corpus) and k != f"{corpus}_{tag(1.0)}"
            }
            if base:
                result[f"tests_{corpus}_vs_r1.00"] = compare(base, conds, KEY_MODES)
    else:  # S3: against the frozen large-v3 Buckeye run
        frozen = summarize_rows(
            json.loads((PROJECT_ROOT / FROZEN_BUCKEYE).read_text(encoding="utf-8"))
        )
        result["frozen_large_v3"] = {m: frozen[m] for m in S3_MODES if m in frozen}
        result["tests_vs_large_v3"] = compare(frozen, runs, ["B2_proposed", "B2_brqe"])
    result["created_utc"] = datetime.datetime.now(datetime.UTC).isoformat()
    result["code"] = code_hashes()
    s1.write_json(out / "analysis.json", result)
    for name, r in runs.items():
        cells = " | ".join(
            f"{m} {r[m]['mean_speaker_mae_ms']:.1f} ms cov {r[m]['word_coverage']:.3f}"
            for m in KEY_MODES
            if m in r and r[m]["mean_speaker_mae_ms"] is not None
        )
        print(f"{name}: {cells}")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("command", choices=["s2-build", "s2-run", "s3-run", "analyze"])
    p.add_argument("--output-dir", type=Path, required=True)
    p.add_argument("--mfa-workers", type=int, default=1)
    a = p.parse_args(argv)
    out = a.output_dir if a.output_dir.is_absolute() else PROJECT_ROOT / a.output_dir
    commands = {
        "s2-build": lambda: s2_build(out),
        "s2-run": lambda: s2_run(out, a.mfa_workers),
        "s3-run": lambda: s3_run(out, a.mfa_workers),
        "analyze": lambda: analyze(out),
    }
    return commands[a.command]()


if __name__ == "__main__":
    sys.exit(main())
