# Scientific Strategy & Value Analysis: Master's Thesis & Publication 2
**Project:** Local Subtitle Alignment Workbench  
**Candidate:** Askar Nurym (Astana IT University, Specialty 7M06105 «Computer Science and Engineering»)  
**Supervisor:** Prof. Tamara Zhukabayeva  
**Target Publication:** Scientific Journal of Astana IT University (Trimester 5)  
**Status:** Approved Research Strategy

---

## 1. The Core Scientific Contribution (Problem Statement & Novelty)

In computer science and engineering master's theses, academic councils and attestation committees (КОКСНВО МНВО РК) strictly distinguish between simple software engineering (integrating existing tools) and genuine scientific contribution.

### 1.1 The Fundamental Technical Bottleneck
- **State-of-the-Art ASR (Whisper):** Highly capable at semantic text transcription, but its internal cross-attention timestamps suffer from temporal blurring (100–300 ms spread) and cumulative drift on long, continuous recordings with pauses, repetitions, or acoustic reverberation.
- **Classic Forced Alignment (Montreal Forced Aligner):** Excels at sub-20ms phonetic boundary localization using triphone acoustic models, but requires an exact matching transcript and faces quadratic memory explosion and context loss on unsegmented long-form lectures (15–60 minutes).
- **The Gap:** No existing open-source system provides a lightweight, local, mathematically bounded method to bridge long-form ASR and sub-phonemic alignment on consumer hardware without cloud dependencies or hallucinated drift.

### 1.2 Our Scientific Contribution: Hierarchical Bounded Alignment
The scientific novelty of this work resides in the **Two-Tier Cross-Modal Synchronization Method**:
1. **Macro-Tier (Acoustic DTW with Overlap Padding):** Formulates a banded dynamic time warping strategy with $0.5\text{ s}$ context padding and silence anchoring that reduces time-warping complexity to $O(T \cdot B)$ (linear in practice) and proves elimination of cumulative temporal drift across 60-minute streams.
2. **Micro-Tier (Invertible Token-Span Forced Alignment):** Introduces a reversible token-span mapping mechanism that reconciles acoustic phonetic dictionary requirements (CMUDict/ARPAbet) with verbatim text display, guaranteeing sub-20ms acoustic boundary accuracy without corrupting the on-screen educational subtitles.

---

## 2. Research Scope: Publication 2 vs Master's Thesis Defense

To maximize academic rigor without spreading resources too thin, the research is partitioned into two strategic milestones:

```
                            TWO-PHASE RESEARCH STRATEGY
┌──────────────────────────────────────────────┬──────────────────────────────────────────────┐
│  PHASE 1: PUBLICATION 2 (AITU JOURNAL)       │  PHASE 2: MASTER'S THESIS DEFENSE            │
│  Autumn / Winter 2026                        │  Spring / Summer 2027                        │
├──────────────────────────────────────────────┼──────────────────────────────────────────────┤
│ • Purely algorithmic & computational focus   │ • Algorithmic Core + Educational Validation  │
│ • Objective benchmark metrics:               │ • Cognitive Ergonomics User Study (N=15-20): │
│   - Word MAE, Phone MAE (ms)                 │   - NASA-TLX Cognitive Load Questionnaire   │
│   - Acc@20ms and Acc@50ms tolerances         │   - Reading comprehension & split-attention  │
│   - Real-Time Factor (RTF) on RTX 3050       │ • Demonstrates real pedagogical impact       │
│ • Clustered Bootstrap & Wilcoxon tests       │ • Full chapter on educational accessibility  │
└──────────────────────────────────────────────┴──────────────────────────────────────────────┘
```

---

## 3. Product & Market Integration Boundary

### 3.1 What is Out of Scope (Avoiding Scope Creep)
- Developing a full commercial SaaS (billing, authentication, user databases, multi-tenant cloud) is **strictly excluded**. It dilutes research effort into routine web development with zero academic value.

### 3.2 What is In Scope (Practical Interoperability)
- **Standardized Bimodal Outputs:**
  1. `subtitles.vtt` with karaoke `<c>` tags: Instantly compatible with HTML5 video players, YouTube, VLC, and LMS platforms (specifically **Moodle**, standard in higher education).
  2. `timeline.jsonld` (schema.org): Conforming to W3C WCAG 2.1 Media Accessibility Guidelines for automated academic search indexing.
- **Lightweight API Service (Trimester 5 Milestone):**
  - A clean, local FastAPI microservice (`POST /align`) containerized via Docker for reproducible demonstration during the thesis defense.
