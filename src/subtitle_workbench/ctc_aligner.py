"""In-process CTC Trellis dynamic programming aligner and TorchAudio fallback.

Implements:
- Pure-NumPy forward Trellis matrix calculation and Viterbi backtracking
- Character-to-word segment aggregation via boundary separator '|'
- Lazy-loading TorchAudioAligner wrapper around torchaudio MMS_FA pipeline (torchaudio
  forced_align recipe: concatenated word tokens, no star token, words from token spans)
- Hardware-aware device management (CPU/CUDA) with eager VRAM cleanup
- Typed exceptions for graceful offline fallback
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Final

import numpy as np

from .models import WordToken

logger = logging.getLogger(__name__)

# Default phonetic/alphabetic dictionary matching MMS_FA / Wav2Vec2 forced alignment
DEFAULT_DICTIONARY: Final[dict[str, int]] = {
    "*": 0,
    "|": 1,
    **{chr(ord("a") + i): i + 2 for i in range(26)},
    "'": 28,
}


class CTCAlignerError(Exception):
    """Base exception for Connectionist Temporal Classification (CTC) alignment errors."""


class CTCAlignerUnavailableError(CTCAlignerError):
    """Raised when PyTorch, TorchAudio, or MMS_FA model weights are missing or unavailable."""


@dataclass(frozen=True)
class Point:
    """Individual alignment lattice coordinate produced during Viterbi backtracking."""

    token_index: int
    time_index: int
    score: float


@dataclass(frozen=True)
class TokenSegment:
    """Contiguous run of audio frames assigned to a single transcript token."""

    label: str
    token_id: int
    start_frame: int
    end_frame: int
    score: float


def get_trellis(
    emissions: np.ndarray,
    tokens: list[int],
    blank_id: int = 0,
) -> np.ndarray:
    """Compute the forward dynamic programming Trellis matrix.

    Parameters
    ----------
    emissions : np.ndarray
        Array of shape (T, C) containing frame-level log-probabilities.
    tokens : list[int]
        Target token ID sequence of length J.
    blank_id : int
        Index of the CTC blank token (default 0).

    Returns
    -------
    np.ndarray
        Accumulated log-probability Trellis matrix of shape (T, J).
    """
    num_frames, num_classes = emissions.shape
    num_tokens = len(tokens)

    if num_frames < num_tokens:
        raise ValueError(
            f"Emission time frames ({num_frames}) cannot be less than target tokens ({num_tokens})"
        )

    for tok in tokens:
        if not (0 <= tok < num_classes):
            raise ValueError(
                f"Token ID {tok} is out of emissions vocabulary bounds [0, {num_classes})"
            )

    trellis = np.full((num_frames, num_tokens), -np.inf, dtype=np.float64)

    # Base condition: at t=0, align to token 0
    trellis[0, 0] = emissions[0, tokens[0]]

    # Forward recurrence
    for t in range(num_frames - 1):
        for j in range(num_tokens):
            score = trellis[t, j]
            if score == -np.inf:
                continue

            # Option 1: Stay at token j at t + 1
            p_stay = score + emissions[t + 1, tokens[j]]
            if p_stay > trellis[t + 1, j]:
                trellis[t + 1, j] = p_stay

            # Option 2: Transition from token j to token j + 1 at t + 1
            if j + 1 < num_tokens:
                p_change = score + emissions[t + 1, tokens[j + 1]]
                if p_change > trellis[t + 1, j + 1]:
                    trellis[t + 1, j + 1] = p_change

    return trellis


def backtrack(
    trellis: np.ndarray,
    emissions: np.ndarray,
    tokens: list[int],
    blank_id: int = 0,
) -> list[Point]:
    """Backtrack optimal Viterbi path through the Trellis matrix.

    Traverses backwards from the terminal frame to t=0, recording the highest-scoring
    token-to-frame alignment path.
    """
    num_frames, num_tokens = trellis.shape
    j = num_tokens - 1

    # Locate optimal terminal time frame for the final token
    if trellis[num_frames - 1, j] > -np.inf:
        t = num_frames - 1
    else:
        t = int(np.argmax(trellis[:, j]))
        if trellis[t, j] == -np.inf:
            raise ValueError("No valid alignment path found through Trellis matrix")

    path: list[Point] = []
    prob = float(np.exp(min(0.0, emissions[t, tokens[j]])))
    path.append(Point(token_index=j, time_index=t, score=prob))

    while t > 0 and j > 0:
        stay_score = trellis[t - 1, j]
        change_score = trellis[t - 1, j - 1]

        if change_score >= stay_score:
            j -= 1
        t -= 1

        prob = float(np.exp(min(0.0, emissions[t, tokens[j]])))
        path.append(Point(token_index=j, time_index=t, score=prob))

    while t > 0:
        t -= 1
        prob = float(np.exp(min(0.0, emissions[t, tokens[0]])))
        path.append(Point(token_index=0, time_index=t, score=prob))

    path.reverse()
    return path


def merge_repeats(
    path: list[Point],
    tokens: list[int],
    id_to_char: dict[int, str],
) -> list[TokenSegment]:
    """Merge consecutive path points for the same token index into TokenSegments."""
    if not path:
        return []

    segments: list[TokenSegment] = []
    curr_token_idx = path[0].token_index
    curr_start = path[0].time_index
    curr_scores = [path[0].score]

    for p in path[1:]:
        if p.token_index == curr_token_idx:
            curr_scores.append(p.score)
        else:
            token_id = tokens[curr_token_idx]
            label = id_to_char.get(token_id, "")
            segments.append(
                TokenSegment(
                    label=label,
                    token_id=token_id,
                    start_frame=curr_start,
                    end_frame=p.time_index,
                    score=float(np.mean(curr_scores)),
                )
            )
            curr_token_idx = p.token_index
            curr_start = p.time_index
            curr_scores = [p.score]

    # Final token segment
    token_id = tokens[curr_token_idx]
    label = id_to_char.get(token_id, "")
    segments.append(
        TokenSegment(
            label=label,
            token_id=token_id,
            start_frame=curr_start,
            end_frame=path[-1].time_index + 1,
            score=float(np.mean(curr_scores)),
        )
    )

    return segments


def merge_words(
    segments: list[TokenSegment],
    separator: str = "|",
    frame_duration: float = 0.02,
    word_id_prefix: str = "word",
) -> list[WordToken]:
    """Aggregate token character segments separated by word boundaries into WordTokens."""
    words: list[WordToken] = []
    curr_word_segs: list[TokenSegment] = []
    word_idx = 0

    def finalize_word(segs: list[TokenSegment]) -> None:
        nonlocal word_idx
        if not segs:
            return
        text = "".join(s.label for s in segs)
        if not text.strip():
            return
        start_sec = round(segs[0].start_frame * frame_duration, 4)
        end_sec = round(segs[-1].end_frame * frame_duration, 4)
        if end_sec <= start_sec:
            end_sec = round(start_sec + frame_duration, 4)

        total_frames = sum(s.end_frame - s.start_frame for s in segs)
        if total_frames > 0:
            avg_score = sum(s.score * (s.end_frame - s.start_frame) for s in segs) / total_frames
        else:
            avg_score = float(np.mean([s.score for s in segs]))
        confidence = float(np.clip(avg_score, 0.0, 1.0))

        words.append(
            WordToken(
                id=f"{word_id_prefix}_{word_idx:04d}",
                text=text,
                normalized=text.lower(),
                start=start_sec,
                end=end_sec,
                confidence=round(confidence, 4),
                phonemes=[],
            )
        )
        word_idx += 1

    for seg in segments:
        if seg.label == separator:
            finalize_word(curr_word_segs)
            curr_word_segs = []
        else:
            curr_word_segs.append(seg)

    finalize_word(curr_word_segs)
    return words


def align_ctc_trellis(
    emissions: np.ndarray,
    tokens: list[int] | str,
    dictionary: dict[str, int] | None = None,
    frame_duration: float = 0.02,
    blank_id: int = 0,
    separator: str = "|",
    word_id_prefix: str = "word",
) -> list[WordToken]:
    """Execute dynamic programming Trellis alignment in pure NumPy.

    Parameters
    ----------
    emissions : np.ndarray
        Posterior emissions array of shape (T, C).
    tokens : list[int] | str
        Target transcript text or explicit token ID sequence.
    dictionary : dict[str, int] | None
        Token-to-index mapping (defaults to DEFAULT_DICTIONARY).
    frame_duration : float
        Temporal length of a single frame in seconds (default 20ms).
    blank_id : int
        Index of the CTC blank token.
    separator : str
        Word boundary token representation (default '|').
    word_id_prefix : str
        Prefix for generated WordToken IDs.

    Returns
    -------
    list[WordToken]
        Aligned word tokens with chunk-local start/end timestamps and confidence scores.
    """
    vocab = dictionary if dictionary is not None else DEFAULT_DICTIONARY
    id_to_char = {v: k for k, v in vocab.items()}

    if isinstance(tokens, str):
        words = tokens.strip().split()
        if not words:
            return []
        target_str = separator + separator.join(words) + separator
        token_ids: list[int] = []
        for ch in target_str.lower():
            if ch in vocab:
                token_ids.append(vocab[ch])
            elif ch == " " and separator in vocab:
                token_ids.append(vocab[separator])
    else:
        token_ids = list(tokens)

    if not token_ids:
        return []

    trellis = get_trellis(emissions, token_ids, blank_id=blank_id)
    path = backtrack(trellis, emissions, token_ids, blank_id=blank_id)
    segments = merge_repeats(path, token_ids, id_to_char)
    words = merge_words(
        segments,
        separator=separator,
        frame_duration=frame_duration,
        word_id_prefix=word_id_prefix,
    )
    return words


def ctc_word_targets(transcript: str, dictionary: dict[str, int]) -> list[tuple[str, list[int]]]:
    """Map each whitespace-separated word to (in-vocabulary lowercase text, token IDs).

    Characters outside the vocabulary are dropped. Words with no in-vocabulary
    character are left out; they appear as unmatched reference words (coverage),
    never as fabricated timings.
    """
    targets: list[tuple[str, list[int]]] = []
    for word in transcript.split():
        chars = [c for c in word.lower() if c in dictionary]
        if chars:
            targets.append(("".join(chars), [dictionary[c] for c in chars]))
    return targets


def words_from_token_spans(
    targets: list[tuple[str, list[int]]],
    spans: list[tuple[int, int, float]],
    frame_duration: float,
    word_id_prefix: str = "word",
) -> list[WordToken]:
    """Split merged token spans (start_frame, end_frame, score) back into words."""
    expected = sum(len(ids) for _, ids in targets)
    if len(spans) != expected:
        raise ValueError(f"Expected {expected} token spans, got {len(spans)}")
    words: list[WordToken] = []
    i = 0
    for w_idx, (text, ids) in enumerate(targets):
        group = spans[i : i + len(ids)]
        i += len(ids)
        frames = sum(e - s for s, e, _ in group)
        score = sum(sc * (e - s) for s, e, sc in group) / frames if frames else 0.0
        start = round(group[0][0] * frame_duration, 4)
        end = round(group[-1][1] * frame_duration, 4)
        words.append(
            WordToken(
                id=f"{word_id_prefix}_{w_idx:04d}",
                text=text,
                normalized=text,
                start=start,
                end=max(end, round(start + frame_duration, 4)),
                confidence=round(float(np.clip(score, 0.0, 1.0)), 4),
                phonemes=[],
            )
        )
    return words


class TorchAudioAligner:
    """In-process CTC forced aligner wrapping torchaudio.pipelines.MMS_FA."""

    def __init__(self, device: str | None = None) -> None:
        self.device_str = device
        self._device = None
        self._bundle = None
        self._model = None
        self._dictionary: dict[str, int] | None = None

    def _ensure_model(self) -> None:
        """Lazy model loader verifying PyTorch/TorchAudio dependencies on first call."""
        if self._model is not None:
            return

        try:
            import torch
            import torchaudio
        except ImportError as err:
            raise CTCAlignerUnavailableError(
                "PyTorch and TorchAudio are required for in-process CTC alignment. "
                "Install with: pip install 'torch>=2.2.0' 'torchaudio>=2.2.0'"
            ) from err

        try:
            target_device = self.device_str
            if target_device is None:
                target_device = "cuda" if torch.cuda.is_available() else "cpu"
            self._device = torch.device(target_device)
            bundle = torchaudio.pipelines.MMS_FA
            self._bundle = bundle
            # No star token: it is a wildcard that absorbs arbitrary audio, not a word
            # separator (MMS_FA has no separator; words come from token spans).
            self._model = bundle.get_model(with_star=False).to(self._device)
            self._dictionary = bundle.get_dict(star=None)
        except Exception as err:
            raise CTCAlignerUnavailableError(
                f"Failed to initialize TorchAudio MMS_FA model: {err}"
            ) from err

    def align(
        self,
        audio_samples: np.ndarray,
        transcript: str,
        sample_rate: int = 16000,
        word_id_prefix: str = "word",
    ) -> list[WordToken]:
        """Align raw audio against a transcript with the torchaudio MMS_FA recipe.

        Tokens of all words are concatenated without separators, aligned with
        ``torchaudio.functional.forced_align``, merged into token spans and split back
        into words by token count. Frame duration is samples / frames / sample rate.
        Words without any character in the MMS_FA vocabulary are not aligned.
        """
        self._ensure_model()
        import torch
        import torchaudio

        targets = ctc_word_targets(transcript, self._dictionary or {})
        if not targets:
            return []
        token_ids = [t for _, ids in targets for t in ids]

        waveform = torch.from_numpy(np.ascontiguousarray(audio_samples)).float().to(self._device)
        if waveform.ndim == 1:
            waveform = waveform.unsqueeze(0)
        num_samples = int(waveform.size(1))
        try:
            with torch.inference_mode():
                emissions, _ = self._model(waveform)
                emissions = torch.log_softmax(emissions, dim=-1)
                if len(token_ids) > emissions.size(1):
                    return []
                ali, scores = torchaudio.functional.forced_align(
                    emissions, torch.tensor([token_ids], device=emissions.device), blank=0
                )
                spans = torchaudio.functional.merge_tokens(ali[0].cpu(), scores[0].exp().cpu())
                num_frames = int(emissions.size(1))
        finally:
            if "emissions" in locals():
                del emissions
            del waveform
            if self._device is not None and self._device.type == "cuda":
                torch.cuda.empty_cache()

        frame_duration = num_samples / num_frames / sample_rate
        return words_from_token_spans(
            targets,
            [(s.start, s.end, float(s.score)) for s in spans],
            frame_duration=frame_duration,
            word_id_prefix=word_id_prefix,
        )
