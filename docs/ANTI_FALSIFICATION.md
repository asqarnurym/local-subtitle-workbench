# Scientific Integrity & Anti-Falsification Policy
**Project:** Local Subtitle Alignment Workbench  
**Author:** Askar Nurym  
**Target Repository:** `local-subtitle-workbench`  
**Status:** Mandatory Standard for Master's Thesis & Scientific Publications

---

## 1. Principles of Scientific Integrity

Following the comprehensive audit of prior materials (October 12, 2026), this document establishes binding rules to prevent data fabrication, selective reporting, circular validation, and algorithmic hallucination.

Every quantitative statement published in the Master's Thesis or Scientific Publication 2 must be traceable to a cryptographically verified, deterministic, and locally reproducible execution log.

---

## 2. Cryptographic Provenance & The Manifest Standard

Every execution of the alignment workbench produces a machine-readable audit trail in `manifest.json`.

```
                              CRYPTOGRAPHIC AUDIT CHAIN
┌─────────────────────────┐
│ Input Audio & Cues      │ ──► SHA-256 Digest ──┐
└─────────────────────────┘                      │
┌─────────────────────────┐                      ▼
│ Source Code Files (*.py)│ ──► SHA-256 Digest ──► [manifest.json] ──► Audit Record
└─────────────────────────┘                      ▲                     (Git & Thesis)
┌─────────────────────────┐                      │
│ Hardware & Models       │ ──► Commit / Version ┘
└─────────────────────────┘
```

### 2.1 Manifest Invariants
The audit manifest must record:
1. **Schema Version & Tool Version:** Identifies the exact release of the workbench.
2. **Code Provenance Fingerprint:** A single SHA-256 hash computed over all Python source files in `src/subtitle_workbench/` plus the Git commit hash and dirty worktree status.
3. **Input Hashes:** SHA-256 of all input audio files and reference cue/transcript JSON files.
4. **Configuration Dict:** Complete parameter set (hop size, window size, band seconds, model identifiers).
5. **Output Hashes:** SHA-256 of all generated files (`subtitles.vtt`, `timeline.jsonld`, `alignment_raw.json`).
6. **Runtime Environment:** Exact Python, NumPy, PyTorch, CUDA, OS, and hardware platform identifiers.
7. **Empirical Metrics:** Evaluated cell count, path length, and path cost.

---

## 3. Strict Rules on Data & Claims

### Rule 1: The Frozen Gold Reference Standard
- Ground truth reference datasets (TIMIT, Buckeye, or annotated lecture TextGrids) are **strictly immutable**.
- Reference files must have their SHA-256 checksums committed to the repository manifest.
- **Prohibition of Self-Certification:** An algorithm may never certify its own boundary accuracy by comparing against its own internal confidence scores, acoustic salience, or energy flux thresholds (permanent retraction of Theorem 3.2). Primary evaluation must be conducted strictly against independent human phonetic reference bounds.

### Rule 2: Absolute Ban on Synthetic Numbers in Empirical Tables
- In all reports, presentations, and draft manuscripts, any table cell representing an unexecuted experiment must be explicitly marked:
  ```
  `UNMEASURED / PENDING_EXPERIMENT`
  ```
- **Prohibition of Placeholders:** Never populate tables with hypothetical, anticipated, or synthetic target numbers (such as previously retracted claims of $\kappa = 0.94, \Delta t = 6.8\text{ ms}$). A number exists in a table if and only if a corresponding `manifest.json` and execution log exist on disk.

### Rule 3: Strict Separation of Raw Scientific vs Display Timings
- **Raw Scientific Timings (`alignment_raw.json`):**
  - Contains exact floating-point boundary timestamps generated directly by the aligner (MFA or CTC Trellis).
  - Used exclusively for computing scientific metrics: $\text{MAE}$ and $\text{Acc}@20\text{ms}$.
- **Display Subtitles (`subtitles.vtt`):**
  - Contains post-processed, millisecond-rounded, and ergonomically clamped intervals (e.g., minimum display duration 0.8 s) for video player UX.
  - **Prohibition:** Never evaluate scientific boundary precision on display-clamped subtitles, as post-processing masks true acoustic prediction errors.

### Rule 4: Statistically Valid Hypothesis Testing
- **Prohibition of Unclustered Frame t-Tests:** Speech frames within an utterance exhibit severe acoustic autocorrelation due to coarticulation and prosody. Naive Student's t-tests treating thousands of frames as independent samples are mathematically invalid and yield artificially deflated p-values.
- **Mandatory Statistical Standards:**
  1. **Clustered Bootstrap:** Resampling by whole utterances or speakers with replacement ($B = 2,000$ iterations) to compute empirical 95% Confidence Intervals for MAE and $\text{Acc}@\tau$.
  2. **Paired Wilcoxon Signed-Rank Test:** Two-tailed non-parametric paired testing across utterance-aggregated errors to establish statistical significance between baseline and proposed methods ($\alpha = 0.01$).
  3. **Bonferroni-Holm Adjustment:** Applied to all p-values across multiple ablation comparisons.

### Rule 5: Formal Claim Ledger Maintenance
All factual claims regarding speedup, memory usage, boundary precision, or baseline performance must be formally tracked in [`CLAIM_LEDGER.csv`](file:///C:/Users/nurym/Desktop/Thesis/.agents/teamwork/m12_corrected_architecture/CLAIM_LEDGER.csv) with assigned statuses:
- `SOURCE_VERIFIED`: Directly verifiable in inspected open-source code or official documentation.
- `DERIVED`: Mathematically or geometrically derived from proven equations.
- `TARGET`: A stated research objective (e.g., $\text{MAE} \le 20\text{ ms}$ on clean speech).
- `HYPOTHESIS`: A scientific proposition subject to experimental testing.
- `RETRACTED`: A prior statement proven false or unverified, permanently documented as withdrawn.
