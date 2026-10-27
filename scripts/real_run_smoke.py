"""Smoke test verifying real model execution path on local workstation.

Executes run_speech_pipeline with engine="ctc" and engine="mfa" (if available).
Profiles real execution time, RTF, peak VRAM (torch.cuda.max_memory_allocated()),
peak host RAM, and verifies manifest and output generation.
Explicitly reports zero accuracy (no ground-truth reference).
"""

from __future__ import annotations

import argparse
import ctypes
import json
import logging
import math
import platform
import shutil
import sys
import tempfile
import time
import wave
from pathlib import Path
from typing import Any

import numpy as np

# Configure logging
logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")
logger = logging.getLogger("real_run_smoke")


def get_peak_vram_mb() -> float | None:
    """Return peak CUDA VRAM in MB if PyTorch with CUDA is available."""
    try:
        import torch

        if torch.cuda.is_available():
            return float(torch.cuda.max_memory_allocated() / (1024 * 1024))
    except Exception:
        pass
    return None


def reset_peak_vram() -> None:
    """Reset CUDA peak memory stats."""
    try:
        import torch

        if torch.cuda.is_available():
            torch.cuda.reset_peak_memory_stats()
    except Exception:
        pass


def get_peak_host_ram_mb() -> float:
    """Query peak host RAM in MB via OS API."""
    if sys.platform == "win32":
        try:
            from ctypes import wintypes

            class PROCESS_MEMORY_COUNTERS_EX(ctypes.Structure):
                _fields_ = [
                    ("cb", wintypes.DWORD),
                    ("PageFaultCount", wintypes.DWORD),
                    ("PeakWorkingSetSize", ctypes.c_size_t),
                    ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t),
                    ("PeakPagefileUsage", ctypes.c_size_t),
                    ("PrivateUsage", ctypes.c_size_t),
                ]

            psapi = ctypes.WinDLL("psapi")
            handle = ctypes.windll.kernel32.GetCurrentProcess()
            counters = PROCESS_MEMORY_COUNTERS_EX()
            counters.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS_EX)
            if psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb):
                return float(counters.PeakWorkingSetSize / (1024 * 1024))
        except Exception:
            pass

    try:
        import resource

        usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return float(usage / 1024 if sys.platform == "darwin" else usage / 1024.0)
    except Exception:
        pass

    return 0.0


def create_smoke_wav(path: Path, duration_sec: float = 2.5, sample_rate: int = 16000) -> Path:
    """Generate a clean PCM16 mono 16 kHz WAV audio file for smoke testing."""
    total_samples = int(duration_sec * sample_rate)
    t = np.arange(total_samples, dtype=np.float64) / float(sample_rate)
    carrier = np.sin(2.0 * math.pi * 320.0 * t) + 0.4 * np.sin(2.0 * math.pi * 640.0 * t)
    envelope = 0.5 + 0.5 * np.sin(2.0 * math.pi * 2.0 * t)
    signal = 0.3 * carrier * envelope
    pcm = np.clip(signal * 32767.0, -32768.0, 32767.0).astype(np.int16)

    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm.tobytes())
    return path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify real speech pipeline execution path and profile hardware footprint."
    )
    parser.add_argument(
        "--wav",
        type=Path,
        default=None,
        help="Path to uncompressed 16 kHz mono WAV file. If omitted, generates a 2.5s test WAV.",
    )
    parser.add_argument(
        "--transcript",
        type=str,
        default="academic lecture speech alignment smoke test",
        help="Transcript text for forced alignment smoke run.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("dist/real_run_smoke"),
        help="Directory where smoke test artifacts will be saved.",
    )
    parser.add_argument(
        "--skip-mfa",
        action="store_true",
        help="Skip Montreal Forced Aligner check and execution.",
    )
    args = parser.parse_args()

    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. Environmental Inspection
    logger.info("============================================================")
    logger.info("Real Model Execution Path & Hardware Profiling Smoke Test")
    logger.info("============================================================")
    logger.info(f"Platform: {platform.platform()} ({platform.machine()})")
    logger.info(f"Python:   {sys.version.split()[0]}")

    cuda_available = False
    device_name = "CPU"
    try:
        import torch

        cuda_available = torch.cuda.is_available()
        if cuda_available:
            device_name = torch.cuda.get_device_name(0)
            logger.info(
                f"CUDA:     Available ({device_name}, VRAM: {torch.cuda.get_device_properties(0).total_memory / (1024**3):.2f} GB)"
            )
        else:
            logger.info("CUDA:     Not available (running on CPU)")
    except ImportError:
        logger.info("CUDA:     PyTorch not installed")

    # Check MFA availability
    from subtitle_workbench.mfa_wrapper import check_mfa_available

    mfa_available = check_mfa_available() and not args.skip_mfa
    logger.info(
        f"MFA:      {'Available on system PATH' if mfa_available else 'Not available on PATH (skipped)'}"
    )

    # 2. Audio Preparation
    temp_dir = None
    if args.wav is not None:
        wav_path = args.wav.resolve()
        if not wav_path.is_file():
            logger.error(f"Provided WAV file does not exist: {wav_path}")
            return 1
    else:
        temp_dir = Path(tempfile.mkdtemp(prefix="smoke_audio_"))
        wav_path = temp_dir / "smoke_speech.wav"
        create_smoke_wav(wav_path, duration_sec=2.5)
        logger.info(f"Generated synthetic test WAV: {wav_path} (2.5s, 16 kHz mono)")

    with wave.open(str(wav_path), "rb") as wf:
        audio_duration = wf.getnframes() / float(wf.getframerate())
    logger.info(f"Audio Duration: {audio_duration:.2f} s")
    logger.info(f"Transcript:     '{args.transcript}'")

    from subtitle_workbench.pipeline import run_speech_pipeline

    summary: dict[str, Any] = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "status": "PASS",
        "provenance": "REAL_EXECUTION_SMOKE_TEST",
        "accuracy_evaluation": "NONE / ZERO_GOLD (Smoke run verified model execution path and hardware profiling only; no reference phoneme/word boundaries provided).",
        "platform": platform.platform(),
        "device": device_name,
        "cuda_available": cuda_available,
        "audio_path": str(wav_path),
        "audio_duration_sec": round(audio_duration, 3),
        "ctc_run": None,
        "mfa_run": None,
    }

    # 3. Test Engine: CTC Trellis
    logger.info("------------------------------------------------------------")
    logger.info("Executing Mode A: CTC Trellis forced alignment...")
    ctc_out = output_dir / "ctc_run"
    if ctc_out.exists():
        shutil.rmtree(ctc_out)

    reset_peak_vram()
    t0 = time.perf_counter()
    try:
        ctc_result = run_speech_pipeline(
            audio_path=wav_path,
            output_dir=ctc_out,
            transcript=args.transcript,
            engine="ctc",
            fallback_to_ctc=True,
        )
        elapsed_ctc = time.perf_counter() - t0
        rtf_ctc = elapsed_ctc / audio_duration if audio_duration > 0 else 0.0
        vram_ctc = get_peak_vram_mb()
        ram_ctc = get_peak_host_ram_mb()

        # Validate outputs
        vtt_file = ctc_out / "subtitles.vtt"
        jsonld_file = ctc_out / "timeline.jsonld"
        raw_file = ctc_out / "alignment_raw.json"
        assert vtt_file.is_file(), "subtitles.vtt was not generated"
        assert jsonld_file.is_file(), "timeline.jsonld was not generated"
        assert raw_file.is_file(), "alignment_raw.json was not generated"

        logger.info(f"CTC SUCCESS in {elapsed_ctc:.3f} s (RTF: {rtf_ctc:.4f}x)")
        if vram_ctc is not None:
            logger.info(f"Peak VRAM: {vram_ctc:.1f} MB")
        logger.info(f"Peak Host RAM: {ram_ctc:.1f} MB")
        logger.info(f"Aligned words count: {len(ctc_result)}")

        summary["ctc_run"] = {
            "status": "SUCCESS",
            "elapsed_seconds": round(elapsed_ctc, 4),
            "rtf": round(rtf_ctc, 4),
            "peak_vram_mb": round(vram_ctc, 1) if vram_ctc is not None else None,
            "peak_ram_mb": round(ram_ctc, 1),
            "aligned_words_count": len(ctc_result),
            "artifacts": {
                "subtitles_vtt": str(vtt_file),
                "timeline_jsonld": str(jsonld_file),
                "alignment_raw": str(raw_file),
            },
        }
    except Exception as err:
        logger.error(f"CTC alignment failed: {err}")
        summary["ctc_run"] = {"status": "FAILED", "error": str(err)}
        summary["status"] = "FAILED"

    # 4. Test Engine: Montreal Forced Aligner (if available)
    logger.info("------------------------------------------------------------")
    if mfa_available:
        logger.info("Executing Mode B: Montreal Forced Aligner (Kaldi GMM-HMM)...")
        mfa_out = output_dir / "mfa_run"
        if mfa_out.exists():
            shutil.rmtree(mfa_out)

        reset_peak_vram()
        t0 = time.perf_counter()
        try:
            mfa_result = run_speech_pipeline(
                audio_path=wav_path,
                output_dir=mfa_out,
                transcript=args.transcript,
                engine="mfa",
                fallback_to_ctc=False,
            )
            elapsed_mfa = time.perf_counter() - t0
            rtf_mfa = elapsed_mfa / audio_duration if audio_duration > 0 else 0.0
            vram_mfa = get_peak_vram_mb()
            ram_mfa = get_peak_host_ram_mb()

            vtt_file = mfa_out / "subtitles.vtt"
            jsonld_file = mfa_out / "timeline.jsonld"
            raw_file = mfa_out / "alignment_raw.json"
            assert vtt_file.is_file(), "subtitles.vtt was not generated"

            logger.info(f"MFA SUCCESS in {elapsed_mfa:.3f} s (RTF: {rtf_mfa:.4f}x)")
            if vram_mfa is not None:
                logger.info(f"Peak VRAM: {vram_mfa:.1f} MB")
            logger.info(f"Peak Host RAM: {ram_mfa:.1f} MB")
            logger.info(f"Aligned words count: {len(mfa_result)}")

            summary["mfa_run"] = {
                "status": "SUCCESS",
                "elapsed_seconds": round(elapsed_mfa, 4),
                "rtf": round(rtf_mfa, 4),
                "peak_vram_mb": round(vram_mfa, 1) if vram_mfa is not None else None,
                "peak_ram_mb": round(ram_mfa, 1),
                "aligned_words_count": len(mfa_result),
                "artifacts": {
                    "subtitles_vtt": str(vtt_file),
                    "timeline_jsonld": str(jsonld_file),
                    "alignment_raw": str(raw_file),
                },
            }
        except Exception as err:
            logger.warning(f"MFA execution failed: {err}")
            summary["mfa_run"] = {"status": "FAILED", "error": str(err)}
    else:
        logger.info("Mode B (MFA): SKIPPED (MFA binary not on PATH or --skip-mfa passed)")
        summary["mfa_run"] = {
            "status": "SKIPPED",
            "reason": "MFA binary not found on system PATH. Install via conda or see docs/RUNBOOK_REAL_BENCHMARK.md.",
        }

    # 5. Write Summary Manifest
    summary_path = output_dir / "smoke_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    logger.info("------------------------------------------------------------")
    logger.info(f"Smoke test summary written to: {summary_path}")
    logger.info(f"Final Status: {summary['status']}")
    logger.info(f"Accuracy Claim: {summary['accuracy_evaluation']}")
    logger.info("============================================================")

    if temp_dir is not None and not args.keep_temp if hasattr(args, "keep_temp") else False:
        shutil.rmtree(temp_dir, ignore_errors=True)

    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
