# Briefing: Implementer Increment 2 (ASR & VAD)

## Mission
Implement Increment 2 for the Local Subtitle Alignment Workbench:
- Faster-Whisper Large-v3 INT8 transcriber
- Silero-VAD pause / silence detection
- Deterministic GPU memory lifecycle management (unloading, gc.collect, cuda.empty_cache)
- Strict compliance with ECC standards (TDD Workflow, Error Handling, Verification Loop)
- Offline-first execution: base package remains lightweight, all torch/faster-whisper dependencies are optional/lazy.

## Branch & Constraints
- Git branch: `feature/increment-2-asr-and-vad`
- Working directory: `C:\Users\nurym\Desktop\local-subtitle-workbench`
- Hardware: NVIDIA GeForce RTX 3050 Laptop GPU (4 GB VRAM)
- Memory bound: peak VRAM <= 1.85 GB for Faster-Whisper Large-v3 INT8
- Device auto-selection: `cuda` if available else `cpu`
- Compute type: `int8_float16` for CUDA, `int8` for CPU
- Base test suite must run offline on CPU without torch or faster-whisper installed.
