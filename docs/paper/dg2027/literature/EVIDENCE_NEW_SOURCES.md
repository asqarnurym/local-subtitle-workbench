# Evidence from new sources (read 21.11.2026)

Each entry was read from the downloaded full text (`literature/pdf/`, plain text in `literature/text/`, both local and outside Git). Quotes are short and page-anchored; everything else is paraphrase. Metadata were checked against the PDF and, where a DOI exists, Crossref. **Text for the paper must be written from these notes, not from memory.** Evidence for older sources is in `docs/LITERATURE_ANNOTATIONS.md` ("Ключевые факты"), verified 03–04.11.2026.

---

## FABench2026 — Chu et al., *FA-Bench: A Benchmark for Phone- and Word-Level Timestamp Accuracy in Forced Alignment and ASR on Clean and Noisy Speech*, arXiv:2609.32396v2, 8 Oct 2026. PDF SHA-256 `35cfbc5e…`

- **What it does (p1–2).** Open benchmark; "Track 1 gives every aligner the reference transcript and Track 2 gives it a recognizer's output" on the same audio, TIMIT and Buckeye with hand-marked boundaries, all evaluation speakers held out, 21 open models and 9 APIs, clean and four degradations.
- **Metric critique (p1, p3).** Matched-word MAE favours recognition-dependent systems: scored only at correctly recognized words, a system's Buckeye MAE "drops by 9% to 14%"; primary metric is boundary F1 at 20 ms, which charges missed and inserted words.
- **Numbers (Table 1, word tier, clean).** MFA 3.4: 21.8 ms (TIMIT), 21.3 ms (Buckeye). Whisper large-v3 own timestamps: 148.0 / 122.7 ms. Two-step "Qwen3-ASR → MFA": 21.8 / 22.7 ms. MMS-FA 31.1 / 37.1; WhisperX 37.2 / 41.7; TorchAudio 39.8 / 42.4.
- **Bias (p1, p4, Fig. 1).** Whisper word times are about 150 ms early at both ends; absolute error hides such offsets.
- **Splits (p2).** Buckeye has no official split; they define one by sex × age (6 train / 2 dev / 2 test speakers per cell). Not the same split as ours.
- **Use in the paper.** (1) External consistency check: our A2 MFA 19.6 ms (Buckeye) and 20.3 ms (TIMIT), B0 Whisper 126.5 ms (Buckeye) are of the same order as their MFA and Whisper rows — qualitative only (different clips, split, metric details, MFA version). (2) **Gap statement must change:** a same-protocol comparison of known transcript vs recognizer output on TIMIT/Buckeye with held-out speakers now exists. (3) Our scenario-B MAE is matched-word MAE; report coverage beside it and cite this critique as a limitation.
- **Status.** arXiv preprint (v2). Cite as preprint.

## Zolkepli2026 — H. Zolkepli, *Where Words Begin and End*, arXiv:2610.17782v2, 19 Oct 2026 (Scicom). SHA-256 `b05a05d5…`

- **Pilot benchmark (Table 6, p12).** Mean word-boundary error, clean: MFA (ARPA) 19.1 ms TIMIT, 21.0 ms Buckeye; MMS with torchaudio 37.5 / 41.4 ms; WhisperX 46.9 / 50.2 ms. MFA "is the most precise" of nine configurations (abstract, p1).
- **Why CTC starts late (p4).** On TIMIT with MMS-300M, "a median 67% of the frames inside a human word are blank" on the forced path; the first character frame "falls a median 33 ms after the human start".
- **Method (p1).** Whisper fine-tuned with LoRA to emit word start/end tokens, trained only on human boundaries; with FA-Bench's protocol 11.6 ms on TIMIT.
- **Use in the paper.** Explains our CTC baselines (A1 40.5 ms, B1 41.3 ms Buckeye; torchaudio MMS_FA) and supports "MFA remains the most precise open HMM aligner" with a 2026 source; neural aligners trained on human boundaries can now beat MFA (state of the art context, not our comparison).
- **Status.** Preprint, single author, company report. Cite cautiously.

## Vaidya2026 — Vaidya, Bailey, Badam, Bendel, He (Descript), *FuseAlign: Forced Alignment in the Wild*, arXiv:2609.33650v1, 27 Sep 2026, "Preprint. Under review." SHA-256 `f5eb5a16…`

- **Claims (p1).** Existing evaluations rely on "short, clean speech, perfect transcripts"; real pipelines run on long recordings and error-prone ASR output. FuseAlign "refines boundaries at millisecond resolution and detects missing transcript words".
- **Presence head (p6).** A globally constrained decoder must place every token, "so one mismatch can shift neighboring intervals"; FuseAlign localizes words independently and a presence head rejects words absent from the audio.
- **Use in the paper.** Related work on long-form, ASR-transcript alignment and on a per-word output beyond a point estimate (presence probability). Contrast: our reliability head predicts whether an MFA boundary is more than 20 ms off; it does not detect absent words. The "one mismatch shifts neighbours" remark matches our S1b mechanism (text placed over the wrong speech near seams).
- **Status.** Preprint under review.

## Kelley2024 — Kelley, Perry, Tucker, *The Mason-Alberta Phonetic Segmenter: a forced alignment system based on deep neural networks and interpolation*, Phonetica 81(5):451–508, 2024, doi:10.1515/phon-2024-0015 (Crossref). Read from arXiv:2310.15425v1. SHA-256 `84672428…`. Note: a correction to its Algorithm 2 appeared in 2026 (doi:10.1515/phon-2026-0074).

- **Result (p1, p32).** Interpolation beyond the 10 ms frame gave "a 27.92% relative increase of boundaries within the 10 ms threshold" and 6.77 % within 20 ms over MFA (best case).
- **Caveat (p31).** MFA started to "marginally outperform" the networks beyond about 25–30 ms.
- **Use in the paper.** Prior work on sub-frame boundary precision with neural models; relevant to BRQE's sub-frame correction. No priority claim.

## Kelley2025 — M. C. Kelley, *Gradient boundaries through confidence intervals for forced alignment estimates using model ensembles*, Phonetica 83(3):285–305, 2026, doi:10.1515/phon-2025-0039 (Crossref; online 6 May 2026). Read from arXiv:2506.01256v4. SHA-256 `d3910965…`

- **Method (p1).** Ten segment classifiers; boundary at the ensemble median with "a 97.85% confidence interval" from order statistics; the range "indicates the model uncertainty", "facilitating tasks like finding boundaries that should be reviewed".
- **Result (p1).** On Buckeye and TIMIT the ensemble boundaries show "a slight overall improvement" over a single model.
- **Use in the paper.** Closest prior work to our reliability head (per-boundary uncertainty for review). Difference: ensemble intervals around a neural aligner vs a single learned head that predicts P(MFA boundary error > 20 ms), evaluated by ROC-AUC and a rejection curve on held-out speakers.
- **Year to cite:** 2026 (journal issue); the bib key keeps "2025" only as an internal name — use `Kelley2026` in the final bib.

## Yeh2025 — Yeh, Meng, Tang, *Whisper Has an Internal Word Aligner*, Proc. IEEE ASRU 2025, pp. 1–7, doi:10.1109/ASRU65441.2025.11434635 (Crossref). Read from arXiv:2509.09987v1. SHA-256 `20f2900e…`

- **Claims (p1).** Prior evaluations of Whisper word timestamps are "relatively loose, typically using a tolerance of more than 200 ms"; selected attention heads give more accurate alignments under 20–100 ms tolerances, without training.
- **Use in the paper.** Supports that Whisper's own word times are coarse (our B0) and that the field is moving to stricter tolerances; not a system we ran.

## Thompson2026 — Thompson, Waller, Calderon Torres, Ming, Arroyo Chavez, Conway, Kushalnagar, Vogler, *Are Caption Metrics Broken? Latency, Deaf and Hard of Hearing User Ratings, and Cross-Technology Bias*, Proc. ASSETS 2026 (ACM SIGACCESS), pp. 1–22, doi:10.1145/3797867.3829032 (Crossref). Read from arXiv:2609.11408v1 (title there ends "…Bias across Technologies"). SHA-256 `bfbae77a…`

- **Study (p1).** 216 validated DHH and hearing participants; live-TV clips with original delay (7–12 s), synchronized TV captions, synchronized ASR captions, ASR with about 2 s delay.
- **Finding (p1, p14, p20).** Latency significantly affects ratings; hard-of-hearing viewers rated delayed TV captions "two points lower"; several participants said "delay was more disruptive than caption errors" (p20).
- **Use in the paper.** Motivation that timing, not only text accuracy, matters to caption users. Scale caveat: seconds of delay in live TV, not millisecond word boundaries; do not claim that 20 ms matters to viewers.

## Povey2011 — Povey et al., *The Kaldi Speech Recognition Toolkit*, IEEE ASRU 2011. Read from the EPFL Infoscience PDF. SHA-256 `07f6ee1b…`

- **Content (p1).** Open-source C++ toolkit on finite-state transducers (OpenFst), GMM and SGMM acoustic models with common linear and affine transforms; Apache 2.0.
- **Use in the paper.** MFA is built on Kaldi (GMM-HMM, speaker-adaptive transforms); one citation where MFA is introduced.

## Software references (READMEs read 21.11.2026)

- **Silero VAD** — Silero Team, GitHub repository snakers4/silero-vad; the README gives a BibTeX entry (author "Silero Team", year 2024). Cite with access date.
- **faster-whisper** — SYSTRAN, GitHub repository SYSTRAN/faster-whisper: reimplementation of Whisper on CTranslate2, "up to 4 times faster than openai/whisper for the same accuracy", 8-bit quantization on CPU and GPU. Cite with access date. Our runs: large-v3, `int8_float16`, CUDA.

## Cuozzo2018 — L. G. D. Cuozzo, D. A. Silva, M. Uliani Neto, F. O. Simões, E. J. Nagle (CPqD), *CNN-Based Phonetic Segmentation Refinement with a Cross-Speaker Setup*, PROPOR 2018, LNCS 11122, pp. 448–456, doi:10.1007/978-3-319-99722-3_45 (Crossref). Read 23.11.2026 from the author copy the author downloaded (9 pp.). SHA-256 `65c568f4…`

- **Method (p2–3).** Post-processing after MFA: a small VGG-like CNN looks at a 50-bin context (2 ms shift, about ±50 ms) of 16 acoustic features (12 MGCC with energy, two spectral-distance deltas, two energy deltas) centred on the MFA boundary and outputs the boundary position in the window. Training places the manual boundary at each of the 50 positions; one model per pair of phone classes, 63 models, covering 85 % of boundaries (p5).
- **Data (p3–4).** Brazilian Portuguese TTS recordings, read phonetically balanced sentences, three speakers; MFA and CNN trained on one female speaker (450 min); "cross speaker" = the other female and the male speaker.
- **Result (p6, Table 2).** Share of phone boundaries off by more than 10 ms: 50.3 → 20.0 % (same speaker), 52.6 → 27.7 % (other female), 58.5 → 41.0 % (male). Abstract: "an absolute gain between 20% and 33% in cross speaker scenario". No statistical tests, no confidence or reliability output.
- **Use in the paper.** Closest prior art for BRQE's refinement head: a CNN that corrects MFA boundaries in a fixed window and transfers across speakers. Differences to state (not "first"): BRQE works on word boundaries of spontaneous English, is trained on 20 disjoint speakers and tested on 20 held-out speakers, adds a reliability head (ROC-AUC, rejection curve), is compared with a constant-offset rival with speaker-level tests, and reports its negative transfer to read speech. Their gain is on read single-speaker TTS data at 5–10 ms tolerances; ours is smaller and on conversational speech — do not compare magnitudes.

## Holm1979 — S. Holm, *A Simple Sequentially Rejective Multiple Test Procedure*, Scandinavian Journal of Statistics 6(2):65–70, 1979, doi:10.2307/4615733. Read 23.11.2026 from a scan the author obtained (6 pp., no text layer; pages read as images). SHA-256 `eb4b0014…`

- **Procedure (p66–67, Scheme 1).** Order the obtained levels (p-values) $R^{(1)} \le \dots \le R^{(n)}$; compare them in turn with α/n, α/(n−1), …, α/1; reject while the level is below its bound and stop at the first that is not, accepting it and all remaining hypotheses. Holm calls it the "sequentially rejective Bonferroni test".
- **Guarantee (p67, Theorem 1).** The procedure "has the multiple level of significance α for free combinations", i.e. the probability of rejecting any true hypothesis is at most α (familywise error), proved from the Boole inequality.
- **Versus Bonferroni (p67).** Never rejects less than the classical Bonferroni test with the same statistics and in non-trivial cases rejects more, so it "ought to replace" Bonferroni.
- **Use in the paper.** One citation where Eq. 4 introduces Holm-adjusted p-values. Our Eq. 4 states the same procedure as adjusted p-values (reject $H_{(k)}$ iff $p^{	ext{Holm}}_{(k)} \le α$); the adjusted-value form is equivalent but is not written that way in Holm's paper — do not attribute the formula's notation to him. Pages 68–70 (power examples, applications) were not read; nothing from them is used.

## Hwang2023 — J. Hwang, M. Hira, C. Chen, X. Zhang, Z. Ni et al., *TorchAudio 2.1: Advancing Speech Recognition, Self-Supervised Learning, and Audio Processing Components for PyTorch*, Proc. IEEE ASRU 2023, pp. 1–9, doi:10.1109/ASRU57964.2023.10389648 (Crossref). Read from arXiv:2310.17864v1. SHA-256 `7921603c…`

- **Forced alignment (p3, §3).** TorchAudio 2.1 adds CTC-based forced alignment: `forced_align` "computes frame-level alignments between audio and transcripts using a CTC-trained neural network model", on CPU and GPU; a tutorial shows alignment "for more than 1000 languages using the CTC-based alignment model" from MMS.
- **Use in the paper.** Software citation for our CTC baselines (A1, B1): `torchaudio.pipelines.MMS_FA` with `forced_align` (`src/subtitle_workbench/ctc_aligner.py`). Pratap2024 covers the MMS model, this covers the alignment implementation.

## Reserve read 23.11.2026 (full texts in `literature/text/`)

### Huang2024 — R. Huang, X. Zhang, Z. Ni, L. Sun, M. Hira, J. Hwang, V. Manohar, V. Pratap, M. Wiesner, S. Watanabe, D. Povey, S. Khudanpur, *Less Peaky and More Accurate CTC Forced Alignment by Label Priors*, Proc. IEEE ICASSP 2024, pp. 11831–11835, doi:10.1109/ICASSP48485.2024.10446111 (Crossref). Read from arXiv:2406.02560v3. SHA-256 `bbf64ff1…`
- **Problem (p1).** CTC models have "peaky output distributions", which "can cause inaccurate forced alignments".
- **Table 1 (p3), ms, Buckeye / TIMIT.** Average predicted word duration (WDUR) for MMS: 181 / 242 ms against 241 / 305 ms in the manual reference, i.e. MMS words about 60 ms too short on both corpora. MFA word boundary error 41 / 23 ms, MMS 53 / 37 ms (their WBE averages start and end per utterance — not our metric).
- **Use in the paper.** Independent support for our signed-error finding: our CTC (torchaudio MMS_FA) words are 58 ms (Buckeye) and 62 ms (TIMIT) too short (`reports/fa_extras_20261123/fa_extras.json`). One clause in the Discussion with Zolkepli2026.

### Sorenson2026 — L. Sorenson, M. Crandall, E. K. Ringger, S. D. Richardson (BYU), *Scaling Forced Alignment to End-User Devices*, arXiv:2609.21145v1, Sep 2026 (preprint). SHA-256 `e052c075…`
- **Content (p1).** Linear-memory (Hirschberg) Viterbi for CTC forced alignment: memory for three-hour inputs from 140 GB to 5 MB, a third of torchaudio's CPU time; pruning keeps alignment within 250 ms of the unpruned result in more than 98 % of cases. Accuracy is agreement with unpruned alignment, not manual boundaries.
- **Remark (p4).** Cutting silence with VAD "introduces cascaded errors (like other chunk-based alignment systems)".
- **Use in the paper.** Optional: long-audio alignment on end-user hardware (our 4 GB laptop GPU) and an independent remark that chunking causes cascaded errors (our CLAIM-107…110). Preprint; do not quote numbers.

### Rousso2026 — R. Rousso, E. Cohen, J. Keshet, *Fully Differentiable Neural Forced Alignment via Soft Dynamic Programming*, arXiv:2606.25460v1, Jun 2026 ("submitted to the IEEE"). SHA-256 `30816e09…`
- **Content (p1, p6–7).** FALCON: phoneme aligner with an identity branch, a boundary branch and a differentiable soft-DP decoder. Table I: phone-level accuracy within 25 ms on Buckeye 69.9 % against 60.6 % for MFA; MFA is better at 10 ms. Word level is evaluated zero-shot with MFA's dictionary and G2P.
- **Use in the paper.** Optional, one clause in Related Work: neural phoneme aligners trained on manual boundaries now beat MFA at 25–100 ms on TIMIT and Buckeye (with Zolkepli2026, Multilingual2026). FA-Bench notes FALCON's training overlaps its Buckeye split. Preprint.

### Strgar2022 — L. Strgar, D. Harwath, *Phoneme Segmentation Using Self-Supervised Speech Models*, Proc. IEEE SLT 2022, pp. 1067–1073, doi:10.1109/SLT54892.2023.10022827 (Crossref). Read from arXiv:2211.01461v1. SHA-256 `1e49fa71…`
- **Evaluation (p5).** Precision and recall of boundaries are ambiguous when several predictions fall within one tolerance window; a strict scheme "prohibits double counting", a lenient one allows it; results "consistently show deviations of 3-4%" (supervised) and 5–7 % (unsupervised).
- **Use in the paper.** Optional, one clause where boundary F1 is defined: our matching is strict by construction (each predicted word is paired with at most one reference word). Cite only if the F1 definition is given in the paper.

## Read but kept in reserve (not for the 6-page paper)


- **Multilingual2026** — Weber, Zehavi, Rousso, Keshet, *Multilingual Word-Level Forced Alignment with Self-Supervised Representations and Learned Dynamic Programming*, arXiv:2606.10675v1 (Jun 2026). Claims to outperform MFA and MMS on TIMIT and Buckeye. Preprint; optional one-clause citation with FuseAlign and Zolkepli.
- **RefFree2026** — Akavarapu, Daniel, Jäger, *Phoneme- and Word-Level Metrics Using Self-Supervised Speech Representations for Forced Alignment Evaluation*, arXiv:2608.28508v1. Reference-free alignment metrics; dissertation reserve.
- **Manenti2016** — Manenti, Pellegrini, Pinquier, *CNN-based phone segmentation experiments in a less-represented language*, Interspeech 2016 (IRIT PDF). Reports 79 % F-measure on Buckeye at 20 ms, "equal to the human inter-annotator agreement rate" (p1). Possible support for the 20 ms tolerance; check against Raymond2002 before use.

## Not obtained (need manual access)

- **CHI 2024**, *How Users Experience Closed Captions on Live Television: Quality Metrics Remain a Challenge*, doi:10.1145/3613904.3641988 — automatic download blocked by ACM; optional.
