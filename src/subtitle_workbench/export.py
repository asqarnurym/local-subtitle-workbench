"""WebVTT, schema.org JSON-LD, raw alignment, and audit manifest serialization."""

import html
import json
import platform
from dataclasses import asdict, is_dataclass
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from urllib.parse import quote

import numpy as np

from . import __version__
from .models import Cue, WordToken, finite_number
from .provenance import code_provenance, sha256


def milliseconds(seconds: float) -> int:
    value = finite_number(seconds, "timestamp")
    if value < 0:
        raise ValueError("timestamp must be nonnegative")
    return int((Decimal(str(value)) * 1000).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def format_vtt_timestamp(seconds: float) -> str:
    """Format seconds into HH:MM:SS.mmm WebVTT timestamp string."""
    total = milliseconds(seconds)
    hours, remainder = divmod(total, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    sec, ms = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{sec:02d}.{ms:03d}"


timestamp = format_vtt_timestamp


def webvtt(cues: list[Cue]) -> str:
    blocks = ["WEBVTT"]
    for cue in cues:
        if milliseconds(cue.end) <= milliseconds(cue.start):
            raise ValueError("cue collapses after millisecond rounding")
        timestamp_line = f"{format_vtt_timestamp(cue.start)} --> {format_vtt_timestamp(cue.end)}"
        payload = html.escape(cue.text, quote=False)
        blocks.append(f"{cue.id}\n{timestamp_line}\n{payload}")
    return "\n\n".join(blocks) + "\n"


def export_karaoke_vtt(
    words: list[WordToken],
    max_line_words: int = 8,
    max_line_chars: int = 42,
    max_pause_break: float = 1.0,
) -> str:
    """Generate W3C WebVTT document with inline <c.word><timestamp>text</c> tags."""
    if not isinstance(words, list):
        raise ValueError("words must be a list")
    if not all(isinstance(w, WordToken) for w in words):
        raise ValueError("all elements in words must be WordToken instances")
    if max_line_words < 1:
        raise ValueError("max_line_words must be at least 1")
    if max_line_chars < 1:
        raise ValueError("max_line_chars must be at least 1")
    if max_pause_break <= 0:
        raise ValueError("max_pause_break must be positive")

    if not words:
        return "WEBVTT\n\n"

    for i in range(len(words) - 1):
        if words[i + 1].start < words[i].start:
            raise ValueError("words must have monotonic timestamps")

    cue_groups: list[list[WordToken]] = []
    current_cue: list[WordToken] = []

    for w in words:
        if not current_cue:
            current_cue.append(w)
            continue

        pause = w.start - current_cue[-1].end
        word_count_exceeded = len(current_cue) >= max_line_words
        prospective_text = " ".join(t.text for t in current_cue + [w])
        char_count_exceeded = len(prospective_text) > max_line_chars
        pause_exceeded = pause >= (max_pause_break - 1e-6)

        if word_count_exceeded or char_count_exceeded or pause_exceeded:
            cue_groups.append(current_cue)
            current_cue = [w]
        else:
            current_cue.append(w)

    if current_cue:
        cue_groups.append(current_cue)

    blocks = ["WEBVTT"]
    for idx, group in enumerate(cue_groups, start=1):
        start_sec = group[0].start
        end_sec = group[-1].end
        if milliseconds(end_sec) <= milliseconds(start_sec):
            raise ValueError(f"cue {idx} collapses after millisecond rounding")
        cue_start_vtt = format_vtt_timestamp(start_sec)
        cue_end_vtt = format_vtt_timestamp(end_sec)

        payload_parts = [
            f"<c.word><{format_vtt_timestamp(t.start)}>{html.escape(t.text, quote=False)}</c>"
            for t in group
        ]
        payload = " ".join(payload_parts)
        blocks.append(f"{idx}\n{cue_start_vtt} --> {cue_end_vtt}\n{payload}")

    return "\n\n".join(blocks) + "\n"


def jsonld(cues: list[Cue], duration: float, media_name: str) -> dict:
    """Emit semantic cue metadata; the context URI is not dereferenced."""
    media = quote(media_name, safe=":/-_.")
    return {
        "@context": "https://schema.org",
        "@type": "VideoObject",
        "@id": media,
        "name": "English subtitle alignment timeline",
        "inLanguage": "en",
        "duration": f"PT{duration:.3f}S",
        "description": "Cue timings transferred from a checked reference audio track.",
        "hasPart": [
            {
                "@type": "Clip",
                "@id": f"{media}#cue-{quote(cue.id, safe='-_')}",
                "name": cue.text,
                "startOffset": round(cue.start, 6),
                "endOffset": round(cue.end, 6),
                "inLanguage": "en",
            }
            for cue in cues
        ],
    }


def export_jsonld(
    words: list[WordToken],
    audio_duration: float,
    media_urn: str,
    language: str = "en",
) -> dict:
    """Generate semantic schema.org JSON-LD VideoObject with Clip parts."""
    duration_val = finite_number(audio_duration, "audio_duration")
    if duration_val < 0:
        raise ValueError("audio_duration must be nonnegative")
    if not isinstance(media_urn, str) or not media_urn:
        raise ValueError("media_urn must be a non-empty string")
    if not isinstance(language, str) or not language:
        raise ValueError("language must be a non-empty string")
    if not isinstance(words, list):
        raise ValueError("words must be a list")
    if not all(isinstance(w, WordToken) for w in words):
        raise ValueError("all elements in words must be WordToken instances")

    media = quote(media_urn, safe=":/-_.")
    has_part = [
        {
            "@type": "Clip",
            "@id": f"{media}#word-{quote(w.id, safe='-_')}",
            "name": w.text,
            "startOffset": round(w.start, 6),
            "endOffset": round(w.end, 6),
            "inLanguage": language,
        }
        for w in words
    ]

    return {
        "@context": "https://schema.org",
        "@type": "VideoObject",
        "@id": media,
        "name": "Speech alignment timeline",
        "inLanguage": language,
        "duration": f"PT{duration_val:.3f}S",
        "description": (
            "Word-level speech alignment timeline compliant with WCAG 2.1 Media "
            "Accessibility Guidelines."
        ),
        "hasPart": has_part,
    }


def export_raw_alignment(
    words: list[WordToken],
    audio_path: Path | str,
    alignment_method: str,
    metrics: dict | None = None,
) -> dict:
    """Export hierarchical alignment structure and summary metrics."""
    if not isinstance(words, list):
        raise ValueError("words must be a list")
    if not all(isinstance(w, WordToken) for w in words):
        raise ValueError("all elements in words must be WordToken instances")
    if not isinstance(audio_path, (str, Path)):
        raise ValueError("audio_path must be a str or Path")
    if not isinstance(alignment_method, str) or not alignment_method:
        raise ValueError("alignment_method must be a non-empty string")
    if metrics is not None and not isinstance(metrics, dict):
        raise ValueError("metrics must be a dict or None")

    audio_p = Path(audio_path)
    total_words = len(words)
    all_phonemes = [p for w in words for p in w.phonemes]
    total_phonemes = len(all_phonemes)

    mean_word_confidence = (
        sum(w.confidence for w in words) / total_words if total_words > 0 else 0.0
    )
    mean_phoneme_confidence = (
        sum(p.confidence for p in all_phonemes) / total_phonemes if total_phonemes > 0 else 0.0
    )
    speech_duration_seconds = sum(w.end - w.start for w in words)
    pause_duration_seconds = (
        sum(max(0.0, words[i + 1].start - words[i].end) for i in range(total_words - 1))
        if total_words > 1
        else 0.0
    )
    speech_to_pause_ratio = (
        speech_duration_seconds / pause_duration_seconds if pause_duration_seconds > 0.0 else 0.0
    )

    summary = {
        "total_words": total_words,
        "total_phonemes": total_phonemes,
        "mean_word_confidence": round(mean_word_confidence, 4),
        "mean_phoneme_confidence": round(mean_phoneme_confidence, 4),
        "speech_duration_seconds": round(speech_duration_seconds, 4),
        "pause_duration_seconds": round(pause_duration_seconds, 4),
        "speech_to_pause_ratio": round(speech_to_pause_ratio, 4),
    }
    if metrics:
        summary.update(metrics)

    words_data = [
        {
            "id": w.id,
            "text": w.text,
            "normalized": w.normalized,
            "start": round(w.start, 4),
            "end": round(w.end, 4),
            "confidence": round(w.confidence, 4),
            "char_start": w.char_start,
            "char_end": w.char_end,
            "phonemes": [
                {
                    "phoneme": p.phoneme,
                    "start": round(p.start, 4),
                    "end": round(p.end, 4),
                    "confidence": round(p.confidence, 4),
                }
                for p in w.phonemes
            ],
        }
        for w in words
    ]

    return {
        "schema_version": 1,
        "audio_file": audio_p.name,
        "audio_path": str(audio_path),
        "alignment_method": alignment_method,
        "summary": summary,
        "words": words_data,
    }


def generate_manifest(
    input_audio_path: Path,
    output_dir: Path,
    words: list[WordToken],
    metrics: dict,
    config: dict | None = None,
) -> dict:
    """Generate cryptographic provenance audit log manifest.json."""
    input_audio_path = Path(input_audio_path)
    output_dir = Path(output_dir)

    if not input_audio_path.is_file():
        raise FileNotFoundError(f"Input audio file not found: {input_audio_path}")

    required_outputs = ["subtitles.vtt", "timeline.jsonld", "alignment_raw.json"]
    output_hashes = {}
    for name in required_outputs:
        out_file = output_dir / name
        if not out_file.is_file():
            raise FileNotFoundError(f"Expected generated output file not found: {out_file}")
        output_hashes[name] = {"sha256": sha256(out_file)}

    if not isinstance(words, list):
        raise ValueError("words must be a list")
    if not all(isinstance(w, WordToken) for w in words):
        raise ValueError("all elements in words must be WordToken instances")
    if not isinstance(metrics, dict):
        raise ValueError("metrics must be a dict")

    if config is not None:
        config_dict = asdict(config) if is_dataclass(config) else dict(config)
    else:
        config_dict = {}

    manifest = {
        "schema_version": 1,
        "tool": {
            "name": "local-subtitle-workbench",
            "version": __version__,
        },
        "code": code_provenance(),
        "inputs": {
            "audio": {
                "filename": input_audio_path.name,
                "sha256": sha256(input_audio_path),
            }
        },
        "config": config_dict,
        "outputs": output_hashes,
        "runtime": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "platform": platform.platform(),
        },
        "metrics": metrics,
        "limitations": [
            (
                "Phoneme-level alignments depend on acoustic model fidelity and "
                "pronunciation dictionary."
            ),
            "Display WebVTT timings are millisecond-rounded and clamped for reading ergonomics.",
            "Acoustic confidence is a model score and does not guarantee human-level accuracy.",
        ],
    }

    manifest_path = output_dir / "manifest.json"
    manifest_json = json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    manifest_path.write_text(manifest_json, encoding="utf-8")
    return manifest


__all__ = [
    "export_jsonld",
    "export_karaoke_vtt",
    "export_raw_alignment",
    "format_vtt_timestamp",
    "generate_manifest",
    "jsonld",
    "milliseconds",
    "timestamp",
    "webvtt",
]
