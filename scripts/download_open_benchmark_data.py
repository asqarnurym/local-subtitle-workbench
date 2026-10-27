"""Download and stage open-access SILVER-reference corpora for relative comparisons.

IMPORTANT: the word/phone boundaries of both corpora were produced by forced alignment
(Montreal Forced Aligner), not by human annotators. Results on them measure agreement
with MFA and are reported as "silver" references; they must not be presented as
accuracy and must not be used to compare an MFA-based method against others.

1. LibriSpeech test-clean (native read English; MFA alignments, gilkeyio/librispeech-alignments),
   sampled evenly across all 40 speakers.
2. L2-ARCTIC (non-native English, 24 speakers / 6 L1s; automatic TextGrids).

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


def stage_librispeech(target_dir: Path, per_speaker: int = 5) -> int:
    """Stage up to ``per_speaker`` test-clean utterances for every speaker."""
    libri_dir = target_dir / "librispeech"
    libri_dir.mkdir(parents=True, exist_ok=True)
    base = (
        "https://datasets-server.huggingface.co/rows?"
        "dataset=gilkeyio/librispeech-alignments&config=default&split=test_clean"
    )
    selected: dict[str, list[dict[str, Any]]] = {}
    offset, page = 0, 100
    client = httpx.Client(timeout=60.0)
    while True:
        resp = client.get(f"{base}&offset={offset}&limit={page}")
        if resp.status_code != 200:
            raise RuntimeError(f"LibriSpeech rows request failed: HTTP {resp.status_code}")
        rows = resp.json().get("rows", [])
        if not rows:
            break
        for r in rows:
            row = r["row"]
            spk = str(row["id"]).split("-")[0]
            bucket = selected.setdefault(spk, [])
            if len(bucket) < per_speaker:
                bucket.append(row)
        offset += len(rows)
        if len(rows) < page:
            break
    logger.info(
        f"Selected {sum(map(len, selected.values()))} utterances from {len(selected)} speakers"
    )

    saved = 0
    for rows in selected.values():
        for row in rows:
            utt_id = row["id"]
            wav_path = libri_dir / f"{utt_id}.wav"
            tg_path = libri_dir / f"{utt_id}.TextGrid"
            if wav_path.is_file() and tg_path.is_file():
                saved += 1
                continue
            audio_src = (row.get("audio") or [{}])[0].get("src")
            if not audio_src:
                raise RuntimeError(f"No audio URL for {utt_id}")
            pcm_arr, dur = decode_flac_to_pcm16_mono(client.get(audio_src).content, 16000)
            with wave.open(str(wav_path), "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(16000)
                wf.writeframes(pcm_arr.tobytes())
            tg_path.write_text(
                format_textgrid(row.get("words", []), row.get("phonemes", []), dur),
                encoding="utf-8",
            )
            (libri_dir / f"{utt_id}.txt").write_text(
                str(row.get("transcript", "")).strip() + "\n", encoding="utf-8"
            )
            saved += 1
    logger.info(f"[+] LibriSpeech staging complete: {saved} utterances in {libri_dir}")
    return saved


L2ARCTIC_SPEAKERS = [
    "ABA",
    "SKA",
    "YBAA",
    "ZHAA",  # Arabic
    "BWC",
    "LXC",
    "NCC",
    "TXHC",  # Mandarin
    "ASI",
    "RRBI",
    "SVBI",
    "TNI",  # Hindi
    "HJK",
    "HKK",
    "YDCK",
    "YKWK",  # Korean
    "EBVS",
    "ERMS",
    "MBMPS",
    "NJS",  # Spanish
    "HQTV",
    "PNV",
    "THV",
    "TLV",  # Vietnamese
]


def stage_l2arctic(target_dir: Path, limit: int = 10, speaker: str = "RRBI") -> int:
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
            raise RuntimeError(f"Failed to process L2-ARCTIC {speaker}/{stem}: {err}") from err

    logger.info(f"[+] L2-ARCTIC staging complete: {saved_count} utterances in {l2_dir}")
    return saved_count


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Stage SILVER-reference corpora (LibriSpeech test-clean, L2-ARCTIC)."
    )
    parser.add_argument("--corpus", choices=["librispeech", "l2arctic", "all"], default="all")
    parser.add_argument(
        "--librispeech-per-speaker",
        type=int,
        default=5,
        help="Utterances per test-clean speaker (40 speakers; default: 5 -> 200 utterances)",
    )
    parser.add_argument(
        "--l2arctic-per-speaker",
        type=int,
        default=10,
        help="Utterances per L2-ARCTIC speaker (default: 10)",
    )
    parser.add_argument(
        "--l2arctic-speakers",
        type=str,
        default="all",
        help="Comma-separated L2-ARCTIC speaker codes or 'all' (24 speakers, 6 L1s)",
    )
    parser.add_argument("--target-dir", type=Path, default=Path("data/corpora"))
    args = parser.parse_args()

    target_dir = args.target_dir.resolve()
    target_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"Target directory: {target_dir}; corpus: {args.corpus}")

    if args.corpus in ("librispeech", "all"):
        stage_librispeech(target_dir, per_speaker=args.librispeech_per_speaker)

    if args.corpus in ("l2arctic", "all"):
        speakers = (
            L2ARCTIC_SPEAKERS
            if args.l2arctic_speakers == "all"
            else [s.strip().upper() for s in args.l2arctic_speakers.split(",") if s.strip()]
        )
        for spk in speakers:
            stage_l2arctic(target_dir, limit=args.l2arctic_per_speaker, speaker=spk)

    logger.info("Silver corpora staging finished.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
