"""Unified forced alignment facade: Montreal Forced Aligner batch and CTC Trellis engines.

Provides:
- AlignmentRequest: one recording's chunks to align (audio path, chunks, speaker label).
- ForcedAligner: facade that slices chunk audio, runs exactly the requested engine
  (no implicit fallback between engines), aligns many recordings in one MFA call,
  and reconciles every recording into a globally monotonic word timeline.
- align_chunks: module-level convenience entry point for a single recording.
"""

from __future__ import annotations

import logging
import shutil
import tempfile
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import numpy as np

from .audio import slice_wav
from .chunker import reconcile_chunk_alignments
from .ctc_aligner import TorchAudioAligner
from .mfa_wrapper import (
    MFAItem,
    MFANotFoundError,
    SubprocessRunner,
    check_mfa_available,
    default_num_jobs,
    run_mfa_corpus,
)
from .models import AudioChunk, WordToken

logger = logging.getLogger(__name__)

Engine = Literal["mfa", "ctc"]
SUPPORTED_ENGINES: tuple[str, ...] = ("mfa", "ctc")


def _read_wav_samples(path: Path | str) -> tuple[np.ndarray, int]:
    """Read mono PCM16 audio samples and sample rate without silence rejection."""
    with wave.open(str(path), "rb") as w:
        sr = w.getframerate()
        raw = w.readframes(w.getnframes())
    samples = np.frombuffer(raw, dtype="<i2").astype(np.float64) / 32768.0
    return samples, sr


@dataclass(frozen=True)
class AlignmentRequest:
    """Chunks of one recording to be force-aligned."""

    audio_path: Path
    chunks: list[AudioChunk]
    speaker: str = "speaker"


class AlignmentFailure(RuntimeError):
    """Raised for a recording whose chunks could not be aligned by the requested engine."""


class ForcedAligner:
    """Facade orchestrating forced alignment with batch MFA and in-process CTC Trellis.

    The CTC model is created once per facade instance and reused across calls.
    MFA options (dictionary, acoustic model, G2P model, fine-tuning) are fixed per
    instance so that every recording in a benchmark is aligned with one configuration.
    """

    def __init__(
        self,
        mfa_runner: SubprocessRunner | None = None,
        ctc_aligner: TorchAudioAligner | None = None,
        dictionary: str = "english_us_arpa",
        acoustic_model: str = "english_us_arpa",
        g2p_model: str | None = "english_us_arpa",
        mfa_fine_tune: bool = True,
        mfa_num_jobs: int | None = None,
        ctc_device: str | None = None,
    ) -> None:
        self.mfa_runner = mfa_runner
        self.ctc_aligner = ctc_aligner
        self.dictionary = dictionary
        self.acoustic_model = acoustic_model
        self.g2p_model = g2p_model
        self.mfa_fine_tune = mfa_fine_tune
        self.mfa_num_jobs = mfa_num_jobs
        self.ctc_device = ctc_device

    # ------------------------------------------------------------------
    # Configuration record (written to manifests)
    # ------------------------------------------------------------------
    def describe(self, engine: str) -> dict[str, object]:
        if engine == "mfa":
            return {
                "engine": "mfa",
                "dictionary": self.dictionary,
                "acoustic_model": self.acoustic_model,
                "g2p_model": self.g2p_model,
                "fine_tune": self.mfa_fine_tune,
                "speaker_adaptation": True,
                # Affects boundaries slightly (job split), so it is part of the record
                "num_jobs": (
                    self.mfa_num_jobs if self.mfa_num_jobs is not None else default_num_jobs()
                ),
            }
        return {"engine": "ctc", "model": "torchaudio.pipelines.MMS_FA"}

    def _get_ctc(self) -> TorchAudioAligner:
        if self.ctc_aligner is None:
            self.ctc_aligner = TorchAudioAligner(device=self.ctc_device)
        return self.ctc_aligner

    @staticmethod
    def _check_engine(engine: str) -> None:
        if engine not in SUPPORTED_ENGINES:
            raise ValueError(
                f"Unknown alignment engine: {engine!r}. Must be one of {SUPPORTED_ENGINES}."
            )

    # ------------------------------------------------------------------
    # Batch API
    # ------------------------------------------------------------------
    def align_requests(
        self,
        requests: list[AlignmentRequest],
        engine: Engine = "mfa",
    ) -> list[list[WordToken] | AlignmentFailure]:
        """Align many recordings; MFA runs once for all chunks of all recordings.

        Returns, per request, either the reconciled word list or an AlignmentFailure
        describing which chunks the engine could not align. Engine-level failures
        (MFA missing, MFA crash, CTC model unavailable) raise immediately.
        """
        self._check_engine(engine)
        if engine == "mfa" and self.mfa_runner is None and not check_mfa_available():
            raise MFANotFoundError(
                "Montreal Forced Aligner ('mfa') requested but not found on PATH or .mfa_env. "
                "Cannot execute phonetic alignment without MFA binary."
            )

        for req in requests:
            if not Path(req.audio_path).is_file():
                raise FileNotFoundError(f"Audio file not found: {req.audio_path}")

        temp_dir = Path(tempfile.mkdtemp(prefix="align_chunks_"))
        try:
            # 1. Slice every chunk of every recording
            flat: list[tuple[int, int, Path, str]] = []  # (req_idx, chunk_idx, wav, text)
            for r_idx, req in enumerate(requests):
                for c_idx, chunk in enumerate(req.chunks):
                    slice_path = temp_dir / f"r{r_idx:05d}_c{c_idx:04d}.wav"
                    slice_wav(req.audio_path, slice_path, chunk.padded_start, chunk.padded_end)
                    flat.append((r_idx, c_idx, slice_path, chunk.text))

            # 2. Run the requested engine
            per_chunk: list[list[WordToken] | None]
            if not flat:
                per_chunk = []
            elif engine == "mfa":
                per_chunk = run_mfa_corpus(
                    [MFAItem(wav, text, requests[r_idx].speaker) for r_idx, _, wav, text in flat],
                    dictionary=self.dictionary,
                    acoustic_model=self.acoustic_model,
                    g2p_model=self.g2p_model,
                    fine_tune=self.mfa_fine_tune,
                    num_jobs=self.mfa_num_jobs,
                    runner=self.mfa_runner,
                )
            else:
                ctc = self._get_ctc()
                per_chunk = []
                for r_idx, c_idx, wav, text in flat:
                    samples, sr = _read_wav_samples(wav)
                    per_chunk.append(
                        ctc.align(
                            samples,
                            text,
                            sample_rate=sr,
                            word_id_prefix=f"r{r_idx:05d}_c{c_idx:04d}",
                        )
                    )

            # 3. Regroup and reconcile per recording
            grouped: list[list[list[WordToken] | None]] = [
                [None] * len(req.chunks) for req in requests
            ]
            for (r_idx, c_idx, _, _), words in zip(flat, per_chunk, strict=True):
                grouped[r_idx][c_idx] = words

            results: list[list[WordToken] | AlignmentFailure] = []
            for req, chunk_words in zip(requests, grouped, strict=True):
                missing = [i for i, w in enumerate(chunk_words) if w is None]
                if missing:
                    results.append(
                        AlignmentFailure(
                            f"{engine} produced no alignment for chunk(s) {missing} "
                            f"of {Path(req.audio_path).name}"
                        )
                    )
                    continue
                results.append(
                    reconcile_chunk_alignments(
                        chunks=req.chunks,
                        chunk_aligned_words=[w for w in chunk_words if w is not None],
                        padded_coordinates=True,
                    )
                )
            return results
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    # ------------------------------------------------------------------
    # Single recording API (strict)
    # ------------------------------------------------------------------
    def align_chunks(
        self,
        chunks: list[AudioChunk],
        audio_path: Path | str,
        engine: Engine = "mfa",
        speaker: str = "speaker",
    ) -> list[WordToken]:
        """Align the chunks of one recording; raises if any chunk cannot be aligned."""
        self._check_engine(engine)
        if not chunks:
            return []
        audio_path = Path(audio_path)
        if not audio_path.is_file():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")
        (result,) = self.align_requests(
            [AlignmentRequest(audio_path=audio_path, chunks=chunks, speaker=speaker)],
            engine=engine,
        )
        if isinstance(result, AlignmentFailure):
            raise result
        return result


def align_chunks(
    chunks: list[AudioChunk],
    audio_path: Path | str,
    engine: Engine = "mfa",
    dictionary: str = "english_us_arpa",
    acoustic_model: str = "english_us_arpa",
) -> list[WordToken]:
    """Module-level entry point for chunked forced alignment of one recording."""
    aligner = ForcedAligner(dictionary=dictionary, acoustic_model=acoustic_model)
    return aligner.align_chunks(chunks=chunks, audio_path=audio_path, engine=engine)


__all__ = [
    "SUPPORTED_ENGINES",
    "AlignmentFailure",
    "AlignmentRequest",
    "ForcedAligner",
    "align_chunks",
]
