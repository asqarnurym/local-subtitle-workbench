# Scientific Grounding, Psychoacoustic Foundations & Metrics Taxonomy
**Project:** Local Subtitle Alignment Workbench  
**Candidate:** Askar Nurym (Astana IT University, Specialty 7M06105 «Computer Science and Engineering»)  
**Supervisor:** Prof. Tamara Zhukabayeva  
**Status:** Mandatory Methodological Standard (Comprehensive Evidence Base)

---

## 1. Executive Summary & Purpose

This document provides the exhaustive scientific, psychoacoustic, and empirical justification for every metric, numerical threshold, dataset, model, and architectural parameter employed in this Master's Thesis and Scientific Publication 2 (*Scientific Journal of Astana IT University*).

**Core Research Mandate:**
> *No number, threshold, or dataset sample in this thesis may be arbitrary, assumed, or taken "out of thin air". Every parameter must be anchored either in international psychoacoustic/broadcast standards, empirical speech science literature (Q1 peer-reviewed), or proven digital signal processing constraints.*

---

## 2. Scientific Justification of Temporal Thresholds

```
                       TEMPORAL ASYNCHRONY SPECTRUM
◄─── Audio Leads Video ───────────────────────── Audio Lags Video ───►
 -125 ms          -50 ms         0 ms        +20 ms        +45 ms        +100 ms
    │               │            │             │             │              │
    ▼               ▼            ▼             ▼             ▼              ▼
[ITU-R BT.1359] [Broadcast]   [Exact]    [Thesis Target] [ITU-R BT.1359] [Mayer Split]
(Max Detectable (Reading Saccade (Zero     (Human Noise   (Min Detectable (Attention
 Lag Limit)      Comfort Window)  Delta)    Floor Ceiling) Advance Limit)  Collapse)
```

### 2.1 The «$\le 20\text{ ms}$» Target Threshold (Phonetic & Word Boundary Resolution)
* **Project Status:** Stated research target in the Individual Master's Plan (НИРМ 3/4: *«валидация точности (<20мс)»*).
* **Scientific Literature & Empirical Grounds (Q1 Peer-Reviewed):**
  1. **Inter-Annotator Noise Floor in Phonetic Science (Raymond et al., 2002; Wesenick & Kipp, 1996; McAuliffe et al., 2017):** In speech science, trained human phoneticians manually segmenting waveforms and spectrograms in Praat exhibit an inter-transcriber standard deviation of:
     $$\sigma_{\text{annotator}} \approx 10\text{ -- }16\text{ ms}$$
     Within a $10\text{ ms}$ window, human-to-human agreement on TIMIT and Buckeye drops to $65\text{--}75\%$ due to continuous acoustic coarticulation, formant transitions, and aspiration onsets. In a $20\text{ ms}$ window, human-to-human agreement reaches $93\text{--}96\%$.
     * **Scientific Conclusion:** Pushing for a target below $20\text{ ms}$ (e.g., $5\text{--}10\text{ ms}$) would overfit to individual human annotator noise. Achieving $\text{MAE} < 20\text{ ms}$ and $\text{Acc}@20\text{ms} \ge 85\%$ represents **Human-Equivalent Precision (Noise Floor Ceiling)**.
  2. **Fundamental Digital Speech Resolution Limit (Stevens, 1998; Rabiner & Schafer, 2010):** Standard Short-Time Fourier Transform (STFT) speech processing operates on a 25 ms analysis window with a 10 ms hop rate. At 10 ms per frame, boundary localization within 1–2 frames ($\le 20\text{ ms}$) represents the physical limit of time-frequency resolution imposed by the Gabor-Heisenberg uncertainty principle in discrete speech analysis.
  3. **Psychoacoustic Fusion & The Precedence Effect (Haas, 1951; Litovsky et al., 1999):** In auditory neuroscience, acoustic wavefronts arriving within $<20\text{--}30\text{ ms}$ are psychoacoustically fused by the human brain into a single perceived auditory event (the *Haas effect*), guaranteeing zero perceptual lag.

### 2.2 The «$\le 50\text{ ms}$» Tolerance Threshold ($\text{Acc}@50\text{ms}$)
* **Project Status:** Target for subtitle word onsets and broadcast video display.
* **International Standards & Cognitive Evidence:**
  1. **ITU-R Recommendation BT.1359-1 (Relative timing of sound and vision for broadcasting):** Controlled subjective evaluations demonstrate that human viewers do not detect audio-visual asynchrony when audio leads video by up to $+45\text{ ms}$ or lags by up to $-125\text{ ms}$. Inside $\pm 50\text{ ms}$, temporal asynchrony is **physiologically imperceptible** under natural viewing conditions.
  2. **Broadcast & Captioning Standards (EBU Recommendation R37 / ATSC IS-191):** EBU R37 mandates that accumulated system timing offsets remain within $+40\text{ ms}$ (audio leading) to $-60\text{ ms}$ (audio lagging). A tolerance of $\pm 50\text{ ms}$ guarantees that subtitles are centered within the active video frame refresh cycle (33.3 ms at 30 fps; 40 ms at 25 fps).
  3. **Reading Saccades & Cognitive Ergonomics (Rayner, 1998; Jensema et al., 2000):** Visual eye-tracking during subtitle reading demonstrates that human reading saccades take 20–35 ms, with foveal fixations lasting 200–300 ms. If a subtitle onset is aligned within $\pm 50\text{ ms}$, the word is already visually stable when the learner's reading saccade lands, eliminating regressive eye movements.

### 2.3 The «$\le 100\text{ ms}$ / $125\text{ ms}$» Maximum Permissible Bound ($\text{Acc}@100\text{ms}$)
* **Cognitive Grounding (Sweller, 2011; Mayer & Anderson, 1992; Kruger & Steyn, 2014):** Desynchronization exceeding $100\text{ ms}$ violates the *Temporal Contiguity Principle*, forcing the brain to buffer auditory information while waiting for visual text, directly increasing extraneous cognitive load.
* **Audiovisual Temporal Window of Integration (TWI) (Dixon & Spitz, 1980; van Wassenhove et al., 2007; Grant et al., 2004):** The brain's multisensory binding window for speech spans $100\text{--}200\text{ ms}$. When sound leads video by $>125\text{ ms}$, cross-modal binding collapses, triggering conscious perception of desynchrony and split-attention.
* **Eye-Tracking Subtitle Cadence (Bisson et al., 2014; Perego et al., 2010):** Eye-tracking studies show that viewers execute predictive fixations on subtitle lines approximately $100\text{--}200\text{ ms}$ before acoustic onset. Asynchrony $>100\text{ ms}$ forces regressive saccades and increases pupil dilation (PCPD), signaling mental strain.

---

## 3. Scientific Justification of Quantitative Metrics

| Metric | Mathematical Definition | Why Chosen? (Scientific & Practical Justification) |
| :--- | :--- | :--- |
| **MAE (Mean Absolute Error)** | $\frac{1}{N} \sum_{i=1}^N \|t_i^{\text{pred}} - t_i^{\text{ref}}\|$ | Standard metric across forced alignment literature (MFA, WhisperX, Charsiu). Measures average temporal displacement in milliseconds. Reported separately for Word and Phoneme levels. |
| **Acc@20ms (%)** | $\frac{1}{N} \sum \mathbb{I}(\Delta t_i \le 20\text{ms}) \times 100\%$ | **Direct thesis target verification.** Measures the percentage of boundaries satisfying the human-equivalent noise floor ($\le 20\text{ ms}$) on TIMIT. Target: $\ge 85\%$. |
| **WER (Word Error Rate)** | $\frac{S + D + I}{N_{\text{ref}}} \times 100\%$ | **Transcription integrity.** Measures text accuracy (substitutions, deletions, insertions). Crucial because boundary alignment is invalid if the underlying words are hallucinated or omitted. |

---

## 4. Scientific Justification of Selected Corpora

```
                          CORPUS TAXONOMY & ROLE SEPARATION
┌─────────────────────────────────┬─────────────────────────────────┬─────────────────────────────────┐
│     SYNTHETIC (CORPUS-SYNTH)    │       GOLD (CORPUS-TIMIT)       │    STRESS (CORPUS-BUCKEYE)      │
├─────────────────────────────────┼─────────────────────────────────┼─────────────────────────────────┤
│ • Math signal bursts            │ • Studio laboratory recordings  │ • Conversational interview      │
│ • Oracle time transform         │ • Hand-aligned phoneme bounds   │ • Hand-corrected Praat grids    │
│ • Unit regression ONLY          │ • Sub-20ms scientific benchmark │ • Fast coarticulation & slurs   │
│ • NEVER report as speech!       │ • Human-equivalent ground truth │ • Robustness stress testing     │
└─────────────────────────────────┴─────────────────────────────────┴─────────────────────────────────┘
```

1. **TIMIT Acoustic-Phonetic Corpus (`CORPUS-TIMIT`, LDC93S1):**
   * *Why chosen:* The universally accepted benchmark in speech processing for phonetic alignment accuracy (DARPA/NIST). Provides hand-verified phonetic segmentations (`.phn`) and word boundaries (`.wrd`) created by acoustic phoneticians at MIT, isolating algorithm accuracy from background noise and room reverberation.
2. **Buckeye Speech Corpus (`CORPUS-BUCKEYE`, OSU):**
   * *Why chosen:* Natural conversational speech from 40 speakers with spontaneous phonetic reductions, glottal stops, and contractions. Tests algorithm robustness against casual speech coarticulation.
3. **Synthetic Signal Suite (`CORPUS-SYNTH`):**
   * *Why chosen:* Programmatically generated audio bursts with exact mathematical time shift ($t_{\text{target}} = 0.24 + 1.08 \times t_{\text{ref}}$). Used strictly for deterministic CI unit tests and packaging smoke tests without downloading speech data.
4. **AITU Educational Benchmark (`CORPUS-AITU` - Planned):**
   * *Why chosen:* Real university auditorium lectures from Astana IT University, planned for double-blind Praat annotation to validate pedagogical impact during the Master's thesis defense.

---

## 5. Scientific Justification of Technological Choices

### 5.1 Why Faster-Whisper (Large-v3 INT8)?
* **Accuracy vs Memory:** Large-v3 yields SOTA transcription accuracy on accented academic English. In FP16 it requires $>3.2\text{ GB}$ VRAM, which would cause OOM errors on a 4 GB laptop GPU. CTranslate2 INT8 quantization makes it fit the 4 GB GPU.
* **Why not Cloud ASR (Google Speech / OpenAI API)?** Violates the strict master's thesis mandate for 100% offline, local, privacy-preserving execution on university hardware without recurring API costs.

### 5.2 Why Banded DTW (`dtw.py`) with 0.5s Overlap Padding?
* **Linear Complexity:** Global unconstrained DTW on a 1-hour audio recording ($180,000 \times 180,000$ frames) requires $\approx 32.4\text{ GB}$ of RAM ($O(T \times U)$). Banded DTW with a $\pm 0.5\text{ s}$ window bounds evaluated cells to $<2,000,000$, running in $<15\text{ MB}$ RAM ($O(T \cdot B)$).
* **Overlap Padding ($0.5\text{ s}$):** Solves the boundary-truncation distortion where phonemes near chunk edges are artificially chopped by hard VAD cuts.

### 5.3 Why Montreal Forced Aligner (Kaldi GMM-HMM)?
* **Phonetic Granularity:** Transformer cross-attention is optimized for semantic words, not sub-phonemic acoustic transitions. MFA models sub-phonemic states (onset, nucleus, offset) via triphone HMMs and CMUDict, providing the acoustic resolution necessary to test the $\le 20\text{ ms}$ hypothesis.

---

## 6. How the System Guarantees Value for Diverse Learner Groups

The empirical thresholds map directly to educational outcomes under Universal Design for Learning (UDL) (Rose & Meyer, 2007):

1. **Deaf and Hard-of-Hearing (DHH) Students:** Require precise word onset synchronization ($\le 50\text{ ms}$) to match subtitles with visible lip movements of the lecturer, preventing cognitive dissonance between visual speech reading and subtitle text.
2. **Second-Language (L2) & Non-Native Learners:** Benefit from synchronized sub-word karaoke highlighting, reducing auditory parsing effort and strengthening sound-spelling correspondence.
3. **Neurodivergent Students (ADHD, Dyslexia):** Tightly synchronized karaoke subtitles eliminate extraneous cognitive load, keeping visual attention anchored to the spoken content without split-attention fatigue.
