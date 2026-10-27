# Runbook: Real Speech Corpus Benchmark Execution

**Author:** Askar Nurym  
**Target System:** AMD Ryzen 9 5900HX, 16 GB RAM, NVIDIA GeForce RTX 3050 Laptop GPU (4 GB VRAM limit), Windows 11  
**Project:** Local Subtitle Alignment Workbench (Publication 2, Master's Thesis)  
**Document Version:** 1.0.0 (Post-Increment 6R Remediation)

---

## 1. Executive Purpose & Governance Invariants

This runbook guides the empirical evaluation of the workbench on real speech corpora (DARPA/NIST TIMIT Core Test and Buckeye Speech Corpus).

### Hard Anti-Falsification Constraints (docs/ANTI_FALSIFICATION.md)
1. **Provenace Verification:** All citable benchmark tables must be generated exclusively from benchmark output files with `"data_provenance": "MODEL_EXECUTION"` and `"offline_synthetic": false`.
2. **Zero Fabrication:** Never substitute synthetic noise for model inference. If a model fails to execute or a corpus is unavailable, the result must be recorded as `UNMEASURED / PENDING_EXPERIMENT`.
3. **Hardware Profiling:** Peak VRAM and RTF metrics must be recorded from actual GPU runtime profiling (`torch.cuda.max_memory_allocated()`), never copied from theoretical design budgets.
4. **Statistical Rigor:** Wilcoxon signed-rank tests must operate on utterance-aggregated absolute boundary errors (not pooled boundary tokens) and include Bonferroni-Holm family-wise error rate corrections.

---

## 2. Prerequisites & Toolchain Setup

### 2.1 Python Environment & Speech Dependencies
The base repository environment runs in Python 3.11 with `uv`. To execute real neural models (Faster-Whisper Large-v3 INT8, PyTorch, TorchAudio MMS_FA CTC Trellis), install the `speech` extra:

```powershell
# Open PowerShell in repository root
Set-Location "C:\Users\nurym\Desktop\local-subtitle-workbench"

# Install all runtime dependencies including neural speech modules
uv sync --locked --extra speech
```

Verify that PyTorch detects your NVIDIA RTX 3050 Laptop GPU:
```powershell
uv run python -c "import torch; print('CUDA Available:', torch.cuda.is_available(), '| Device:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU')"
```
*Expected Output:* `CUDA Available: True | Device: NVIDIA GeForce RTX 3050 Laptop GPU`

### 2.2 Montreal Forced Aligner (MFA) Installation (Mode B)
MFA compiles Kaldi C++ binaries and OpenFST libraries distributed via `conda-forge`. It cannot be installed via `pip`/`uv` wheels on Windows 11.

Install MFA in a dedicated Conda environment and download the official ARPA acoustic model and dictionary:

```powershell
# 1. Create and activate Conda environment for MFA
conda create -n mfa -c conda-forge montreal-forced-aligner python=3.11 -y
conda activate mfa

# 2. Download official English models
mfa model download acoustic english_mfa
mfa model download dictionary english_mfa
mfa model download g2p english_g2p

# 3. Verify MFA executable on PATH
mfa version
```

Ensure that the Conda environment's `Scripts/` or `Library/bin/` folder is on your system `PATH` so that `check_mfa_available()` returns `True` in PowerShell.

### 2.3 TorchAudio MMS_FA Pre-Caching (Mode A)
Pre-cache Meta's MMS_FA Wav2Vec2 bundle to avoid download latency during benchmark timing:

```powershell
uv run python -c "import torchaudio; bundle = torchaudio.pipelines.MMS_FA; model = bundle.get_model(); print('MMS_FA successfully cached.')"
```

---

## 3. Speech Corpora Directory Layout & Verification

Corpora archives are licensed academic resources and must be provisioned locally by the author. Place uncompressed datasets under `data/corpora/`.

### 3.1 Expected Directory Structure
```
local-subtitle-workbench/
└── data/
    └── corpora/
        ├── timit/
        │   ├── DOC/
        │   │   ├── PROMPTS.TXT
        │   │   └── SPKRINFO.TXT
        │   ├── TEST/
        │   │   ├── DR1/
        │   │   │   ├── FAKS0/
        │   │   │   │   ├── SA1.PHN
        │   │   │   │   ├── SA1.TXT
        │   │   │   │   ├── SA1.WAV
        │   │   │   │   └── SA1.WRD
        │   │   │   └── ...
        │   │   └── ... (DR2..DR8, 24 core test speakers)
        │   └── TRAIN/
        └── buckeye/
            ├── s01/
            │   ├── s0101a.wav
            │   ├── s0101a.words
            │   └── s0101a.TextGrid
            └── ...
```

### 3.2 TIMIT Core Test Verification
The DARPA/NIST TIMIT Core Test consists of exactly 24 speakers (2 male, 1 female per dialect region DR1--DR8), each speaking 8 sentences (SX and SI sentences; SA sentences are excluded from phonetic benchmarks per convention), totaling 192 test utterances.

Run the integrity verification check:
```powershell
uv run python -c "from subtitle_workbench.corpora import parse_timit_phn; from pathlib import Path; p = Path('data/corpora/timit/TEST'); files = list(p.rglob('*.PHN')) if p.exists() else []; print(f'Found {len(files)} TIMIT test .PHN files.')"
```
*Pass Criterion:* Exactly 192 files found for the Core Test set (or 168 excluding SA sentences).

---

## 4. Execution Protocol: 3-Stage Gated Run

Execute in three progressive stages to catch configuration or VRAM issues before running large batches.

### Stage 1: Pipeline Smoke Test (1 Utterance, Zero Gold)
Verifies that CUDA memory allocation, audio slicing, and model backends operate without exceptions:

```powershell
uv run python scripts/real_run_smoke.py --output-dir dist/smoke_real
```

*Pass Criteria:*
- Exits with return code 0.
- `smoke_summary.json` reports `"status": "PASS"`.
- `"device"` matches `NVIDIA GeForce RTX 3050 Laptop GPU`.
- Peak VRAM $\le 1.85$ GB ($\le 1894$ MB).
- Both `subtitles.vtt` and `timeline.jsonld` exist.

### Stage 2: Small-Scale Empirical Pilot (10 Real Utterances)
Runs the full three-way ablation on 10 real TIMIT recordings to verify utterance-level metric computation and Wilcoxon statistics:

```powershell
uv run python scripts/speech_benchmark.py `
    --corpus timit `
    --corpus-dir data/corpora/timit/TEST `
    --output-dir dist/benchmark_pilot `
    --modes mode1_whisper mode2_ctc mode3_hybrid `
    --max-utterances 10
```

*Pass Criteria:*
- Output JSON `dist/benchmark_pilot/benchmark_results.json` contains:
  - `"data_provenance": "MODEL_EXECUTION"`
  - `"corpus": "timit"`
  - `"offline_synthetic": false`
  - Real execution time and real non-null `rtf`, `peak_vram_mb`.
- Paired Wilcoxon reports `holm_adjusted_p` for comparison pairs.

### Stage 3: Full TIMIT Core Test Benchmark (192 Utterances)
Executes the definitive empirical evaluation for Publication 2:

```powershell
uv run python scripts/speech_benchmark.py `
    --corpus timit `
    --corpus-dir data/corpora/timit/TEST `
    --output-dir dist/benchmark_timit_core `
    --modes mode1_whisper mode2_ctc mode3_hybrid
```

*Expected Runtime:* Approximately 8--15 minutes on AMD Ryzen 9 5900HX + RTX 3050 Laptop GPU.

---

## 5. Compiling Publication LaTeX Tables

Once Stage 3 completes with `"data_provenance": "MODEL_EXECUTION"`, compile the final LaTeX tables for the manuscript:

```powershell
uv run python scripts/generate_paper_tables.py `
    --input dist/benchmark_timit_core/benchmark_results.json `
    --output-dir docs/paper
```

*Verification:*
- The table generator accepts the file without requiring `--allow-simulated`.
- Captions automatically state: `"TIMIT Core Test Alignment Accuracy Across Ablation Modes"`.
- Output tables in `docs/paper/`:
  - `table_alignment_accuracy.tex`
  - `table_computational_performance.tex`
  - `table_statistical_significance.tex`
- All cells contain real experimental numbers; no `UNMEASURED` placeholders remain.

---

## 6. Fallback Procedures & Contingencies

### Scenario A: CUDA Out-Of-Memory (OOM) on RTX 3050
- *Symptom:* `torch.cuda.OutOfMemoryError` during Whisper transcription.
- *Root Cause:* Prior Python sessions did not release GPU memory, or background applications (browser, games) consumed VRAM.
- *Remedy:*
  1. Close external GPU applications.
  2. Run `nvidia-smi` in PowerShell to verify available VRAM $> 3.5$ GB.
  3. Ensure `--compute-type int8_float16` or `int8` is active in `asr.py`.
  4. If necessary, execute on CPU via `--device cpu` as an accessibility baseline.

### Scenario B: Montreal Forced Aligner (MFA) Fails on Windows 11
- *Symptom:* Kaldi binary crash, missing DLL error, or `MFANotFoundError`.
- *Action:*
  1. Verify conda environment is active: `conda activate mfa`.
  2. Test standalone MFA command: `mfa align --help`.
  3. If Kaldi C++ DLL dependencies cannot be resolved on Windows, execute with CTC Trellis only:
     ```powershell
     uv run python scripts/speech_benchmark.py `
         --corpus timit `
         --corpus-dir data/corpora/timit/TEST `
         --output-dir dist/benchmark_timit_ctc `
         --modes mode1_whisper mode2_ctc
     ```
- *Paper Impact:* If MFA cannot be run on the workstation, adjust the paper's primary contribution to compare Whisper attention timestamps vs. PyTorch CTC Trellis (Mode 1 vs. Mode 2), recording MFA as a Linux/HPC alternative in future work. Do not claim MFA results if MFA was not executed.
