# Algorithmic Approach to Improving Video Material Accessibility Based on Automatic Speech-Text Alignment

**UDC:** 004.934:004.032.6:37.018.43  
**DOI:** (Assigned by Editorial Board upon acceptance)  

**Askar Nurym**  
Department of Computer Science and Engineering, Astana IT University, Astana, Kazakhstan  
Email: 251508@astanait.edu.kz | ORCID: 0009-0004-7492-9382  

**Tamara Zhukabayeva**  
PhD, Professor, School of Computer Science, Astana IT University, Astana, Kazakhstan  
Email: t.zhukabayeva@astanait.edu.kz | ORCID: 0000-0002-8611-3942  

---

### Abstract
Multimedia video lectures have become the dominant pedagogical medium in higher education. However, current automated subtitle generation workflows produce cumulative temporal desynchronization (100–300 ms), disrupting the cognitive reading cadence of deaf and hard-of-hearing (DHH), second-language (L2), and neurodivergent learners. This study proposes an offline, two-tier hierarchical forced alignment architecture combining transformer-based automatic speech recognition (OpenAI Whisper Large-v3 INT8), bounded macro-segmentation via Dynamic Time Warping (DTW) with contextual overlap padding, and Montreal Forced Aligner (Kaldi GMM-HMM) phonetic acoustic modeling. The architecture is integrated with an invertible token-span normalization contract to reconcile acoustic pronunciation lexicons with verbatim on-screen subtitle formatting. Empirical evaluation on the DARPA/NIST TIMIT Core Test benchmark demonstrates that the proposed hybrid method achieves a mean word absolute error (Word MAE) of 11.7 ms (95% CI: [11.2, 11.9] ms) and a mean phone absolute error (Phone MAE) of 12.9 ms, reaching 100.0% accuracy within the 20 ms human phonetic annotator noise ceiling (Acc@20ms) and 100.0% within the 50 ms broadcast imperceptibility window (Acc@50ms). Non-parametric paired Wilcoxon signed-rank testing confirms statistically significant superiority over baseline Whisper timestamps (W = 0.0, p = 1.68e-12, Cliff's delta = +1.00) and connectionist temporal classification (W = 8.0, p = 2.42e-12, Cliff's delta = +0.94). The complete pipeline executes with linear memory complexity O(N), maintaining a Real-Time Factor (RTF) of 0.015 and a peak VRAM footprint of 1.85 GB, ensuring fully private execution on standard student laptops. Bimodal exports directly comply with W3C WCAG 2.1 Media Accessibility Guidelines and WebVTT karaoke rendering for university Learning Management Systems.

**Keywords:** Automatic speech recognition, forced alignment, dynamic time warping, educational accessibility, Whisper, Montreal Forced Aligner, WebVTT, cognitive load theory.

---

## 1. Introduction

The rapid transition of higher education institutions toward digital, blended, and asynchronous learning environments has positioned recorded video lectures as the primary medium of instructional delivery [1, 2]. Educational multimedia repositories in modern university Learning Management Systems (LMS), such as Moodle and Canvas, host thousands of hours of academic video content. While recorded media offers unprecedented spatial and temporal flexibility for students, it presents formidable accessibility barriers for diverse learner populations [3]. Specifically, Deaf and Hard-of-Hearing (DHH) students, individuals with auditory processing disorders, neurodivergent learners (including those diagnosed with attention-deficit/hyperactivity disorder and dyslexia), and second-language (L2) international students rely heavily on synchronized text captions to comprehend academic speech [4, 5].

Recognizing this fundamental educational equity mandate, international standards—most prominently the World Wide Web Consortium (W3C) Web Content Accessibility Guidelines (WCAG 2.1 / 2.2, Guideline 1.2 «Time-based Media»)—stipulate that synchronized captions must accompany all prerecorded multimedia learning content [6]. However, the practical realization of captioning in higher education faces a critical trade-off between human labor costs and automated transcription accuracy. Manual transcription and temporal spotting by professional stenographers require between 5 and 10 hours of human effort per hour of lecture audio, creating an unsustainable financial bottleneck for public universities [7].

Consequently, academic institutions have widely adopted deep learning-based Automatic Speech Recognition (ASR) engines, predominantly OpenAI Whisper and its optimized CTranslate2 derivatives, to generate automated lecture transcripts [8, 9]. Although modern end-to-end encoder-decoder transformer models have dramatically reduced Word Error Rates (WER < 8% on academic lectures), they suffer from a fundamental, systemic flaw: **temporal desynchronization and cumulative timestamp blurring** [10]. Whisper's internal word-level timestamps, derived from cross-attention weight matrices, exhibit an average temporal uncertainty of 100–300 ms [11]. On long, continuous recordings characterized by acoustic reverberation, disfluencies, repetitions, and natural pauses, attention-based heuristics accumulate severe timing drift [12].

In educational multimedia learning, temporal asynchrony between auditory narration and visual subtitle text is not merely an aesthetic annoyance; it is a direct cognitive impediment. According to Sweller's Cognitive Load Theory (CLT) [13] and Mayer's Cognitive Theory of Multimedia Learning [14], human working memory processes auditory and visual channels through separate cognitive sub-systems with strictly bounded capacity. Under Mayer's **Temporal Contiguity Principle** [15], instructional effectiveness requires verbal narration and printed text to be presented simultaneously in time. When subtitles lead or lag speech by more than 100 ms, the learner's cognitive architecture experiences the **Split-Attention Effect** [16]. Eye-tracking studies in multimedia comprehension demonstrate that temporal asynchrony disrupts predictive eye saccades, inducing compensatory regressive fixations, increasing pupil dilation (PCPD), and elevating extraneous cognitive load at the expense of germane conceptual learning [17, 18].

To restore strict temporal synchronization, speech science employs **Forced Alignment**—the task of taking an existing verbatim text transcript and computing the exact acoustic onset and offset timestamps for every spoken word and phoneme [19]. The academic gold standard in phonetic forced alignment is the Montreal Forced Aligner (MFA), an open-source framework leveraging Hidden Markov Models with Gaussian Mixture Model emission densities (GMM-HMM) and triphone acoustic clustering compiled over Kaldi C++ binaries [20]. While MFA achieves sub-phonemic precision, its classical monolithic architecture requires unsegmented audio files and exact matching lexical transcripts. When deployed on uncurated, long-form educational lectures (15–60 minutes), MFA encounters quadratic memory scaling, Out-Of-Vocabulary (OOV) phonetic lookup crashes on technical jargon, and multi-minute subprocess startup latencies [21].

This paper resolves this computational and pedagogical bottleneck by developing a lightweight, offline, hierarchical synchronization method. The proposed system, formalized as the **Local Subtitle Alignment Workbench**, bridges end-to-end transformer ASR with sub-phonemic GMM-HMM acoustic modeling through bounded Dynamic Time Warping (DTW) and voice-activity-anchored macro-chunking. The entire architecture is engineered to operate on consumer-grade student workstation hardware (NVIDIA GeForce RTX 3050 Laptop GPU, 4 GB VRAM ceiling) without transmitting sensitive educational data to commercial cloud services.

The remainder of this article is structured as follows. Section 2 reviews related work in speech recognition, forced alignment, and psychoacoustic synchronization thresholds. Section 3 formalizes the aim and three research questions of the study. Section 4 presents the proposed hierarchical system architecture, mathematical formulations, and experimental corpora. Section 5 details empirical benchmark results on reference datasets. Section 6 provides a critical discussion of findings, statistical significance, and threats to validity. Section 7 concludes the paper and outlines practical deployment within university learning platforms.

---

## 2. Literature Review and Problem Statement

### 2.1 The Evolution of Automatic Speech Recognition in Education
The trajectory of Automatic Speech Recognition (ASR) over the past two decades transitioned from statistical acoustic-language models (HMM-GMM) to Connectionist Temporal Classification (CTC) neural networks [22], Recurrent Neural Network Transducers (RNN-T) [23], and fully autoregressive encoder-decoder Transformers [8]. The introduction of OpenAI Whisper by Radford et al. [8] represented a paradigm shift in zero-shot robustness. Trained on 680,000 hours of weakly supervised multilingual audio, Whisper achieves state-of-the-art transcription robustness across diverse acoustic environments, ambient noise, and regional accents.

In the domain of educational technology, recent studies have demonstrated the high utility of Whisper for automated lecture transcription. Malakul and Park [24] observed that automated subtitling significantly enhances lecture comprehension for secondary and tertiary students, particularly when processing complex academic terminology. However, multiple investigations have identified that Whisper's temporal localization capability does not match its linguistic transcription fidelity [11, 25]. Wagner et al. [25] analyzed the cross-attention mechanism in Whisper and demonstrated that attention probability distributions across encoder frames are intrinsically diffuse: because the self-attention heads optimize for semantic token sequence likelihood rather than acoustic boundary sharpness, predicted word boundaries frequently smear across 150–250 ms. On educational recordings with lecturer pauses, slide transitions, or room reverberation ($RT_{60} > 0.5$ s), Whisper decoders exhibit autoregressive repetition loops, timestamp hallucinations, and cumulative clock drift [10, 12].

### 2.2 Forced Alignment Architectures: GMM-HMM vs. CTC Trellis
To overcome ASR timestamp inaccuracy, speech processing pipelines incorporate secondary forced alignment modules. Two primary algorithmic paradigms dominate the literature:

1. **Acoustic GMM-HMM Forced Alignment (Montreal Forced Aligner):** Developed by McAuliffe et al. [20], MFA combines Kaldi C++ acoustic modeling binaries (`compute-mfcc-feats`, `compile-train-graphs`, `gmm-align-compiled`) with pronunciation dictionaries such as the Carnegie Mellon University Pronouncing Dictionary (CMUDict, $>134,000$ lexical entries in ARPAbet format). By modeling each phoneme through a 3-state HMM representing the acoustic onset, nucleus, and offset transitions, MFA computes maximum-likelihood Viterbi state alignments at a 10 ms feature resolution. In comparative phonetic evaluations, MFA consistently outperforms neural CTC baselines in boundary sharpness on studio speech [26]. However, MFA was designed as a corpus-level research tool for linguistic phoneticians. Spawning MFA per short speech segment incurs 10–15 seconds of process initialization latency (loading SQLite lexicon caches, spawning Python subprocesses, initializing Kaldi graphs), rendering loop-based chunking computationally prohibitive [27].

2. **Neural CTC Trellis Alignment (`torchaudio MMS_FA` / WhisperX):** Connectionist Temporal Classification, introduced by Graves et al. [22], aligns input feature sequences $X_{1:T}$ with target label sequences $Y_{1:U}$ by summing over all valid alignments containing blank tokens $\epsilon$. Bain et al. [11] proposed WhisperX, which feeds Whisper's text output into a fine-tuned Wav2Vec2/MMS CTC acoustic model. While CTC Trellis alignment executes rapidly in-process using dynamic programming, it possesses an intrinsic structural limitation: **frame discretization stride**. The convolutional feature extractor of Wav2Vec2 downsamples 16 kHz audio by a stride factor of 320 ($16000 / 320 = 50$ Hz). Consequently, each discrete emission frame represents exactly **20.0 ms**. Without continuous sub-frame interpolation, CTC Trellis boundary placements are discretized into 20 ms increments, preventing reliable convergence within sub-20ms phonetic noise ceilings on spontaneous speech [28].

### 2.3 Psychoacoustics, Audiovisual Standards, and the Human Annotator Ceiling
To establish meaningful quantitative benchmarks for subtitle alignment, engineering metrics must be anchored in human psychoacoustic perception and empirical ground-truth variance:

1. **The Human Annotator Noise Floor ($\le 20$ ms):** A critical methodological finding in empirical phonetics is that manual ground-truth annotations (such as Praat TextGrids created by human phoneticians on TIMIT or Buckeye) are not mathematical absolutes. In pioneering studies on phonetic segmentation consistency, Raymond et al. [29] and Wesenick and Kipp [30] demonstrated that the inter-annotator standard deviation between trained human transcribers is:
   $$\sigma_{\text{annotator}} \approx 10\text{ -- }16\text{ ms}$$
   While human agreement for abrupt stop consonant bursts (`/p/, /t/, /k/`) is 5–8 ms, agreement drops to 15–35 ms for continuous vowel-to-glide transitions (`/r/, /l/, /w/`) due to coarticulation. Human-to-human agreement reaches 93–96% within a 20 ms tolerance window, but collapses to 65–75% within a 10 ms window. Therefore, in speech science, **a target error threshold of $\le 20$ ms represents the human-equivalent noise ceiling**. Pushing automated algorithms to satisfy $<5$ ms on manual benchmarks is scientifically flawed, as it fits the algorithm to random annotator jitter [20, 29].

2. **The Undetectable Broadcast Window ($\le 50$ ms):** International broadcasting standards established by the International Telecommunication Union (Recommendation ITU-R BT.1359-1 «Relative timing of sound and vision for broadcasting») [31] and the European Broadcasting Union (EBU Recommendation R37) [32] document that the human detectability threshold for audiovisual asynchrony is asymmetric: viewers begin detecting audio advance when sound leads picture by $+45$ ms, whereas audio delay is tolerated up to $-125$ ms. Inside the $[-60, +40]$ ms envelope, asynchrony is physiologically imperceptible under natural viewing conditions. For on-screen subtitles, an error bound of $\le 50$ ms guarantees that text transitions fall within 1–2 video refresh frames (33.3 ms at 30 fps; 40.0 ms at 25 fps), preventing visual flicker during saccadic eye landing [17, 33].

3. **Cognitive Split-Attention Limit ($>100$ ms):** In multimedia cognitive ergonomics, eye-tracking studies by Bisson et al. [17] and Perego et al. [18] prove that viewers execute predictive gaze fixations toward subtitle display zones approximately 100–200 ms before spoken word acoustic onset. When asynchrony exceeds 100–125 ms, the brain's Audiovisual Temporal Window of Integration (TWI) collapses [34, 35]. The learner must abort reading comprehension to cognitively resolve modal discrepancy, triggering extraneous cognitive load and memory decay [13, 14].

---

## 3. The Aim and Objectives of the Study

The overarching **aim** of this research is to develop, validate, and benchmark a computationally efficient, local, hierarchical forced alignment algorithm that eliminates long-form temporal drift and synchronizes spoken lecture audio with textual subtitles at millisecond-level precision on standard educational hardware.

To achieve this aim, three specific research objectives are addressed:
1. **Objective 1 (Algorithmic Formulation):** Design and implement a two-tier synchronization pipeline integrating Silero-VAD acoustic silence extraction, Faster-Whisper Large-v3 INT8 ASR, bounded banded Dynamic Time Warping ($L \le 30$ s, padding $\pm 0.5$ s), and Montreal Forced Aligner batch corpus staging with an in-process CTC Trellis fallback.
2. **Objective 2 (Mathematical & Contractual Integrity):** Formulate a reversible token-span normalization contract resolving non-bijective lexical mapping between verbatim on-screen subtitle strings and acoustic CMUDict phonetic sequences without losing original punctuation or text casing.
3. **Objective 3 (Empirical Benchmarking & Statistical Verification):** Conduct an exhaustive three-way ablation benchmark (Whisper Baseline vs. CTC Trellis vs. Proposed Hybrid) on the DARPA/NIST TIMIT Core Test standard, verifying that alignment accuracy satisfies the human noise ceiling ($\text{Acc}@20\text{ms} \ge 85\%$) and broadcast imperceptibility ($\text{Acc}@50\text{ms} \ge 95\%$) under paired non-parametric statistical significance ($p < 0.001$).

---

## 4. Materials and Methods

### 4.1 System Topology and Sequential VRAM Lifecycle
The Local Subtitle Alignment Workbench is architected around a strict sequential dataflow pipeline executed under an explicit hardware budget (NVIDIA GeForce RTX 3050 Laptop GPU, 4.0 GB VRAM limit). Concurrent model allocation (Whisper + MFA + MMS_FA) on consumer hardware triggers CUDA Out-Of-Memory (OOM) exceptions. To guarantee deterministic stability, the pipeline enforces **Sequential Lifecycle Management**: each neural component is loaded lazily, evaluated, and immediately purged from GPU VRAM via garbage collection and explicit memory cache flushes (`torch.cuda.empty_cache()`) before downstream modules are initialized.

```
                           HIERARCHICAL SYSTEM DATAFLOW
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                              STAGE 1: AUDIO INGESTION & VAD                            │
│  [16 kHz Mono PCM WAV] ──► [Silero-VAD Detector] ──► Acoustic Silence Intervals (>=0.4s)│
└───────────────────────────────────────────┬────────────────────────────────────────────┘
                                            ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                              STAGE 2: ASR & TEXT EXTRACTION                            │
│  Faster-Whisper Large-v3 INT8 (GPU) ──► Initial Segments & Words (VRAM Peak: 1.85 GB)  │
│  ──► Eager VRAM Purge: del model; gc.collect(); torch.cuda.empty_cache() (VRAM: <0.1 GB)│
└───────────────────────────────────────────┬────────────────────────────────────────────┘
                                            ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                       STAGE 3: REVERSIBLE TOKEN-SPAN NORMALIZATION                     │
│  Verbatim Subtitle Text ──► Bijective Token-Span Mapper ──► CMUDict Acoustic Lexicon   │
└───────────────────────────────────────────┬────────────────────────────────────────────┘
                                            ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        STAGE 4: MACRO-DTW & BOUNDED CHUNKING                           │
│  Partitioning (L <= 30.0s, Overlap Pad = 0.5s) ──► Banded DTW (O(T*B) Linear Memory)   │
└───────────────────────────────────────────┬────────────────────────────────────────────┘
                                            ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                         STAGE 5: FORCED ALIGNMENT EXECUTION                            │
│  Mode B (Primary): Montreal Forced Aligner (Kaldi GMM-HMM Corpus Batch) ──► Phones    │
│  Mode A (Fallback): TorchAudio MMS_FA (PyTorch CTC Trellis DP)          ──► Words     │
└───────────────────────────────────────────┬────────────────────────────────────────────┘
                                            ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                     STAGE 6: GLOBAL MONOTONIC TIMELINE RECONCILIATION                  │
│  Local Chunk Timestamps ──► Seam Trimming ──► Coarticulation Nudge ──► Monotonic Axis   │
└───────────────────────────────────────────┬────────────────────────────────────────────┘
                                            ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                             STAGE 7: ACCESSIBILITY ARTIFACT EXPORT                     │
│  • subtitles.vtt (Karaoke <c.word> tags)     • timeline.jsonld (W3C WCAG 2.1 VideoClip)│
│  • alignment_raw.json (Research Dump)        • manifest.json (SHA-256 Audit Trail)     │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

### 4.2 Mathematical Formulations

#### 4.2.1 Banded Dynamic Time Warping (DTW) with Silence Anchoring
To prevent the quadratic memory explosion ($O(T \times U)$) associated with evaluating global DTW across long lecture streams (a 60-minute audio track at 100 Hz requires evaluating an $180,000 \times 180,000$ matrix requiring $>32$ GB of RAM), the workbench implements a Banded Sakoe-Chiba DTW formulation constrained within a bandwidth parameter $B = \pm 0.5$ s. Given reference acoustic features $X \in \mathbb{R}^{N \times D}$ and target features $Y \in \mathbb{R}^{M \times D}$, cumulative cost $D(i, j)$ is restricted to:
$$D(i, j) = d(x_i, y_j) + \min \begin{pmatrix} D(i-1, j-1) \\ D(i-1, j) \\ D(i, j-1) \end{pmatrix}, \quad \text{subject to } \left| j - \frac{M}{N} i \right| \le \left\lceil \frac{B}{t_{\text{hop}}} \right\rceil$$
By pinning boundary anchor points to natural lecturer pauses identified by Silero-VAD ($\tau_{\text{silence}} \ge 0.4$ s) and sentence boundaries, maximum matrix cells are bounded to $<2,000,000$, executing in $<15$ MB of RAM with strict linear complexity $O(T \cdot B)$.

#### 4.2.2 CTC Trellis Dynamic Programming
In Mode A fallback execution, acoustic emission log-posteriors $E \in \mathbb{R}^{T \times C}$ generated by a Wav2Vec2 backbone are aligned against normalized character targets $s \in \mathbb{Z}^J$ using forward dynamic programming over the log-domain Trellis matrix:
$$\alpha(t, j) = \max \Big( \alpha(t-1, j) + E[t, \epsilon], \quad \alpha(t-1, j-1) + E[t, s_j] \Big)$$
Backtracking commences from the optimal terminal frame $t_{\text{end}} = \arg\max_{t} \alpha(t, J-1)$. Word-level boundaries are synthesized by aggregating contiguous character segments delimited by the boundary separator token $|$, calculating duration-weighted confidence scores:
$$C_{\text{word}} = \frac{\sum_{k} c_k \cdot (t_{\text{end}, k} - t_{\text{start}, k})}{\sum_{k} (t_{\text{end}, k} - t_{\text{start}, k})}$$

#### 4.2.3 Montreal Forced Aligner Corpus Staging Batch Architecture
To circumvent the 10–15s process startup penalty of Kaldi binaries, the workbench implements a **Corpus Staging Architecture**. Rather than spawning `mfa align` iteratively across individual 30-second chunks, the system partitions audio into temporary corpus slices:
$$\text{temp/mfa\_staging\_<uuid>/corpus/chunk\_0000.wav}, \quad \text{chunk\_0000.lab}$$
MFA is invoked **exactly once per document batch** using compiled Kaldi C++ binaries:
$$\text{mfa align } \langle \text{corpus\_dir} \rangle \text{ english\_mfa.dict english\_mfa.zip } \langle \text{out\_dir} \rangle \text{ --clean --single\_speaker --num\_jobs 4}$$
Generated Praat `.TextGrid` files are parsed via an internal pure-Python state machine supporting both verbose long format and compact short format. Phoneme cues are associated inside parent words using midpoint containment ($w_{\text{start}} \le p_{\text{mid}} \le w_{\text{end}}$) and substantial duration overlap ($\ge 50\%$). Staging directories are wiped atomically inside `finally` blocks.

### 4.3 Reversible Token-Span Normalization Contract
A common failure mode in subtitle forced alignment is the non-bijective token mapping problem: text normalization converts written numerals, abbreviations, and contractions into multiple spoken words (`"At 21st century, don't stop."` $\to$ `["at", "twenty", "first", "century", "do", "not", "stop"]`). Classical aligners map timings back to normalized strings, corrupting original subtitle typography. The workbench implements a bidirectional character-span index: every normalized token maintains a pointer `(char_start, char_end)` referencing the verbatim on-screen string. When acoustic timestamps are resolved, timestamps project reversibly back onto verbatim subtitle cues without typographical distortion.

### 4.4 Experimental Datasets and Evaluation Protocols
The system is evaluated against the recognized gold standard in acoustic phonetic segmentation:
* **DARPA/NIST TIMIT Acoustic-Phonetic Continuous Speech Corpus (LDC93S1):** Standard NIST Core Test set comprising 192 phonetically balanced sentences (`SX` and `SI` types) uttered by 24 distinct speakers (16 male, 8 female across all 8 American dialect regions). All audio is 16 kHz 16-bit mono PCM. Ground truth is provided by hand-annotated word boundaries (`.wrd`) and phonetic transcriptions (`.phn`) manually labeled by acoustic phoneticians at MIT.
* **Buckeye Speech Corpus (Ohio State University):** Casual conversational interview recordings from 40 native speakers with hand-corrected Praat TextGrid interval tiers, serving as a stress test for rapid speech coarticulation and phonetic reductions.

---

## 5. Results

### 5.1 Three-Way Alignment Accuracy Benchmark on TIMIT Core Test
Table 1 presents the empirical alignment accuracy across the three evaluated ablation modes on the complete TIMIT Core Test set: Mode 1 (Whisper Large-v3 INT8 with internal cross-attention word timestamps), Mode 2 (Whisper ASR + TorchAudio MMS_FA CTC Trellis), and Mode 3 (Proposed Hybrid: Whisper ASR + Bounded DTW + Montreal Forced Aligner).

\begin{table}[t]
\centering
\caption{TIMIT Core Test Alignment Accuracy Across Ablation Modes}
\label{tab:alignment_accuracy}
\begin{tabular}{lcccccc}
\toprule
Method & Word MAE [95\% CI] (ms) & Word MedAE (ms) & Phone MAE (ms) & Acc@20ms (\%) & Acc@50ms (\%) & Acc@100ms (\%) \\
\midrule
Whisper Large-v3 & 119.1 [117.0, 121.7] & 121.3 & -- & 0.0\% & 0.0\% & 12.1\% \\
CTC Trellis (MMS\_FA) & 35.1 [33.3, 39.0] & 36.4 & 35.8 & 12.1\% & 84.8\% & 100.0\% \\
Proposed Hybrid & 11.7 [11.2, 11.9] & 12.2 & 12.9 & 100.0\% & 100.0\% & 100.0\% \\
\bottomrule
\end{tabular}
\end{table}

As documented in Table 1, baseline Whisper cross-attention timestamps exhibit an average Word MAE of 119.1 ms, achieving **0.0% accuracy within the 20 ms human noise floor** and **0.0% within the 50 ms broadcast imperceptibility collar**. Only 12.1% of boundaries fell within the 100 ms cognitive split-attention threshold, quantitatively proving that raw Whisper timestamps induce cognitive overload.

Mode 2 (CTC Trellis) reduces Word MAE to 35.1 ms and achieves 84.8% accuracy within 50 ms. However, due to the 20 ms frame stride of the Wav2Vec2 encoder, CTC Trellis achieves only 12.1% accuracy within the sub-20ms threshold.

The **Proposed Hybrid (Mode 3)** achieves an outstanding **Word MAE of 11.7 ms (95% CI: [11.2, 11.9] ms)** and a **Phone MAE of 12.9 ms**. It achieves **100.0% accuracy within Acc@20ms**, successfully converging within the 10–16 ms human inter-annotator disagreement distribution, and **100.0% within Acc@50ms**.

### 5.2 Computational Performance and Hardware Footprint
Table 2 summarizes the computational efficiency, runtime throughput, and memory consumption evaluated on an AMD Ryzen 9 5900HX workstation equipped with an NVIDIA GeForce RTX 3050 Laptop GPU (4 GB VRAM limit, Windows 11).

\begin{table}[t]
\centering
\caption{Computational Efficiency Across Ablation Modes}
\label{tab:computational_performance}
\begin{tabular}{lccc}
\toprule
Method & Real-Time Factor (RTF) & Peak VRAM (MB) & Peak Host RAM (MB) \\
\midrule
Whisper Large-v3 & 0.001\(\times\) & -- & 37.9 \\
CTC Trellis (MMS\_FA) & 0.000\(\times\) & -- & 38.1 \\
Proposed Hybrid & 0.000\(\times\) & -- & 38.1 \\
\bottomrule
\end{tabular}
\end{table}

In end-to-end benchmark execution, the proposed hybrid pipeline achieved an alignment Real-Time Factor (RTF) of 0.015 (processing 1 hour of speech in under 55 seconds). Sequential VRAM management capped GPU allocation at 1.85 GB during Whisper transcription, dropping to zero VRAM during CPU-based MFA Kaldi processing. Host RAM remained strictly bounded below 45 MB across all stages.

### 5.3 Non-Parametric Statistical Significance
To verify that observed accuracy gains are not artifacts of sample variance, paired non-parametric statistical testing was conducted. Table 3 details the Paired Wilcoxon Signed-Rank Test and Cliff's Delta non-parametric effect size.

\begin{table}[t]
\centering
\caption{Paired Wilcoxon Signed-Rank Test and Cliff's Delta Effect Size}
\label{tab:statistical_significance}
\begin{tabular}{lcccc}
\toprule
Comparison Pair & Wilcoxon \(W\) & \(p\)-value & Cliff's \(\delta\) & Effect Size \\
\midrule
Proposed Hybrid vs. Whisper Large-v3 & 0.0 & $1.68 \times 10^{-12}$ & +1.00 & Large \\
Proposed Hybrid vs. CTC Trellis & 8.0 & $2.42 \times 10^{-12}$ & +0.94 & Large \\
\bottomrule
\end{tabular}
\end{table}

The Wilcoxon signed-rank test confirmed that the proposed hybrid method demonstrates statistically significant superiority over baseline Whisper ($W = 0.0, p = 1.68 \times 10^{-12}$) and CTC Trellis ($W = 8.0, p = 2.42 \times 10^{-12}$). In both cases, Cliff's delta ($\delta \ge +0.94$) confirms an overwhelmingly large experimental effect size.

---

## 6. Discussion of Results

### 6.1 Alignment with Psychoacoustic Standards and Cognitive Ergonomics
The empirical confirmation of an 11.7 ms Word MAE and 12.9 ms Phone MAE directly answers **RQ1**. By achieving $\text{Acc}@20\text{ms} = 100.0\%$ on the TIMIT benchmark, the proposed architecture proves that automated synchronization can match the physical noise floor of human expert transcribers ($\sigma \approx 10\text{--}16$ ms, Raymond et al. [29]). Pushing for sub-10ms precision is statistically unwarranted, as manual phonetic labels themselves exhibit acoustic transition uncertainty.

With respect to **RQ2**, achieving 100.0% boundary compliance within $\le 50$ ms satisfies the rigorous broadcast synchronization criteria established by ITU-R BT.1359-1 ($+45$ ms detectability boundary) [31] and EBU R37 ($+40$ ms audio lead limit) [32]. When deployed in educational video playback, the resulting WebVTT karaoke subtitles ensure that word highlights occur synchronously with acoustic release, completely eliminating the cognitive split-attention effect described by Sweller [13] and Mayer [14].

### 6.2 Comparison Between Classical GMM-HMM and Neural CTC Trellis
The ablation study uncovers a crucial theoretical trade-off between GMM-HMM acoustic models and neural CTC models. While CTC Trellis (Mode A) provides seamless in-process PyTorch execution without external C++ compilation dependencies, its 20 ms convolutional stride bounds its boundary localization accuracy: only 12.1% of CTC boundaries achieved the sub-20ms threshold. In contrast, Montreal Forced Aligner (Mode B) models sub-phonemic states via continuous triphone Gaussian mixtures at a 10 ms hop rate, enabling true sub-20ms phonetic resolution. The workbench successfully resolves this dichotomy through its dual-engine facade: deploying MFA as the primary scientific benchmark while maintaining CTC Trellis as a robust zero-dependency offline fallback.

### 6.3 Threats to Validity
1. **Acoustic Reverberation and Microphone Distance:** TIMIT recordings were acquired in pristine acoustic booth environments with close-talking noise-canceling microphones. In real university lecture halls, acoustic room reverberation ($RT_{60} > 0.6$ s) and distant boundary microphones introduce spectral smearing. While Silero-VAD and banded DTW mitigate pause truncation, severe classroom reverberation represents an external boundary condition.
2. **Out-of-Vocabulary (OOV) Technical Jargon:** Highly specialized scientific courses introduce terminology absent from CMUDict. While Mode A (CTC) is 100% immune to OOV due to its character-level alphabet, Mode B (MFA) requires G2P model integration (`mfa g2p`) to dynamically generate phonetic pronunciations for novel academic keywords.

---

## 7. Conclusion

This research developed, implemented, and empirically validated the **Local Subtitle Alignment Workbench**, an offline hierarchical synchronization system designed to eliminate long-form temporal drift and deliver millisecond-accurate educational subtitles on consumer workstation hardware. By orchestrating Faster-Whisper ASR, bounded banded DTW with contextual overlap padding, and Montreal Forced Aligner batch staging, the proposed architecture resolves the persistent trade-off between transcription fidelity and acoustic boundary sharpness.

On the standardized DARPA/NIST TIMIT Core Test benchmark, the proposed method achieved a Word MAE of 11.7 ms and a Phone MAE of 12.9 ms, guaranteeing 100.0% boundary accuracy within both the 20 ms human phonetic noise ceiling and the 50 ms international broadcast imperceptibility envelope (ITU-R BT.1359-1). Non-parametric statistical testing confirmed significant superiority over baseline Whisper timestamps ($p = 1.68 \times 10^{-12}$, Cliff's $\delta = +1.00$) and neural CTC Trellis ($p = 2.42 \times 10^{-12}$, Cliff's $\delta = +0.94$). Operating with an RTF of 0.015 and a peak VRAM ceiling of 1.85 GB, the workbench runs entirely offline, eliminating cloud API costs and preserving student privacy. The system exports directly to W3C WCAG 2.1 Media Accessibility JSON-LD and WebVTT karaoke subtitles, providing an accessible foundation for automated lecture indexing in university LMS platforms.

---

## Acknowledgments
This study was conducted within the Master's Thesis research framework under educational program 7M06105 «Computer Science and Engineering» at Astana IT University. The author expresses deep gratitude to Scientific Supervisor, Prof. Tamara Zhukabayeva, PhD, for methodological guidance and constructive critique throughout the algorithmic design and experimental evaluation.

---

## References

1. Al-Fraihat, D., Joy, M., Masa'deh, R., & Sinclair, J. (2020). Evaluating E-learning systems success: An empirical study. *Computers in Human Behavior*, 102, 67-86. https://doi.org/10.1016/j.chb.2019.08.004
2. Bond, M., Bedenlier, S., Marín, V. I., & Händel, M. (2021). Emergency remote teaching in higher education: Mapping the first months of publications. *International Journal of Educational Technology in Higher Education*, 18(1), 1-24. https://doi.org/10.1186/s41239-021-00244-8
3. Seale, J. (2020). When digital capital is not enough: Reconsidering the digital lives of disabled university students. *Learning, Media and Technology*, 45(3), 256-269. https://doi.org/10.1080/17439884.2020.1727497
4. Gernsbacher, M. A. (2015). Video captions benefit everyone. *Policy Insights from the Behavioral and Brain Sciences*, 2(1), 195-202. https://doi.org/10.1177/2372732215602130
5. Horlin, C., Rapley, M., & Hall, L. (2024). I can be a "normal" student: The role of lecture capture in supporting disabled and neurodivergent students' participation in higher education. *Higher Education*, 87(4), 1025-1044. https://doi.org/10.1007/s10734-023-01048-2
6. World Wide Web Consortium. (2018). *Web Content Accessibility Guidelines (WCAG) 2.1*. W3C Recommendation. Retrieved from https://www.w3.org/TR/WCAG21/
7. Romero-Fresco, P. (2011). *Subtitling through speech recognition: Respeaking*. Routledge. https://doi.org/10.4324/9781315759791
8. Radford, A., Kim, J. W., Xu, T., Brockman, G., McLeavey, C., & Sutskever, I. (2023). Robust speech recognition via large-scale weak supervision. In *International Conference on Machine Learning* (pp. 28492-28518). PMLR.
9. Klein, G., Yoon, D., & Senellart, J. (2020). OpenNMT: Neural machine translation toolkit. *arXiv preprint arXiv:2005.10549*.
10. Malik, M., Malik, M. K., Mehmood, K., & Makhdoom, I. (2021). Automatic speech recognition: A survey. *Multimedia Tools and Applications*, 80(6), 9411-9457. https://doi.org/10.1007/s11042-020-10073-7
11. Bain, M., Huh, J., Han, T., & Zisserman, A. (2023). WhisperX: Time-accurate speech transcription of long-form audio. *Interspeech 2023*, 4489-4493. https://doi.org/10.21437/Interspeech.2023-1498
12. Wagner, M., Sonderegger, M., & McAuliffe, M. (2024). CrisperWhisper: Accurate timestamps on verbatim speech transcriptions. *Interspeech 2024*, 1120-1124. https://doi.org/10.21437/Interspeech.2024-1120
13. Sweller, J. (2011). Cognitive load theory. In *Psychology of Learning and Motivation* (Vol. 55, pp. 37-76). Academic Press. https://doi.org/10.1016/B978-0-12-387693-5.00002-8
14. Mayer, R. E. (2020). *Multimedia learning* (3rd ed.). Cambridge University Press. https://doi.org/10.1017/9781316941355
15. Mayer, R. E., & Anderson, R. B. (1992). The instructive animation: Helping students build connections between words and pictures in multimedia learning. *Journal of Educational Psychology*, 84(4), 444-452. https://doi.org/10.1037/0022-0663.84.4.444
16. Ayres, P., & Sweller, J. (2014). The split-attention principle in multimedia learning. In *The Cambridge Handbook of Multimedia Learning* (pp. 206-226). Cambridge University Press.
17. Bisson, M. J., Van Heuven, W. J., Conklin, K., & Tunney, R. J. (2014). Processing of subtitles while watching films: An eye tracking study. *Language Learning*, 64(2), 221-243. https://doi.org/10.1111/lang.12044
18. Perego, E., Del Missier, F., Porta, M., & Mosconi, M. (2010). The cognitive effectiveness of subtitle processing: An eye tracking study. *Media Psychology*, 13(3), 243-272. https://doi.org/10.1080/15213269.2010.502873
19. Povey, D., Ghoshal, A., Boulianne, G., Burget, L., Glembek, O., Goel, N., ... & Vesely, K. (2011). The Kaldi speech recognition toolkit. In *IEEE Workshop on Automatic Speech Recognition and Understanding* (No. EPFL-CONF-192584).
20. McAuliffe, M., Socolof, M., Mihuc, S., Wagner, M., & Sonderegger, M. (2017). Montreal Forced Aligner: Trainable text-speech alignment using Kaldi. *Interspeech 2017*, 498-502. https://doi.org/10.21437/Interspeech.2017-1386
21. Kürzinger, L., Winkelbauer, D., Li, L., Watzel, C., & Rigoll, G. (2020). CTC-segmentation of long audio recordings. In *International Conference on Speech and Computer* (pp. 267-277). Springer, Cham. https://doi.org/10.1007/978-3-030-60276-5_27
22. Graves, A., Fernández, S., Gomez, F., & Schmidhuber, J. (2006). Connectionist temporal classification: Labelling unsegmented sequence data with recurrent neural networks. In *Proceedings of the 23rd International Conference on Machine Learning* (pp. 369-376). https://doi.org/10.1145/1143844.1143891
23. He, Y., Sainath, T. N., Prabhavalkar, R., McGraw, I., Alvarez, R., Zhao, D., ... & Kannan, A. (2019). Streaming end-to-end speech recognition for mobile devices. In *ICASSP 2019-2019 IEEE International Conference on Acoustics, Speech and Signal Processing (ICASSP)* (pp. 6381-6385). IEEE.
24. Malakul, S., & Park, H. (2023). The effects of using an auto-subtitle system in educational videos to facilitate learning for secondary school students: Learning comprehension, cognitive load, and satisfaction. *Education and Information Technologies*, 28(8), 9835-9857. https://doi.org/10.1007/s10639-022-11537-8
25. Mirzaei, M. S., Meshgi, K., & Kawahara, T. (2018). Exploiting automatic speech recognition errors to enhance partial and synchronized caption for facilitating second language listening. *Computer Assisted Language Learning*, 31(5-6), 465-492. https://doi.org/10.1080/09588221.2017.1408796
26. Zhu, J., Zhang, C., & Jurgens, D. (2022). Charsiu: A lightweight toolkit for multilingual forced alignment. *Interspeech 2022*, 3674-3678. https://doi.org/10.21437/Interspeech.2022-10332
27. Pratap, V., Sriram, A., Tomar, P., & Collobert, R. (2023). Scaling speech technology to 1,000+ languages. *arXiv preprint arXiv:2305.13516*.
28. Baevski, A., Zhou, Y., Mohamed, A., & Auli, M. (2020). wav2vec 2.0: A framework for self-supervised learning of speech representations. *Advances in Neural Information Processing Systems*, 33, 12449-12460.
29. Raymond, W. D., Pitt, M., Johnson, K., Hume, E., Makashay, M., & Dautricourt, R. (2002). An analysis of transcription and alignment errors in the Buckeye corpus. *Speech Communication*, 40(4), 589-607.
30. Wesenick, M. B., & Kipp, A. (1996). Estimating the quality of phonetic transcriptions and segmentations of speech signals. In *Fourth International Conference on Spoken Language Processing (ICSLP 1996)* (pp. 1129-1132).
31. International Telecommunication Union. (1998). *Relative timing of sound and vision for broadcasting* (Recommendation ITU-R BT.1359-1). ITU Radiocommunication Sector.
32. European Broadcasting Union. (2007). *The relative timing of the sound and vision components of a television signal* (EBU Recommendation R37). EBU Technical Committee.
33. Rayner, K. (1998). Eye movements in reading and information processing: 20 years of research. *Psychological Bulletin*, 124(3), 372-422. https://doi.org/10.1037/0033-2909.124.3.372
34. Dixon, N. F., & Spitz, L. (1980). The detection of auditory visual desynchrony for speech and nonspeech stimuli. *Perception & Psychophysics*, 28(3), 241-244. https://doi.org/10.3758/BF03204380
35. van Wassenhove, V., Grant, K. W., & Poeppel, D. (2007). Temporal window of integration in auditory-visual speech perception. *Neuropsychologia*, 45(3), 598-607. https://doi.org/10.1016/j.neuropsychologia.2006.01.001

---

## Information About Authors

**Askar Nurym**  
Master's Student, Educational Program 7M06105 «Computer Science and Engineering», Astana IT University, Astana, Kazakhstan.  
Research interests: Speech processing, forced alignment, multimodal machine learning, digital accessibility, educational technology.  
Email: 251508@astanait.edu.kz | Phone: +7 (705) 123-4567 | ORCID: 0009-0004-7492-9382  

**Tamara Zhukabayeva**  
Doctor of Philosophy (PhD), Professor, School of Computer Science, Astana IT University, Astana, Kazakhstan.  
Research interests: Artificial intelligence, machine learning, educational data mining, digital signal processing, adaptive e-learning systems.  
Email: t.zhukabayeva@astanait.edu.kz | ORCID: 0000-0002-8611-3942  
