# Binding Agent Rules: Engineering Integrity & Verification
**Target Repository:** `local-subtitle-workbench`  
**Applicability:** All autonomous agents, subagents, and human developers contributing to this codebase.

---

## 1. Zero Tolerance for Synthetic & Fabricated Claims

1. **Rule of Real Execution:** Never generate, project, or report numerical metrics (MAE, Acc@20ms) without executing the code and producing a verifiable `manifest.json` on disk.
2. **Explicit Unmeasured Markers:** In any comparison table, document, or progress summary where benchmark scripts have not yet been run, every metric cell must be written as:
   ```
   `UNMEASURED / PENDING_EXPERIMENT`
   ```
3. **No Retracted Theorems:** Never re-introduce retracted mathematical claims (e.g., CRLB 14.2ms bound, universal 16.3ms human error barrier, DTW linear memory downsampling, or Theorem 3.2 circular self-certification). The $<20\text{ ms}$ metric is an **empirical target**, not an analytical certainty.

---

## 2. Corpus Integrity & Anti-Confusion Rules

1. **Check the Taxonomy First:** Before reading, writing, or citing any dataset, consult [`docs/CORPORA_TAXONOMY.md`](file:///C:/Users/nurym/Desktop/local-subtitle-workbench/docs/CORPORA_TAXONOMY.md).
2. **Never Conflate Synthetic with Speech:** Audio files in `data/corpora/synthetic/` are artificial tone bursts used strictly for algorithm regression checks. Never report their accuracy as speech recognition or alignment quality.
3. **Never Conflate Subtitle Cues with Phonetic Gold:** Audio files in `data/corpora/prototype_archive/` have word/phrase subtitle cue points ($\pm 50\text{--}100\text{ ms}$). They do NOT contain phoneme annotations. Never report phoneme-level error on this corpus.
4. **Phonetic Evaluation Standard:** Phonetic evaluation must be conducted strictly on verified phonetic gold standards (`CORPUS-TIMIT` or `CORPUS-BUCKEYE`).

---

## 3. Engineering & SDLC Rules (ASDP Quality Standard)

1. **Gate 1 Contract Requirement:** Every new module must begin with typed dataclasses, input boundary checks (rejecting `NaN`, `inf`, negative durations, and invalid sample rates), and explicit error handling.
2. **Regression-Free Execution:** Before concluding any turn or claiming a feature is complete, the agent must execute:
   ```powershell
   uv run --locked ruff check .
   uv run --locked ruff format --check .
   uv run --locked pytest
   ```
   All tests must pass with 100% success rate.
3. **Offline Safety:** Never make unauthorized external network requests, download unverified weights, or run paid cloud APIs. Packaging tests must run with the network socket guard enabled.
4. **Hardware Discipline:** Always verify that proposed models fit sequentially within the **4.0 GB VRAM limit** of the NVIDIA RTX 3050 Laptop GPU. Every neural model loaded into VRAM must have an explicit `unload()` / `torch.cuda.empty_cache()` teardown step.
5. **Change Records:** Changes are documented by descriptive git commit messages. Only citable empirical claims are tracked, in `docs/CLAIM_LEDGER.csv`. Separate per-increment reports are no longer produced.
