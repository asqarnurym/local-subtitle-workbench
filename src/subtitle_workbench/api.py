"""FastAPI microservice for local subtitle forced alignment.

Provides HTTP REST endpoints for automated speech-text alignment, generating
W3C WCAG 2.1 Media Accessibility JSON-LD and WebVTT karaoke subtitles for
Learning Management Systems (LMS).
"""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, File, Form, HTTPException, UploadFile, status
from fastapi.responses import JSONResponse

from . import __version__
from .pipeline import run_speech_pipeline

app = FastAPI(
    title="Local Subtitle Alignment Workbench API",
    version=__version__,
    description=(
        "Offline speech-to-text forced alignment microservice ensuring cognitive "
        "accessibility in educational media (W3C WCAG 2.1 compliant)."
    ),
)


@app.get("/health", summary="Health Check")
async def health_check() -> dict[str, str]:
    """Verify service health and readiness."""
    return {
        "status": "healthy",
        "service": "subtitle-workbench",
        "version": __version__,
    }


@app.get("/info", summary="Service Capabilities & Configuration")
async def service_info() -> dict[str, Any]:
    """Return supported alignment engines and export formats."""
    return {
        "version": __version__,
        "supported_engines": ["auto", "mfa", "ctc"],
        "default_engine": "auto",
        "constraints": {
            "max_chunk_sec": 30.0,
            "min_silence_sec": 0.4,
            "overlap_padding_sec": 0.5,
            "vram_limit_gb": 1.85,
        },
        "export_formats": ["vtt", "jsonld", "alignment_raw", "manifest"],
    }


@app.post("/align-speech", summary="Align Speech Audio to Subtitle Text")
async def align_speech_endpoint(
    audio: UploadFile = File(..., description="16-bit 16kHz mono PCM WAV audio file"),  # noqa: B008
    transcript: str | None = Form(  # noqa: B008
        None, description="Verbatim lecture transcript (if omitted, Whisper ASR transcribes)"
    ),
    engine: Literal["auto", "mfa", "ctc"] = Form(  # noqa: B008
        "auto", description="Forced alignment engine (auto, mfa, ctc)"
    ),
    vad_silence_min_sec: float = Form(0.4, description="Minimum silence duration for VAD splits"),  # noqa: B008
    max_chunk_sec: float = Form(30.0, description="Maximum duration per macro chunk"),  # noqa: B008
    chunk_padding_sec: float = Form(0.5, description="Contextual overlap padding"),  # noqa: B008
) -> JSONResponse:
    """Execute end-to-end alignment pipeline on uploaded audio."""
    if engine not in ("auto", "mfa", "ctc"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported engine: '{engine}'. Must be 'auto', 'mfa', or 'ctc'.",
        )
    if vad_silence_min_sec <= 0.0 or max_chunk_sec <= 0.0 or chunk_padding_sec < 0.0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Timing parameters must be strictly positive (padding nonnegative).",
        )

    # Use a secure isolated temporary working directory
    with tempfile.TemporaryDirectory(prefix="wb_api_") as temp_dir_str:
        temp_dir = Path(temp_dir_str)
        audio_save_path = temp_dir / "input_audio.wav"
        output_dir = temp_dir / "aligned_outputs"

        try:
            # Stream uploaded file to disk
            with audio_save_path.open("wb") as buffer:
                shutil.copyfileobj(audio.file, buffer)

            # Execute pipeline
            manifest = run_speech_pipeline(
                audio_path=audio_save_path,
                output_dir=output_dir,
                transcript=transcript,
                engine=engine,
                vad_silence_min_sec=vad_silence_min_sec,
                max_chunk_sec=max_chunk_sec,
                chunk_padding_sec=chunk_padding_sec,
                fallback_to_ctc=True,
            )

            # Read back generated artifacts
            vtt_path = output_dir / "subtitles.vtt"
            jsonld_path = output_dir / "timeline.jsonld"
            raw_path = output_dir / "alignment_raw.json"

            vtt_content = vtt_path.read_text(encoding="utf-8") if vtt_path.exists() else ""
            jsonld_content = (
                json.loads(jsonld_path.read_text(encoding="utf-8")) if jsonld_path.exists() else {}
            )
            raw_content = (
                json.loads(raw_path.read_text(encoding="utf-8")) if raw_path.exists() else []
            )

            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={
                    "status": "success",
                    "filename": audio.filename,
                    "engine_used": manifest.get("pipeline", {}).get("engine", engine),
                    "subtitles_vtt": vtt_content,
                    "timeline_jsonld": jsonld_content,
                    "alignment_raw": raw_content,
                    "manifest": manifest,
                },
            )

        except ValueError as val_err:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Audio processing error: {val_err}",
            ) from val_err
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Internal alignment error: {exc}",
            ) from exc
