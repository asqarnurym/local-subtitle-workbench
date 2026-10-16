# Increment Report: Preliminary Planning & Scientific Foundations
**Increment ID:** `INCREMENT_0_PRELIMINARY_PLANNING`  
**Date:** 2026-10-12 / 2026-10-17  
**Git Branch:** `main` (committed) / `feature/increment-1-speech-models-and-norm` (branched)  
**Git Commit SHA:** `9c4dc1e`  
**Author:** Askar Nurym  
**Status:** Completed & Verified

---

## 1. Executive Summary & Objective
Increment 0 established the complete theoretical, architectural, and procedural foundation for the Local Subtitle Alignment Workbench prior to heavy speech code development. Following an exhaustive technical audit of prior project drafts (M9, M10, M11), all fabricated metrics and flawed analytical theorems were retracted and replaced by a verified, reproducible specification aligning directly with the Master's Thesis Individual Plan (Specialty 7M06105) and ASDP course engineering standards.

---

## 2. Traceability to Individual Plan & Quality Gates
- **Thesis Milestone:** Подготовка к НИРМ 3 (Алгоритм точной синхронизации DTW + сегментация) и Статье 2 (AITU Journal).
- **ASDP Quality Gates Addressed:**
  - [x] Gate 1: Requirements & Architectural Contracts (Topology, memory budgets, UML).
  - [x] Gate 2: Modular Isolation Standards (No monolithic coupling).
  - [x] Gate 3: Verification Baseline (72/72 existing tests verified passing).
  - [x] Gate 4: Distributability & Packaging Baseline.
  - [x] Gate 5: Manifest & Anti-Falsification Standards.

---

## 3. Detailed Inventory of Changes

### 3.1 Files Created
| File Path | Lines of Code | Architectural Role |
| :--- | :---: | :--- |
| `docs/ARCHITECTURE.md` | 196 | Hierarchical pipeline topology (Whisper + DTW + MFA), memory budget (RTX 3050 4GB), UML sequence diagram, data contracts. |
| `docs/KNOWLEDGE_BASE.md` | 148 | Cognitive Load Theory (Ayres & Sweller), WCAG 2.1, speech acoustics, G2P, HMM vs CTC Trellis, DTW math, human annotator variance ($\sigma \approx 10\text{--}16$ ms). |
| `docs/CORPORA_TAXONOMY.md` | 134 | Strict folder isolation (`data/corpora/*`), licensing, project vs publication validity, anti-confusion rules for LLMs. |
| `docs/ANALOGS_BACKLOG.md` | 138 | Node-by-node alternatives backlog (wave vs FFmpeg, Whisper vs WhisperX, MFA vs MMS_FA) with isolated simulation testbed protocols. |
| `docs/ANTI_FALSIFICATION.md` | 98 | Cryptographic SHA-256 manifests, frozen gold policy, raw vs display timing separation, clustered bootstrap statistics. |
| `docs/SDLC_PROCESS.md` | 130 | The 5 ASDP Quality Gates, Definition of Done, 6-stage delivery roadmap, offline packaging guards. |
| `docs/RESEARCH_STRATEGY.md` | 82 | Scientific novelty analysis, Two-Phase Research Strategy (Publication 2 technical core vs Thesis defense cognitive study), product boundary. |
| `.agents/PROJECT_CONTEXT.md` | 46 | Mission, scope boundaries, hardware limits, and document map for autonomous agents. |
| `.agents/RULES.md` | 50 | Binding agent rules enforcing local execution, zero synthetic numbers, and hardware constraints. |
| `.agents/AGENT_ROLES.md` | 64 | 4-role multi-agent loop (Architect, Developer, Tester, Auditor) and closed feedback cycle. |
| `docs/increments/TEMPLATE_INCREMENT_REPORT.md` | 68 | Standard template for logging every increment's audit trail. |

---

## 4. Verification Evidence & Quality Gate Results

### 4.1 Automated Test Execution
```
Command: uv run --locked pytest
Result: PASS
Total Tests: 72 passed in 4.21s
Existing Tests Regressed: 0
```

### 4.2 Code Linter & Formatting
```
Command: uv run --locked ruff check .
Result: All checks passed!
```

---

## 5. Architectural & Design Decisions Made
- **Decision 1 (Whisper + DTW + MFA Triad):** Strictly preserved the core technologies promised in the approved Master's Individual Plan, rejecting attempts to replace MFA with pure character-level MMS_FA in the primary scientific tier.
- **Decision 2 (Corpus Separation):** Enforced physical subfolder isolation (`synthetic/`, `prototype_archive/`, `timit/`, `buckeye/`) and prohibited claiming phonetic accuracy on the Prototype archive due to lack of phonetic lab annotations.
- **Decision 3 (Sequential VRAM Management):** Budgeted sequential execution on NVIDIA RTX 3050 Laptop GPU, ensuring peak allocation $\le 1.85\text{ GB} \le 3.5\text{ GB} < 4.0\text{ GB}$.

---

## 6. Handover & Prerequisites for Increment 1
- **Working Tree:** Clean. Baseline committed to `main` (`9c4dc1e`), feature branch `feature/increment-1-speech-models-and-norm` checked out.
- **Next Task:** Increment 1 (Speech data models in `models.py` and token-span text normalizer in `text_norm.py`).
