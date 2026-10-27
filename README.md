# Local Subtitle Alignment Workbench

An offline hierarchical subtitle synchronization system for generating millisecond-accurate educational subtitles on consumer workstation hardware. Author: Askar Nurym (Astana IT University).

The workbench provides an end-to-end local speech pipeline: Voice Activity Detection (VAD), Automated Speech Recognition (ASR), banded Dynamic Time Warping (DTW) with contextual overlap padding, and forced phonetic alignment via Montreal Forced Aligner (Kaldi GMM-HMM) or PyTorch CTC Trellis (Meta MMS_FA). Outputs include standard WebVTT subtitles, W3C WCAG 2.1 Media Accessibility JSON-LD timelines, and cryptographic audit manifests.

## System Architecture

```
 Audio Input (16 kHz PCM WAV)
         │
         ▼
 [1. Silero-VAD] ──────────► Acoustic pause detection & chunking (audio.py)
         │
         ▼
 [2. Faster-Whisper ASR] ──► Large-v3 INT8 transcription & initial timestamps (asr.py)
         │                   (Deterministic VRAM unload: gc.collect() & cuda.empty_cache())
         ▼
 [3. Banded Macro-DTW] ────► Monotone sequence alignment with overlap padding (dtw.py)
         │
         ▼
 [4. Forced Alignment] ────► Dual-Engine Alignment Facade (alignment.py)
         │                   ├─ Mode B: Montreal Forced Aligner (Kaldi GMM-HMM batch staging)
         │                   └─ Mode A: TorchAudio MMS_FA CTC Trellis (in-process fallback)
         ▼
 [5. Exporters] ───────────► WebVTT, WCAG 2.1 JSON-LD, and SHA-256 Manifest (export.py)
         │
         ▼
 [6. Delivery Layers] ─────► Local CLI, FastAPI REST service (api.py), Docker container
```

| Module | Responsibility | Key Contracts & Invariants |
| --- | --- | --- |
| `audio.py` | Audio ingestion & Silero-VAD | Mono PCM16 16 kHz; pause-delimited acoustic chunks $\le 30.0$ s |
| `asr.py` | Faster-Whisper ASR | Large-v3 INT8 CTranslate2; deterministic VRAM lifecycle |
| `dtw.py` | Banded Dynamic Time Warping | Monotone alignment path; bounded band around diagonal ($O(T \cdot B)$) |
| `alignment.py` | Forced phonetic alignment | MFA CLI batch staging (`temp/mfa_staging_*`) & MMS_FA CTC Trellis |
| `pipeline.py` | Orchestration & provenance | End-to-end execution `run_speech_pipeline`; input/output SHA-256 manifest |
| `export.py` | Standardized subtitle export | WebVTT karaoke cues, schema.org / WCAG 2.1 `VideoObject` JSON-LD |
| `api.py` | FastAPI microservice | Asynchronous job runner, background worker, multipart uploads |
| `metrics.py` | Benchmark evaluation | Boundary MAE, Acc@20ms/50ms/100ms, clustered bootstrap CI, Wilcoxon with Holm adjustment |
| `corpora.py` | Standard corpus parsers | NIST TIMIT Core Test (`.phn`, `.wrd`), Buckeye Praat TextGrid, synthetic generator |

## Status of Evaluation

- **Harness Implementation:** The automated empirical benchmark suite (`scripts/speech_benchmark.py`), statistical significance module (`metrics.py`), and LaTeX table generator (`scripts/generate_paper_tables.py`) are fully implemented and verified via comprehensive unit and challenger tests.
- **Real Corpus Results (UNMEASURED / PENDING_EXPERIMENT):** No empirical results on real speech corpora (DARPA/NIST TIMIT Core Test or Buckeye Speech Corpus) have been executed yet. The author is responsible for obtaining and mounting licensed corpus archives in `data/corpora/timit` and `data/corpora/buckeye`.
- **Synthetic Pipeline Self-Test:** The `--offline-synthetic` mode (`dist/benchmark_demo`) uses a deterministic 10-utterance acoustic slice to verify pipeline data flow, metric calculation math, and LaTeX generation. It does **not** execute real speech models and must **not** be cited as empirical performance. All unbacked metrics from prior preliminary drafts have been retracted (see [INCREMENT_6R](docs/increments/INCREMENT_6R_INTEGRITY_REMEDIATION.md)).

## Installation

Requirements: Python 3.11 or 3.12 and `uv`. Base installation runs entirely offline with zero GPU dependencies (pure Python + NumPy + SciPy).

```sh
# Base environment (audio ingestion, DTW, exporters, CLI, benchmark harness)
uv sync --locked

# Speech models extra (Faster-Whisper, PyTorch, TorchAudio MMS_FA)
uv sync --locked --extra speech

# Web API extra (FastAPI, Uvicorn, HTTPX)
uv sync --locked --extra api

# All extras
uv sync --locked --all-extras
```

### Montreal Forced Aligner (Optional External Toolchain)
For sub-20ms GMM-HMM phonetic alignment (Mode B), install Montreal Forced Aligner via Conda on Windows 11:
```powershell
conda create -n mfa -c conda-forge montreal-forced-aligner
conda activate mfa
mfa model download acoustic english_mfa
mfa model download dictionary english_mfa
```
The workbench auto-detects `mfa` on PATH; if absent, it gracefully falls back to in-process TorchAudio CTC Trellis (Mode A).

## Usage

### 1. Command Line Interface (CLI)
```sh
# End-to-end speech pipeline (ASR + DTW + Forced Alignment)
uv run subtitle-workbench align-speech --audio lecture.wav --engine ctc --output-dir out/

# Audio-to-audio timing transfer (DTW reference-to-target)
uv run subtitle-workbench align-audio --reference ref.wav --target tgt.wav --cues cues.json --output out/
```

### 2. FastAPI REST Microservice
```sh
uv run uvicorn subtitle_workbench.api:app --host 127.0.0.1 --port 8000
```
Open interactive Swagger documentation at `http://127.0.0.1:8000/docs`.

### 3. Pipeline Self-Test & Benchmark Harness
```sh
# Run deterministic synthetic pipeline self-test
uv run python scripts/speech_benchmark.py --offline-synthetic --output-dir dist/benchmark_demo

# Generate publication LaTeX tables (requires --allow-simulated for synthetic runs)
uv run python scripts/generate_paper_tables.py --input dist/benchmark_demo/benchmark_results.json --output-dir docs/paper --allow-simulated
```

## Verification and Continuous Integration

All code passes strict quality gates: linting, formatting, type contracts, offline network isolation, and automated tests.

```sh
# Linting & formatting
uv run --locked ruff check .
uv run --locked ruff format --check .

# Full test suite (offline, socket-guarded)
uv run --locked pytest

# Standalone wheel packaging and offline smoke test
uv run --locked python -m build --wheel --no-isolation
uv run python scripts/smoke_wheel.py --wheel dist/local_subtitle_workbench-0.1.0-py3-none-any.whl --output dist/smoke_out
```

## Hardware Budget and Resource Management

- **Target Workstation:** AMD Ryzen 9 5900HX, 16 GB Host RAM, NVIDIA GeForce RTX 3050 Laptop GPU (4 GB VRAM limit, Windows 11).
- **VRAM Lifecycle Management:** Models are loaded sequentially. After ASR transcription, Faster-Whisper is unloaded, and Python garbage collection plus `torch.cuda.empty_cache()` are explicitly invoked before forced alignment runs, capping sequential peak allocation under 1.85 GB VRAM.
- **Privacy & Offline Integrity:** Zero external cloud API calls or telemetry. The application executes entirely on local hardware.

## License

MIT License. See [LICENSE](LICENSE).
