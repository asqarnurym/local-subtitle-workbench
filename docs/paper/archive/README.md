# Archived Preliminary Manuscript Drafts

> [!CAUTION]
> **CONTAINS SIMULATED NUMBERS -- NOT CITABLE -- see INCREMENT_6R**
>
> All empirical metrics, alignment accuracies, Wilcoxon statistics, and hardware resource values in these archived drafts (`ARTICLE_2_MANUSCRIPT_DRAFT.md`, `ARTICLE_2_MANUSCRIPT_AITU.tex`, `ARTICLE_2_MANUSCRIPT_AITU.docx`) were generated from hard-coded synthetic noise simulation during Increment 6 (`simulate_predictions()` with Gaussian offsets: ~120 ms, ~35 ms, ~12 ms) and not from actual model execution on TIMIT or Buckeye.
> All unbacked metric numbers in the text and tables have been retracted and marked `UNMEASURED / PENDING_EXPERIMENT`.
> These files are preserved strictly for historical transparency and audit compliance. Do NOT cite them as experimental results.

**Archive Date:** 2026-10-27  
**Status:** Archived / Suspended until full completion of engineering and real experimental benchmark phases (Increment 6R).

## Contents
1. `ARTICLE_2_MANUSCRIPT_DRAFT.md`: Initial markdown draft of Publication 2 (banner added; numbers marked `UNMEASURED / PENDING_EXPERIMENT`).
2. `ARTICLE_2_MANUSCRIPT_AITU.tex`: LaTeX draft formatted for single-column academic review (banner added; numbers marked `UNMEASURED / PENDING_EXPERIMENT`).
3. `ARTICLE_2_MANUSCRIPT_AITU.docx`: Word version compiled from preliminary draft; marked by this archive warning.
4. `simulated_selftest/`: Preserved raw simulated LaTeX tables from Increment 6.

## Rationale for Archival and Retraction
An audit revealed that Increment 6 benchmark tables were generated in `--offline-synthetic` mode and mislabeled with `"corpus": "timit"`. The final article must be drafted only after:
1. Real speech corpus data (TIMIT / Buckeye) is provided by the author and executed via `scripts/speech_benchmark.py` under verified `MODEL_EXECUTION` provenance.
2. Every cited paper is verified from a complete, locally downloaded full-text PDF.
3. Publication standards are targeted according to verified international journal requirements.
