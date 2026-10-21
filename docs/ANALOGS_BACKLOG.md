# Analogs & Alternatives Backlog: Component Ablation & Benchmark Suite
**Project:** Local Subtitle Alignment Workbench  
**Author:** Askar Nurym  
**Target Repository:** `local-subtitle-workbench`  
**Status:** Research & Engineering Backlog (Non-Blocking for Initial SDLC Prototype)

---

## 1. Purpose & Methodological Framework

While the main SDLC roadmap delivers the primary proven architecture (Native `wave` + Silero-VAD + `faster-whisper` Large-v3 INT8 + Banded DTW + Montreal Forced Aligner), sound scientific methodology requires systematic evaluation against technological analogs.

This document formalizes the **Analogs Backlog**:
1. It inventories competitive algorithms and modern libraries for every pipeline node.
2. It defines scientific hypotheses regarding performance, quality, and resource trade-offs.
3. It specifies an **Isolated Simulation Testbed Protocol** to benchmark each analog on a standardized small calibration subset without polluting or destabilizing the core codebase.

---

## 2. Pipeline Node Inventory & Analog Matrix

```
                       PIPELINE NODES & ANALOG SPECTRUM
Node 1: Ingestion      [Native wave]  ◄──vs──►  [FFmpeg CLI / PyAV / librosa]
Node 2: VAD            [Silero-VAD]   ◄──vs──►  [WebRTC VAD / PyAnnote / Energy]
Node 3: ASR Engine     [Faster-Whisper]◄─vs──►  [Whisper / whisper.cpp / Distil-Whisper / Parakeet / Canary]
Node 4: Macro DTW      [Banded DTW]   ◄──vs──►  [FastDTW / ASR-anchor linear interpolation]
Node 5: Forced Align   [MFA (Kaldi)]  ◄──vs──►  [TorchAudio MMS_FA / Charsiu / Gentle]
Node 6: Serialization  [Custom HalfUp]◄──vs──►  [WebVTT-py / PySRT / ffmpeg subtitler]
```

---

## 3. Node-by-Node Analysis & Isolated Benchmark Tasks

### Node 1: Audio Ingestion & Resampling
- **Primary Method:** Native Python `wave` module.
  - *Properties:* Pure standard library, zero external binary dependency, strict PCM16 validation. Rejects non-16kHz audio before memory allocation.
- **Backlog Analogs:**
  1. `analog-1a: ffmpeg_subprocess` — Spawns `ffmpeg.exe` to decode any container (MP4, MKV, MP3, AAC) and resample with `soxr` filter to 16 kHz mono PCM.
  2. `analog-1b: pyav_stream` — In-process C-bindings to FFmpeg (av library) via Python.
  3. `analog-1c: torchaudio_sox` — `torchaudio.load` using Sox / Torch backend.
- **Scientific Questions:**
  - Does native `wave` loading save $>150\text{ ms}$ process spawn overhead per invocation compared to `ffmpeg.exe`?
  - Does high-quality `soxr` sinc resampling in FFmpeg yield lower downstream WER than linear interpolation on 44.1 kHz lecture audio?
- **Isolated Simulation Protocol (`tests/analogs/test_ingestion_analogs.py`):**
  - Run each analog over 5 test audio files (sample rates: 16kHz, 44.1kHz, 48kHz; containers: WAV, MP4, MP3).
  - Measure: Wall-clock ingestion latency (ms), Peak RAM (MB), Audio sample SNR against reference PCM.

---

### Node 2: Voice Activity Detection (VAD)
- **Primary Method:** Silero-VAD v4 (ONNX Runtime / TorchScript).
  - *Properties:* Deep neural network trained on massive diverse acoustic domains; frame resolution: 30 ms.
- **Backlog Analogs:**
  1. `analog-2a: webrtc_vad` — Gaussian Mixture Model VAD used in WebRTC telephony (aggressiveness 0–3, 10–30 ms frames).
  2. `analog-2b: energy_zero_crossing` — Classical DSP thresholding on Short-Time Energy (STE) and Zero-Crossing Rate (ZCR).
  3. `analog-2c: pyannote_vad` — SOTA neural segmentation model (BiLSTM / SincNet).
- **Scientific Questions:**
  - Does WebRTC-VAD fail on low-energy lecture consonants and trailing vowel fades compared to Silero?
  - Does PyAnnote provide superior pause boundaries at the expense of excessive GPU VRAM consumption ($>800\text{ MB}$)?
- **Isolated Simulation Protocol (`tests/analogs/test_vad_analogs.py`):**
  - Evaluate on 10 minutes of auditorium lecture audio with classroom background murmur (SNR 15 dB).
  - Measure: Speech boundary Precision / Recall against manual silence labels, processing RTF.

---

### Node 3: Speech Recognition (ASR Engine)
- **Primary Method:** `faster-whisper` Large-v3 (CTranslate2 INT8 quantized).
  - *Properties:* Fast inference via custom 8-bit matrix multiplication kernels, ~1.85 GB VRAM allocation.
- **Backlog Analogs:**
  1. `analog-3a: vanilla_openai_whisper` — Official PyTorch FP16 / FP32 implementation from OpenAI repository.
  2. `analog-3b: whisperx_batched` — Batched inference using HuggingFace Transformers pipeline + VAD chunking.
  3. `analog-3c: distil_whisper` — Knowledge-distilled Whisper (6x faster decoder, 50% fewer parameters).
  4. `analog-3d: conformer_ctc` — NeMo Conformer-CTC (non-autoregressive, zero hallucination loops).
  5. `analog-3e: whisper_cpp` — Georgi Gerganov's pure C/C++ GGML port of Whisper with 4-bit/5-bit quantization. **Crucial for universal educational accessibility:** enables local offline transcription on standard student laptops with integrated graphics (pure CPU execution without CUDA/GPU or heavy PyTorch runtimes).
  6. `analog-3f: parakeet_tdt` — NVIDIA NeMo Parakeet-TDT 1.1B (FastConformer architecture with Token-and-Duration Transducer). Evaluates single-pass non-autoregressive transcription where token acoustic durations are natively emitted by the decoder.
  7. `analog-3g: canary_1b` — NVIDIA Canary-1B (FastConformer encoder + Transformer decoder with multi-task punctuation, capitalization, and multilingual transcription).
  8. `analog-3h: audio_llm_qwen2_audio` — Alibaba Qwen2-Audio (Audio-Language Model baseline). Used to benchmark generative LLM audio comprehension versus classical acoustic ASR pipelines in terms of VRAM consumption, latency, and hallucination rates.
- **Scientific Questions:**
  - Does INT8 quantization in CTranslate2 degrade transcription accuracy (WER) on technical computer science lectures relative to FP16 PyTorch?
  - Can Distil-Whisper reach $\text{RTF} < 0.08$ on RTX 3050 without degrading Word Error Rate beyond $+1.0\%$ absolute?
  - Can `whisper.cpp` with 4-bit / 5-bit quantization on an 8-core CPU provide acceptable RTF ($< 0.3$) for offline student accessibility without any dedicated GPU hardware?
  - Do non-autoregressive Transducer models (Parakeet-TDT) eliminate the acoustic time-warping drift inherent in attention-based Whisper decoders?
  - What are the memory, latency, and hallucination trade-offs of generative Audio-LLMs (Qwen2-Audio) compared to bounded pipeline architectures (Whisper + MFA) for millisecond subtitle synchronization?
- **Isolated Simulation Protocol (`tests/analogs/test_asr_analogs.py`):**
  - Evaluate on 3 benchmark lecture recordings (10 minutes total).
  - Measure: WER (%), Memory Peak VRAM (GB), CPU RAM (GB), Inference RTF on both RTX 3050 GPU and pure CPU.

---

### Node 4: Macro-Alignment & Drift Correction
- **Primary Method:** Banded Dynamic Time Warping (`dtw.py`) over standardised log RMS energy and spectral centroid features.
  - *Properties:* Monotone complete path with deterministic tie-breaking and $O(T \cdot B)$ memory bounds.
- **Backlog Analogs:**
  1. `analog-4a: fast_dtw` — Multilevel downsample-and-refine approximation (Salvador & Chan).
  2. `analog-4b: asr_anchor_interp` — Pure piecewise linear interpolation between confident ASR segment timestamps without acoustic feature comparison.
  3. `analog-4c: chromagram_dtw` — DTW over 12-dimensional pitch chroma features (Librosa).
- **Scientific Questions:**
  - Does FastDTW introduce boundary discretization errors ($>40\text{ ms}$) near coarse-grid resolution steps?
  - Is acoustic energy DTW superior to pure ASR anchor interpolation when an educational video contains teacher pauses or audio edits?
- **Isolated Simulation Protocol (`tests/analogs/test_macro_dtw_analogs.py`):**
  - Run on synthetic stretched fixtures and real audio pairs with non-linear pacing variations.
  - Measure: Mean Absolute Timing Error (ms), Number of evaluated cells, Runtime (ms).

---

### Node 5: Forced Alignment (Core Scientific Node)
- **Primary Method:** Montreal Forced Aligner (Kaldi GMM-HMM + CMUDict acoustic models).
  - *Properties:* Standard phonetic science benchmark; models sub-phonemic states down to 10 ms resolution.
- **Backlog Analogs:**
  1. `analog-5a: mms_fa_ctc` — Meta TorchAudio `MMS_FA` (Wav2Vec2 300M multi-lingual CTC Trellis).
  2. `analog-5b: charsiu_phoneme_ctc` — Charsiu (Wav2Vec2 fine-tuned explicitly on ARPAbet phoneme classification).
  3. `analog-5c: gentle_aligner` — Kaldi Dnn-HMM forced aligner wrapper (used in commercial video editing).
  4. `analog-5d: whisper_cross_attention_dtw` — Native Faster-Whisper word timestamps extracted from cross-attention weights.
- **Scientific Questions:**
  - Can neural CTC models (`charsiu` / `MMS_FA`) match or exceed the $<20\text{ ms}$ boundary precision of classical Kaldi triphone GMM-HMMs on clean speech?
  - How do the methods compare in execution overhead (CLI subprocess spawn vs in-process PyTorch tensor graph)?
  - How do out-of-vocabulary technical terms affect G2P fallback across the engines?
- **Isolated Simulation Protocol (`tests/analogs/test_aligner_analogs.py`):**
  - Evaluate on the TIMIT NIST Core Test (192 sentences with phonetic gold standard).
  - Measure: Phone MAE (ms), Word MAE (ms), Acc@20ms (%), Acc@50ms (%), Processing RTF, RAM/VRAM footprint.

---

## 4. Backlog Execution & Promotion Policy

1. **Isolation Guarantee:** Analog implementations must be located exclusively in `src/subtitle_workbench/experimental/` or `tests/analogs/`. They must not alter the default behavior of the core CLI tool `subtitle-workbench`.
2. **Promotion to Core:** An analog is promoted to the primary pipeline if and only if:
   - It demonstrates statistically significant superior accuracy ($\Delta \text{MAE} < 0, p < 0.01$) or superior efficiency ($\Delta \text{RTF} < -30\%$) on the frozen benchmark.
   - It passes all existing regression tests with zero breaking changes to output schemas (`subtitles.vtt`, `manifest.json`).
   - The decision is approved and logged in the project audit records.
