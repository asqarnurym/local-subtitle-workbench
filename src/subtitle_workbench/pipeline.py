"""Offline alignment, audit manifest, and output publication."""

import hashlib
import json
import platform
import time
from dataclasses import asdict
from math import ceil
from pathlib import Path
from typing import Any, Literal

import numpy as np

from . import __version__
from .aligner import ForcedAligner
from .asr import WhisperTranscriber, extract_vad_silences
from .audio import extract_features, get_duration, load_wav, validate_wav
from .chunker import ChunkConfig, partition_into_chunks, reconcile_chunk_alignments
from .dtw import banded_dtw
from .export import (
    export_jsonld,
    export_karaoke_vtt,
    export_raw_alignment,
    generate_manifest,
    jsonld,
    webvtt,
)
from .models import ASRSegment, Config, Cue, WordToken, validate_cues
from .provenance import code_provenance, sha256
from .text_norm import normalize_transcript

__all__ = [
    "align",
    "code_provenance",
    "run_speech_pipeline",
    "sha256",
]


def align(
    reference_path: Path,
    target_path: Path,
    cues_path: Path,
    output_dir: Path,
    config: Config | None = None,
) -> dict:
    config = config or Config()
    started = time.perf_counter()
    paths = [Path(reference_path), Path(target_path), Path(cues_path)]
    output_dir = Path(output_dir)
    outputs = [
        output_dir / name
        for name in ("subtitles.vtt", "timeline.jsonld", "alignment-path.json", "manifest.json")
    ]
    if any(path.exists() for path in outputs):
        raise ValueError("output files already exist; choose a new output directory")
    if any(output.resolve() == source.resolve() for output in outputs for source in paths):
        raise ValueError("output may not overwrite an input")
    if paths[2].stat().st_size > 2_000_000:
        raise ValueError("cue JSON exceeds 2 MB limit")
    reference, target = (load_wav(path, config) for path in paths[:2])
    with paths[2].open(encoding="utf-8") as stream:
        try:
            cue_data = json.load(stream)
        except RecursionError as error:
            raise ValueError("cue JSON nesting exceeds parser limit") from error
        cues = validate_cues(cue_data, reference.duration)
    reference_times, reference_features = extract_features(reference, config)
    target_times, target_features = extract_features(target, config)
    result = banded_dtw(
        reference_features,
        target_features,
        ceil(config.band_seconds / config.hop_seconds),
        config.max_cells,
    )
    mapped = np.empty(len(reference_times))
    _, starts = np.unique(result.path[:, 0], return_index=True)
    ends = np.append(starts[1:], len(result.path))
    for index, (start, end) in enumerate(zip(starts, ends, strict=True)):
        mapped[index] = np.median(target_times[result.path[start:end, 1]])
    mapped = np.maximum.accumulate(mapped)
    # Audio endpoints anchor the full track; interior cues interpolate the observed path.
    knots = np.append(reference_times, reference.duration)
    values = np.append(mapped, target.duration)
    values[0] = 0.0
    aligned = [
        Cue(
            cue.id,
            float(np.interp(cue.start, knots, values)),
            float(np.interp(cue.end, knots, values)),
            cue.text,
        )
        for cue in cues
    ]
    validate_cues({"language": "en", "cues": [asdict(cue) for cue in aligned]}, target.duration)
    vtt = webvtt(aligned)
    target_hash = sha256(paths[1])
    timeline = jsonld(aligned, target.duration, f"urn:local-subtitle-workbench:video:{target_hash}")
    elapsed = time.perf_counter() - started
    path_data = {
        "columns": ["reference_frame", "target_frame"],
        "frame_hop_seconds": config.hop_seconds,
        "frame_time_origin_seconds": 0.0,
        "path": result.path.tolist(),
    }
    payloads = [
        vtt,
        json.dumps(timeline, ensure_ascii=False, indent=2) + "\n",
        json.dumps(path_data, indent=2) + "\n",
    ]
    manifest = {
        "schema_version": 1,
        "tool": {"name": "local-subtitle-workbench", "version": __version__},
        "code": code_provenance(),
        "inputs": {
            key: {"filename": path.name, "sha256": sha256(path)}
            for key, path in zip(
                ("reference_audio", "target_audio", "reference_cues"), paths, strict=True
            )
        },
        "config": asdict(config),
        "outputs": {
            path.name: {"sha256": hashlib.sha256(payload.encode("utf-8")).hexdigest()}
            for path, payload in zip(outputs[:3], payloads, strict=True)
        },
        "runtime": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "platform": platform.platform(),
        },
        "metrics": {
            "reference_duration_seconds": reference.duration,
            "target_duration_seconds": target.duration,
            "reference_frames": len(reference_times),
            "target_frames": len(target_times),
            "evaluated_cells": result.cells,
            "path_length": len(result.path),
            "mean_path_cost": result.cost / len(result.path),
            "cue_count": len(aligned),
            "alignment_elapsed_seconds": elapsed,
            "alignment_rtf": elapsed / target.duration,
        },
        "limitations": [
            "Reference cues must already be correctly timed and labelled English.",
            "Audio-to-audio timing transfer does not recognize or force-align text.",
            "Path cost is not speech recognition accuracy or timing error.",
        ],
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    payloads.append(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    for path, payload in zip(outputs, payloads, strict=True):
        with path.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(payload)
    return manifest


def run_speech_pipeline(
    audio_path: Path | str,
    output_dir: Path | str,
    transcript: str | Path | None = None,
    engine: Literal["auto", "mfa", "ctc"] = "auto",
    vad_silence_min_sec: float = 0.4,
    max_chunk_sec: float = 30.0,
    chunk_padding_sec: float = 0.5,
    fallback_to_ctc: bool = True,
    transcriber: Any | None = None,
    aligner: Any | None = None,
) -> dict:
    """Execute end-to-end speech alignment pipeline across 7 stages."""
    if engine not in ("auto", "mfa", "ctc"):
        raise ValueError(f"unsupported engine: {engine!r}; choose from 'auto', 'mfa', 'ctc'")
    if vad_silence_min_sec <= 0.0:
        raise ValueError("vad_silence_min_sec must be positive")
    if max_chunk_sec <= 0.0:
        raise ValueError("max_chunk_sec must be positive")
    if chunk_padding_sec < 0.0:
        raise ValueError("chunk_padding_sec must be nonnegative")

    audio_path = Path(audio_path)
    output_dir = Path(output_dir)

    # Stage 1: Audio Validation & Target Pre-flight
    validate_wav(audio_path)
    audio_duration = get_duration(audio_path)

    outputs = [
        output_dir / name
        for name in (
            "subtitles.vtt",
            "timeline.jsonld",
            "alignment_raw.json",
            "manifest.json",
        )
    ]
    if any(p.exists() for p in outputs):
        raise ValueError("output files already exist; choose a new output directory")

    resolved_audio = audio_path.resolve()
    if output_dir.resolve() == resolved_audio or any(
        p.resolve() == resolved_audio for p in outputs
    ):
        raise ValueError("output may not overwrite an input")

    transcript_file_path: Path | None = None
    if isinstance(transcript, Path):
        transcript_file_path = transcript
    elif isinstance(transcript, str) and (
        Path(transcript).is_file()
        or (
            "\n" not in transcript
            and (
                transcript.endswith((".txt", ".vtt", ".srt", ".json", ".transcript"))
                or ("/" in transcript or "\\" in transcript)
            )
        )
    ):
        transcript_file_path = Path(transcript)

    if transcript_file_path is not None:
        if not transcript_file_path.is_file():
            raise FileNotFoundError(f"Transcript file not found: {transcript_file_path}")
        resolved_transcript = transcript_file_path.resolve()
        if output_dir.resolve() == resolved_transcript or any(
            p.resolve() == resolved_transcript for p in outputs
        ):
            raise ValueError("output may not overwrite an input")

    # Stage 2: VAD & ASR / Transcript Handling
    started = time.perf_counter()
    silence_min_ms = int(round(vad_silence_min_sec * 1000))

    if transcript is None:
        transcriber_inst = (
            transcriber
            if transcriber is not None
            else WhisperTranscriber(min_silence_duration_ms=silence_min_ms)
        )
        try:
            try:
                silences = extract_vad_silences(audio_path, min_silence_duration_ms=silence_min_ms)
            except Exception:
                silences = []
            segments = transcriber_inst.transcribe(audio_path)
        finally:
            if hasattr(transcriber_inst, "unload") and callable(transcriber_inst.unload):
                transcriber_inst.unload()
    else:
        if transcript_file_path is not None:
            raw_text = transcript_file_path.read_text(encoding="utf-8")
        else:
            raw_text = str(transcript)

        text = raw_text.strip()
        if not text:
            raise ValueError("transcript cannot be empty")

        try:
            silences = extract_vad_silences(audio_path, min_silence_duration_ms=silence_min_ms)
        except Exception:
            silences = []

    # Stage 3: Normalization & WordToken Seeding
    if transcript is not None:
        spans = normalize_transcript(text)
        if not spans:
            raise ValueError("transcript contains no valid words after normalization")

        n_spans = len(spans)
        step = audio_duration / n_spans
        initial_words = [
            WordToken(
                id=f"w_{i}",
                text=span.token,
                normalized=span.normalized,
                start=i * step,
                end=(i + 1) * step,
                confidence=0.9,
                char_start=span.char_start,
                char_end=span.char_end,
            )
            for i, span in enumerate(spans)
        ]
        segments = [
            ASRSegment(
                id="seg_0",
                start=0.0,
                end=audio_duration,
                text=text,
                words=initial_words,
            )
        ]
    else:
        if not segments:
            raise ValueError("no speech segments detected in audio")

    # Stage 4: Macro-chunking
    chunk_cfg = ChunkConfig(
        max_chunk_duration=max_chunk_sec,
        min_silence_duration=vad_silence_min_sec,
        overlap_padding=chunk_padding_sec,
    )
    chunks = partition_into_chunks(
        segments=segments,
        silences=silences,
        total_duration=audio_duration,
        config=chunk_cfg,
    )

    # Stage 5 & 6: Forced Alignment & Global Monotonic Reconciliation
    if aligner is None:
        aligner_inst = ForcedAligner()
    else:
        aligner_inst = aligner

    aligned_result = aligner_inst.align_chunks(
        chunks=chunks,
        audio_path=audio_path,
        engine=engine,
        fallback_to_ctc=fallback_to_ctc,
    )

    if aligned_result and isinstance(aligned_result[0], list):
        reconciled_words = reconcile_chunk_alignments(
            chunks, aligned_result, padded_coordinates=True
        )
    else:
        reconciled_words = aligned_result

    # Stage 7: Artifact Export & Cryptographic Manifest
    output_dir.mkdir(parents=True, exist_ok=True)

    vtt_text = export_karaoke_vtt(reconciled_words)
    (output_dir / "subtitles.vtt").write_text(vtt_text, encoding="utf-8")

    audio_hash = sha256(audio_path)
    media_urn = f"urn:local-subtitle-workbench:speech:{audio_hash}"
    jsonld_data = export_jsonld(
        reconciled_words, audio_duration=audio_duration, media_urn=media_urn
    )
    (output_dir / "timeline.jsonld").write_text(
        json.dumps(jsonld_data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    raw_alignment_data = export_raw_alignment(
        reconciled_words, audio_path=audio_path, alignment_method=engine
    )
    (output_dir / "alignment_raw.json").write_text(
        json.dumps(raw_alignment_data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    elapsed_sec = time.perf_counter() - started
    rtf = elapsed_sec / audio_duration if audio_duration > 0.0 else 0.0
    mean_conf = (
        sum(w.confidence for w in reconciled_words) / len(reconciled_words)
        if reconciled_words
        else 0.0
    )
    metrics = {
        "audio_duration_seconds": round(audio_duration, 4),
        "word_count": len(reconciled_words),
        "chunk_count": len(chunks),
        "mean_word_confidence": round(mean_conf, 4),
        "pipeline_elapsed_seconds": round(elapsed_sec, 4),
        "pipeline_rtf": round(rtf, 4),
    }

    manifest = generate_manifest(
        input_audio_path=audio_path,
        output_dir=output_dir,
        words=reconciled_words,
        metrics=metrics,
        config={
            "engine": engine,
            "vad_silence_min_sec": vad_silence_min_sec,
            "max_chunk_sec": max_chunk_sec,
            "chunk_padding_sec": chunk_padding_sec,
            "fallback_to_ctc": fallback_to_ctc,
        },
    )

    return manifest
