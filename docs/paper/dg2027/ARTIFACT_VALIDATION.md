# Validation of figures, tables and evidence (21.11.2026)

What was checked, how, and what must change before an artifact goes into the DG 2027 paper. Nothing in `reports/` was modified.

## 1. Integrity checks (automatic)

| Check | Result |
|---|---|
| `scripts/verify_frozen_evidence.py` (frozen runs, 27 artifacts, 4319 reference files, all six frozen LaTeX tables regenerated from `benchmark_results.json` and compared byte for byte, every `MODEL_EXECUTION` claim source resolved) | **PASS_WITH_LIMITATIONS** (the limitations are the documented ones in the script). First run failed: CLAIM-108…110 had folder paths instead of JSON files; fixed in `CLAIM_LEDGER.csv` (commit "Point CLAIM-108 to CLAIM-110 …"), rerun passed |
| SHA-256 of E1 figures (24 files) and E1 tables (2) against `reports/e1_analysis_20261102/figure_manifest.json` | all match |
| SHA-256 of BRQE sensitivity figures (4) against its manifest | all match |
| SHA-256 of S3 figure (PNG, PDF) against `final_check.json` | match |
| S1b and S2 figures | no hash manifest exists; files unchanged since their result commits (`727e891`, `02b5acd`); numbers checked visually below |
| PNG resolution | every PNG is 300 dpi; width 2220 px (7.4 in), S3 2700 px (9 in) |
| Pipeline numbers re-derived during P-1…P-4 (word MAE of all 12 frozen modes, training run, S3 runs; reliability ROC-AUC) | match frozen values to 0.01 ms / 0.001 |

## 2. Visual check against the numbers (English PNGs)

| Figure | Agrees with | Issues for the paper |
|---|---|---|
| E1 `word_error_ecdf_en` | Acc@20 ≈ 0.71 (A2 Buckeye) at the dotted 20 ms line; CTC and Whisper ordering as in tables | Good candidate for the paper (one figure shows RQ1). Four panels: in a 6-page IEEE paper use `figure*` or keep only the Buckeye row |
| E1 `reliability_retention_en` | 0 % rejection: 16.97 / 27.67 ms (Buckeye), 19.89 / 20.08 ms (TIMIT) = frozen A2/B2+BRQE | Good candidate for RQ2 (reliability head). Y-axes differ between panels (by design) |
| E1 `speaker_brqe_gain_en` | Buckeye 20/20 speakers improve, Holm p = 1.34e-05; TIMIT Holm p = 0.467 (CLAIM-104) | Tall (2520 px); too large for 6 pages. Use a sentence or a compact version |
| E1 `word_start_end_en` | TIMIT: BRQE lowers end errors, raises start errors (known limitation, §10.1) | Optional |
| E1 `word_duration_mae_en` | — | Optional |
| E1 `phone_group_mae_en` | — | **Defect:** empty "Other" category on every x-axis. Remove before any use |
| BRQE `brqe_sensitivity_en` | 9/9 configurations above zero gain; 6 epochs best, 24 worst (`BRQE_SENSITIVITY_RESULTS.md`) | Optional; one sentence is enough in 6 pages |
| S1b `s1b_failures_en` | 0/3/6 and 2/7/12 failed, 15/20/20 without anchors; chunk rates 0.0/1.5/1.3 % and 4.8/3.9/4.6 % = CLAIM-109/110 | Good candidate if S1b gets a figure |
| S1b `s1b_position_en` | titles "14 of 20" (A2) and "8 of 20" (B2) = survivors (CLAIM-108) | Caption must say "recordings that aligned"; B2 mean spike at minute 7 is from 8 recordings |
| S2 `s2_tempo_en` | TIMIT 19.8–20.4, Buckeye A2 17.9–20.3; TIMIT BRQE 21.8 vs 20.2 at 1.25 = CLAIM-111/113 | S2 is planned as one sentence; not needed |
| S3 `s3_asr_size` | MAE and coverage values = `S3_RESULTS.md` table | **Inconsistent style:** sans-serif font while all others are serif; left y-axis does not start at zero and shows no CIs although no difference is significant (visually overstates differences); right panel draws two identical coverage lines. No RU version. Redraw or do not use |

## 3. Tables

| Table | Status | For the paper |
|---|---|---|
| `reports/buckeye/tables/table_alignment_accuracy.tex`, TIMIT same | verified (regenerated = committed) | **Must add word coverage** next to scenario B (rule in `IMPROVEMENT_PLAN.md` §10.1: coverage beside every error). "%" appears both in the header and in cells; caption has nested parentheses. Merge TIMIT and Buckeye into one compact table |
| `table_statistical_significance.tex` (both corpora) | verified | Clip-paired tests. The paper's statistics should be the speaker-level E1 tests (`speaker_tests_*.tex`) or both, stated clearly |
| `table_quality_estimation.tex` (both) | verified | ROC-AUC 0.756 / 0.749 (CLAIM-105) |
| E1 `speaker_tests_buckeye.tex`, `speaker_tests_timit.tex` | hashes match | Preferred source for significance in the paper |

## 4. Diagrams

The old architecture diagrams (`reports/paper_architecture_20261104`, local, never in Git) were moved to the Windows Recycle Bin on the author's instruction; the author draws new pipeline diagrams by hand. The 2026 pipeline figure (`Prototype/figures/`) may serve as a style reference only, not as content.

## 5. Summary for the paper

Recommended figures (at most 3 in 6 pages): E1 ECDF (Buckeye row) for RQ1, E1 reliability-retention for RQ2, S1b failures for the long-recording paragraph; plus the author's pipeline diagram. Table: one merged accuracy table with coverage. Fix the two defects (phone groups "Other", S3 style) only if those figures are used.
