"""WebVTT and schema.org JSON-LD serialization."""

import html
from decimal import ROUND_HALF_UP, Decimal
from urllib.parse import quote

from .models import Cue, finite_number


def milliseconds(seconds: float) -> int:
    value = finite_number(seconds, "timestamp")
    if value < 0:
        raise ValueError("timestamp must be nonnegative")
    return int((Decimal(str(value)) * 1000).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def timestamp(seconds: float) -> str:
    total = milliseconds(seconds)
    hours, remainder = divmod(total, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    sec, ms = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{sec:02d}.{ms:03d}"


def webvtt(cues: list[Cue]) -> str:
    blocks = ["WEBVTT"]
    for cue in cues:
        if milliseconds(cue.end) <= milliseconds(cue.start):
            raise ValueError("cue collapses after millisecond rounding")
        payload = html.escape(cue.text, quote=False)
        blocks.append(f"{cue.id}\n{timestamp(cue.start)} --> {timestamp(cue.end)}\n{payload}")
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
