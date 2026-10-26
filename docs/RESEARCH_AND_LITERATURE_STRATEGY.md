# Research & Literature Grounding Strategy: Publication Standards and Local Evidence Protocol

**Project:** Local Subtitle Alignment Workbench  
**Author:** Askar Nurym  
**Target Repository:** `local-subtitle-workbench`  
**Scope:** Post-Increment 6 Comprehensive Research & Final Publication Target  
**Status:** Approved Strategy & Execution Protocol

---

## 1. Executive Summary & Paradigm Shift

Intermediate academic reporting milestones (such as НИРМ 4) focus on minimum compliance with university administrative forms. In contrast, the objective of the **Local Subtitle Alignment Workbench** is to deliver a **complete, definitive, publication-grade research study** targeting premier international journals (IEEE, Elsevier, Springer).

This strategy document formalizes two non-negotiable operational principles:
1. **Decoupled Manuscript Writing:** The full manuscript writing phase will occur strictly **after** the engineering, algorithmic, and production-wrapper components are complete and frozen.
2. **Local Full-Text Evidence Protocol:** No scientific claim, metric threshold, or architectural choice may rely on LLM pretraining memory. Every citation must be verified by reading an actual, locally downloaded, full-text PDF in `C:\Users\nurym\Desktop\Thesis\Article base`.

---

## 2. Target Journal Specifications & Publication Standards

The research is scoped to fit premier international journals in educational technology, speech processing, and software systems. The table below formalizes the structural and bibliographical bounds.

| Publication Target | Typical Format | Page Budget | Word Count Ceiling | Reference Count | Structural Nuances |
| :--- | :--- | :---: | :---: | :---: | :--- |
| **IEEE Transactions on Learning Technologies (TLT)** | 2-column IEEEtran, 10 pt Times | 8–10 pages | 7,500–10,000 words | 40–55 references | Strong emphasis on cognitive load theory, educational efficacy, and quantitative multimedia accessibility evaluation. Over-length page charges apply above 10 pages. |
| **IEEE Transactions on Audio, Speech, and Language Processing (TASLP)** | 2-column IEEEtran, 10 pt Times | 9–11 pages | 8,000–10,500 words | 45–60 references | Focus on algorithmic speech processing rigor, phonetic alignment metrics, acoustic modeling (HMM vs CTC), and mathematical formulation. |
| **IEEE Access (Special Section on Educational Multimedia)** | 2-column IEEE Access template | 10–14 pages | 8,500–12,000 words | 45–65 references | Open-access multidisciplinary; allows comprehensive coverage of both the signal processing core and the software engineering/containerization architecture. |
| **Elsevier Speech Communication** | 1- or 2-column Elsevier layout | 10–15 pages | 7,000–9,500 words | 35–50 references | Phonetic segmentation focus; requires explicit discussion of phonetic transitions, coarticulation, and human annotator variability. Includes 3–5 highlights. |
| **Springer Education and Information Technologies (EAIT)** | 1-column standard format | 15–20 pages | 7,500–11,000 words | 40–60 references | Balanced evaluation of algorithmic accessibility tooling and inclusive higher-education pedagogical integration. |
| **Scientific Journal of Astana IT University (Baseline)** | 1-column A4 (TNR 12 pt, 1.0) | 11–14 pages | 5,500–6,800 words | 28–35 references | Local statutory requirement (КОКСОН МНВО РК). Median Computer Science article length based on 2023–2024 empirical issue audits. |

---

## 3. The "Local Full-Text Only" Verification Protocol

To prevent citation falsification, inaccurate paraphrasing, or metric drift:

```
                  LOCAL FULL-TEXT CITATION PIPELINE
[Scientific Claim / Need] 
           │
           ▼
[Search Engine: Google Scholar / ResearchGate / arXiv / Semantic Scholar]
           │
           ▼
[Legal PDF Download ──► Saved to 'Thesis/Article base/<AuthorYear_Title.pdf>']
           │
           ▼
[Full-Text PDF Inspection: Script / Extraction / Line Verification]
           │
           ▼
[Exact Data & DOI Extracted: Page number, Equation, or Empirical Bound]
           │
           ▼
[Integration into Manuscript Draft]
```

### Verification Rules:
1. **Zero Memory Citation:** The agent must never cite a paper based on training weights. If the PDF does not exist on disk in `Article base/`, it cannot be cited.
2. **Numeric Cross-Check:** Any numerical boundary (e.g., $10\text{--}16$ ms, $45$ ms, $100$ ms) must be verified against the exact table or paragraph in the downloaded PDF.
3. **Traceable Naming Standard:** All newly downloaded papers must be placed in:
   `C:\Users\nurym\Desktop\Thesis\Article base\` using the naming convention:
   `<AuthorSurname><Year>_<BriefTitle>.pdf`.

---

## 4. Existing Local PDF Library Audit (`Thesis/Article base`)

A total of **54 full-text PDF documents** currently reside in `C:\Users\nurym\Desktop\Thesis\Article base`. The table below organizes them by thematic role in the thesis:

| Domain | Key Local Files in `Article base/` | Thematic Coverage & Utility |
| :--- | :--- | :--- |
| **Cognitive Load & Neurodiversity** | • `Cognitive load and neurodiversity in online education...pdf`<br>• `Neurodiversity and cognitive load in online learning...pdf`<br>• `Five Strategies for Optimizing Instructional Materials...pdf`<br>• `Measuring cognitive load in the presence of educational video...pdf`<br>• `Something old, something new from cognitive load theory.pdf`<br>• `Latest trends to optimize computer-based learning...pdf`<br>• `Five ways to increase the effectiveness of instructional video.pdf` | Provides the cognitive ergonomic foundation: Sweller's Cognitive Load Theory (CLT), Mayer's Temporal Contiguity Principle, and empirical split-attention metrics in neurodivergent learners. |
| **Subtitles & Educational Accessibility** | • `Video Captions Benefit Everyone.pdf` (Gernsbacher 2015)<br>• `The effects of using an auto‑subtitle system in educational videos...pdf` (Malakul & Park 2023)<br>• `Exploiting Automatic Speech Recognition Errors to Enhance Partial and Synchronized Caption...pdf` (Mirzaei et al. 2018)<br>• `I can be a “normal” student the role of lecture capture...pdf` (Horlin et al. 2024)<br>• `Inclusive Emotion Technologies Addressing the Needs of dDeaf and Hard of Hearing Learners...pdf` | Proves that automated, synchronized subtitles benefit not only DHH students, but also non-native and neurodivergent learners by improving retention and reducing cognitive friction. |
| **Speech Recognition (ASR)** | • `Robust Speech Recognition via Large-Scale Weak Supervision.pdf` (Radford et al. 2022 / Whisper)<br>• `WhisperX Time-Accurate Speech Transcription of Long-Form Audio.pdf` (Bain et al. 2023)<br>• `CrisperWhisper_Accurate Timestamps on Verbatim Speech Transcriptions.pdf` (Wagner et al. 2024)<br>• `Automatic speech recognition a survey.pdf` (Malik et al. 2020)<br>• `Turning_Whisper_into_Real-Time_Transcription_Syste.pdf` | Covers the evolution of transformer ASR, cross-attention timestamp limitations, CTC Trellis alignment, and the need for secondary forced alignment on continuous speech. |
| **Time Alignment & Multimodal Systems** | • `Dynamic Time Warping based Adversarial Framework for Time-Series Domain.pdf`<br>• `Eventfulness for Interactive Video Alignment.pdf`<br>• `A Systematic Review of Audio Visual Synchronization_Focus on Facial Expressions and Lip Movements.pdf`<br>• `Automatic Adaptation of Open Educational Resources...pdf` (Ingavelez-Guerra et al. 2022)<br>• `The_Efficacy_of_Collaborative_Authoring_of_Video_S.pdf` (Natalie et al. 2021) | Technical formulations of Dynamic Time Warping (DTW), non-linear timeline matching, and automated OER metadata generation. |

---

## 5. Gap Analysis & Literature Download Plan

While the 54 existing local papers comprehensively cover ASR, subtitles, and cognitive load theory, specific architectural and mathematical choices require downloading primary Q1 sources into `Article base/`:

```
                               LITERATURE GAP MATRIX
┌───────────────────────────┬────────────────────────────────────────────────────────┬─────────────────────┐
│ Architectural / Metric Gap │ Target Q1 Reference to Download                        │ Recommended Source  │
├───────────────────────────┼────────────────────────────────────────────────────────┼─────────────────────┤
│ Gap 1: Human annotator    │ Raymond et al. (2002) "An analysis of transcription    │ ResearchGate /      │
│ noise ceiling (10-16 ms)  │ and alignment errors in the Buckeye corpus"            │ ScienceDirect       │
├───────────────────────────┼────────────────────────────────────────────────────────┼─────────────────────┤
│ Gap 2: Montreal Forced    │ McAuliffe et al. (2017) "Montreal Forced Aligner:       │ Interspeech Archive │
│ Aligner Kaldi GMM-HMM     │ Trainable text-speech alignment using Kaldi"           │ / ISCA Speech       │
├───────────────────────────┼────────────────────────────────────────────────────────┼─────────────────────┤
│ Gap 3: Broadcast sync     │ ITU-R Recommendation BT.1359-1 "Relative timing of     │ ITU Official Portal │
│ threshold (<=50 ms)       │ sound and vision for broadcasting" (1998)              │ (Open Standard)     │
├───────────────────────────┼────────────────────────────────────────────────────────┼─────────────────────┤
│ Gap 4: Broadcast audio    │ EBU Recommendation R37 "The relative timing of sound   │ EBU Tech Portal     │
│ lead threshold (<=40 ms)  │ and vision components of a television signal" (2007)   │ (Open Standard)     │
├───────────────────────────┼────────────────────────────────────────────────────────┼─────────────────────┤
│ Gap 5: Audiovisual TWI    │ Dixon & Spitz (1980) "The detection of auditory visual │ SpringerLink /      │
│ collapse (>100 ms)        │ desynchrony for speech and nonspeech stimuli"          │ ResearchGate        │
├───────────────────────────┼────────────────────────────────────────────────────────┼─────────────────────┤
│ Gap 6: Temporal Window    │ van Wassenhove et al. (2007) "Temporal window of       │ ScienceDirect /     │
│ of Integration in speech  │ integration in auditory-visual speech perception"      │ ResearchGate        │
├───────────────────────────┼────────────────────────────────────────────────────────┼─────────────────────┤
│ Gap 7: TIMIT Corpus       │ Garofolo et al. (1993) "DARPA TIMIT Acoustic-Phonetic  │ NIST Speech /       │
│ official documentation    │ Continuous Speech Corpus" NISTIR 4930                  │ LDC / arXiv         │
└───────────────────────────┴────────────────────────────────────────────────────────┴─────────────────────┘
```

### Action Items for Literature Grounding:
1. Search and download the 7 gap articles as full-text PDFs into `Thesis/Article base/`.
2. Extract exact quotes, table numbers, and findings to an annotated index file (`docs/LITERATURE_ANNOTATIONS.md`).
3. Incorporate verified textual citations only during the final manuscript drafting stage.
