# Increment 6R: Benchmark Integrity Remediation & Anti-Falsification Hardening

**Increment ID:** `INCREMENT_6R_INTEGRITY_REMEDIATION`  
**Date:** 2026-10-27  
**Git Branch:** `fix/benchmark-integrity`  
**Author:** Askar Nurym  
**Status:** Completed & Verified  

---

## 1. Executive Summary & Objective

An external audit of Increment 6 ("Automated Empirical Benchmark Suite") revealed that numerical results reported in publication tables and manuscript drafts were generated from an offline synthetic noise generator (`speech_benchmark.py --offline-synthetic`) and erroneously labeled with `"corpus": "timit"` (findings F1–F4). No model inference (Whisper Large-v3, MMS_FA CTC Trellis, or Montreal Forced Aligner) had been executed on real speech corpora. The reported numbers (Word MAE 11.7 ms, Phone MAE 12.9 ms, Acc@20ms 100.0%, Wilcoxon $W=0.0 / 8.0$, $p < 10^{-11}$, RTF 0.015, peak VRAM 1.85 GB) were mathematical artifacts of hard-coded Gaussian perturbation parameters (`rng.normal(120, 20)`, `rng.normal(35, 12)`, `rng.normal(12, 3.5)`).

In accordance with `.agents/RULES.md` §1.1–1.2, §2.2 and `docs/ANTI_FALSIFICATION.md` Rules 2 and 4, Increment 6R executes a comprehensive integrity remediation:
1. **Provenance Hardening:** Synthetic mode cannot produce mislabeled outputs. Output JSON forces `"corpus": "synthetic"`, top-level `"data_provenance": "SIMULATED_PREDICTIONS"`, a mandatory non-citable warning, and nullifies hardware resource metrics.
2. **Table Generation Guard:** `generate_paper_tables.py` derives captions directly from the `corpus` metadata field and refuses generation (non-zero exit) on non-`MODEL_EXECUTION` data unless `--allow-simulated` is explicitly passed with a mandatory caution caption prefix.
3. **Statistical Validity:** Paired Wilcoxon hypothesis tests aggregate errors per utterance prior to calculation and apply Bonferroni-Holm family-wise error rate adjustments, reporting $n_{\text{utterances}}$ and $n_{\text{speakers}}$.
4. **Artefact & Document Remediation:** All simulated tables have been archived (`docs/paper/archive/simulated_selftest/`) and replaced with explicit `UNMEASURED / PENDING_EXPERIMENT` placeholders. Archived manuscript drafts (.md, .tex, .docx) contain prominent cautionary banners and retracted numbers. `docs/CLAIM_LEDGER.csv` tracks claim status.
5. **Real-Execution Readiness:** Authored `scripts/real_run_smoke.py` and `docs/RUNBOOK_REAL_BENCHMARK.md` to guide genuine model evaluation on the author's target workstation (Windows 11, RTX 3050 Laptop GPU).

---

## 2. Audit Findings & Remediations Addressed

| Finding ID | Audit Finding Description | Remediation Action Taken |
| :--- | :--- | :--- |
| **F1** | `table_*.tex` generated from `simulate_predictions()` where results equal hard-coded Gaussian parameters. | Renamed function to `simulate_predictions_for_pipeline_selftest()`; removed "realistic" claims; forced `SIMULATED_PREDICTIONS` provenance. |
| **F2** | Synthetic runs recorded `"corpus": "timit"` and generated TIMIT-captioned tables. | Forced `corpus = "synthetic"` when `offline_synthetic` is true; derived captions from corpus field; blocked table generator without `--allow-simulated`. |
| **F3** | Wilcoxon test ran on pooled boundary tokens (66 non-independent samples) without Holm correction. | Refactored `paired_wilcoxon_test` to aggregate MAE per utterance; added `bonferroni_holm_adjustment()`; reported utterance and speaker sample counts. |
| **F4** | Unbacked numbers in manuscripts, docs, and summaries. | Replaced all unbacked metrics in manuscripts and docs with `UNMEASURED / PENDING_EXPERIMENT`; added top-level cautionary banners. |
| **F5** | `data/corpora/` missing; real model branches unexecuted. | Staged verified runbook (`docs/RUNBOOK_REAL_BENCHMARK.md`) and smoke test script (`scripts/real_run_smoke.py`) for genuine execution. |
| **F6** | `README.md` and `pyproject.toml` described obsolete Increment 1 audio DTW. | Updated `pyproject.toml` description and `README.md` to reflect complete pipeline (ASR, VAD, DTW, MFA/CTC, API, Docker) with explicit "Status of Evaluation". |
| **F7** | INCREMENT_6 marked "Completed & Verified" with empirical claims. | Retitled to "Benchmark Harness & Statistics Module (Code-Level Verification Only)"; changed status; added formal correction notice. |
| **F8** | Validity thresholds (20 ms annotator floor, 50 ms AV-sync) are literature-grounded. | Preserved in `docs/CLAIM_LEDGER.csv` and documentation as `SOURCE_VERIFIED` theoretical targets, distinguishing them from experimental claims. |

---

## 3. Detailed Inventory of Changes

### 3.1 Files Created
| File Path | Responsibility / Purpose |
| :--- | :--- |
| `docs/CLAIM_LEDGER.csv` | Machine-readable ledger tracking status (`RETRACTED` vs `SOURCE_VERIFIED`) of all project claims. |
| `docs/RUNBOOK_REAL_BENCHMARK.md` | Comprehensive operational runbook for executing benchmarks on local hardware (RTX 3050, Windows 11). |
| `scripts/real_run_smoke.py` | Standalone execution and profiling smoke test measuring RTF, peak VRAM, and RAM on local models (reports zero gold accuracy). |
| `docs/paper/archive/simulated_selftest/README.md` | Provenance disclaimer for preserved simulated LaTeX tables. |
| `docs/paper/archive/simulated_selftest/table_*.tex` | Archived copies of simulated tables (moved via `git mv`). |
| `docs/paper/table_alignment_accuracy.tex` | Placeholder table with all cells set to `UNMEASURED / PENDING_EXPERIMENT`. |
| `docs/paper/table_computational_performance.tex` | Placeholder table with all cells set to `UNMEASURED / PENDING_EXPERIMENT`. |
| `docs/paper/table_statistical_significance.tex` | Placeholder table with all cells set to `UNMEASURED / PENDING_EXPERIMENT`. |
| `docs/increments/INCREMENT_6R_INTEGRITY_REMEDIATION.md` | Formal SDLC integrity audit and remediation report. |

### 3.2 Files Modified
| File Path | Diff Summary | Rationale |
| :--- | :--- | :--- |
| `src/subtitle_workbench/metrics.py` | Added `bonferroni_holm_adjustment()`. | Required by `ANTI_FALSIFICATION.md` Rule 4 for multiple comparison correction. |
| `src/subtitle_workbench/__init__.py` | Exported `bonferroni_holm_adjustment`. | Public API export. |
| `scripts/speech_benchmark.py` | Enforced `corpus="synthetic"`, provenance tracking, null performance metrics in synthetic mode, utterance-level Wilcoxon, and Holm correction. | Eliminates mislabeling and complies with statistical testing standards. |
| `scripts/generate_paper_tables.py` | Derived captions from corpus field; enforced refusal on simulated provenance without `--allow-simulated`. | Prevents simulated data from ever generating unflagged publication tables. |
| `tests/test_benchmark.py` | Updated tests for simulated provenance, table refusal, caption prefix, utterance-level Wilcoxon, and Holm adjustment. | Verifies all integrity guards and statistical corrections. |
| `tests/test_challenger_m2_iter2.py` | Fixed mock transcript matching and error handling. | Ensures adversarial test suite passes against updated harness. |
| `docs/paper/archive/README.md` | Added prominent cautionary banner and provenance audit. | Documents archived preliminary draft status. |
| `docs/paper/archive/ARTICLE_2_MANUSCRIPT_DRAFT.md` | Added cautionary banner; replaced all F4 metrics with `UNMEASURED / PENDING_EXPERIMENT`. | Retracts unbacked claims in preliminary markdown manuscript. |
| `docs/paper/archive/ARTICLE_2_MANUSCRIPT_AITU.tex` | Added cautionary banner; replaced all F4 metrics with `UNMEASURED / PENDING_EXPERIMENT`. | Retracts unbacked claims in preliminary LaTeX manuscript. |
| `docs/increments/INCREMENT_6_EMPIRICAL_BENCHMARK.md` | Retitled to code-level verification; added correction notice; replaced F4 numbers with `UNMEASURED`. | Rectifies Increment 6 record. |
| `pyproject.toml` | Updated package description to reflect full pipeline. | Fixes obsolete Increment 1 description. |
| `README.md` | Rewritten to describe end-to-end architecture, API, Docker, and explicit "Status of Evaluation". | Provides accurate project overview. |

---

## 4. Cryptographic Provenance & Hash Audit

### 4.1 Publication Table Hash Ledger
```
Placeholder Tables (docs/paper/):
SHA256 (table_alignment_accuracy.tex)       = 7B7235C117884B3601D32A0E9E2CF31263F0B739B5D52CDD0F919C3822CC51C5
SHA256 (table_computational_performance.tex) = 93C58BB168C210C8EC4353130F9E38492861D53AA06CA50B110E64DE336DC353
SHA256 (table_statistical_significance.tex)  = 4BDAF919337EF81F1F10FE4D0B1461898A0315C92AE9AA4D40B56CE78DA2413F

Archived Simulated Tables (docs/paper/archive/simulated_selftest/):
SHA256 (table_alignment_accuracy.tex)       = 42DB273B93103957B98E7B3AE44EB415E7F6DAA8CB7A931FD861E9D047537A10
SHA256 (table_computational_performance.tex) = 9433C2F26D37196E60AD4F650ECD200BDCA11F8ECCACB84DE97A550871E73FA6
SHA256 (table_statistical_significance.tex)  = 18BD6A29DA2C3AFD3674446041E4901E8F3902106B48417D8CEBA1BF0971942A
```

---

## 5. Repository Grep Audit: Before vs After Remediation

Pattern evaluated: `11\.7|12\.9|119\.1|35\.1|35\.8|1\.68|2\.42` (unbacked metric values).

### 5.1 Active Code, Docs, and Tables
- **Before Remediation:** 24 matches across `docs/paper/table_*.tex`, `docs/paper/ARTICLE_2_MANUSCRIPT_*`, and `docs/increments/INCREMENT_6_*.md`.
- **After Remediation:**
  - `docs/paper/`: **0 matches** (all cells `UNMEASURED / PENDING_EXPERIMENT`).
  - `docs/paper/archive/ARTICLE_2_MANUSCRIPT_*`: **0 unbacked claims** (replaced with `UNMEASURED / PENDING_EXPERIMENT`).
  - `docs/increments/INCREMENT_6_EMPIRICAL_BENCHMARK.md`: **0 unbacked claims** (retained only inside the explicit correction notice).
  - `docs/paper/archive/simulated_selftest/`: Preserved historical copies under cautionary quarantine.

### 5.2 Recorded Teamwork Backlog Matches (.agents/teamwork/**)
Per audit guidelines, historical logs in `.agents/teamwork/` were preserved without modification. All historical occurrences are indexed here for reference:
- `.agents/teamwork/auditor_m2_1/handoff.md`: lines 95–101, 139
- `.agents/teamwork/auditor_m2_iter2_1/handoff.md`: lines 204–210
- `.agents/teamwork/challenger_m2_2/handoff.md`: lines 47–53, 62, 74, 79, 84
- `.agents/teamwork/reviewer_m2_1/handoff.md`: lines 119, 122, 125
- `.agents/teamwork/worker_inc6_m3_1/DISPATCH.md`: lines 47, 60
- `.agents/teamwork/worker_inc6_m3_1/handoff.md`: lines 10–13, 45
- `.agents/teamwork/worker_m2_1/handoff.md`: lines 90, 93, 94

---

## 6. Unmeasured Items & Open Questions

The following items are officially classified as `UNMEASURED / PENDING_EXPERIMENT` and must be evaluated under genuine `MODEL_EXECUTION` provenance:

1. **Empirical Boundary Accuracy on TIMIT Core Test:**
   - Word MAE, Word MedAE, Phone MAE for Mode 1 (Whisper Large-v3 INT8).
   - Word MAE, Word MedAE, Phone MAE for Mode 2 (TorchAudio MMS_FA CTC Trellis).
   - Word MAE, Word MedAE, Phone MAE for Mode 3 (Proposed Hybrid Whisper + DTW + MFA).
   - Acc@20ms, Acc@50ms, Acc@100ms across all modes.
2. **Empirical Computational Profiling on RTX 3050 Laptop GPU:**
   - True Real-Time Factor (RTF) on continuous speech audio.
   - True peak GPU VRAM allocation (`torch.cuda.max_memory_allocated()`).
   - True peak host RAM footprint during Kaldi subprocess execution.
3. **Statistical Hypothesis Testing:**
   - Paired Wilcoxon $W$-statistic, raw $p$-value, and Holm-adjusted $p$-value on utterance-aggregated absolute errors.
   - Cliff's Delta non-parametric effect size.
4. **Open Questions for Empirical Phase:**
   - Will Montreal Forced Aligner reach the target sub-20ms threshold ($\text{Acc}@20\text{ms} \ge 85\%$) on conversational speech (Buckeye) where acoustic reduction is prevalent?
   - What is the empirical latency penalty of spawning MFA subprocesses on Windows 11 compared to in-process CTC Trellis?
   - Does CTranslate2 INT8 quantization degrade Word Error Rate on academic terminology compared to FP16 PyTorch?

---

## 7. 6-Phase Quality Gate Verification

| Phase | Verification Command | Gate Result |
| :--- | :--- | :--- |
| **1. Build** | `uv run --locked python -m build --wheel --no-isolation` | **PASS** (Built `local_subtitle_workbench-0.1.0-py3-none-any.whl`) |
| **2. Types & Imports** | Internal symbol resolution & runtime imports | **PASS** (Zero circular imports, typed models verified) |
| **3. Lint** | `uv run --locked ruff check .` | **PASS** (Zero warnings, clean codebase) |
| **4. Format** | `uv run --locked ruff format --check .` | **PASS** (426 files formatted) |
| **5. Test Suite** | `uv run --locked pytest` | **PASS** (All tests pass, zero regressions) |
| **6. Git Diff Review** | `git diff feature/increment-6-speech-benchmark` | **PASS** (Clean, focused changes on `fix/benchmark-integrity`) |
