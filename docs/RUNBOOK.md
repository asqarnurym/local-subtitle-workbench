# Runbook: running the benchmark on real corpora

Target machine: Windows 11, AMD Ryzen 9 5900HX, NVIDIA RTX 3050 Laptop GPU (4 GB). All commands run in PowerShell from the repository root.

## 1. Environment

```powershell
uv sync --locked --all-extras
```

**Always pass `--all-extras` to `uv run`.** A bare `uv run` performs an exact sync of the default environment and *uninstalls* every extra, including `speech` (Faster-Whisper, CTranslate2, torch, the `nvidia-*` CUDA wheels: 45 packages on this machine). After that, Whisper cannot use the GPU and the benchmark cannot run (see 1.1). Every command in this runbook therefore uses `uv run --locked --all-extras`.

Tests (the `api` extra is required; without it test collection fails on FastAPI):

```powershell
uv run --locked --all-extras ruff check .
uv run --locked --all-extras pytest -m "not model"
```

### 1.1 Verify that Whisper can use the GPU

```powershell
uv run --locked --all-extras python -c "from subtitle_workbench.asr import whisper_cuda_available; print(whisper_cuda_available())"
```

Expected: `True`. Faster-Whisper runs on CTranslate2, which needs cuBLAS 12 and cuDNN 9. They are installed as pip wheels (`nvidia-cublas-cu12`, `nvidia-cudnn-cu12`) by the `speech` extra, and their DLL folders are registered at runtime. If the result is `False`, check that the NVIDIA driver is installed (`nvidia-smi`).

The benchmark uses `--device cuda` by default and **stops with an error** if the GPU is not usable; it never silently falls back to the CPU. Use `--device cpu` only deliberately (results record the device in `config.asr.device`).

The torch wheel from PyPI is CPU-only on Windows; it is used only by the CTC baseline (MMS_FA), which does not need the GPU for accuracy.

**Status (2026-10-28): resolved, check returns `True`.**

- Symptom: `whisper_cuda_available()` returned `False` although `nvidia-smi` saw the GPU (driver 617.42).
- Cause: the `speech` extra was not installed in `.venv`. The check had been run with a bare `uv run`, which removed all extras; `import ctranslate2` then failed, and `whisper_cuda_available()` turns any exception into `False`. The CTranslate2 wheel and the DLL registration were not at fault. Confirmed with `uv sync --locked --dry-run`, which reports `Would uninstall 45 packages` (ctranslate2, faster-whisper, torch, nvidia-*).
- Fix: `uv sync --locked --all-extras`, then always `uv run --locked --all-extras ...`. No code change.
- Verified after the fix: CTranslate2 4.8.3, `get_cuda_device_count() = 1`, supported CUDA compute types include `int8_float16` (the type the workbench uses on CUDA); `nvidia-cublas-cu12 12.9.2.10`, `nvidia-cudnn-cu12 9.27.0.42`; `cublas64_12.dll`, `cublasLt64_12.dll`, `cudnn64_9.dll`, `cudnn_ops64_9.dll`, `cudnn_cnn64_9.dll` load after `register_nvidia_dll_dirs()`; `whisper_cuda_available()` prints `True`.
- Not verified yet: an actual Whisper transcription on the GPU (no model run in this session).

### 1.2 Montreal Forced Aligner

```powershell
conda create -n mfa -c conda-forge montreal-forced-aligner
conda activate mfa
mfa model download acoustic english_us_arpa
mfa model download dictionary english_us_arpa
mfa model download g2p english_us_arpa
mfa version
```

`mfa` must be on `PATH` in the shell that runs the benchmark (or installed under `~/.mfa_env`). The workbench calls `mfa align` once per speaker (speaker adaptation; one call per speaker avoids an MFA 3.4.3 `--fine_tune` bug, see section 6), with one job, `--g2p_model_path english_us_arpa` (pronunciations for out-of-vocabulary words) and `--fine_tune` (boundary refinement below the 10 ms frame shift).

**Status (2026-10-28): installed, no action needed.** MFA 3.4.3 (`montreal-forced-aligner-3.4.3`, `kalpy 0.10.5`, Kaldi build `cuda129`) is already installed as a conda-style environment in `~/.mfa_env`. The earlier "not found" came from checking only `PATH` (`conda` is not on `PATH`, and `mfa` is not on it outside the workbench). The workbench finds it: `mfa_wrapper._ensure_mfa_on_path()` adds `~/.mfa_env/Scripts`, `Library/bin` and `Library/usr/bin` to `PATH`, and `check_mfa_available()` returns `True`. `~/.mfa_env/Scripts/mfa.exe version` prints `3.4.3`. Pretrained models in `~/Documents/MFA/pretrained_models`: acoustic `english_us_arpa.zip`, dictionary `english_us_arpa.dict`, g2p `english_us_arpa.zip`. Not verified yet: an actual `mfa align` run.

## 2. Reference corpora

| Corpus | Reference | How to stage |
| --- | --- | --- |
| TIMIT sample (160 utt., 16 speakers) | gold, manual | `uv run --locked --all-extras python scripts/download_reference_corpora.py --corpus timit-sample` |
| TIMIT full (LDC93S1) | gold, manual | unpack into `data/corpora/timit` |
| Buckeye (40 speakers, spontaneous) | gold, manual | register at buckeyecorpus.osu.edu, download the speaker zips, then `uv run --locked --all-extras python scripts/download_reference_corpora.py --corpus buckeye --buckeye-source <folder with s01.zip..s40.zip>` |
| LibriSpeech test-clean (40 speakers) | silver (MFA) | `uv run --locked --all-extras python scripts/download_open_benchmark_data.py --corpus librispeech` |
| L2-ARCTIC (24 speakers, 6 L1s) | silver (forced alignment) | `uv run --locked --all-extras python scripts/download_open_benchmark_data.py --corpus l2arctic` |

Silver corpora measure agreement with MFA-produced boundaries. Report them as such, and never use them to argue that an MFA-based mode is more accurate than another mode.

## 3. Runs

Samples (drawn once with `scripts/make_benchmark_sample.py`; the script refuses to overwrite an existing file). Speakers and IDs are sorted, then drawn uniformly without replacement with `numpy.random.default_rng(seed)`:

```powershell
uv run --locked --all-extras python scripts/make_benchmark_sample.py --corpus timit --speakers 10 --per-speaker 1 --seed 20260401 --output reports/timit_pilot_20260401.json
uv run --locked --all-extras python scripts/make_benchmark_sample.py --corpus buckeye --per-speaker 10 --seed 20260401 --output reports/buckeye_sample_20260401.json
```

Created 2026-10-28: TIMIT pilot 10 utterances from 10 speakers (sha256 `da928910…843e`); Buckeye 400 clips, 10 from each of 40 speakers (sha256 `9719b13d…20fb`). Do not use `--max-utterances` for the pilot: it takes the first N IDs, which all belong to one speaker.

Speaker split and full-run samples (decisions D6, D7 in `docs/IMPROVEMENT_PLAN.md`). Buckeye speakers are split once into 20 test and 20 train speakers; reported numbers come only from the test group, and the train group is used only for BRQE:

```powershell
uv run --locked --all-extras python scripts/make_speaker_split.py --corpus buckeye --n-test 20 --seed 20260401 --output reports/buckeye_split_20260401.json
uv run --locked --all-extras python scripts/make_benchmark_sample.py --corpus buckeye --per-speaker 50  --seed 20260401 --split reports/buckeye_split_20260401.json --group test  --output reports/buckeye_test_sample_20260401.json
uv run --locked --all-extras python scripts/make_benchmark_sample.py --corpus buckeye --per-speaker 150 --seed 20260401 --split reports/buckeye_split_20260401.json --group train --output reports/buckeye_train_sample_20260401.json
```

Created 2026-10-29 (random, not stratified: no speaker metadata is staged locally): split sha256 `49bcad6e…f2f7`, test speakers s02 s03 s07 s09 s11 s12 s15 s17 s18 s19 s20 s22 s27 s31 s33 s34 s35 s36 s37 s38; test sample 1000 clips (sha256 `0986421d…4d08`); train sample 3000 clips (sha256 `c27f6de2…b876`).

Pilots (`--utterance-list` runs exactly the listed IDs and records the file path, sha256 and seed in `config.sample` of the results and the manifest; it cannot be combined with `--max-utterances`):

```powershell
uv run --locked --all-extras python scripts/speech_benchmark.py --corpus timit   --data-dir data/corpora/timit   --utterance-list reports/timit_pilot_20260401.json   --output-dir reports/pilot_timit
uv run --locked --all-extras python scripts/speech_benchmark.py --corpus buckeye --data-dir data/corpora/buckeye --utterance-list reports/buckeye_sample_20260401.json --output-dir reports/pilot_buckeye
```

Full runs:

```powershell
uv run --locked --all-extras python scripts/speech_benchmark.py --corpus timit   --data-dir data/corpora/timit   --refiner-dir models/brqe --output-dir reports/timit
uv run --locked --all-extras python scripts/speech_benchmark.py --corpus buckeye --data-dir data/corpora/buckeye --utterance-list reports/buckeye_test_sample_20260401.json --refiner-dir models/brqe --output-dir reports/buckeye
```

Clips with empty audio are corpus defects, not alignment failures: they are excluded before any stage and listed with the reason in `config.excluded_corpus_defects`. In the staged Buckeye these are `s1901b_0111`–`s1901b_0121` (header-only WAV files); one of them (`s1901b_0119`) is in the test sample, so the Buckeye full run has 999 clips.

Each run writes `benchmark_results.json` (per-mode summary and paired tests), `benchmark_utterances.json` (one row per utterance and mode, including failures and their error text), `benchmark_predictions.json` (predicted word and phone boundaries per mode and utterance, reused by later analyses) and `manifest.json` (code hash, input audio and output hashes, configuration, hardware). `benchmark_results.json` also has a `runtime` section (wall-clock seconds and real-time factor per stage); it is recorded for transparency only and is not an evaluation target.

## 3b. BRQE (train speakers only)

BRQE refines MFA boundaries and estimates their reliability (`docs/IMPROVEMENT_PLAN.md` §6). It is trained only on the 20 train speakers; `train_brqe.py` refuses a run that contains a test speaker.

```powershell
# 1. MFA alignments (A2, B2) on the train sample; numbers of this run are never reported
uv run --locked --all-extras python scripts/speech_benchmark.py --corpus buckeye --data-dir data/corpora/buckeye --utterance-list reports/buckeye_train_sample_20260401.json --modes A2_proposed,B2_proposed --output-dir reports/brqe_train_run
# 2. Speaker-grouped 5-fold CV inside the train speakers + pre-registered decision (§6.5)
uv run --locked --all-extras python scripts/train_brqe.py --run reports/brqe_train_run --split reports/buckeye_split_20260401.json --cv 5 --report reports/brqe_cv_20260401.json
# 3. Final training on all train speakers -> models/brqe (brqe.pt, brqe.json, const_offsets.json)
uv run --locked --all-extras python scripts/train_brqe.py --run reports/brqe_train_run --split reports/buckeye_split_20260401.json --final models/brqe --report reports/brqe_final_20260401.json
```

With `--refiner-dir models/brqe`, `speech_benchmark.py` adds the modes `A2_const`, `A2_brqe`, `B2_const`, `B2_brqe`. They reuse the A2/B2 MFA alignments (no extra MFA calls); the BRQE weights' sha256 is recorded in `config.refiners`, and the reliability head's ROC-AUC, PR-AUC and word MAE after rejection are in `modes.*_brqe.quality_estimation`.

## 3a. Validation protocol

Steps 1-6 must be completed in order. A failed step stops the protocol.

1. **Clean tree and tests.** `git status` is empty. `ruff check .` and `pytest -m "not model"` pass (see section 1).
2. **Buckeye sample.** Use 10 clips per speaker across all 40 speakers (about 400 clips), drawn with `seed = 20260401` from the staged clips in `data/corpora/buckeye`. Save the selected clip IDs and the seed to `reports/buckeye_sample_20260401.json` (section 3, `make_benchmark_sample.py`). The TIMIT pilot uses `reports/timit_pilot_20260401.json` (1 utterance from each of 10 speakers, same seed). The sample files are versioned: `.gitignore` ignores `reports/*` except `reports/*_sample_*.json` and `reports/timit_pilot_*.json`, so they are part of the freeze tag; run outputs in `reports/` stay ignored. Their sha256 is also recorded in every run's `config.sample`.
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
uv run --locked --all-extras python scripts/generate_paper_tables.py --input reports/timit/benchmark_results.json --output-dir reports/timit/tables
```

The generator refuses simulated input unless `--allow-simulated` is passed (self-tests only).

## 6. Troubleshooting

- **`device='cuda' requested but CTranslate2 cannot use a CUDA GPU`**: see 1.1.
- **`Montreal Forced Aligner ('mfa') requested but not found`**: activate the Conda environment or add it to `PATH` (an install in `~/.mfa_env` is found automatically).
- **`whisper_cuda_available()` is `False` / `ModuleNotFoundError: ctranslate2`**: the `speech` extra was removed by a bare `uv run`; run `uv sync --locked --all-extras`.
- **`MFA execution failed with exit code 3` and `Fatal Python error: Aborted`, or MFA hangs at "Exporting alignment TextGrids"** (2026-10-28/29, MFA 3.4.3): a thread-safety race in MFA's threaded alignment collection (several threads build the lexicon compiler from one dictionary object at once; the stack trace shows concurrent `load_l_align_from_file`). Seen in 3 of 3 runs while the laptop was also busy, 0 of 6 runs with 8 or 4 jobs on an idle machine. The benchmark therefore runs MFA with `num_jobs = 1` (`MFA_NUM_JOBS` in `scripts/speech_benchmark.py`, recorded as `config.aligners.mfa.num_jobs`); 2 of 2 runs with one job passed with Whisper loaded. The job count slightly changes boundaries (on the 10 TIMIT pilot files, 1 vs 8 jobs: 2 of 164 word boundaries and 16 of 628 phone boundaries differ, at most 20 and 30 ms), so it must not change after the freeze. Keep other heavy programs closed during runs.
- **`KaldiFatalError: You provided the "cs" option but are not calling with keys in sorted order: 100 < 9`** during "Fine tuning alignments" (2026-10-29, MFA 3.4.3, Buckeye pilot, 40 speakers in one call): `--fine_tune` iterates utterances ordered by `kaldi_id` (`"<speaker_id>-<utterance_id>"`, compared as text) but reads the alignment archive by utterance ID, which Kaldi requires in sorted text order. With several speakers the two orders diverge (`1-9` is followed by `10-100`). Within one speaker they always agree, so the workbench calls MFA once per speaker (`ForcedAligner(mfa_per_speaker=True)`, recorded as `config.aligners.mfa.invocation = per_speaker`). Speaker adaptation is per speaker in either case. No newer MFA release exists (3.4.3 is the latest on PyPI as of 2026-10-29).
- **`mfa produced no alignment for chunk(s) ...`** in `benchmark_utterances.json`: MFA could not align that utterance (beam failure). It is reported as a failed utterance and excluded from paired tests; it is not replaced by another engine.
- **CUDA out of memory**: close other GPU applications; Whisper is unloaded before alignment.
