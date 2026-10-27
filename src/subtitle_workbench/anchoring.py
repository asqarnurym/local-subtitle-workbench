"""Transcript anchoring: coarse word-level alignment of a known transcript to ASR output.

When the lecture transcript is known (scenario A), forced alignment still needs to
know which part of the text belongs to which part of a long recording before the
audio can be cut into bounded chunks. This module performs the coarse,
word-level stage of the two-stage ("downsample-then-align") synchronization:

1. The reference transcript and the Whisper hypothesis are aligned as token
   sequences with a banded monotonic dynamic-programming alignment
   (Needleman-Wunsch scoring inside a diagonal band, i.e. a DTW-style path over
   words rather than over 10 ms acoustic frames).
2. Every reference word matched to an identical hypothesis word becomes an
   anchor and inherits the hypothesis timestamps.
3. Unmatched reference words are placed between the surrounding anchors,
   proportionally to their character length.

The fine stage (frame-level boundaries) is done afterwards by the forced aligner
inside each chunk. Anchoring statistics are returned so that the share of
interpolated words is always reported, never hidden.
"""

from __future__ import annotations

from dataclasses import dataclass

from .models import WordToken
from .text_norm import normalize_transcript

MATCH_SCORE = 2
MISMATCH_SCORE = -1
GAP_SCORE = -1
MIN_BAND = 50
BAND_FRACTION = 0.1
MIN_WORD_SEC = 0.01


@dataclass(frozen=True)
class ReferenceToken:
    """One source word of the reference transcript (contractions/numbers kept whole)."""

    text: str
    normalized: str
    char_start: int
    char_end: int


@dataclass(frozen=True)
class AnchoringResult:
    words: list[WordToken]
    n_reference: int
    n_hypothesis: int
    n_anchors: int

    @property
    def anchor_ratio(self) -> float:
        return self.n_anchors / self.n_reference if self.n_reference else 0.0

    def to_dict(self) -> dict[str, float | int]:
        return {
            "n_reference_words": self.n_reference,
            "n_hypothesis_words": self.n_hypothesis,
            "n_anchors": self.n_anchors,
            "anchor_ratio": round(self.anchor_ratio, 4),
        }


def reference_tokens(text: str) -> list[ReferenceToken]:
    """Group normalized spans back into source words.

    The normalizer expands e.g. "don't" -> "do not" and "42" -> "forty two" as
    several spans sharing one character range; they are merged into one token.
    """
    tokens: list[ReferenceToken] = []
    for span in normalize_transcript(text):
        if tokens and (tokens[-1].char_start, tokens[-1].char_end) == (
            span.char_start,
            span.char_end,
        ):
            prev = tokens[-1]
            tokens[-1] = ReferenceToken(
                prev.text, f"{prev.normalized} {span.normalized}", prev.char_start, prev.char_end
            )
        else:
            tokens.append(
                ReferenceToken(span.token, span.normalized, span.char_start, span.char_end)
            )
    return tokens


def _key(normalized: str) -> str:
    return normalized.lower().replace("'", "").strip()


def banded_sequence_alignment(
    ref_keys: list[str],
    hyp_keys: list[str],
    band: int | None = None,
) -> list[tuple[int, int]]:
    """Return (ref_index, hyp_index) pairs of exact matches on the best monotonic path.

    Dynamic programming is restricted to a band around the length-scaled diagonal,
    giving O(n * band) time and memory for hour-long lectures.
    """
    n, m = len(ref_keys), len(hyp_keys)
    if n == 0 or m == 0:
        return []
    if band is None:
        band = max(MIN_BAND, int(BAND_FRACTION * max(n, m)))
    band = max(band, abs(n - m) + 1)
    neg = -(10**9)

    def window(i: int) -> tuple[int, int]:
        centre = i * m / n
        return max(0, int(centre) - band), min(m, int(centre) + band)

    # score[i] / move[i] cover hyp positions lo_i..hi_i (inclusive), column j means
    # "first j hypothesis words consumed".
    windows = [window(i) for i in range(n + 1)]
    score: list[list[int]] = []
    move: list[bytearray] = []  # 0 = diag, 1 = up (skip ref), 2 = left (skip hyp)

    for i in range(n + 1):
        lo, hi = windows[i]
        row = [neg] * (hi - lo + 1)
        mv = bytearray(hi - lo + 1)
        plo, phi = windows[i - 1] if i > 0 else (0, -1)
        for j in range(lo, hi + 1):
            k = j - lo
            if i == 0 and j == 0:
                row[k] = 0
                continue
            best, how = neg, 0
            if i > 0 and j > 0 and plo <= j - 1 <= phi:
                prev = score[i - 1][j - 1 - plo]
                if prev > neg:
                    s = MATCH_SCORE if ref_keys[i - 1] == hyp_keys[j - 1] else MISMATCH_SCORE
                    best, how = prev + s, 0
            if i > 0 and plo <= j <= phi:
                prev = score[i - 1][j - plo]
                if prev > neg and prev + GAP_SCORE > best:
                    best, how = prev + GAP_SCORE, 1
            if j > lo:
                prev = row[k - 1]
                if prev > neg and prev + GAP_SCORE > best:
                    best, how = prev + GAP_SCORE, 2
            elif i == 0 and j > 0:
                best, how = GAP_SCORE * j, 2
            row[k] = best
            mv[k] = how
        score.append(row)
        move.append(mv)

    # Backtrace from (n, best reachable j near m)
    lo_n, hi_n = windows[n]
    i, j = n, min(m, hi_n)
    pairs: list[tuple[int, int]] = []
    while i > 0 or j > 0:
        lo, _ = windows[i]
        if i == 0:
            j -= 1
            continue
        how = move[i][j - lo] if lo <= j else 1
        if how == 0 and j > 0:
            if ref_keys[i - 1] == hyp_keys[j - 1]:
                pairs.append((i - 1, j - 1))
            i, j = i - 1, j - 1
        elif how == 1:
            i -= 1
        else:
            j -= 1
    pairs.reverse()
    return pairs


def anchor_transcript(
    reference_text: str,
    hypothesis_words: list[WordToken],
    total_duration: float,
) -> AnchoringResult:
    """Assign approximate times to every reference word using ASR anchors."""
    if total_duration <= 0.0:
        raise ValueError("total_duration must be positive")
    refs = reference_tokens(reference_text)
    if not refs:
        raise ValueError("transcript contains no valid words after normalization")

    hyps = sorted(hypothesis_words, key=lambda w: (w.start, w.end))
    pairs = banded_sequence_alignment(
        [_key(r.normalized) for r in refs], [_key(h.normalized or h.text) for h in hyps]
    )

    # Keep strictly increasing anchors only
    anchor_times: dict[int, tuple[float, float, float]] = {}
    last_end = 0.0
    for r_i, h_j in pairs:
        h = hyps[h_j]
        if h.start >= last_end - 1e-6 and h.end <= total_duration + 1e-6:
            anchor_times[r_i] = (h.start, min(h.end, total_duration), h.confidence)
            last_end = h.end

    times: list[tuple[float, float, float]] = [(0.0, 0.0, 0.0)] * len(refs)
    i = 0
    while i < len(refs):
        if i in anchor_times:
            times[i] = anchor_times[i]
            i += 1
            continue
        # Gap of unmatched words [i, k)
        k = i
        while k < len(refs) and k not in anchor_times:
            k += 1
        lo = times[i - 1][1] if i > 0 else 0.0
        hi = anchor_times[k][0] if k < len(refs) else total_duration
        weights = [max(1, len(refs[t].text)) for t in range(i, k)]
        total_w = float(sum(weights))
        span = max(hi - lo, MIN_WORD_SEC * len(weights))
        cursor = lo
        for t, w in zip(range(i, k), weights, strict=True):
            dur = span * w / total_w
            times[t] = (cursor, cursor + dur, 0.0)
            cursor += dur
        i = k

    words: list[WordToken] = []
    for idx, (ref, (s, e, conf)) in enumerate(zip(refs, times, strict=True)):
        e = min(round(e, 4), round(total_duration, 4))
        s = max(0.0, min(round(s, 4), e - MIN_WORD_SEC))
        if e <= s:
            e = round(s + MIN_WORD_SEC, 4)
        words.append(
            WordToken(
                id=f"w_{idx}",
                text=ref.text,
                normalized=ref.normalized,
                start=s,
                end=e,
                confidence=round(min(max(conf, 0.0), 1.0), 4),
                char_start=ref.char_start,
                char_end=ref.char_end,
            )
        )
    return AnchoringResult(
        words=words,
        n_reference=len(refs),
        n_hypothesis=len(hyps),
        n_anchors=len(anchor_times),
    )


__all__ = [
    "AnchoringResult",
    "ReferenceToken",
    "anchor_transcript",
    "banded_sequence_alignment",
    "reference_tokens",
]
