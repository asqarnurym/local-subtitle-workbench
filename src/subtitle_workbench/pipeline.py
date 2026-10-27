"""Offline alignment, audit manifest, and output publication."""

import hashlib
import json
import platform
from dataclasses import asdict, dataclass
from math import ceil
from pathlib import Path
from typing import Any, Literal

import numpy as np

from . import __version__
from .aligner import SUPPORTED_ENGINES, ForcedAligner
from .anchoring import anchor_transcript
from .asr import WhisperTranscriber, extract_vad_silences
from .audio import extract_features, get_duration, load_wav, validate_wav
from .chunker import ChunkConfig, partition_into_chunks
from .dtw import banded_dtw
from .export import (
    export_jsonld,
    export_karaoke_vtt,
    export_raw_alignment,
    generate_manifest,
    jsonld,
    webvtt,
)
from .models import ASRSegment, AudioChunk, Config, Cue, WordToken, validate_cues
from .provenance import code_provenance, sha256
from .text_norm import normalize_transcript

__all__ = [
    "AlignmentJob",
    "align",
    "prepare_alignment_job",
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


@dataclass
class AlignmentJob:
    """Everything prepared for one recording before forced alignment.

    Produced by :func:`prepare_alignment_job` (VAD, Whisper ASR, transcript anchoring,
    chunking). Many jobs can then be aligned together in one MFA batch.
    """

    audio_path: Path
    duration: float
    speaker: str
    scenario: str  # "A" (transcript known) or "B" (ASR transcript)
    hypothesis_words: list[WordToken]
    seeded_words: list[WordToken]
    chunks: list[AudioChunk]
    silences: list[tuple[float, float]]
    anchoring: dict[str, Any] | None = None


def _validate_timing(vad_silence_min_sec: float, max_chunk_sec: float, chunk_padding_sec: float):
    if vad_silence_min_sec <= 0.0:
        raise ValueError("vad_silence_min_sec must be positive")
    if max_chunk_sec <= 0.0:
        raise ValueError("max_chunk_sec must be positive")
    if chunk_padding_sec < 0.0:
        raise ValueError("chunk_padding_sec must be nonnegative")


SEED_SEGMENT_WORDS = 40


def _segments_from_words(words: list[WordToken]) -> list[ASRSegment]:
    """Group anchored transcript words into bounded pseudo-segments.

    Long lecture transcripts exceed the per-segment text limit, so the seeded words are
    grouped into consecutive segments of at most SEED_SEGMENT_WORDS words.
    """
    segments: list[ASRSegment] = []
    for idx in range(0, len(words), SEED_SEGMENT_WORDS):
        group = words[idx : idx + SEED_SEGMENT_WORDS]
        segments.append(
            ASRSegment(
                id=f"seg_{idx // SEED_SEGMENT_WORDS}",
                start=group[0].start,
                end=max(w.end for w in group),
                text=" ".join(w.text for w in group),
                words=group,
            )
        )
    return segments


def prepare_alignment_job(
    audio_path: Path | str,
    transcriber: Any,
    transcript_text: str | None = None,
    speaker: str = "speaker",
    vad_silence_min_sec: float = 0.4,
    max_chunk_sec: float = 30.0,
    chunk_padding_sec: float = 0.5,
    vad_backend: Any | None = None,
) -> AlignmentJob:
    """Run the pre-alignment stages of the reference pipeline for one recording.

    Stages (none is skipped, none falls back silently):
      1. Silero-VAD pause detection.
      2. Whisper ASR with word timestamps (always run; in scenario A it provides anchors).
      3. Scenario A: banded sequence alignment of the known transcript to the ASR
         hypothesis (coarse word-level anchoring). Scenario B: ASR words are used.
      4. Pause-anchored chunking into bounded windows with overlap padding.

    The transcriber is not unloaded here so that one model instance can serve many jobs.
    """
    _validate_timing(vad_silence_min_sec, max_chunk_sec, chunk_padding_sec)
    audio_path = Path(audio_path)
    validate_wav(audio_path)
    duration = get_duration(audio_path)

    text: str | None = None
    if transcript_text is not None:
        text = str(transcript_text).strip()
        if not text:
            raise ValueError("transcript cannot be empty")

    silence_min_ms = int(round(vad_silence_min_sec * 1000))
    silences = extract_vad_silences(
        audio_path, min_silence_duration_ms=silence_min_ms, vad_backend=vad_backend
    )
    segments = transcriber.transcribe(audio_path)
    hypothesis_words = [w for seg in segments for w in seg.words]

    anchoring: dict[str, Any] | None = None
    if text is None:
        if not segments:
            raise ValueError("no speech segments detected in audio")
        seed_segments = segments
        scenario = "B"
    else:
        anchored = anchor_transcript(text, hypothesis_words, duration)
        anchoring = anchored.to_dict()
        seed_segments = _segments_from_words(anchored.words)
        scenario = "A"

    chunks = partition_into_chunks(
        segments=seed_segments,
        silences=silences,
        total_duration=duration,
        config=ChunkConfig(
            max_chunk_duration=max_chunk_sec,
            min_silence_duration=vad_silence_min_sec,
            overlap_padding=chunk_padding_sec,
        ),
    )
    return AlignmentJob(
        audio_path=audio_path,
        duration=duration,
        speaker=speaker,
        scenario=scenario,
        hypothesis_words=hypothesis_words,
        seeded_words=[w for seg in seed_segments for w in seg.words],
        chunks=chunks,
        silences=silences,
        anchoring=anchoring,
    )


def run_speech_pipeline(
    audio_path: Path | str,
    output_dir: Path | str,
    transcript_text: str | None = None,
    transcript_path: Path | str | None = None,
    engine: Literal["mfa", "ctc"] = "mfa",
    vad_silence_min_sec: float = 0.4,
    max_chunk_sec: float = 30.0,
    chunk_padding_sec: float = 0.5,
    transcriber: Any | None = None,
    aligner: Any | None = None,
    vad_backend: Any | None = None,
    speaker: str = "speaker",
) -> dict:
    """Execute the complete reference speech alignment pipeline for one recording.

    Scenario A: ``transcript_text`` or ``transcript_path`` is given (known lecture text).
    Scenario B: neither is given; the Whisper transcript is aligned.
    """
    if engine not in SUPPORTED_ENGINES:
        raise ValueError(f"unsupported engine: {engine!r}; choose from 'mfa', 'ctc'")
    _validate_timing(vad_silence_min_sec, max_chunk_sec, chunk_padding_sec)
    if transcript_text is not None and transcript_path is not None:
        raise ValueError("pass either transcript_text or transcript_path, not both")

    audio_path = Path(audio_path)
    output_dir = Path(output_dir)

    # Stage 1: Audio validation & output pre-flight
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

    if transcript_path is not None:
        transcript_file = Path(transcript_path)
        if not transcript_file.is_file():
            raise FileNotFoundError(f"Transcript file not found: {transcript_file}")
        resolved_transcript = transcript_file.resolve()
        if output_dir.resolve() == resolved_transcript or any(
            p.resolve() == resolved_transcript for p in outputs
        ):
            raise ValueError("output may not overwrite an input")
        transcript_text = transcript_file.read_text(encoding="utf-8")

    if transcript_text is not None:
        if not transcript_text.strip():
            raise ValueError("transcript cannot be empty")
        if not normalize_transcript(transcript_text):
            raise ValueError("transcript contains no valid words after normalization")

    # Stages 2-4: VAD, ASR, anchoring, chunking
    silence_min_ms = int(round(vad_silence_min_sec * 1000))
    transcriber_inst = (
        transcriber
        if transcriber is not None
        else WhisperTranscriber(min_silence_duration_ms=silence_min_ms)
    )
    try:
        job = prepare_alignment_job(
            audio_path,
            transcriber=transcriber_inst,
            transcript_text=transcript_text,
            speaker=speaker,
            vad_silence_min_sec=vad_silence_min_sec,
            max_chunk_sec=max_chunk_sec,
            chunk_padding_sec=chunk_padding_sec,
            vad_backend=vad_backend,
        )
    finally:
        # Free GPU memory before the aligner runs
        if hasattr(transcriber_inst, "unload") and callable(transcriber_inst.unload):
            transcriber_inst.unload()

    # Stages 5-6: forced alignment & global monotonic reconciliation
    aligner_inst = aligner if aligner is not None else ForcedAligner()
    reconciled_words = aligner_inst.align_chunks(
        chunks=job.chunks,
        audio_path=audio_path,
        engine=engine,
    )

    # Stage 7: artifact export & manifest
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

    mean_conf = (
        sum(w.confidence for w in reconciled_words) / len(reconciled_words)
        if reconciled_words
        else 0.0
    )
    metrics: dict[str, Any] = {
        "audio_duration_seconds": round(audio_duration, 4),
        "word_count": len(reconciled_words),
        "chunk_count": len(job.chunks),
        "mean_word_confidence": round(mean_conf, 4),
        "scenario": job.scenario,
    }
    if job.anchoring is not None:
        metrics["anchoring"] = job.anchoring

    config: dict[str, Any] = {
        "engine": engine,
        "scenario": job.scenario,
        "vad_silence_min_sec": vad_silence_min_sec,
        "max_chunk_sec": max_chunk_sec,
        "chunk_padding_sec": chunk_padding_sec,
    }
    describe = getattr(aligner_inst, "describe", None)
    if callable(describe):
        described = describe(engine)
        if isinstance(described, dict):
            config["aligner"] = described
    asr_info = {
        key: getattr(transcriber_inst, attr, None)
        for key, attr in (
            ("model", "model_size_or_path"),
            ("device", "device"),
            ("compute_type", "compute_type"),
        )
    }
    if all(isinstance(v, str) for v in asr_info.values()):
        config["asr"] = asr_info

    manifest = generate_manifest(
        input_audio_path=audio_path,
        output_dir=output_dir,
        words=reconciled_words,
        metrics=metrics,
        config=config,
    )

    return manifest
