# System Architecture & Technical Blueprint
**Project:** Local Subtitle Alignment Workbench  
**Scientific Context:** Master's Thesis & Scientific Publication 2 (Astana IT University)  
**Author:** Askar Nurym  
**Target Platform:** AMD Ryzen 9 5900HX, 16 GB RAM, NVIDIA RTX 3050 Laptop GPU (4 GB VRAM), Windows 11  
**Status:** Approved Technical Design

---

## 1. Architectural Overview & System Mission

The **Local Subtitle Alignment Workbench** is an offline, modular Python system designed to synchronize spoken audio with textual subtitles at millisecond precision for educational multimedia accessibility.

In strict compliance with the Master's Individual Plan, the workbench integrates three foundational technologies into a unified hierarchical pipeline:
1. **Automatic Speech Recognition (ASR):** OpenAI Whisper (via `faster-whisper` CTranslate2 INT8) for verbatim transcription and initial segment timestamps.
2. **Macro-Alignment & Segmentation (DTW):** Bounded Dynamic Time Warping (`dtw.py`) with Silero-VAD silence boundary anchoring to eliminate temporal drift on long educational recordings.
3. **Forced Alignment (MFA & CTC Trellis):** Montreal Forced Aligner (Kaldi GMM-HMM + CMUDict) as the primary phonetic scientific engine, with an in-process PyTorch CTC Trellis (`torchaudio MMS_FA`) fallback.

```
                           HIERARCHICAL SYSTEM TOPOLOGY
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                                STAGE 1: INGESTION                                      │
│  [16 kHz Mono PCM WAV] ──► [Silero-VAD Detector] ──► Acoustic Silence Intervals        │
└───────────────────────────────────────────┬────────────────────────────────────────────┘
                                            ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                              STAGE 2: ASR & TEXT SPANS                                 │
│  Faster-Whisper Large-v3 INT8 (GPU) ──► Word/Segment Timestamps ──► Token Span Mapping │
└───────────────────────────────────────────┬────────────────────────────────────────────┘
                                            ▼ (VRAM Unload: torch.cuda.empty_cache())
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        STAGE 3: MACRO-DTW & BOUNDED CHUNKING                           │
│  Partitioning (L <= 30s) + Overlap (Δ_pad = 0.5s) ──► Banded DTW (dtw.py) Drift Stitch │
└───────────────────────────────────────────┬────────────────────────────────────────────┘
                                            ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                         STAGE 4: FORCED ALIGNMENT (PHONETIC & WORD)            │
│       Mode B (Primary): Montreal Forced Aligner (Kaldi HMM-GMM) ──► Phonemes (<20ms)   │
│       Mode A (Fallback): TorchAudio MMS_FA (CTC Trellis DP)    ──► Words (<50ms)       │
└───────────────────────────────────────────┬────────────────────────────────────────────┘
                                            ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                             STAGE 5: ARTIFACT EXPORT                                   │
│  • subtitles.vtt (Karaoke <c> tags)        • alignment_raw.json (Scientific Research)  │
│  • timeline.jsonld (schema.org Video/Clip) • manifest.json (SHA-256 Audit Trail)       │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Scientific & Engineering Justification of Selected Components

Every component in the architecture is chosen based on empirical trade-offs between accuracy, computational complexity, memory boundaries, and reproducibility on the target hardware.

| Stage | Chosen Component | Alternative Considered | Scientific & Practical Justification |
| :--- | :--- | :--- | :--- |
| **Audio Ingestion** | **Pure Python `wave` (PCM16 16kHz)** | `FFmpeg` / `PyAV` subprocess | • **Zero external dependency:** Operates natively without system binaries or DLL conflicts.<br>• **Deterministic memory:** Strict header inspection rejects invalid rates or channels before allocation.<br>• **Audio fidelity:** Guarantees uncompressed, un-resampled PCM data for downstream models. *(FFmpeg is maintained in the backlog as an optional containerized preprocessor).* |
| **VAD** | **Silero-VAD v4 (ONNX / TorchScript)** | Energy thresholding / WebRTC VAD | • **Acoustic robustness:** Silero-VAD is trained on diverse noisy audio (SNR 10–30 dB) and reliably detects natural pause boundaries without false positives on breath/reverberation.<br>• **Lightweight:** Evaluates 30 ms windows in $<1\text{ ms}$ on CPU. |
| **ASR** | **Faster-Whisper Large-v3 (INT8)** | Vanilla Whisper / Distil-Whisper / whisper.cpp / NeMo Parakeet-TDT | • **Memory Sizing:** Large-v3 INT8 via CTranslate2 consumes **~1.85 GB VRAM**, fitting comfortably into our 4.0 GB GPU limit (Vanilla FP16 requires $>3.2\text{ GB}$).<br>• **Execution Speed:** 3.5x faster decoding than Vanilla Whisper on NVIDIA Turing/Ampere tensor cores.<br>• **Transcription Fidelity:** Retains SOTA low WER on accented academic speech.<br>• **Accessibility Alternatives:** `whisper.cpp` provides pure-CPU offline fallback for low-resource student laptops without dedicated GPUs; `Parakeet-TDT` provides a non-autoregressive Transducer benchmark in the analogs backlog. |
| **Macro Alignment** | **Banded DTW with Overlap Padding (`dtw.py`)** | Global Unbounded DTW / FastDTW | • **Memory Bound:** Unbounded DTW on a 60-min lecture ($180,000 \times 180,000$) requires $\approx 32.4\text{ GB}$ of RAM ($O(T \times U)$).<br>• **Banded DP:** Bandwidth of $\pm 0.5\text{ s}$ around diagonal bounds evaluated cells to $<2,000,000$ ($O(T \cdot B)$), keeping memory $<15\text{ MB}$.<br>• **Chunk Padding:** $0.5\text{ s}$ context padding prevents acoustic truncation at chunk borders. |
| **Forced Alignment** | **Montreal Forced Aligner (Kaldi GMM-HMM)** | TorchAudio MMS_FA / Charsiu / Gentle | • **Target Granularity:** MFA models acoustic transitions down to individual **phoneme states** via triphone acoustic models and CMUDict pronunciation lexicon, enabling the thesis target of $<20\text{ ms}$ error.<br>• **Academic Gold Standard:** Universally recognized in speech and linguistic science (McAuliffe et al., 2017). |
| **Alignment Fallback** | **TorchAudio `MMS_FA` (CTC Trellis)** | Wav2Vec2-base / Kaldi-C++ in-process | • **Self-Contained Execution:** 100% PyTorch in-process execution without external Conda/Kaldi dependencies for CI/CD and rapid word-level testing.<br>• **Character Vocabulary:** Evaluates Trellis dynamic programming over character emission matrices. |

### 2.1 Montreal Forced Aligner (MFA) Operational Architecture & Windows 11 Toolchain

In speech science, Montreal Forced Aligner (McAuliffe et al., Interspeech 2017) is an open-source orchestration tool around compiled **Kaldi C++ binaries** (`compute-mfcc-feats`, `compile-train-graphs`, `gmm-align-compiled`) using GMM-HMM acoustic models and the CMUDict pronunciation lexicon.

Two critical architectural decisions govern MFA in this workbench:
1. **External CLI Integration (No PyPI Dependency):**  
   Kaldi C++ binaries and OpenFST DLLs on Windows 11 are distributed via `conda-forge`. MFA **cannot** be packaged as a direct wheel in `pyproject.toml` (which uses Python 3.12 with `uv`). The workbench interfaces with MFA as an external CLI tool (`mfa.exe`) via `subprocess.run`, gracefully detecting its presence on system PATH (`check_mfa_available()`).
2. **Corpus Staging Batch Architecture (Overhead Prevention):**  
   Each invocation of `mfa align` incurs 10–15 seconds of process startup latency (Python CLI bootstrap, SQLite dictionary cache, Kaldi initialization). Spawning MFA per 30-second chunk in a loop would introduce disastrous overhead (50 chunks $\times$ 12s = 600s). The workbench stages all audio chunks into a temporary corpus directory (`temp/mfa_staging_<uuid>/corpus/chunk_0000.wav`, `.lab`), executes `mfa align` **once per document** (~22s total for 50 chunks), and parses the resulting Praat `.TextGrid` files.
3. **Tripartite Dual-Engine Coexistence:**  
   - **Mode B (MFA):** Primary scientific benchmark fulfilling the AITU Master's Individual Plan for sub-20ms phoneme boundaries.  
   - **Mode A (MMS_FA CTC Trellis):** Self-contained, in-process PyTorch dynamic programming fallback for zero-dependency execution.  
   - **Publication 2:** The direct empirical benchmark comparing Kaldi GMM-HMM vs Neural CTC Trellis on accented educational speech forms the core experimental contribution for the *Scientific Journal of Astana IT University*.

---

## 3. Hardware & VRAM Memory Budget (NVIDIA RTX 3050 Laptop 4 GB)

To prevent CUDA Out-Of-Memory (OOM) crashes, the pipeline enforces **Strict Sequential Execution** with explicit garbage collection and cache flushing between stages.

```
                           GPU VRAM TIMELINE (BUDGET: 4.0 GB)
VRAM (GB)
 4.0 ┌──────────────────────────────────────────────────────────── (Hard GPU Limit)
 3.5 ┌ - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - (Safe Headroom)
 3.0 │
 2.5 │
 2.0 │     ┌──────────────┐
     │     │Faster-Whisper│
 1.5 │     │Large-v3 INT8 │                          ┌──────────────┐
     │     │  (~1.85 GB)  │                          │  MMS_FA /    │
 1.0 │     │              │                          │  PyTorch GPU │
     │     │              │     (torch.cuda.empty)   │  (~1.45 GB)  │
 0.5 │     │              │ ──► [VRAM FLUSHED]   ──► │              │
 0.0 └─────┴──────────────┴──────────────────────────┴──────────────┴──────── Time
        Stage 2 (ASR)          Inter-Stage            Stage 4 (Align)
```

| Pipeline Stage | Active Component | Hardware Device | Working Memory | Peak VRAM | Status vs 4.0 GB Budget |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **1. Audio Ingestion** | `load_wav` / Silero-VAD | CPU (NumPy/ONNX) | ~60 MB RAM | 0.0 GB | Safe |
| **2. Transcription (ASR)** | Faster-Whisper Large-v3 INT8 | GPU (CUDA 12.4) | ~1.85 GB VRAM | **1.85 GB** | **46.2% of VRAM (Safe)** |
| **-- Inter-Stage Cleanup --** | `del model; gc.collect(); torch.cuda.empty_cache()` | CPU / GPU | - | **<0.15 GB** | Cleared |
| **3. Macro-DTW** | Banded DTW (`dtw.py`) | CPU (NumPy) | ~45 MB RAM | 0.0 GB | Safe |
| **4. Forced Alignment: MFA (Mode B)** | MFA (Kaldi Subprocess) | CPU (Kaldi C++) | ~400 MB RAM | 0.0 GB | Safe (Zero VRAM) |
| **4. Forced Alignment: CTC (Mode A)** | MMS_FA (TorchAudio CTC) | GPU (CUDA 12.4) | ~1.45 GB VRAM | **1.45 GB** | **36.2% of VRAM (Safe)** |
| **5. Artifact Export** | WebVTT / JSON-LD / Manifest | CPU (Python) | ~10 MB RAM | 0.0 GB | Safe |

*Maximum concurrent VRAM allocation at any point in the pipeline is $\max(1.85, 1.45) = 1.85\text{ GB} \le 3.5\text{ GB}$.*

---

## 4. Sequence of Operations (Data Flow Contract)

```mermaid
sequenceDiagram
    autonumber
    actor User as User / CLI
    participant Ingest as Audio & VAD (audio.py)
    participant ASR as Faster-Whisper (asr.py)
    participant Norm as Normalizer (text_norm.py)
    participant DTW as Macro Chunker & DTW (dtw.py)
    participant Align as Forced Aligner (mfa_wrapper.py)
    participant Export as Exporter (export.py)

    User->>Ingest: Ingest 16 kHz Mono WAV
    Ingest->>Ingest: Detect silence intervals (Silero-VAD)
    Ingest->>ASR: Pass clean audio samples
    ASR->>ASR: Transcribe audio (Large-v3 INT8)
    ASR->>Norm: Return coarse segments & words
    ASR->>ASR: Unload Whisper from GPU VRAM
    Norm->>DTW: Normalized token spans + silence anchors
    DTW->>DTW: Partition chunks (L <= 30s) with 0.5s padding
    DTW->>Align: Pass acoustic chunks & corresponding text
    alt Mode B: Montreal Forced Aligner
        Align->>Align: Stage chunks into temp corpus (.wav + .lab) & run batch MFA
        Align->>Align: Parse output TextGrids to phonemes (<20ms)
    else Mode A: CTC Trellis Fallback
        Align->>Align: Run MMS_FA CTC Trellis dynamic programming
        Align->>Align: Aggregate character frames to word bounds
    end
    Align->>Export: Return refined word & phoneme intervals
    Export->>Export: Generate WebVTT (karaoke tags) & JSON-LD
    Export->>Export: Compute SHA-256 manifest & runtime metrics
    Export-->>User: Output subtitles.vtt, timeline.jsonld, manifest.json
```

---

## 5. Module Contracts & Data Structures

### 5.1 Typed Data Models (`models.py`)
```python
@dataclass(frozen=True)
class WordToken:
    id: str
    text: str
    start: float
    end: float
    confidence: float
    phonemes: list["PhonemeCue"] = field(default_factory=list)


@dataclass(frozen=True)
class PhonemeCue:
    phoneme: str
    start: float
    end: float
    confidence: float


@dataclass(frozen=True)
class ASRSegment:
    id: str
    start: float
    end: float
    text: str
    words: list[WordToken]


@dataclass(frozen=True)
class AlignmentResult:
    words: list[WordToken]
    phonemes: list[PhonemeCue]
    alignment_method: str  # "mfa_hmm" or "mms_ctc"
    path_cost: float
    evaluated_cells: int
```

### 5.2 Text Normalization Contract (`text_norm.py`)
To prevent the non-bijective token mapping bug identified in audit finding F11, normalization maps tokens at the **word level**, maintaining an explicit mapping between verbatim tokens and normalized acoustic representations:
- Verbatim: `"At 21st century, don't stop."`
- Normalized: `["at", "twenty", "first", "century", "do", "not", "stop"]`
- Mapping: Explicit span index list associating normalized tokens with verbatim word boundaries.
