"""Download and stage open-access speech corpora for alignment benchmark.

Supports two open-access evaluation corpora:
1. LibriSpeech test-clean (Native English reading speech) via Hugging Face API.
2. L2-ARCTIC (Non-native accented speech) via Hugging Face chikingsley mirror.

Produces uncompressed 16 kHz mono PCM16 WAV audio and Praat .TextGrid files
compatible with the workbench evaluation pipeline.
"""

from __future__ import annotations

import argparse
import io
import logging
import sys
import wave
import zipfile
from pathlib import Path
from typing import Any

import av
import httpx
import numpy as np
import torch
import torchaudio.functional as F
from huggingface_hub import hf_hub_download

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")
logger = logging.getLogger("download_open_benchmark")


def format_textgrid(
    words: list[dict[str, Any]],
    phones: list[dict[str, Any]],
    total_duration: float,
) -> str:
    """Format Praat long-form TextGrid string with contiguous intervals."""
    total_duration = max(0.01, round(total_duration, 6))

    # Build words intervals
    word_intervals: list[tuple[float, float, str]] = []
    cur_t = 0.0
    for w in sorted(words, key=lambda x: float(x["start"])):
        start = max(0.0, min(total_duration, float(w["start"])))
        end = max(start, min(total_duration, float(w["end"])))
        text = str(w.get("word", "")).strip()
        if start > cur_t:
            word_intervals.append((cur_t, start, ""))
        if end > start:
            word_intervals.append((start, end, text))
            cur_t = end
    if cur_t < total_duration:
        word_intervals.append((cur_t, total_duration, ""))

    if not word_intervals:
        word_intervals = [(0.0, total_duration, "")]

    # Build phones intervals
    phone_intervals: list[tuple[float, float, str]] = []
    cur_t = 0.0
    for p in sorted(phones, key=lambda x: float(x["start"])):
        start = max(0.0, min(total_duration, float(p["start"])))
        end = max(start, min(total_duration, float(p["end"])))
        text = str(p.get("phoneme", "")).strip()
        if start > cur_t:
            phone_intervals.append((cur_t, start, "sil"))
        if end > start:
            phone_intervals.append((start, end, text))
            cur_t = end
    if cur_t < total_duration:
        phone_intervals.append((cur_t, total_duration, "sil"))

    if not phone_intervals:
        phone_intervals = [(0.0, total_duration, "sil")]

    lines = [
        'File type = "ooTextFile"',
        'Object class = "TextGrid"',
        "",
        "xmin = 0.0",
        f"xmax = {total_duration:.6f}",
        "tiers? <exists>",
        "size = 2",
        "item []:",
        "    item [1]:",
        '        class = "IntervalTier"',
        '        name = "words"',
        "        xmin = 0.0",
        f"        xmax = {total_duration:.6f}",
        f"        intervals: size = {len(word_intervals)}",
    ]
    for idx, (xmin, xmax, text) in enumerate(word_intervals, start=1):
        clean_text = text.replace('"', '""')
        lines.extend(
            [
                f"        intervals [{idx}]:",
                f"            xmin = {xmin:.6f}",
                f"            xmax = {xmax:.6f}",
                f'            text = "{clean_text}"',
            ]
        )

    lines.extend(
        [
            "    item [2]:",
            '        class = "IntervalTier"',
            '        name = "phones"',
            "        xmin = 0.0",
            f"        xmax = {total_duration:.6f}",
            f"        intervals: size = {len(phone_intervals)}",
        ]
    )
    for idx, (xmin, xmax, text) in enumerate(phone_intervals, start=1):
        clean_text = text.replace('"', '""')
        lines.extend(
            [
                f"        intervals [{idx}]:",
                f"            xmin = {xmin:.6f}",
                f"            xmax = {xmax:.6f}",
                f'            text = "{clean_text}"',
            ]
        )

    return "\n".join(lines) + "\n"


def decode_flac_to_pcm16_mono(
    flac_bytes: bytes, target_sr: int = 16000
) -> tuple[np.ndarray, float]:
    """Decode FLAC audio bytes to 16 kHz mono int16 PCM array."""
    container = av.open(io.BytesIO(flac_bytes))
    frames = [f.to_ndarray() for f in container.decode(audio=0)]
    if not frames:
        raise ValueError("Empty audio stream in FLAC payload")
    audio = np.concatenate(frames, axis=-1)

    # Convert to mono if multi-channel
    if audio.ndim == 2 and audio.shape[0] > 1:
        audio = np.mean(audio, axis=0, keepdims=True).astype(np.int16)
    elif audio.ndim == 1:
        audio = audio[np.newaxis, :]

    orig_sr = container.streams.audio[0].rate
    if orig_sr != target_sr:
        tensor = torch.from_numpy(audio.astype(np.float32))
        resampled = F.resample(tensor, orig_sr, target_sr)
        audio = resampled.clamp(-32768, 32767).to(torch.int16).numpy()

    duration = audio.shape[-1] / float(target_sr)
    return audio.flatten(), duration


def stage_librispeech(target_dir: Path, limit: int = 50) -> int:
    """Download and stage LibriSpeech test-clean utterances with TextGrids."""
    libri_dir = target_dir / "librispeech"
    libri_dir.mkdir(parents=True, exist_ok=True)

    logger.info(f"Fetching {limit} LibriSpeech test-clean records via HuggingFace API...")
    url = (
        f"https://datasets-server.huggingface.co/rows?"
        f"dataset=gilkeyio/librispeech-alignments&config=default&split=test_clean&offset=0&limit={limit}"
    )

    resp = httpx.get(url, timeout=30.0)
    if resp.status_code != 200:
        logger.error(f"Failed to fetch LibriSpeech rows: HTTP {resp.status_code}")
        return 0

    rows = resp.json().get("rows", [])
    logger.info(f"Received {len(rows)} rows. Downloading audio and formatting TextGrids...")

    saved_count = 0
    client = httpx.Client(timeout=30.0)
    for idx, r in enumerate(rows, start=1):
        row = r["row"]
        utt_id = row["id"]
        words = row.get("words", [])
        phones = row.get("phonemes", [])
        transcript = row.get("transcript", "")
        audio_info = row.get("audio", [{}])[0]
        audio_src = audio_info.get("src")

        if not audio_src:
            continue

        wav_path = libri_dir / f"{utt_id}.wav"
        tg_path = libri_dir / f"{utt_id}.TextGrid"
        txt_path = libri_dir / f"{utt_id}.txt"

        if wav_path.is_file() and tg_path.is_file():
            saved_count += 1
            continue

        try:
            flac_data = client.get(audio_src).content
            pcm_arr, dur = decode_flac_to_pcm16_mono(flac_data, target_sr=16000)

            # Write WAV
            with wave.open(str(wav_path), "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(16000)
                wf.writeframes(pcm_arr.tobytes())

            # Write TextGrid
            tg_text = format_textgrid(words, phones, total_duration=dur)
            tg_path.write_text(tg_text, encoding="utf-8")

            # Write TXT
            txt_path.write_text(transcript.strip() + "\n", encoding="utf-8")

            saved_count += 1
            if idx % 10 == 0 or idx == len(rows):
                logger.info(f"  [{idx}/{len(rows)}] Staged {utt_id} ({dur:.2f}s)")
        except Exception as err:
            logger.warning(f"  Failed to process {utt_id}: {err}")

    logger.info(f"[+] LibriSpeech staging complete: {saved_count} utterances in {libri_dir}")
    return saved_count


def stage_l2arctic(target_dir: Path, limit: int = 50, speaker: str = "RRBI") -> int:
    """Download and stage L2-ARCTIC accented speech utterances with TextGrids."""
    l2_dir = target_dir / "l2arctic"
    l2_dir.mkdir(parents=True, exist_ok=True)

    logger.info(f"Downloading L2-ARCTIC speaker archive {speaker}.zip via HuggingFace Hub...")
    zip_path = hf_hub_download(
        repo_id="chikingsley/l2-arctic-release-v5.0",
        filename=f"{speaker}.zip",
        repo_type="dataset",
    )

    logger.info(f"Extracting and resampling up to {limit} utterances from {zip_path}...")
    zf = zipfile.ZipFile(zip_path)

    # Find paired wav and textgrid files
    wav_files = sorted(
        [f for f in zf.namelist() if f.startswith(f"{speaker}/wav/") and f.endswith(".wav")]
    )
    saved_count = 0

    for wav_rel in wav_files[:limit]:
        stem = Path(wav_rel).stem
        tg_rel = f"{speaker}/textgrid/{stem}.TextGrid"
        if tg_rel not in zf.namelist():
            continue

        out_id = f"{speaker}_{stem}"
        wav_out = l2_dir / f"{out_id}.wav"
        tg_out = l2_dir / f"{out_id}.TextGrid"

        if wav_out.is_file() and tg_out.is_file():
            saved_count += 1
            continue

        try:
            # Read and resample WAV (from 44.1 kHz to 16 kHz)
            raw_wav = zf.read(wav_rel)
            with wave.open(io.BytesIO(raw_wav), "rb") as wf:
                in_sr = wf.getframerate()
                n_frames = wf.getnframes()
                frames = wf.readframes(n_frames)
                in_audio = np.frombuffer(frames, dtype=np.int16)

            tensor = torch.from_numpy(in_audio.astype(np.float32)).unsqueeze(0)
            if in_sr != 16000:
                resampled = F.resample(tensor, in_sr, 16000)
            else:
                resampled = tensor
            out_pcm = resampled.clamp(-32768, 32767).to(torch.int16).numpy().flatten()

            # Save 16 kHz WAV
            with wave.open(str(wav_out), "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(16000)
                wf.writeframes(out_pcm.tobytes())

            # Save TextGrid directly (timestamps are in seconds, invariant to sample rate)
            raw_tg = zf.read(tg_rel).decode("utf-8", errors="replace")
            tg_out.write_text(raw_tg, encoding="utf-8")

            saved_count += 1
            if saved_count % 10 == 0 or saved_count == limit:
                logger.info(f"  [{saved_count}/{limit}] Staged {out_id}")
        except Exception as err:
            logger.warning(f"  Failed to process {stem}: {err}")

    logger.info(f"[+] L2-ARCTIC staging complete: {saved_count} utterances in {l2_dir}")
    return saved_count


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Download and stage open-access LibriSpeech and L2-ARCTIC speech corpora."
    )
    parser.add_argument(
        "--corpus",
        choices=["librispeech", "l2arctic", "all"],
        default="all",
        help="Which open corpus to stage (default: all)",
    )
    parser.add_argument(
        "--librispeech-limit",
        type=int,
        default=50,
        help="Number of LibriSpeech test-clean utterances to stage (default: 50)",
    )
    parser.add_argument(
        "--l2arctic-limit",
        type=int,
        default=50,
        help="Number of L2-ARCTIC utterances to stage (default: 50)",
    )
    parser.add_argument(
        "--l2arctic-speaker",
        type=str,
        default="RRBI",
        help="L2-ARCTIC speaker archive to extract (default: RRBI - Russian Male)",
    )
    parser.add_argument(
        "--target-dir",
        type=Path,
        default=Path("data/corpora"),
        help="Base directory to place corpora (default: data/corpora)",
    )
    args = parser.parse_args()

    target_dir = args.target_dir.resolve()
    target_dir.mkdir(parents=True, exist_ok=True)

    logger.info("============================================================")
    logger.info("Open Speech Corpora Staging Utility")
    logger.info(f"Target Directory: {target_dir}")
    logger.info(f"Corpus Selection: {args.corpus}")
    logger.info("============================================================")

    if args.corpus in ("librispeech", "all"):
        stage_librispeech(target_dir, limit=args.librispeech_limit)

    if args.corpus in ("l2arctic", "all"):
        stage_l2arctic(target_dir, limit=args.l2arctic_limit, speaker=args.l2arctic_speaker)

    logger.info("============================================================")
    logger.info("Corpora staging finished successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
