# Agent Project Context: Local Subtitle Alignment Workbench
**Target Repository:** `local-subtitle-workbench`  
**Author:** Askar Nurym (Astana IT University, Specialty 7M06105)  
**Supervisor:** Prof. Tamara Zhukabayeva  
**Thesis Topic:** «Methods to improve accessibility in education through sound-to-video synchronization»  
**Publication 2:** «Algorithmic approach to improving video material accessibility based on automatic speech-text alignment» (Scientific Journal of AITU)

---

## 1. Project Mission & Architectural Core
The goal is to develop an offline, high-precision forced alignment workbench that synchronizes spoken audio with subtitle text at millisecond precision for educational multimedia accessibility.

The core scientific architecture integrates the **Whisper + DTW + MFA Triad**:
- **ASR:** OpenAI Whisper (via `faster-whisper` Large-v3 INT8 with CTranslate2) for verbatim transcription and coarse segment timestamps.
- **Macro-Alignment & Segmentation:** Banded Dynamic Time Warping (`dtw.py`) with Silero-VAD silence anchoring to eliminate temporal drift on long educational lectures.
- **Micro-Forced Alignment:** Montreal Forced Aligner (Kaldi GMM-HMM + CMUDict) for phonetic boundary precision ($<20\text{ ms}$ target), with PyTorch CTC-Trellis (`torchaudio MMS_FA`) as an in-process fallback.
- **Exporters:** Bimodal outputs adhering to WCAG 2.1: WebVTT with word-level karaoke `<c>` tags and schema.org `VideoObject`/`Clip` JSON-LD.

---

## 2. Hard Execution Constraints
- **Scope Boundary:** Strictly Speech-to-Text Forced Alignment and Subtitle Generation. Strictly excluded: Text-to-Speech (TTS), visual slide/scene descriptions, LLM summaries.
- **Language Scope:** English-only initial verifiable core (per Individual Plan); Multilingual (RU/KZ) treated as future extensions.
- **Hardware Platform:** AMD Ryzen 9 5900HX, 16 GB RAM, NVIDIA GeForce RTX 3050 Laptop GPU (4 GB VRAM), Windows 11.
- **Memory Ceiling:** Peak VRAM $\le 3.5\text{ GB} < 4.0\text{ GB}$ via explicit sequential execution and inter-stage memory cleanup.
- **Runtime Toolchain:** Python 3.11 / 3.12, `uv` package manager, `hatchling` build backend, `ruff` linter, `pytest` test runner.

---

## 3. Directory Layout & Document Map
```
local-subtitle-workbench/
├── docs/
│   ├── ARCHITECTURE.md          # Full system architecture, UML diagrams, memory budgets
│   ├── KNOWLEDGE_BASE.md        # Cognitive Load Theory, WCAG 2.1, speech acoustics, G2P
│   ├── CORPORA_TAXONOMY.md      # Strict dataset partitioning, licenses, anti-confusion rules
│   ├── ANALOGS_BACKLOG.md       # Component alternatives backlog & simulation protocols
│   ├── ANTI_FALSIFICATION.md    # Manifest standard, frozen gold, statistical testing
│   ├── SDLC_PROCESS.md          # 5 Quality Gates, Definition of Done, roadmap
│   ├── ALGORITHM.md             # Existing DTW mathematical specification
│   ├── DEVELOPMENT.md           # Developer setup and branch workflow
│   └── VALIDATION.md            # Existing verification protocol
├── .agents/
│   ├── PROJECT_CONTEXT.md       # (This file) Agent orientation and scope summary
│   ├── RULES.md                 # Binding behavioral and anti-fabrication rules for agents
│   └── AGENT_ROLES.md           # Orchestration roles and feedback loop specification
├── src/subtitle_workbench/      # Core source code
├── tests/                       # Unit and integration test suites
└── scripts/                     # Benchmarks and wheel smoke verification
```
