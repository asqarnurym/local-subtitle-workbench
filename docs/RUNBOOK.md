# Runbook: running the benchmark on real corpora

Target machine: Windows 11, AMD Ryzen 9 5900HX, NVIDIA RTX 3050 Laptop GPU (4 GB). All commands run in PowerShell from the repository root.

## 1. Environment

```powershell
uv sync --locked --all-extras
```

Tests (the `api` extra is required; without it test collection fails on FastAPI):

```powershell
uv run --locked --all-extras ruff check .
uv run --locked --all-extras pytest -m "not model"
```

### 1.1 Verify that Whisper can use the GPU

```powershell
uv run python -c "from subtitle_workbench.asr import whisper_cuda_available; print(whisper_cuda_available())"
```

Expected: `True`. Faster-Whisper runs on CTranslate2, which needs cuBLAS 12 and cuDNN 9. They are installed as pip wheels (`nvidia-cublas-cu12`, `nvidia-cudnn-cu12`) by the `speech` extra, and their DLL folders are registered at runtime. If the result is `False`, check that the NVIDIA driver is installed (`nvidia-smi`).

The benchmark uses `--device cuda` by default and **stops with an error** if the GPU is not usable; it never silently falls back to the CPU. Use `--device cpu` only deliberately (results record the device in `config.asr.device`).

The torch wheel from PyPI is CPU-only on Windows; it is used only by the CTC baseline (MMS_FA), which does not need the GPU for accuracy.

**Status (2026-10-28):** `whisper_cuda_available()` returned `False` on the target laptop although `nvidia-smi` sees the GPU. Cause not yet found (candidate: the installed CTranslate2 wheel is CPU-only). Do not run the benchmark with `--device cuda` until this check returns `True`.

### 1.2 Montreal Forced Aligner

```powershell
conda create -n mfa -c conda-forge montreal-forced-aligner
conda activate mfa
mfa model download acoustic english_us_arpa
mfa model download dictionary english_us_arpa
mfa model download g2p english_us_arpa
mfa version
```

`mfa` must be on `PATH` in the shell that runs the benchmark (or installed under `~/.mfa_env`). The workbench calls `mfa align` once per batch with per-speaker directories (speaker adaptation), `--g2p_model_path english_us_arpa` (pronunciations for out-of-vocabulary words) and `--fine_tune` (boundary refinement below the 10 ms frame shift).

**Status (2026-10-28):** MFA was not found on the laptop (`conda` and `mfa` absent). Install it before any B2 or A2 run.

## 2. Reference corpora

| Corpus | Reference | How to stage |
| --- | --- | --- |
| TIMIT sample (160 utt., 16 speakers) | gold, manual | `uv run python scripts/download_reference_corpora.py --corpus timit-sample` |
| TIMIT full (LDC93S1) | gold, manual | unpack into `data/corpora/timit` |
| Buckeye (40 speakers, spontaneous) | gold, manual | register at buckeyecorpus.osu.edu, download the speaker zips, then `uv run python scripts/download_reference_corpora.py --corpus buckeye --buckeye-source <folder with s01.zip..s40.zip>` |
| LibriSpeech test-clean (40 speakers) | silver (MFA) | `uv run python scripts/download_open_benchmark_data.py --corpus librispeech` |
| L2-ARCTIC (24 speakers, 6 L1s) | silver (forced alignment) | `uv run python scripts/download_open_benchmark_data.py --corpus l2arctic` |

Silver corpora measure agreement with MFA-produced boundaries. Report them as such, and never use them to argue that an MFA-based mode is more accurate than another mode.

## 3. Runs

Pilot (10 utterances, checks the toolchain end to end):

```powershell
uv run python scripts/speech_benchmark.py --corpus timit --data-dir data/corpora/timit --max-utterances 10 --output-dir reports/pilot_timit
```

Full runs:

```powershell
uv run python scripts/speech_benchmark.py --corpus timit   --data-dir data/corpora/timit   --output-dir reports/timit
uv run python scripts/speech_benchmark.py --corpus buckeye --data-dir data/corpora/buckeye --output-dir reports/buckeye
```

Each run writes `benchmark_results.json` (per-mode summary and paired tests), `benchmark_utterances.json` (one row per utterance and mode, including failures and their error text) and `manifest.json` (code hash, input audio hashes, configuration, hardware).

## 3a. Validation protocol

Steps 1-6 must be completed in order. A failed step stops the protocol.

1. **Clean tree and tests.** `git status` is empty. `ruff check .` and `pytest -m "not model"` pass (see section 1).
2. **Buckeye sample.** Use 10 clips per speaker across all 40 speakers (about 400 clips), drawn with `seed = 20260401` from the staged clips in `data/corpora/buckeye`. Save the selected clip IDs and the seed to `reports/buckeye_sample_20260401.json`.
3. **Pilot criteria.** On the 10-utterance TIMIT pilot and then on the Buckeye sample: share of failed utterances below 5%, and `word_metrics.coverage` at least 90%. If either fails, do not start the full run; investigate `benchmark_utterances.json` first.
4. **Freeze.** After a passing pilot, tag the commit (`bench-frozen-<date>`). Code, sample and configuration do not change after the tag; any change means a new tag and a new pilot.
5. **Full run and tables.** Sections 3 and 5, run from the frozen tag only.
6. **Ledger.** For each claim that uses the results, add a row to `docs/CLAIM_LEDGER.csv` with `data_provenance = MODEL_EXECUTION`, the run directory and the git tag.

## 4. Checks before using numbers

1. `data_provenance` is `MODEL_EXECUTION` and `reference_type` is `gold` for accuracy claims.
2. `hardware.whisper_cuda_available` is `true` and `config.asr.device` is `cuda` (or CPU was chosen deliberately).
3. `code.git_worktree_dirty` in the manifest is `false` (commit before the run).
4. For every mode: `n_utterances_failed` and `word_metrics.coverage` are reported; investigate failures in `benchmark_utterances.json`.
5. `ci_unit` is `speaker` when at least 10 speakers are present, otherwise `utterance`.

## 5. Tables

```powershell
uv run python scripts/generate_paper_tables.py --input reports/timit/benchmark_results.json --output-dir reports/timit/tables
```

The generator refuses simulated input unless `--allow-simulated` is passed (self-tests only).

## 6. Troubleshooting

- **`device='cuda' requested but CTranslate2 cannot use a CUDA GPU`**: see 1.1.
- **`Montreal Forced Aligner ('mfa') requested but not found`**: activate the Conda environment or add it to `PATH`.
- **`mfa produced no alignment for chunk(s) ...`** in `benchmark_utterances.json`: MFA could not align that utterance (beam failure). It is reported as a failed utterance and excluded from paired tests; it is not replaced by another engine.
- **CUDA out of memory**: close other GPU applications; Whisper is unloaded before alignment.
