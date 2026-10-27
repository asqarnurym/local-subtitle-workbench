# Archived Simulated Self-Test Tables

## Provenance and Retraction Notice

The LaTeX tables preserved in this directory (`table_alignment_accuracy.tex`, `table_computational_performance.tex`, `table_statistical_significance.tex`) were generated during Increment 6 using `scripts/speech_benchmark.py --offline-synthetic`.

### Audit Findings
1. **F1 (Simulated Predictions)**: The tables were generated from 10 synthetic utterances (17.1 seconds total audio, 33 words). No ASR or forced alignment model was executed. Instead, `simulate_predictions()` added hard-coded Gaussian noise offsets (`rng.normal(120, 20)` ms for Whisper, `rng.normal(35, 12)` ms for CTC, and `rng.normal(12, 3.5)` ms for Hybrid) to synthetic timestamps. The numbers in these tables reflect only the hard-coded simulation parameters.
2. **F2 (Misleading Captioning)**: Because `speech_benchmark.py` recorded the CLI default `"corpus": "timit"` alongside `"offline_synthetic": true`, `scripts/generate_paper_tables.py` captioned Table 1 as *"TIMIT Core Test Alignment Accuracy Across Ablation Modes"*, presenting synthetic self-test perturbations as empirical TIMIT results.

### Invalidation
These files are permanently archived for historical and audit transparency under `.agents/RULES.md` and `docs/ANTI_FALSIFICATION.md`. They are **NOT CITABLE** and do **NOT** represent empirical results. Active publication tables in `docs/paper/` have been replaced with unmeasured experiment placeholders (`UNMEASURED / PENDING_EXPERIMENT`).
