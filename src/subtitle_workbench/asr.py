"""Automatic Speech Recognition (Faster-Whisper) and Silero-VAD silence detection.

Releases GPU memory deterministically after transcription so that the aligner can reuse it.
All heavy libraries (torch, faster-whisper) are imported lazily to keep base
installations lightweight.
"""

import contextlib
import gc
import math
import os
import sys
import wave
from pathlib import Path
from typing import Any

import numpy as np

from .audio import validate_wav
from .models import ASRSegment, WordToken
from .text_norm import normalize_text_spans


class ASRError(Exception):
    """Base exception for all ASR and VAD errors."""


class AudioFormatError(ASRError):
    """Raised when audio input does not conform to required PCM16 16 kHz format."""


class ASRInferenceError(ASRError):
    """Raised when Faster-Whisper transcription fails or encounters invalid model states."""


class VRAMAllocationError(ASRError):
    """Raised when GPU VRAM allocation fails or exceeds the hardware threshold."""


def _sanitize_text(text: str, allow_newlines: bool = False) -> str:
    """Strip ASCII control characters, del, C1 controls, and surrogates."""
    if allow_newlines:
        return "".join(
            c
            for c in text
            if (ord(c) >= 32 or c in "\t\n\r")
            and ord(c) != 127
            and not (128 <= ord(c) <= 159)
            and not (0xD800 <= ord(c) <= 0xDFFF)
        ).strip()
    return "".join(
        c
        for c in text
        if ord(c) >= 32
        and ord(c) != 127
        and not (128 <= ord(c) <= 159)
        and not (0xD800 <= ord(c) <= 0xDFFF)
    ).strip()


def _is_vram_allocation_error(exc: Exception) -> bool:
    """Detect if an exception is caused by GPU out of memory or allocation failure."""
    msg = str(exc).lower()
    return (
        "out of memory" in msg
        or "failed to allocate" in msg
        or "cannot allocate" in msg
        or "bad_alloc" in msg
        or ("cuda" in msg and ("allocat" in msg or "memory" in msg or "cublas" in msg))
    )


_DLL_DIRS_REGISTERED = False


def register_nvidia_dll_dirs() -> list[str]:
    """Expose CUDA runtime DLLs shipped as pip wheels (nvidia-cublas-cu12, nvidia-cudnn-cu12).

    CTranslate2 (used by Faster-Whisper) loads cuBLAS/cuDNN dynamically. On Windows the
    pip wheels place the DLLs under ``site-packages/nvidia/*/bin``, which is not on the
    DLL search path by default; without this step Faster-Whisper silently cannot use the GPU.
    """
    global _DLL_DIRS_REGISTERED
    found: list[str] = []
    if sys.platform != "win32":
        return found
    import site

    roots = [Path(p) for p in site.getsitepackages()]
    try:
        roots.append(Path(site.getusersitepackages()))
    except Exception:
        pass
    for root in roots:
        nvidia_base = root / "nvidia"
        if nvidia_base.is_dir():
            for sub in nvidia_base.iterdir():
                bin_dir = sub / "bin"
                if bin_dir.is_dir():
                    found.append(str(bin_dir))
    if not _DLL_DIRS_REGISTERED and found:
        os.environ["PATH"] = os.pathsep.join(found) + os.pathsep + os.environ.get("PATH", "")
        for d in found:
            with contextlib.suppress(OSError):
                os.add_dll_directory(d)  # type: ignore[attr-defined]
        _DLL_DIRS_REGISTERED = True
    return found


def whisper_cuda_available() -> bool:
    """Return True if CTranslate2 can run Whisper on a CUDA GPU (driver + cuBLAS present)."""
    try:
        register_nvidia_dll_dirs()
        import ctranslate2

        if ctranslate2.get_cuda_device_count() < 1:
            return False
        if sys.platform == "win32":
            import ctypes

            ctypes.WinDLL("cublas64_12.dll")  # type: ignore[attr-defined]
        return True
    except Exception:
        return False


def _resolve_device_and_compute_type(
    device: str | None,
    compute_type: str | None,
) -> tuple[str, str]:
    """Select the execution device for Faster-Whisper.

    ``device=None`` picks CUDA when CTranslate2 can use it, otherwise CPU (the choice is
    recorded in pipeline manifests). An explicit ``device="cuda"`` is strict: it raises
    instead of silently running on CPU.
    """
    if device is None:
        device = "cuda" if whisper_cuda_available() else "cpu"
    elif device == "cuda" and not whisper_cuda_available():
        raise ASRInferenceError(
            "device='cuda' requested but CTranslate2 cannot use a CUDA GPU. Install the "
            "'speech' extra (nvidia-cublas-cu12, nvidia-cudnn-cu12) and an NVIDIA driver."
        )

    if compute_type is None:
        compute_type = "int8_float16" if device == "cuda" else "int8"

    return device, compute_type


class WhisperTranscriber:
    """Encapsulates Faster-Whisper Large-v3 INT8 transcription with deterministic VRAM cleanup."""

    def __init__(
        self,
        model_size_or_path: str = "large-v3",
        device: str | None = None,
        compute_type: str | None = None,
        vad_filter: bool = True,
        min_silence_duration_ms: int = 400,
        model_instance: Any | None = None,
    ) -> None:
        if (
            isinstance(min_silence_duration_ms, bool)
            or not isinstance(min_silence_duration_ms, int)
            or min_silence_duration_ms <= 0
        ):
            raise ASRInferenceError("min_silence_duration_ms must be a positive integer")
        self.model_size_or_path = model_size_or_path
        self._device, self._compute_type = _resolve_device_and_compute_type(device, compute_type)
        self.vad_filter = vad_filter
        self.min_silence_duration_ms = min_silence_duration_ms
        self._model = model_instance

    @property
    def device(self) -> str:
        return self._device

    @property
    def compute_type(self) -> str:
        return self._compute_type

    @property
    def is_loaded(self) -> bool:
        return self._model is not None

    def _get_or_load_model(self) -> Any:
        if self._model is not None:
            return self._model

        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise ASRInferenceError(
                "faster-whisper is not installed. Please install with optional dependency: "
                "pip install local-subtitle-workbench[speech]"
            ) from exc

        try:
            self._model = WhisperModel(
                self.model_size_or_path,
                device=self._device,
                compute_type=self._compute_type,
            )
        except Exception as exc:
            if _is_vram_allocation_error(exc):
                raise VRAMAllocationError(f"CUDA VRAM allocation failed: {exc}") from exc
            raise ASRInferenceError(f"Failed to load Faster-Whisper model: {exc}") from exc

        return self._model

    def transcribe(
        self,
        audio_path: Path | str,
        language: str = "en",
        **kwargs: Any,
    ) -> list[ASRSegment]:
        """Transcribe PCM16 16 kHz WAV into typed ASRSegments and WordTokens.

        Normalized forms are generated via normalize_text_spans.
        """
        if not isinstance(audio_path, (str, Path)):
            raise AudioFormatError(
                f"audio_path must be a Path or str, got {type(audio_path).__name__}"
            )
        if isinstance(language, bool) or not isinstance(language, str) or not language.strip():
            raise ASRInferenceError("language must be a non-empty string")
        clean_language = language.strip().lower()

        path = Path(audio_path)
        try:
            validate_wav(path, sample_rate=16000)
        except (FileNotFoundError, ValueError, OSError, RuntimeError, TypeError) as exc:
            raise AudioFormatError(f"Audio format validation failed for {path}: {exc}") from exc

        model = self._get_or_load_model()
        vad_params = (
            {"min_silence_duration_ms": self.min_silence_duration_ms} if self.vad_filter else None
        )

        transcribe_kwargs: dict[str, Any] = {
            "language": clean_language,
            "vad_filter": self.vad_filter,
            "vad_parameters": vad_params,
        }
        transcribe_kwargs.update(kwargs)
        transcribe_kwargs["word_timestamps"] = True

        try:
            segments_iter, _ = model.transcribe(
                str(path),
                **transcribe_kwargs,
            )
            raw_segments = list(segments_iter)
        except Exception as exc:
            if _is_vram_allocation_error(exc):
                raise VRAMAllocationError(f"CUDA VRAM allocation failed: {exc}") from exc
            raise ASRInferenceError(f"ASR transcription failed: {exc}") from exc

        try:
            result_segments: list[ASRSegment] = []
            for seg_idx, raw_seg in enumerate(raw_segments):
                seg_id = f"seg_{seg_idx}"
                raw_text = getattr(raw_seg, "text", "") or ""
                seg_text = _sanitize_text(raw_text, allow_newlines=True)
                if not seg_text:
                    continue

                words_list: list[WordToken] = []
                raw_words = getattr(raw_seg, "words", None) or []

                for w_idx, raw_word in enumerate(raw_words):
                    word_raw = getattr(raw_word, "word", "")
                    clean_text = _sanitize_text(word_raw, allow_newlines=False)
                    if not clean_text:
                        continue

                    spans = normalize_text_spans(clean_text)
                    if spans:
                        norm_word = " ".join(s.normalized for s in spans)
                        # Strip outer boundary punctuation while preserving compound hyphens
                        token_text = clean_text.strip(
                            ".,!?;:\"'()[]{}<>-—–_`~@#$%^&*+=|\\/«»“”‘’…„‚‹›¿¡€£¥₹₽₩\u2212"
                        )
                        if not token_text:
                            token_text = spans[0].token
                    else:
                        norm_word = clean_text.lower()
                        token_text = clean_text

                    w_start = float(getattr(raw_word, "start", 0.0))
                    w_end = float(getattr(raw_word, "end", w_start + 0.01))
                    if math.isnan(w_start) or math.isinf(w_start):
                        w_start = 0.0
                    if math.isnan(w_end) or math.isinf(w_end):
                        w_end = w_start + 0.01
                    if w_start > w_end:
                        w_start, w_end = w_end, w_start
                    if w_start < 0.0:
                        w_start = 0.0
                    r_start = round(w_start, 4)
                    r_end = round(w_end, 4)
                    if r_end <= r_start:
                        r_end = round(r_start + 0.01, 4)

                    prob = float(getattr(raw_word, "probability", 0.95))
                    conf = round(min(max(prob, 0.0), 1.0), 4)

                    w_id = f"{seg_id}_w_{w_idx}"
                    words_list.append(
                        WordToken(
                            id=w_id,
                            text=token_text,
                            normalized=norm_word,
                            start=r_start,
                            end=r_end,
                            confidence=conf,
                        )
                    )

                if not words_list:
                    # Synthesize word tokens from seg_text if raw_words was omitted by backend
                    text_spans = normalize_text_spans(seg_text)
                    if text_spans:
                        raw_seg_start = float(getattr(raw_seg, "start", 0.0))
                        raw_seg_end = float(getattr(raw_seg, "end", raw_seg_start + 0.01))
                        if math.isnan(raw_seg_start) or math.isinf(raw_seg_start):
                            raw_seg_start = 0.0
                        if math.isnan(raw_seg_end) or math.isinf(raw_seg_end):
                            raw_seg_end = raw_seg_start + 0.01
                        if raw_seg_start > raw_seg_end:
                            raw_seg_start, raw_seg_end = raw_seg_end, raw_seg_start
                        if raw_seg_start < 0.0:
                            raw_seg_start = 0.0
                        if raw_seg_end <= raw_seg_start:
                            raw_seg_end = raw_seg_start + 0.01
                        span_dur = (raw_seg_end - raw_seg_start) / len(text_spans)
                        for s_idx, span in enumerate(text_spans):
                            ws = raw_seg_start + s_idx * span_dur
                            we = ws + span_dur
                            r_ws = round(ws, 4)
                            if words_list and r_ws < words_list[-1].end:
                                r_ws = words_list[-1].end
                            r_we = round(we, 4)
                            if r_we <= r_ws:
                                r_we = round(r_ws + 0.01, 4)
                            words_list.append(
                                WordToken(
                                    id=f"{seg_id}_w_{s_idx}",
                                    text=span.token,
                                    normalized=span.normalized,
                                    start=r_ws,
                                    end=r_we,
                                    confidence=0.9,
                                )
                            )

                if not words_list:
                    continue

                words_list.sort(key=lambda w: (w.start, w.end))

                min_w_start = min(w.start for w in words_list)
                max_w_end = max(w.end for w in words_list)
                raw_seg_s = float(getattr(raw_seg, "start", min_w_start))
                raw_seg_e = float(getattr(raw_seg, "end", max_w_end))
                if math.isnan(raw_seg_s) or math.isinf(raw_seg_s):
                    raw_seg_s = min_w_start
                if math.isnan(raw_seg_e) or math.isinf(raw_seg_e):
                    raw_seg_e = max_w_end
                if raw_seg_s > raw_seg_e:
                    raw_seg_s, raw_seg_e = raw_seg_e, raw_seg_s
                if raw_seg_s < 0.0:
                    raw_seg_s = 0.0
                r_seg_start = round(min(raw_seg_s, min_w_start), 4)
                r_seg_end = round(max(raw_seg_e, max_w_end), 4)
                if r_seg_end <= r_seg_start:
                    r_seg_end = round(r_seg_start + 0.01, 4)

                result_segments.append(
                    ASRSegment(
                        id=seg_id,
                        start=r_seg_start,
                        end=r_seg_end,
                        text=seg_text,
                        words=words_list,
                    )
                )

            return result_segments
        except ASRError:
            raise
        except Exception as exc:
            raise ASRInferenceError(f"ASR segment normalization failed: {exc}") from exc

    def unload(self) -> None:
        """Clear model reference and flush CPU and GPU memory caches."""
        self._model = None
        gc.collect()
        try:
            import torch

            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except (ImportError, Exception):
            pass

    def __enter__(self) -> "WhisperTranscriber":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.unload()


def extract_vad_silences(
    audio_path: Path | str,
    min_silence_duration_ms: int = 400,
    vad_backend: Any | None = None,
) -> list[tuple[float, float]]:
    """Extract acoustic silence intervals using Silero-VAD.

    Returns a list of (start_seconds, end_seconds) tuples for pauses >= min_silence_duration_ms.
    """
    if not isinstance(audio_path, (str, Path)):
        raise AudioFormatError(f"audio_path must be a Path or str, got {type(audio_path).__name__}")
    if (
        isinstance(min_silence_duration_ms, bool)
        or not isinstance(min_silence_duration_ms, int)
        or min_silence_duration_ms <= 0
    ):
        raise ASRInferenceError("min_silence_duration_ms must be a positive integer")

    path = Path(audio_path)
    try:
        validate_wav(path, sample_rate=16000)
    except (FileNotFoundError, ValueError, OSError, RuntimeError, TypeError) as exc:
        raise AudioFormatError(f"Audio format validation failed for {path}: {exc}") from exc

    try:
        with wave.open(str(path), "rb") as wav:
            n_frames = wav.getnframes()
            sample_rate = wav.getframerate()
            raw_bytes = wav.readframes(n_frames)
    except (FileNotFoundError, ValueError, OSError, RuntimeError, wave.Error) as exc:
        raise AudioFormatError(f"Audio reading failed for {path}: {exc}") from exc

    duration = n_frames / float(sample_rate)
    min_silence_sec = min_silence_duration_ms / 1000.0

    try:
        if vad_backend is not None:
            samples = np.frombuffer(raw_bytes, dtype="<i2").astype(np.float32) / 32768.0
            if callable(vad_backend):
                try:
                    speech_chunks = vad_backend(
                        samples,
                        sample_rate=sample_rate,
                        min_silence_duration_ms=min_silence_duration_ms,
                    )
                except TypeError:
                    speech_chunks = vad_backend(str(path))
            elif hasattr(vad_backend, "get_speech_timestamps"):
                speech_chunks = vad_backend.get_speech_timestamps(samples)
            else:
                raise ASRInferenceError(f"Unsupported vad_backend type: {type(vad_backend)}")
        else:
            try:
                from faster_whisper.vad import VadOptions, get_speech_timestamps
            except ImportError as exc:
                raise ASRInferenceError(
                    "faster-whisper is required for VAD silence extraction. "
                    "Install with optional dependency: pip install local-subtitle-workbench[speech]"
                ) from exc

            samples = np.frombuffer(raw_bytes, dtype="<i2").astype(np.float32) / 32768.0
            vad_opts = VadOptions(min_silence_duration_ms=min_silence_duration_ms)
            try:
                try:
                    speech_chunks = get_speech_timestamps(samples, vad_options=vad_opts)
                except TypeError:
                    speech_chunks = get_speech_timestamps(samples, vad_opts)
            except Exception as exc:
                raise ASRInferenceError(f"Silero-VAD inference failed: {exc}") from exc

        if not speech_chunks:
            if duration >= min_silence_sec - 1e-6:
                r_dur = round(duration, 4)
                return [(0.0, r_dur)] if r_dur > 0.0 else []
            return []

        raw_pairs: list[tuple[float, float]] = []
        for c in speech_chunks:
            if isinstance(c, dict) and "start" in c and "end" in c:
                s_val = float(c["start"])
                e_val = float(c["end"])
                if math.isnan(s_val) or math.isnan(e_val) or math.isinf(s_val) or math.isinf(e_val):
                    raise ASRInferenceError(
                        "Silero-VAD chunk timestamps must be finite real numbers"
                    )
                raw_pairs.append((s_val, e_val))
            elif isinstance(c, (tuple, list)) and len(c) == 2:
                s_val = float(c[0])
                e_val = float(c[1])
                if math.isnan(s_val) or math.isnan(e_val) or math.isinf(s_val) or math.isinf(e_val):
                    raise ASRInferenceError(
                        "Silero-VAD chunk timestamps must be finite real numbers"
                    )
                raw_pairs.append((s_val, e_val))

        if not raw_pairs:
            if duration >= min_silence_sec - 1e-6:
                r_dur = round(duration, 4)
                return [(0.0, r_dur)] if r_dur > 0.0 else []
            return []

        # Distinguish sample indices from seconds:
        # Faster-Whisper Silero-VAD native output is always in sample indices.
        # Custom backends may return seconds or samples. Timestamps in seconds
        # can never exceed duration by > 2.0s or 20%.
        if vad_backend is None:
            is_sample_indices = True
        else:
            is_sample_indices = any(
                max(s, e) > max(duration + 2.0, duration * 1.2) for s, e in raw_pairs
            )

        normalized_chunks: list[tuple[float, float]] = []
        for s, e in raw_pairs:
            if s > e:
                s, e = e, s
            if is_sample_indices:
                s = s / float(sample_rate)
                e = e / float(sample_rate)
            s = max(0.0, min(duration, s))
            e = max(0.0, min(duration, e))
            if e > s:
                normalized_chunks.append((s, e))

        if not normalized_chunks:
            if duration >= min_silence_sec - 1e-6:
                r_dur = round(duration, 4)
                return [(0.0, r_dur)] if r_dur > 0.0 else []
            return []

        normalized_chunks.sort(key=lambda x: (x[0], x[1]))

        silences: list[tuple[float, float]] = []
        current_time = 0.0

        for s_start, s_end in normalized_chunks:
            if s_start > current_time:
                pause_dur = s_start - current_time
                if pause_dur >= min_silence_sec - 1e-6:
                    sil_s = round(current_time, 4)
                    sil_e = round(s_start, 4)
                    if sil_e > sil_s:
                        silences.append((sil_s, sil_e))
            current_time = max(current_time, s_end)

        if duration > current_time:
            pause_dur = duration - current_time
            if pause_dur >= min_silence_sec - 1e-6:
                sil_s = round(current_time, 4)
                sil_e = round(duration, 4)
                if sil_e > sil_s:
                    silences.append((sil_s, sil_e))

        return silences
    except ASRError:
        raise
    except Exception as exc:
        if _is_vram_allocation_error(exc):
            raise VRAMAllocationError(f"Silero-VAD VRAM allocation failed: {exc}") from exc
        raise ASRInferenceError(f"Silero-VAD processing failed: {exc}") from exc
