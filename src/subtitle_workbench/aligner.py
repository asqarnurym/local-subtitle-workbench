"""Unified forced alignment facade orchestrating MFA batch and CTC Trellis fallback.

Provides:
- ForcedAligner: facade class coordinating audio chunk slicing, engine selection
  ("auto", "mfa", "ctc"), fallback routing, and global monotonic seam reconciliation.
- align_chunks: module-level entry point adhering to Increment 4 architectural contract.
"""

from __future__ import annotations

import logging
import shutil
import tempfile
import wave
from pathlib import Path
from typing import Literal

import numpy as np

from .audio import slice_wav
from .chunker import reconcile_chunk_alignments
from .ctc_aligner import TorchAudioAligner
from .mfa_wrapper import (
    MFANotFoundError,
    SubprocessRunner,
    check_mfa_available,
    run_mfa_batch,
)
from .models import AudioChunk, WordToken

logger = logging.getLogger(__name__)


def _read_wav_samples(path: Path | str) -> tuple[np.ndarray, int]:
    """Read mono PCM16 audio samples and sample rate without silence rejection."""
    with wave.open(str(path), "rb") as w:
        sr = w.getframerate()
        raw = w.readframes(w.getnframes())
    samples = np.frombuffer(raw, dtype="<i2").astype(np.float64) / 32768.0
    return samples, sr


class ForcedAligner:
    """Facade orchestrating forced alignment with batch MFA and in-process CTC Trellis."""

    def __init__(
        self,
        mfa_runner: SubprocessRunner | None = None,
        ctc_aligner: TorchAudioAligner | None = None,
    ) -> None:
        self.mfa_runner = mfa_runner
        self.ctc_aligner = ctc_aligner

    def align_chunks(
        self,
        chunks: list[AudioChunk],
        audio_path: Path | str,
        transcripts: list[str] | None = None,
        engine: Literal["auto", "mfa", "ctc"] = "auto",
        fallback_to_ctc: bool = True,
        dictionary: str = "english_us_arpa",
        acoustic_model: str = "english_us_arpa",
    ) -> list[WordToken]:
        """Align AudioChunks against continuous audio and reconcile global monotonic timeline.

        Parameters
        ----------
        chunks : list[AudioChunk]
            Bounded audio chunks partitioned with symmetric overlap padding.
        audio_path : Path
            Path to the source uncompressed mono PCM16 16kHz WAV file.
        transcripts : list[str] | None
            Optional explicit transcript texts per chunk (defaults to chunk.text).
        engine : Literal["auto", "mfa", "ctc"]
            Alignment backend engine selector (defaults to "auto").
        fallback_to_ctc : bool
            Whether to fallback to CTC Trellis when MFA is unavailable on PATH.
        dictionary : str
            MFA pronunciation dictionary identifier.
        acoustic_model : str
            MFA acoustic model identifier.

        Returns
        -------
        list[WordToken]
            Globally reconciled, strictly monotonic, seam-deduplicated word tokens.
        """
        if not chunks:
            return []

        audio_path = Path(audio_path)
        if not audio_path.is_file():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        # Resolve transcripts per chunk
        if transcripts is not None:
            if len(transcripts) != len(chunks):
                raise ValueError(
                    f"transcripts count ({len(transcripts)}) must match "
                    f"chunks count ({len(chunks)})"
                )
            chunk_transcripts = transcripts
        else:
            chunk_transcripts = [c.text for c in chunks]

        # Engine resolution
        mfa_ok = check_mfa_available() if self.mfa_runner is None else True
        chosen_engine: str
        if engine == "auto":
            if mfa_ok:
                chosen_engine = "mfa"
            elif fallback_to_ctc:
                logger.warning(
                    "Montreal Forced Aligner ('mfa') not found on PATH. "
                    "Falling back to in-process PyTorch CTC Trellis aligner."
                )
                chosen_engine = "ctc"
            else:
                raise MFANotFoundError(
                    "Montreal Forced Aligner ('mfa') not found on PATH "
                    "and fallback_to_ctc is False."
                )
        elif engine == "mfa":
            if not mfa_ok:
                raise MFANotFoundError(
                    "Montreal Forced Aligner ('mfa') requested but not found on PATH or .mfa_env. "
                    "Cannot execute phonetic alignment without MFA binary."
                )
            chosen_engine = "mfa"
        elif engine == "ctc":
            chosen_engine = "ctc"
        else:
            raise ValueError(
                f"Unknown alignment engine: {engine!r}. Must be 'auto', 'mfa', or 'ctc'."
            )

        # Slice chunk WAVs into temporary directory
        temp_dir = Path(tempfile.mkdtemp(prefix="align_chunks_"))
        try:
            chunk_wav_pairs: list[tuple[Path, str]] = []
            for idx, (chunk, text) in enumerate(zip(chunks, chunk_transcripts, strict=True)):
                slice_path = temp_dir / f"chunk_{idx:04d}.wav"
                slice_wav(audio_path, slice_path, chunk.padded_start, chunk.padded_end)
                chunk_wav_pairs.append((slice_path, text))

            # Execute alignment backend
            chunk_aligned_words: list[list[WordToken]]
            if chosen_engine == "mfa":
                chunk_aligned_words = run_mfa_batch(
                    chunk_wavs=chunk_wav_pairs,
                    dictionary=dictionary,
                    acoustic_model=acoustic_model,
                    runner=self.mfa_runner,
                )
            else:
                aligner = self.ctc_aligner or TorchAudioAligner()
                chunk_aligned_words = []
                for idx, (slice_path, text) in enumerate(chunk_wav_pairs):
                    samples, sr = _read_wav_samples(slice_path)
                    try:
                        words = aligner.align(
                            samples,
                            text,
                            sample_rate=sr,
                            word_id_prefix=f"chunk_{idx:04d}",
                        )
                    except TypeError:
                        words = aligner.align(samples, text, sample_rate=sr)
                    chunk_aligned_words.append(words)

            # Reconcile into globally monotonic word sequence
            reconciled = reconcile_chunk_alignments(
                chunks=chunks,
                chunk_aligned_words=chunk_aligned_words,
                padded_coordinates=True,
            )
            return reconciled

        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


def align_chunks(
    chunks: list[AudioChunk],
    audio_path: Path | str,
    transcripts: list[str] | None = None,
    engine: Literal["auto", "mfa", "ctc"] = "auto",
    fallback_to_ctc: bool = True,
    dictionary: str = "english_us_arpa",
    acoustic_model: str = "english_us_arpa",
) -> list[WordToken]:
    """Module-level entry point for chunked forced alignment."""
    aligner = ForcedAligner()
    return aligner.align_chunks(
        chunks=chunks,
        audio_path=audio_path,
        transcripts=transcripts,
        engine=engine,
        fallback_to_ctc=fallback_to_ctc,
        dictionary=dictionary,
        acoustic_model=acoustic_model,
    )
