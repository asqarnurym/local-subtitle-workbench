# Speech & Subtitle Corpora Taxonomy: Standards, Licenses & Anti-Confusion Rules
**Project:** Local Subtitle Alignment Workbench  
**Author:** Askar Nurym  
**Target Repository:** `local-subtitle-workbench`  
**Purpose:** Strict partitioning, licensing audit, and empirical validity classification of all speech datasets to prevent LLM / agentic hallucination or invalid cross-domain metric claims.

---

## 1. Directory Structure Standard

All datasets used by the workbench must strictly reside within isolated subdirectories under `data/corpora/`. No corpus data may be commingled.

```
data/corpora/
├── synthetic/               # Synthetic signal bursts for unit DTW math verification
├── prototype_archive/       # Archived 24-lecture educational video set from Prototype
├── timit/                   # DARPA/NIST Acoustic-Phonetic Gold Standard (LDC93S1)
├── buckeye/                 # OSU Buckeye Conversational Speech Corpus (Casual English)
└── aitu_lectures/           # Planned double-blind annotated AITU lecture benchmark
```

---

## 2. Comparative Corpus Taxonomy

| Corpus ID | Primary Path | Annotation Tier | Audio Quality | License | Validity for Project | Validity for Publication 2 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **`CORPUS-SYNTH`** | `data/corpora/synthetic/` | Synthetic Math Oracle | Synthetic tone bursts | MIT / Local generator | **VALID** (Unit regression, CI wheel smoke test) | **INVALID** (Must NEVER be reported as speech accuracy) |
| **`CORPUS-PROTO`** | `data/corpora/prototype_archive/` | Word / Subtitle Cues ($\pm 50\text{--}100\text{ ms}$) | Lecture mixed ($SNR \approx 15\text{--}25\text{ dB}$, $RT_{60} \approx 0.5\text{--}0.8\text{ s}$) | Local educational archive (In-house) | **VALID** (End-to-end pipeline UX, subtitle generation) | **QUALIFIED** (Valid for subtitle word-collar Acc@50ms; INVALID for phoneme MAE) |
| **`CORPUS-TIMIT`** | `data/corpora/timit/` | Phoneme + Word Lab Gold ($\pm 10\text{--}16\text{ ms}$) | Studio clean ($SNR > 35\text{ dB}$, $RT_{60} < 0.1\text{ s}$) | LDC License (`LDC93S1`, Commercial Restricted) | **VALID** (Algorithmic calibration) | **VALID** (Primary gold-standard benchmark for sub-20ms phoneme target) |
| **`CORPUS-BUCKEYE`**| `data/corpora/buckeye/` | Phoneme + Word Lab Gold ($\pm 15\text{--}35\text{ ms}$) | High coarticulation, conversational speech | Free Academic Non-Commercial | **VALID** (Stress testing) | **VALID** (Stress-test benchmark for spontaneous reductions) |
| **`CORPUS-AITU`**   | `data/corpora/aitu_lectures/` | Double-blind Praat Gold (Planned) | Real university auditorium lectures | Creative Commons / In-house AITU | **VALID** (Final system target) | **VALID** (When double-blind annotation and IAA are published) |

---

## 3. Individual Corpus Specifications & Constraints

### 3.1 Corpus 1: Synthetic Signal Suite (`CORPUS-SYNTH`)
- **Directory:** `data/corpora/synthetic/`
- **Source:** Generated programmatically via `python -m subtitle_workbench.demo`.
- **Characteristics:** 6 artificial frequency tone bursts, transformed by exact mathematical function:
  $$t_{\text{target}} = 0.24 + 1.08 \times t_{\text{reference}}$$
- **Ground Truth:** Exact mathematical timestamp oracle (`oracle.json`).
- **Validity for Project:** Valid for unit tests, GitHub Actions CI wheel smoke tests, and banded DTW algorithm sanity checks.
- **Validity for Publication:** **STRICTLY INVALID.** It does not contain human speech.
- **ANTI-CONFUSION RULE FOR AGENTS/LLMS:**
  > [!CAUTION]
  > Never report timing error or collar rates from `CORPUS-SYNTH` in the scientific paper or thesis as speech recognition or alignment performance. Label all synthetic results explicitly as «Controlled Synthetic Signal Verification».

---

### 3.2 Corpus 2: Prototype Educational Archive (`CORPUS-PROTO`)
- **Directory:** `data/corpora/prototype_archive/`
- **Source:** Historical lecture set from `C:/Users/nurym/Desktop/Thesis/Corpus/Prototype/corpus_manifest.csv`.
- **Physical Dimensions:** 24 audio/video files, total duration 3.2936 hours (11,857 seconds). Minimum duration 79.2 s, maximum duration 1183.6 s (19.73 minutes).
- **Acoustic Domain:** Real educational lectures (talking head, slide screencasts, auditorium acoustics). Ambient noise, room reverberation ($RT_{60} \approx 0.5\text{ s}$).
- **Ground Truth Tier:** Word-level subtitle cue timestamps from manual or semi-automated subtitle editors.
- **Annotation Uncertainty:** Human subtitle editor cue points carry a perceptual tolerance of $\pm 50\text{--}100\text{ ms}$. **No phoneme-level annotations exist in this dataset.**
- **Validity for Project:** Valid for long-form lecture processing, WebVTT rendering, and subtitle reading UX evaluation.
- **Validity for Publication:** Valid for measuring Word Error Rate (WER) and broad broadcast synchronization collar ($\text{Acc}@50\text{ms}, \text{Acc}@100\text{ms}$).
- **ANTI-CONFUSION RULE FOR AGENTS/LLMS:**
  > [!WARNING]
  > Prior claims of «24 lectures of 30–60 minutes with double-blind phonetic annotation $\kappa=0.94, \Delta t=6.8\text{ ms}$» were completely retracted (audit finding F06). Never report phonetic alignment accuracy or sub-20ms phonetic MAE on `CORPUS-PROTO`.

---

### 3.3 Corpus 3: TIMIT Acoustic-Phonetic Continuous Speech Corpus (`CORPUS-TIMIT`)
- **Directory:** `data/corpora/timit/`
- **Source:** DARPA / NIST / Texas Instruments / MIT (Catalog LDC93S1).
- **Physical Dimensions:** Standard NIST Core Test set: 24 speakers (16 male, 8 female across 8 American dialect regions), 192 phonetically balanced sentences (`SX` and `SI`).
- **Acoustic Domain:** 16 kHz 16-bit mono PCM. Pristine studio recording ($SNR > 35\text{ dB}$, negligible reverberation).
- **Ground Truth Tier:** Manually verified word boundaries (`.wrd`) and time-aligned phonetic transcriptions (`.phn`) created by trained acoustic phoneticians at MIT.
- **Licensing:** Proprietary LDC license. Requires institutional access; audio files must never be checked into public Git repositories.
- **Validity for Project & Publication:** **GOLD STANDARD.** The primary benchmark for evaluating the thesis requirement of $<20\text{ ms}$ phonetic and word alignment error against an indisputable international reference.
- **ANTI-CONFUSION RULE FOR AGENTS/LLMS:**
  > [!NOTE]
  > TIMIT consists of read laboratory speech with deliberate, clear articulation. Performance on TIMIT represents the upper acoustic bound of the algorithm and does not guarantee identical accuracy on noisy lecture halls.

---

### 3.4 Corpus 4: Buckeye Speech Corpus (`CORPUS-BUCKEYE`)
- **Directory:** `data/corpora/buckeye/`
- **Source:** Ohio State University Department of Psychology.
- **Physical Dimensions:** Conversational interview speech from 40 native speakers born in Columbus, Ohio.
- **Acoustic Domain:** Casual conversational speech with frequent phonetic reductions, contractions, glottalization, and informal pronunciation.
- **Ground Truth Tier:** Phonetically aligned TextGrids (`.words`, `.phones`) hand-corrected by linguistic phoneticians.
- **Licensing:** Free academic non-commercial license.
- **Validity for Project & Publication:** Stress-testing the Forced Aligner on rapid conversational speech and extreme coarticulation.
- **ANTI-CONFUSION RULE FOR AGENTS/LLMS:**
  > [!NOTE]
  > Buckeye phonetic boundaries exhibit higher human inter-annotator disagreement ($\sigma \approx 15\text{--}35\text{ ms}$) than TIMIT due to casual speech reductions. Report this variance transparently.

---

### 3.5 Corpus 5: AITU Educational Lecture Benchmark (`CORPUS-AITU`)
- **Directory:** `data/corpora/aitu_lectures/`
- **Status:** **PLANNED MASTER'S RESEARCH DATASET.**
- **Specification:** A dedicated subset of 4 lecture clips (total 20 minutes) extracted from Astana IT University computer science lectures:
  - Audio pre-processed to 16 kHz mono PCM WAV.
  - Double-blind phonetic annotation in Praat by two independent annotators.
  - Published Inter-Annotator Agreement (Cohen's Kappa and boundary RMSE).
- **Validity for Project & Publication:** Will serve as the empirical validation testbed for the Master's Thesis defense and final journal publication.

---

## 4. Summary Checklist for Any Empirical Citation

Before citing or logging any numerical evaluation metric in publications, the agent or researcher must verify:
1. [ ] Is the corpus identified by its explicit ID (`CORPUS-TIMIT`, `CORPUS-PROTO`, etc.)?
2. [ ] Is the evaluated tier explicitly stated (Phoneme level vs Word level)?
3. [ ] Does the claimed metric match the annotation resolution (no phone claims on `CORPUS-PROTO`)?
4. [ ] Are the raw test run logs and SHA-256 audio hashes preserved in `manifest.json`?
5. [ ] Is the experimental cell marked `UNMEASURED` until script execution completes?
