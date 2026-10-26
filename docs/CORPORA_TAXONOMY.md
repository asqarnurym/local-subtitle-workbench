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
├── timit/                   # DARPA/NIST Acoustic-Phonetic Gold Standard (LDC93S1)
├── buckeye/                 # OSU Buckeye Conversational Speech Corpus (Casual English)
└── aitu_lectures/           # Planned double-blind annotated AITU lecture benchmark
```

---

## 2. Comparative Corpus Taxonomy

| Corpus ID | Primary Path | Annotation Tier | Audio Quality | License | Validity for Project | Validity for Publication 2 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **`CORPUS-SYNTH`** | `data/corpora/synthetic/` | Synthetic Math Oracle | Synthetic tone bursts | MIT / Local generator | **VALID** (Unit regression, CI wheel smoke test) | **INVALID** (Must NEVER be reported as speech accuracy) |
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

### 3.2 Corpus 2: TIMIT Acoustic-Phonetic Continuous Speech Corpus (`CORPUS-TIMIT`)
- **Directory:** `data/corpora/timit/`
- **Source:** DARPA / NIST / Texas Instruments / MIT (Catalog LDC93S1).
- **Physical Dimensions:** Standard NIST Core Test set: 24 speakers (16 male, 8 female across 8 American dialect regions), 192 phonetically balanced sentences (`SX` and `SI`).
- **Acoustic Domain:** 16 kHz 16-bit mono PCM. Pristine studio recording ($SNR > 35\text{ dB}$, negligible reverberation).
- **Ground Truth Tier:** Manually verified word boundaries (`.wrd`) and time-aligned phonetic transcriptions (`.phn`) created by trained acoustic phoneticians at MIT.
- **Licensing:** Proprietary LDC license. Requires institutional access; audio files must never be checked into public Git repositories.
- **Validity for Project & Publication:** **GOLD STANDARD.** The primary benchmark for evaluating the thesis requirement of $<20\text{ ms}$ phonetic and word alignment error against an indisputable international reference.
- **ANTI-CONFUSION RULE FOR AGENTS/LLMS:**
  > [!NOTE]
  > TIMIT consists of read laboratory speech with deliberate, clear articulation. Performance on TIMIT represents the upper acoustic bound of the algorithm and reflects the human annotator noise floor ($\sigma \approx 10\text{--}16\text{ ms}$).

---

### 3.3 Corpus 3: Buckeye Speech Corpus (`CORPUS-BUCKEYE`)
- **Directory:** `data/corpora/buckeye/`
- **Source:** Ohio State University Department of Psychology (Pitt et al., 2005).
- **Physical Dimensions:** Conversational interview speech from 40 native speakers born in Columbus, Ohio.
- **Acoustic Domain:** Casual conversational speech with frequent phonetic reductions, contractions, glottalization, and informal pronunciation.
- **Ground Truth Tier:** Phonetically aligned TextGrids (`.words`, `.phones`) hand-corrected by linguistic phoneticians.
- **Licensing:** Free academic non-commercial license.
- **Validity for Project & Publication:** Stress-testing the Forced Aligner on rapid conversational speech and extreme coarticulation.
- **ANTI-CONFUSION RULE FOR AGENTS/LLMS:**
  > [!NOTE]
  > Buckeye phonetic boundaries exhibit higher human inter-annotator disagreement ($\sigma \approx 15\text{--}35\text{ ms}$) than TIMIT due to casual speech reductions. Report this variance transparently.

---

### 3.4 Corpus 4: AITU Educational Lecture Benchmark (`CORPUS-AITU`)
- **Directory:** `data/corpora/aitu_lectures/`
- **Status:** **PLANNED MASTER'S RESEARCH DATASET (Thesis Defense Stage).**
- **Specification:** A dedicated subset of 4 lecture clips (total 20 minutes) extracted from Astana IT University computer science lectures:
  - Audio pre-processed to 16 kHz mono PCM WAV.
  - Double-blind phonetic annotation in Praat by two independent annotators.
  - Published Inter-Annotator Agreement (Cohen's Kappa and boundary RMSE).
- **Validity for Project & Publication:** Will serve as the empirical validation testbed for the Master's Thesis defense and final journal publication.

---

## 4. Research & Generalization Backlog (External Evaluation Corpora)

The following reference datasets are cataloged for multi-domain validation, cross-lingual testing, and thesis defense expansion:

1. **LRS3-TED Audiovisual Speech Corpus (`BACKLOG-LRS3`):**
   - *Source:* Oxford Visual Geometry Group & DeepMind (Afouras et al., Interspeech 2018).
   - *Description:* Over 400 hours of video lectures and TED talks with synchronized word alignments and video frames. Ideal for testing educational talking-head video synchronization and visual lip-sync.
   - *Licensing:* Creative Commons / Academic Research.
2. **LibriSpeech-Alignments (`BACKLOG-LIBRISPEECH`):**
   - *Source:* Panayotov et al. (ICASSP 2015) with precomputed Montreal Forced Aligner acoustic alignments (Montreal Corpus Tools).
   - *Description:* 1000 hours of read English audiobooks with standardized word and phone boundaries. Used for large-scale baseline calibration.
3. **CSTR VCTK Corpus (`BACKLOG-VCTK`):**
   - *Source:* Centre for Speech Technology Research (CSTR), University of Edinburgh (Yamagishi et al.).
   - *Description:* 110 English speakers with diverse regional and international accents reading identical texts. High value for evaluating forced alignment robustness across accented educational speech.
4. **FLEURS Multilingual Speech Benchmark (`BACKLOG-FLEURS`):**
   - *Source:* Google Research (Conneau et al., 2022).
   - *Description:* 102 languages including Kazakh and Russian with n-way parallel audio and normalized transcripts. Serves as the benchmark for cross-lingual pipeline generalization.

---

## 5. Summary Checklist for Any Empirical Citation

Before citing or logging any numerical evaluation metric in publications, the agent or researcher must verify:
1. [ ] Is the corpus identified by its explicit ID (`CORPUS-TIMIT`, `CORPUS-BUCKEYE`, etc.)?
2. [ ] Is the evaluated tier explicitly stated (Phoneme level vs Word level)?
3. [ ] Are the raw test run logs and SHA-256 audio hashes preserved in `manifest.json`?
4. [ ] Is the experimental cell marked `UNMEASURED` until script execution completes?
