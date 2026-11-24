# Statement bank for the DG 2027 paper

> **Check status (24.11.2026).** All sections, Table I and the Abstract plan were checked against the sources; the open decisions were settled (§10f). Still open: the items of §10d not marked done and the missing evidence notes of eight older sources.

**Paper.** "Word Boundary Accuracy and Reliability Estimation in Forced Alignment for Accessible Educational Video" (Askar Nurym, Tamara Zhukabayeva, Astana IT University). IEEE DG 2027, 4–6 pages, A4 two-column IEEE template, English.

**Date.** 23.11.2026.

**Purpose.** This file holds ready-to-paste statements for every section of `latex/main.tex`. Each statement has its support. The paper is assembled later by choosing statements; nothing here is paper text yet. No other file was changed, nothing was committed, and no model or experiment was run.

## 0. Rules, conventions and budget

### 0.1 Rules followed

1. **Our results.** Results come only from CLAIM-101…118 in `docs/CLAIM_LEDGER.csv`, with their wording and caveats. Other numbers come from `reports/` JSON fields that also appear in a checked `docs/*_RESULTS.md`. Such statements are marked **needs CLAIM before submission** when they claim more than a CLAIM says.
2. **Other works.** Statements about other works rest on `literature/EVIDENCE_NEW_SOURCES.md` (cited below as EVN, with line numbers), `docs/LITERATURE_ANNOTATIONS.md` (LA, with line numbers), or the full text with a page. Eight older sources have no note in EVN or LA: Gernsbacher2015, Horlin2024, Radford2023, Bain2023, Pratap2024, McAuliffe2017, Mirzaei2018 and LeCunff2024. Their pages were read on 23.11.2026 from the PDFs in `Thesis/Article base/`, using `pdftotext` output in the session scratchpad. Their notes must be added to LA before submission (see §10d).
3. **Positioning** (`TITLE_KEYWORDS_RQ.md`, lines 46–55):
   - FA-Bench appears only with other recent evaluations, as the source of the F1 metric, and once in the Discussion. It is never in the title, abstract or contributions.
   - The text never says "verify", "validate", "replicate", "confirm" or "first".
   - The gap is stated as differences.
   - The limits stay visible.
4. **References.** Only the 25 selected references are used freely. Optional references (Povey2011, Moreno1998, Mirzaei2018) and reserve references (Kelley2024, Mu2026, LeCunff2024, Manenti2016, Huang2024, Strgar2022, Sorenson2026, Rousso2026) appear only in OPTIONAL statements. Dropped keys (Malakul2023, Wagner2024, Kurzinger2020, Dror2018, Zhu2022, Raymond2002) are never used.
5. **What the paper never claims:**
   - learning benefit, user impact, "novel", "state of the art" or "first";
   - speed as an evaluation metric;
   - millisecond relevance drawn from Thompson2026, whose delays are in seconds.
6. **Scenario-B numbers.** Every scenario-B error carries its word coverage. CLAIM-115 asks for its caveat next to every scenario-B number; see §10d, item 5.
7. **Template style:**
   - "Fig. 1" even at the start of a sentence;
   - equations as "(1)": write `\eqref{label}` with the labels of `latex/equations.tex`;
   - a zero before decimals;
   - "data" is plural;
   - "et al." with no period after "et";
   - no symbols or math in the title or abstract;
   - abbreviations defined at first use in the body, even if the abstract defines them;
   - no footnotes in the references;
   - the Acknowledgment in the third person;
   - Nurym2026 cited in the third person ("Prior work [n] …") for the blind copy.

### 0.2 Conventions in this file

- **ID format.** `**ID** [REQUIRED|OPTIONAL] statement`. REQUIRED marks the recommended core; OPTIONAL marks surplus or space-dependent text. Order follows the flow of each section.
- **Citations.** Written as `[BibKey]`; replace them with `\cite{}`. Page numbers in support lines refer to the version that was read. Where that is an arXiv or author copy, it is said so.
- **Support types:**
  - (a) CLAIM id;
  - (b) report path and field;
  - (c) bib key, page and evidence line;
  - (d) method description in `FORMULAS.md`, `PSEUDOCODE.md` or a code path.
- **Abbreviations to define at first use in the body.** ASR, VAD, MFA, CTC, MMS, NFA, GMM-HMM, MAE, Acc@20 ("share of boundaries within 20 ms"), CI, BRQE (boundary refinement and quality estimation), CNN, MLP, ROC-AUC (area under the receiver operating characteristic curve), WebVTT, G2P, CV (cross-validation). "Boundary F1" is defined with `\eqref{eq:f1}`.
- **Mode names**, used in text and Table I:
  - B0: Whisper timestamps;
  - B1: Whisper text and CTC;
  - B2: Whisper text and MFA (proposed, scenario B; no anchoring);
  - A1: known text and CTC;
  - A2: known text, anchoring and MFA (proposed, scenario A);
  - "+const": constant offset;
  - "+BRQE": the learned module.

### 0.3 Word budget

About 4,000–4,500 words of body text fit 6 pages with 1 table, 3–4 figures (with the pipeline diagram), 2 algorithms, 2 equation blocks and about 25 references. The table below gives targets. Counts are words of statement text only, without support lines. They were computed with a script after writing.

| Section | Target (words) | REQUIRED in bank | OPTIONAL in bank |
|---|---:|---:|---:|
| Abstract (separate, one paragraph) | 180–220 | fact list only | — |
| I. Introduction | 550 | 674 | 127 |
| II. Related Work (A 130 / B 270 / C 200) | 600 | 707 | 339 |
| III. Method (A 230 / B 110 / C 250 / D 110) | 700 | 671 | 104 |
| IV. Experimental Setup (A 200 / B 120 / C 240 / D 90) | 650 | 702 | 183 |
| V. Results (A 380 / B 400 / C 220) | 1,000 | 1,025 | 516 |
| VI. Discussion with Limitations (330 / 270) | 600 | 776 | 238 |
| VII. Conclusion | 150 | 179 | 19 |
| **Body total** | **4,250** | **4,734** | **1,526** |
| Captions (Table I, Fig. 1–4) | about 200 | §9 | — |

Using every REQUIRED statement gives about 11 % over target. This is the cut margin: the first cuts are marked "can be dropped if short of space" in the notes. See §10e.

---

## 1. Title and Abstract plan

**Title** (from `TITLE_KEYWORDS_RQ.md`; no symbols): Word Boundary Accuracy and Reliability Estimation in Forced Alignment for Accessible Educational Video

**Keywords:** forced alignment, word boundary accuracy, speech-text alignment, automatic speech recognition, Montreal Forced Aligner, boundary refinement, reliability estimation, captions, accessibility, educational video

**Abstract facts** (one paragraph, in contribution order). There are no citations, symbols or math, and units are spelled out. "F1" can be written "F-score" (see §10d).

- **AB-01** Captions help many learners only if words appear at the right moment. This paper studies word-boundary accuracy and reliability in a local captioning pipeline for accessible educational video.
  - Support: Gernsbacher2015 p. 195 (captions benefit many viewers; "only if" is our motivation, not a finding; write "depend on timing" if a reviewer could read it as one). No other benchmark is named.
- **AB-02** The pipeline combines speech detection, speech recognition or a known transcript, transcript anchoring and the Montreal Forced Aligner with a lightweight learned module that refines each word boundary and scores the reliability of each word. It runs on a laptop with a 4 gigabyte graphics card.
  - Support: (d) `PSEUDOCODE.md` Algorithm 1; `docs/ARCHITECTURE.md` line 5; SET-D-01.
- **AB-03** It is evaluated on spontaneous and read English (999 Buckeye clips from 20 speakers unseen in training and 160 TIMIT utterances) against reference boundaries based on hand-corrected labels.
  - Support: CLAIM-101, 104; SET-A-01.
- **AB-04** On spontaneous speech with a known transcript, the module lowers the mean absolute word-boundary error from 19.6 to 17.0 milliseconds and beats a constant-offset correction for all 20 test speakers. Its reliability score detects words with boundary errors above 20 milliseconds with an area under the receiver operating characteristic curve of about 0.75. It does not significantly improve read speech.
  - Support: CLAIM-103, 105, 104, 119. One clause about read speech is enough; it keeps the claim honest at no cost.
- **AB-05** On long recordings, an overlap-and-stitch scheme passes a pre-registered check of the error near chunk seams that the original chunking fails. With a known transcript, the error on recordings that aligned is 19.2 to 20.4 milliseconds at one to ten minutes.
  - Support: CLAIM-107, 108 (survivors: "that aligned" must stay). "Pre-registered" may stay; the design selection is in RES-C-10.
- **AB-06** With recognized instead of known text, the boundary F-score at a 20 millisecond tolerance is 0.624 instead of 0.710, with 89.0 percent of words matched.
  - Support: CLAIM-114, 102. No cause (CLAIM-117 is not used in the abstract).

---

## 2. Introduction (target 550 words)

> Checked 24.11.2026 against the CLAIMs, the report files and the PDFs. Author decisions were settled on 24.11.2026 (§10f).

- **INT-01** [REQUIRED] Captions make video accessible to deaf and hard-of-hearing viewers, and studies report that they also help hearing viewers [Gernsbacher2015].
  - Support: (c) Gernsbacher2015 p. 195 (abstract: captions "benefit everyone who watches videos") and p. 196 ("captions benefit persons who are D/deaf or hard of hearing … Captions also benefit hearing persons"). Horlin2024 was removed here: its 48 % counts pausing, speed change and captions together, so it does not show that captions help.
  - Note: pages read from the full text (rule 2); detail is in RW-A.
- **INT-02** [REQUIRED] Caption users also care about timing: in a survey on television captions shown with delays of two to twelve seconds or without delay, ratings were lower with delay, and several participants found it more disruptive than caption errors [Thompson2026].
  - Support: (c) Thompson2026 arXiv p. 1 (216 participants; delays up to 7–12 s for TV, mean 2 s for ASR), pp. 12–13 (mean quality 5.09 vs 3.66 for TV, 5.20 vs 4.81 for ASR) and p. 20 ("delay was more disruptive than caption errors"); EVN lines 52–54.
  - Note: seconds scale only. Do not imply that 20 ms matters to viewers.
- **INT-03** [REQUIRED] Word-level timing lets a player highlight each word as it is spoken, and open aligners already produce subtitle files of this kind [Rastorgueva2023].
  - Support: (c) Rastorgueva2023 p. 5257: NFA "can generate subtitle files for highlighting words or tokens as they are spoken"; LA line 87.
  - Note: our exporter writes WebVTT with one inline timestamp per word (`src/subtitle_workbench/export.py`, `export_karaoke_vtt`).
- **INT-04** [REQUIRED] A time alone does not say how far it can be trusted. Per-boundary uncertainty has been proposed to find boundaries that should be reviewed [Kelley2026]; this paper scores the reliability of each word.
  - Support: (c) Kelley2026 arXiv p. 1 ("facilitating tasks like finding boundaries that should be reviewed"); EVN line 40.
  - Note: the sentence on a captioner who checks words "instead of every word" was removed (saved labour; CLAIM-105 reason allows review only as a possibility in the Discussion, DIS-10).
- **INT-05** [REQUIRED] Open tools produce word times in two ways:
  - an automatic speech recognition (ASR) model such as Whisper reports its own word timestamps [Radford2023];
  - a forced aligner places a known or recognized transcript on the audio. Examples are the Montreal Forced Aligner (MFA) [McAuliffe2017] and aligners based on connectionist temporal classification (CTC) [Pratap2024], [Hwang2023].
  - Support: (c) Radford2023 arXiv p. 3 (the model predicts timestamps unless told not to); McAuliffe2017 p. 498 ("speech and its corresponding orthographic transcription are automatically aligned at the word and phone level"); Pratap2024 arXiv v1 §3.1.3, p. 6 (acoustic model trained with CTC; "Forced Alignment using CTC"); Hwang2023 p. 3, EVN line 82.
- **INT-06** [REQUIRED] Recent evaluations on TIMIT and Buckeye place MFA ahead of the CTC-based aligners they test [Rousso2024], [McAuliffe2026], [Zolkepli2026], [Chu2026FABench].
  - Support: (c):
    - Rousso2024 p. 1 and p. 4 ("MFA outperformed both WhisperX and MMS", on words that WhisperX and MMS recognized correctly); LA lines 64–65;
    - McAuliffe2026 p. 352, Table 4 (MFA ARPA 3.0: 19.93 and 21.75 ms; MMS 43.06 and 49.54; WhisperX 110.04 and 110.90; the PDF text layer scrambles the table, values as checked in LA lines 151–153); p. 352 text: "MFA 3.0 substantially outperforms all three ASR-based aligners";
    - Zolkepli2026 p. 12, Table 6 (MFA 19.1 and 21.0; MMS 37.5 and 41.4; WhisperX 46.9 and 50.2);
    - Chu2026FABench p. 3, Table 1 (MFA 3.4 21.8 and 21.3; MMS-FA 31.1 and 37.1; WhisperX 37.2 and 41.7).
  - Note: "recognizer timestamps" was removed: Rousso2024 and McAuliffe2026 do not test them. "Manual boundaries" was removed (TIMIT words, SET-A-01). Positioning rule 1 (cite FA-Bench only within the group). Do not write "MFA is the most precise aligner": the same works show neural aligners ahead of MFA (Zolkepli2026 abstract; MAPS in Chu2026FABench Table 1).
- **INT-07** [REQUIRED] These works compare or propose aligners and recognizers, mostly on short utterances. This paper proposes and tests additions to a local captioning pipeline, and measures inside it what the choice of transcript costs.
  - Support: positioning rule 2 (`TITLE_KEYWORDS_RQ.md` line 48); Vaidya2026 p. 1 ("short, clean speech, perfect transcripts"); McAuliffe2026 p. 351 (utterances separated by 300 ms of silence).
  - Note: "rank existing aligners" was corrected: McAuliffe2026 presents MFA 3.0 and Zolkepli2026 trains a new aligner. Rule 2 changed the same way 24.11.2026.
- **INT-08** [REQUIRED] The paper differs from those evaluations in three ways:
  - it adds a learned module that refines each aligner boundary and scores its reliability, tested on speakers unseen in training;
  - it measures where accuracy is lost on recordings of one to ten minutes;
  - it tests its main comparisons speaker by speaker.
  - Support: positioning rule 5 (`TITLE_KEYWORDS_RQ.md` lines 51–54); CLAIM-103, 105, 107–110; E1 protocol (`docs/E1_ANALYSIS_RESULTS.md` §1).
  - Note: a difference, not a priority claim. FA-Bench also holds out speakers (EVN line 13), so the difference is the speaker-level tests, not the split alone. "Every comparison" was removed (tolerance curves and the CLAIM-117 observation have no speaker test). "Unseen in training": see M-C-11 for the pilots.
- **INT-09** [REQUIRED] Prior work [Nurym2026] built a multimodal accessibility pipeline with ASR-based word-level captions and reported its processing speed, but left manual validation of caption accuracy for future work. The present paper measures the word timing of a captioning pipeline and tests a learned correction of it.
  - Support: `Prototype/academic_paper/paper.tex` line 52 (abstract: "actual accuracy has not been manually evaluated during this research … Manual validation of caption accuracy and description quality is left for future work"; RTF reported); `IMPROVEMENT_PLAN.md` §11.3.
  - Note: "improves" was removed. Third person for the blind copy. The 2026 paper meant transcription accuracy (WER/CER), so do not write that it left "timing accuracy" open.
- **INT-10** [REQUIRED] RQ1: How large is the word-boundary error of open pipelines that combine speech recognition with forced alignment, measured against reference boundaries based on hand-corrected labels on read (TIMIT) and spontaneous (Buckeye) English, and how much does a known transcript reduce it compared with recognized text?
  - Support: `TITLE_KEYWORDS_RQ.md` line 36.
  - Note: differs from RQ1 in that file in two places: "word- and phone-boundary" is cut to "word-boundary" (no phone result is in the Results), and "manual boundaries" is replaced (SET-A-01). Approved 24.11.2026.
- **INT-11** [REQUIRED] RQ2: Does a lightweight learned post-alignment module reduce forced-alignment boundary error more than a constant-offset correction on held-out speakers, and does its reliability score separate words whose boundaries are more than 20 ms off?
  - Support: `TITLE_KEYWORDS_RQ.md` line 37.
  - Note: "words whose boundaries" replaces "boundaries", because the label is per word (`FORMULAS.md` Eq. 10; CLAIM-105 reason).
- **INT-12** [REQUIRED] RQ3: On recordings of one to ten minutes, how do recording length and chunking affect boundary error and the share of failed alignments?
  - Support: `TITLE_KEYWORDS_RQ.md` line 38.
- **INT-13** [REQUIRED] Contribution 1, refinement and reliability. A lightweight boundary refinement and quality estimation (BRQE) module corrects each MFA boundary and scores the reliability of each word. It is trained only on speakers disjoint from the test set and frozen before testing. On held-out spontaneous speech it beats a constant-offset correction under both mean absolute error (MAE) and boundary F1 for all 20 test speakers, and its reliability score detects words with boundaries more than 20 ms off (ROC-AUC about 0.75). It does not significantly improve read speech.
  - Support:
    - CLAIM-103, 104, 105, 114; contribution 1 (`TITLE_KEYWORDS_RQ.md`, corrected text);
    - 20 of 20 speakers under MAE: (b) `reports/e1_analysis_20261102/analysis.json` A2brqe_vs_A2const and B2brqe_vs_B2const, n_speakers_improved = 20.
  - Note:
    - CLAIM-118 and "ends of speech segments" removed. CLAIM-119 for the MAE speaker count.
    - "Frozen before testing": the weights (M-C-08); pilots on test speakers are in M-C-11.
- **INT-14** [REQUIRED] Contribution 2, long recordings. On recordings of one to ten minutes, the original chunking raises the error near chunk seams, and an overlap-and-stitch scheme passes a pre-registered seam check. Failed recordings grow with length, because a single failed chunk fails the whole recording; no length effect on the error was found among the recordings that aligned.
  - Support: CLAIM-107 (pre-registered check C; seams measured on one-minute recordings), CLAIM-108, CLAIM-109, CLAIM-110.
  - Note: "accuracy is lost at chunk seams rather than with length" was weakened: the length test is not significant, which the protocol does not read as absence (`docs/S1B_RESULTS.md` §3), and only survivors are scored. The seam check covers 60 s recordings only. Contribution 2 changed to match 24.11.2026.
- **INT-15** [REQUIRED] Contribution 3, what a recognized transcript costs. Inside one local pipeline on a 4 GB laptop GPU, with speaker-level tests and a metric that charges missed words, boundary F1 at 20 ms on spontaneous speech is 0.624 with recognized text (word coverage 89.0 %) and 0.710 with a known transcript. The paper reports what the difference consists of as a post-hoc observation.
  - Support: CLAIM-114 (secondary analysis), CLAIM-102 (coverage), CLAIM-117 (24.11.2026 wording), CLAIM-101; `docs/ARCHITECTURE.md` line 5 (4 GB GPU); contribution 3 (`TITLE_KEYWORDS_RQ.md`, corrected text).
  - Note: "the cost comes from recognition, not alignment", "placed equally well" and "about 9 points" were removed. No advice on where effort is better spent.
- **INT-16** [OPTIONAL] No novelty is claimed for post-alignment boundary correction itself, which has precedents in boundary correction over HMM alignment and CNN refinement of MFA boundaries [Stolcke2014], [Cuozzo2018].
  - Support: `TITLE_KEYWORDS_RQ.md` line 63; (c) Stolcke2014 p. 5552 (LA lines 97–100); Cuozzo2018 author copy pp. 1–2 (EVN line 68).
  - Note: if dropped here, keep RW-C-01.
- **INT-17** [OPTIONAL] The rest of the paper is organized as follows: Section II reviews related work, Section III describes the method, Section IV the experimental setup, Section V the results, and Section VI discusses them and their limits.
  - Support: section plan in `latex/main.tex`.
  - Note: can be dropped if short of space.
- **INT-18** [OPTIONAL] In a survey of disabled, neurodivergent and neurotypical students, 48 % of participants mentioned pausing, changing speed or using captions to adapt lecture recordings to their needs [Horlin2024].
  - Support: (c) Horlin2024 p. 2082.
  - Note: same as RW-A-02; use one of them.

---

## 3. Related Work (target 600 words)

> Checked 24.11.2026 against the PDFs (page text). Author decisions were settled on 24.11.2026 (§10f).

### 3.A Caption Timing and Accessibility (target 130)

- **RW-A-01** [REQUIRED] A review of more than 100 empirical studies concludes that same-language captions improve comprehension of, attention to and memory for video in children, adolescents, college students and adults [Gernsbacher2015].
  - Support: (c) Gernsbacher2015 p. 195 (abstract), full text from `Thesis/Article base/Video Captions Benefit Everyone.pdf`.
  - Note: not yet in LA (rule 2).
- **RW-A-02** [REQUIRED] In a qualitative survey of disabled, neurodivergent and neurotypical university students, 48 % of participants mentioned pausing, changing speed or using captions to adapt lecture recordings to their needs [Horlin2024].
  - Support: (c) Horlin2024 p. 2082: "adapting pace by pausing, slowing down, speeding up, and using captions in the recordings was mentioned by 48% of participants"; p. 2079, sample groups.
  - Note: the 48 % is of all participants, not only disabled students.
- **RW-A-03** [REQUIRED] In a survey of 216 participants on television captions, delay lowered quality ratings (for example, mean 3.66 with delay and 5.09 without for original TV captions, on a scale of 1 to 7) [Thompson2026].
  - Support: (c) Thompson2026 arXiv p. 1, pp. 12–13.
  - Note: the two-point figure for hard-of-hearing viewers was removed; the paper calls that analysis exploratory (p. 13–14).
- **RW-A-04** [REQUIRED] These delays were of seconds (about 2 to 12 s). They show that delays of this size matter to the viewers surveyed, not that word-boundary errors of tens of milliseconds do, and this paper makes no claim about viewers.
  - Support: EVN lines 52 and 54 (scale caveat).
  - Note: mandatory caveat whenever Thompson2026 is cited.
- **RW-A-05** [OPTIONAL] Partial and synchronized captions for second-language listening align ASR output with the transcript to time each word, then show only the words that are hard to hear [Mirzaei2018].
  - Support: (c) Mirzaei2018, self-archived Kyoto copy p. 3 ("PSC synchronizes the text to speech in word-level using ASR technology") and p. 4 (forced alignment of ASR transcripts with the human transcript); `Thesis/Article base/` PDF.
  - Note: optional reference. Its own pages may differ from the journal's pp. 17–36.
- **RW-A-06** [NOT USED] In focus groups, only neurodivergent students raised concerns about the quality of captions and transcripts in online learning, such as keeping up with automated captions or finding mistakes in transcripts [LeCunff2024].
  - Support: (c) LeCunff2024 PDF p. 8 ("Only neurodivergent students raised concerns about the quality of the captions and transcripts …"); `Thesis/Article base/` PDF.
  - Note: reserve reference, on caption quality, not timing. It must not be used as advice to improve the transcript.

### 3.B ASR Timestamps and Forced Alignment (target 270)

- **RW-B-01** [REQUIRED] Whisper is a speech recognizer trained on 680,000 hours of weakly supervised audio [Radford2023]. faster-whisper reimplements it on CTranslate2 with 8-bit quantization on CPU and GPU [FasterWhisper].
  - Support: (c) Radford2023 arXiv p. 2 ("scaling weakly supervised speech recognition … to 680,000 hours of labeled audio data"); FasterWhisper README, EVN line 64.
  - Note: do not repeat the README's speed claim (rule 5).
- **RW-B-02** [REQUIRED] Whisper's own word timestamps are coarse. Earlier evaluations of them typically used tolerances above 200 ms, while selected attention heads inside Whisper give more accurate word alignments at 20–100 ms tolerances without training [Yeh2025].
  - Support: (c) Yeh2025 arXiv p. 1; EVN line 47.
  - Note: not a system we ran.
- **RW-B-03** [REQUIRED] WhisperX observes that Whisper's word-level timestamps are not available out of the box. It therefore adds voice activity detection (VAD) and forced alignment of the recognized text with an external phoneme model [Bain2023].
  - Support: (c) Bain2023 arXiv:2303.00747v2 p. 1 ("word-level timestamps are not available out-of-the-box"; VAD, then forced alignment with a phoneme recognition model) and p. 2 §2.4. Interspeech page numbers are not used: the PDF at hand is the arXiv version.
- **RW-B-04** [REQUIRED] The Massively Multilingual Speech (MMS) project trains a CTC acoustic model for forced alignment [Pratap2024], and TorchAudio implements CTC forced alignment on CPU and GPU with a tutorial for the MMS alignment model [Hwang2023].
  - Support: (c) Pratap2024 arXiv v1 §3.1.3, p. 6; Hwang2023 arXiv p. 3; EVN lines 82–83.
- **RW-B-05** [REQUIRED] The NeMo Forced Aligner (NFA) uses CTC-based models to produce word-level subtitles. It was evaluated on AMI meeting recordings with a 200 ms match window, where MFA aligned only 5 of 16 audio files [Rastorgueva2023].
  - Support: (c) Rastorgueva2023 p. 5257 (Viterbi alignment with NeMo CTC-based models; 200 ms window) and p. 5258, Table 1 ("only 5 out of 16 audio files were aligned successfully"); LA lines 87–92.
  - Note: the 200 ms window is much coarser than our 20 ms (LA line 93).
- **RW-B-06** [REQUIRED] MFA is built on the Kaldi toolkit. It uses a Gaussian mixture model and hidden Markov model (GMM-HMM) architecture, with triphone acoustic models and speaker adaptation of acoustic features [McAuliffe2017].
  - Support: (c) McAuliffe2017 p. 498 ("MFA is built on top of Kaldi"; "standard GMM/HMM architecture"; "triphone acoustic models and speaker adaptation") and p. 499 (fMLLR).
  - Note: add [Povey2011] after "Kaldi" if space allows (RW-B-11).
- **RW-B-07** [REQUIRED] On TIMIT and Buckeye, MFA placed word boundaries more accurately than WhisperX and MMS at all tested time resolutions, in a comparison limited to words the recognizers got right [Rousso2024]. MFA 3.0 reached mean word-boundary errors of 19.93 ms on TIMIT and 21.75 ms on Buckeye [McAuliffe2026].
  - Support: (c) Rousso2024 p. 1 (comparison "only on words correctly recognized") and p. 4 ("at all time resolutions"); LA lines 64–65. McAuliffe2026 p. 352, Table 4; LA lines 151–152.
- **RW-B-08** [REQUIRED] Two 2026 preprints also compare aligners on TIMIT and Buckeye: one finds MFA the most precise of nine existing configurations and then trains a more precise aligner [Zolkepli2026]; the other gives each system either the reference transcript or a recognizer's output, with held-out speakers [Chu2026FABench].
  - Support: (c) Zolkepli2026 arXiv p. 1; Chu2026FABench arXiv v2 pp. 1–2.
  - Note: the model counts were removed and the trained aligner added, because "MFA the most precise" alone is half of the abstract. Rule 1: among several. Both are preprints, so recheck for published versions (`REFERENCE_AUDIT.md` §6).
- **RW-B-09** [REQUIRED] Evaluations of forced alignment have been described as relying on short, clean speech and perfect transcripts, whereas captioning pipelines run on long recordings and often on error-prone recognized text [Vaidya2026].
  - Support: (c) Vaidya2026 arXiv p. 1 ("relying on short, clean speech, perfect transcripts … real-world media and data-processing pipelines operate on long and diverse recordings").
  - Note: "most of these evaluations" was corrected to the source's own statement: Zolkepli2026 and Chu2026FABench also test degraded speech and recognizer output.
- **RW-B-10** [REQUIRED] This paper reports seam error, the effect of length and failed chunks separately, on recordings of one to ten minutes spliced from clips with reference boundaries.
  - Support: positioning rule 5 (`TITLE_KEYWORDS_RQ.md` line 53); CLAIM-107–110.
  - Note: "unlike these evaluations", "manual" and "where accuracy is lost" were removed. A difference only, no claim about what others did not do.
- **RW-B-11** [OPTIONAL] MFA builds on Kaldi, an open-source toolkit with finite-state transducers and GMM acoustic models with linear and affine feature transforms [Povey2011].
  - Support: (c) Povey2011 p. 1; EVN line 58.
  - Note: optional reference.
- **RW-B-12** [OPTIONAL] MFA 3.0 can segment longer audio files with VAD and iterate over the transcript [McAuliffe2026], while its benchmark uses utterances separated by 300 ms of silence.
  - Support: (c) McAuliffe2026 p. 350 ("segmenting longer audio files … MFA can iteratively segment the transcript") and p. 351 (300 ms rule); LA lines 156 and 163.
- **RW-B-13** [OPTIONAL] Very long audio can be aligned by recursive speech recognition with a gradually restricted dictionary and language model, a method tolerant to noise and to gaps in the transcript [Moreno1998].
  - Support: (c) Moreno1998 p. 1; LA lines 110–114.
  - Note: optional reference.
- **RW-B-14** [OPTIONAL] A neural forced aligner based on a speech LLM handles spliced speech of up to 300 s; its reference labels come mostly from MFA [Mu2026].
  - Support: (c) Mu2026 ACL pp. 1–2 (up to 300 s) and pp. 4–5 (pseudo-timestamp labels by MFA); LA lines 170–181 (manual labels only for an internal Chinese set).
  - Note: "rather than from manual boundaries" was corrected. Reserve reference. Do not compare its numbers with ours.
- **RW-B-15** [OPTIONAL] Cutting audio with VAD introduces cascaded errors, as in other chunk-based alignment systems [Sorenson2026].
  - Support: (c) Sorenson2026 arXiv p. 4; EVN lines 94–95.
  - Note: reserve reference; preprint, so do not quote its numbers.
- **RW-B-16** [OPTIONAL] Neural aligners trained on manual boundaries can now beat MFA. One example is Whisper fine-tuned to emit word start and end tokens, which reaches a word-boundary error of 11.6 ms on TIMIT [Zolkepli2026]. These systems are not compared here.
  - Support: (c) Zolkepli2026 arXiv p. 1; EVN line 21. Optionally add [Rousso2026] (EVN lines 98–99; reserve).

### 3.C Boundary Refinement and Confidence (target 200)

- **RW-C-01** [REQUIRED] Correcting boundaries after HMM alignment is an established idea. Boundary correction models with system fusion raised the share of TIMIT phone boundaries within 20 ms from 93.9 % to 96.8 % [Stolcke2014].
  - Support: (c) Stolcke2014 p. 5552 (abstract: "from 93.9% to 96.8% boundary accuracy with a 20-ms tolerance"); LA lines 97–100.
  - Note: phone boundaries on read speech. No priority claim (LA lines 101–108).
- **RW-C-02** [REQUIRED] Cuozzo et al. [Cuozzo2018] refine MFA boundaries with a small CNN that takes a 50-frame window of acoustic features (2 ms per frame) around each boundary and outputs the corrected position. They train one model per pair of phone classes on Brazilian Portuguese text-to-speech recordings of one speaker and test it on that speaker and two others.
  - Support: (c) Cuozzo2018 author copy pp. 2–5 (63 models, covering 85 % of boundaries); EVN lines 68–69. "50 candidate positions" was replaced by the method as described.
  - Note: define CNN (convolutional neural network) here or in Section III, whichever comes first.
- **RW-C-03** [REQUIRED] For two other speakers, that refinement cut the share of phone boundaries more than 10 ms off from 52.6 % to 27.7 % and from 58.5 % to 41.0 % [Cuozzo2018].
  - Support: (c) Cuozzo2018 author copy p. 6, Table 2; EVN line 70.
  - Note: "no statistical tests and no reliability output" was removed (a verdict on another work); the difference is stated in RW-C-06. Do not compare these magnitudes with ours (EVN line 71; RW-C-07).
- **RW-C-04** [REQUIRED] Kelley [Kelley2026] aligns with an ensemble of ten classifiers and places each boundary at the ensemble median with a 97.85 % confidence interval. The width of the interval shows model uncertainty and can help find boundaries to review. The ensemble gave a slight overall improvement on Buckeye and TIMIT.
  - Support: (c) Kelley2026, arXiv v4 p. 1; EVN lines 40–41.
- **RW-C-05** [REQUIRED] FuseAlign adds a presence head that predicts whether a transcript word occurs in the audio and rejects absent words [Vaidya2026]. It scores word presence, not boundary error.
  - Support: (c) Vaidya2026 arXiv p. 6; EVN lines 28–29.
- **RW-C-06** [REQUIRED] The module proposed here differs from these works in several ways:
  - it refines word and phone boundaries of spontaneous English after MFA;
  - it is trained on 20 speakers and tested on 20 others;
  - it outputs a reliability score for each word, evaluated by ROC-AUC and a rejection curve;
  - it is compared with a constant-offset rival using speaker-level tests;
  - it is reported with its result on read speech, where it gives no significant improvement.
  - Support: EVN line 71 (Cuozzo2018 use), line 42 (Kelley2026 use), line 29 (Vaidya2026 use); CLAIM-103, 104, 105.
  - Note: stated as differences, not "first" (rule 3).
- **RW-C-07** [OPTIONAL] Those gains were measured on text-to-speech recordings of phonetically balanced sentences at 5–10 ms tolerances, ours on conversational speech, so their sizes are not compared.
  - Support: EVN line 71.
- **RW-C-08** [OPTIONAL] Neural segmentation with sub-frame interpolation increased the share of boundaries within 10 ms by 27.92 % relative to MFA, but MFA marginally outperformed the networks beyond about 25–30 ms [Kelley2024].
  - Support: (c) Kelley2024 arXiv pp. 1, 31–32; EVN lines 34–35.
  - Note: reserve reference. It parallels our TIMIT result (RES-B-13); see DIS-09.

---

## 4. Method (target 700 words)

> Checked 24.11.2026 against the code in `src/` and `scripts/`, not only `PSEUDOCODE.md`. Author decisions were settled on 24.11.2026 (§10f).

### 4.A Pipeline (target 230)

- **M-A-01** [REQUIRED] Fig. 1 and Algorithm 1 show the pipeline for one recording. It takes 16 kHz mono audio and an optional transcript, and returns word and phone boundaries with a reliability score for each word.
  - Support: (d) `PSEUDOCODE.md` Algorithm 1 (input and output); `latex/algorithms.tex` `alg:pipeline`.
- **M-A-02** [REQUIRED] Silero VAD [SileroVAD] marks pauses of at least 0.4 s. Whisper large-v3 [Radford2023], run through faster-whisper [FasterWhisper] with int8_float16 computation, returns the recognized words with timestamps.
  - Support: (d) `PSEUDOCODE.md` Algorithm 1, lines 1–2; (b) `reports/buckeye/benchmark_results.json` config.asr (model = large-v3, compute_type = int8_float16).
  - Note: the VAD is the Silero model called from faster-whisper 1.2.1 (`IMPROVEMENT_PLAN.md` §10.3).
- **M-A-03** [REQUIRED] In scenario A, the known transcript is anchored to Whisper's words (Section III-B). In scenario B, Whisper's own words are aligned.
  - Support: (d) `PSEUDOCODE.md` Algorithm 1, lines 3–6.
- **M-A-04** [REQUIRED] Words are split into chunks of at most 30 s with 0.5 s of padding. Cuts go at the midpoint of the latest suitable VAD pause if there is one, otherwise at a segment boundary (Whisper segments in scenario B, groups of 40 transcript words in scenario A), otherwise at the widest gap between words.
  - Support: (d) `src/subtitle_workbench/chunker.py` `partition_into_chunks`; `src/subtitle_workbench/pipeline.py` SEED_SEGMENT_WORDS = 40, `_segments_from_words`.
  - Note: "ASR segment boundary" was corrected; in scenario A the segments are not from the ASR. `PSEUDOCODE.md` line 7 has the same simplification.
- **M-A-05** [REQUIRED] MFA 3.4.3 aligns all chunks of a speaker in one call. It uses the english_us_arpa acoustic model and dictionary, a grapheme-to-phoneme (G2P) model for out-of-vocabulary words, speaker adaptation, and the --fine_tune option, which places boundaries below the 10 ms frame shift.
  - Support: (d) `PSEUDOCODE.md` Algorithm 1, line 8; (b) `reports/buckeye/benchmark_results.json` config.aligners.mfa (speaker_adaptation = true, fine_tune = true, invocation = per_speaker); `docs/RUNBOOK.md` line 51 (fine_tune); `IMPROVEMENT_PLAN.md` line 45 (version 3.4.3).
- **M-A-06** [REQUIRED] A chunk that MFA cannot align is recorded as a failure and is never replaced by another aligner's output.
  - Support: (d) `PSEUDOCODE.md` Algorithm 1, line 8 ("a failure is recorded, never replaced").
- **M-A-07** [REQUIRED] The chunk alignments are merged into one monotonic timeline and refined by BRQE (Section III-C). The words can be exported as WebVTT captions with an inline timestamp for every word.
  - Support: (d) `PSEUDOCODE.md` Algorithm 1, lines 9–11; `src/subtitle_workbench/export.py` `export_karaoke_vtt` (inline per-word timestamps; cues break at 8 words, 42 characters or a 1 s pause).
  - Note: "can be exported". The API does not yet call BRQE or the stitch (`IMPROVEMENT_PLAN.md` §11.5; §10d).
- **M-A-08** [REQUIRED] Every benchmark clip is shorter than 30 s (the longest Buckeye test clip is 10.7 s), so it forms a single chunk. Chunking matters only for the long recordings of Section III-D.
  - Support: (d) `PSEUDOCODE.md`, notes under Algorithm 1; audio headers of the 1,000 test-sample files (maximum 10.744 s, read 24.11.2026).
- **M-A-09** [OPTIONAL] Fig. 1 caption statement: Proposed pipeline. Scenario A anchors a known transcript to Whisper's words, and scenario B aligns Whisper's own words. MFA aligns them chunk by chunk, and BRQE refines every boundary and outputs a reliability score for each word.
  - Support: (d) `PSEUDOCODE.md` Algorithm 1.
  - Note: the author draws Fig. 1 (`ARTIFACT_VALIDATION.md` §4).

### 4.B Transcript Anchoring (target 110)

- **M-B-01** [REQUIRED] Chunking needs a time for every word, so scenario A first gives each word of the known transcript an approximate time by anchoring it to Whisper's words.
  - Support: (d) `PSEUDOCODE.md` Algorithm 3 (output: "approximate times for every reference word") and Algorithm 1, line 7 (chunks are cut from word times).
- **M-B-02** [REQUIRED] The two word sequences are aligned by dynamic programming, as in \eqref{eq:anchor}. Identical normalized words score +2, others −1, and gaps −1. Only cells within a band of width w = max(50, 0.1 max(n, m), |n − m| + 1) around the diagonal are filled, so the cost is O(n·w).
  - Support: (d) `FORMULAS.md` Eq. 6; `PSEUDOCODE.md` Algorithm 3, lines 1–2; `src/subtitle_workbench/anchoring.py` `banded_sequence_alignment`.
  - Note: if the equation is dropped for space, keep this sentence in words.
- **M-B-03** [REQUIRED] Exact matches on the best path become anchors if they do not start before the previous anchor ends and lie within the recording. Runs of words without an anchor share the interval between neighbouring anchors in proportion to their character length.
  - Support: (d) `src/subtitle_workbench/anchoring.py` `anchor_transcript` (words at either end use the start or end of the recording; each word lasts at least 10 ms); `FORMULAS.md` Eq. 7 (`eq:interp`).
- **M-B-04** [OPTIONAL] The interpolation can be stated as \eqref{eq:interp}.
  - Support: (d) `FORMULAS.md` Eq. 7.
  - Note: drop first if short of space.

### 4.C Boundary Refinement and Quality Estimation (target 250)

- **M-C-01** [REQUIRED] For every MFA boundary, BRQE reads a 64-band log-mel window of ±100 ms (25 ms frames, 5 ms hop, 41 frames) and six scalar features: start or end, word or phone, scenario, log duration, sub-frame offset, and a bias.
  - Support: (d) `FORMULAS.md` Eq. 8; `PSEUDOCODE.md` Algorithm 2, lines 1–4; `src/subtitle_workbench/refiner.py`.
- **M-C-02** [REQUIRED] Three 1-D convolutions, followed by one hidden layer of 128 units that also receives the scalar features (dropout 0.2), feed two heads, as in \eqref{eq:brqe-h} and \eqref{eq:brqe}. One head gives a shift of at most 0.1 s that is added to the boundary; the other gives the probability that the MFA boundary is more than 20 ms off.
  - Support: (d) `refiner.py` `_build_net` (a single hidden layer, so "MLP" in Eq. 8 means that layer); `FORMULAS.md` Eq. 8 (Δmax = 0.1 s); Eq. 9 (label 1[|ε| > 0.02 s]).
- **M-C-03** [REQUIRED] After refinement, if a token starts before the previous one ends, both times move to their midpoint, and tokens shorter than 5 ms get their original times back. The word reliability is one minus the larger error probability of the word's start and end, as in \eqref{eq:reliability}.
  - Support: (d) `refiner.py` `_shifted`, `refine_prediction`; `FORMULAS.md` Eq. 10.
  - Note: the second step runs after the first, so do not claim that refined tokens never overlap (the docstring says so, the code does not guarantee it).
- **M-C-04** [REQUIRED] The training loss \eqref{eq:loss} adds two parts:
  - an L1 error in milliseconds, divided by 20, on boundaries within 0.1 s of the reference;
  - 0.5 times the binary cross-entropy of the error label.
  - Training uses AdamW (learning rate 10⁻³, weight decay 10⁻⁴), batch 512 and 12 epochs with one seed.
  - Support: (d) `FORMULAS.md` Eq. 9; `PSEUDOCODE.md` training paragraph; (b) `reports/buckeye/benchmark_results.json` config.refiners.brqe_config.
- **M-C-05** [REQUIRED] BRQE was trained on 3,000 clips from the 20 Buckeye training speakers. Their MFA boundaries in both scenarios (A2 with known text and B2 with Whisper's text; words and phones; 382,270 boundaries matched to manual ones) form one training set with manual boundaries as targets. One set of weights serves both scenarios, with the scenario as an input feature.
  - Support: (d) `scripts/train_brqe.py` SCENARIO_MODES, `load_training_boundaries`; (b) `reports/brqe_cv_20260401.json` n_matched = 382270; `benchmark_results.json` config.refiners.trained_on (3000 clips, 20 speakers).
  - Note: corrected. The old text ("aligned with known text as in scenario A") followed the plan in `IMPROVEMENT_PLAN.md` §6.3, not the code. The B2 clips that failed (10 of 3,000) are absent. Decided: as in the code; the plan has a dated note.
- **M-C-06** [REQUIRED] The constant-offset rival shifts each boundary by the median training correction (over boundaries within 0.1 s of the reference) for its boundary kind and scenario, as in \eqref{eq:const}. These medians are at most 1.4 ms.
  - Support: (d) `FORMULAS.md` Eq. 11; `ConstantRefiner.fit`; `models/brqe/const_offsets.json` (largest −1.4 ms, word start, B).
  - Note: can be written in words without the equation.
- **M-C-07** [REQUIRED] A rule fixed before any cross-validation numbers existed decided whether refinement entered the pipeline: in 5-fold speaker cross-validation on the training speakers, it had to lower word MAE below that of the constant offset in both scenarios (paired Wilcoxon over 20 speakers, p < 0.05). Both scenarios met the rule (20 of 20 speakers, p < 0.001).
  - Support: `IMPROVEMENT_PLAN.md` §6.5 (rule fixed 29.10.2026 before CV numbers); (b) `reports/brqe_cv_20260401.json` decision.refinement_enters_proposed = true, per_scenario A = true, B = true, tests.word_{A,B}.brqe_vs_const (speakers_improved = 20, p_value = 9.57e-05, normal approximation); CLAIM-103 reason.
- **M-C-08** [REQUIRED] BRQE was trained and selected without test speakers, and its weights and the offsets were frozen and hashed before they were applied to any test speaker.
  - Support: (d) `scripts/train_brqe.py` refuses runs with test speakers; commit `bb74b81` (29.10.2026 08:26) with weights, before the BRQE pilot (14:46 local time) and tag `bench-frozen-20261029c`; (b) config.refiners hashes.
  - Note: narrowed. "Before any run on test speakers" was wrong: see M-C-11.
- **M-C-11** [REQUIRED; place in Setup V-A] Pipeline defects were found and fixed in pilots on 400 clips from all 40 speakers; the samples, BRQE weights and benchmark code were then frozen. Of the 999 test clips, 22 had been in a pilot. BRQE was trained on the training speakers only, and its weights were fixed before it was applied to any test speaker.
  - Support: (b) `reports/pilot_buckeye/benchmark_results.json` and `reports/pilot_brqe_buckeye/benchmark_results.json` (n_speakers = 40, n_utterances = 400; 28.10.2026 23:23 and 29.10.2026 09:46 UTC); overlap counted 24.11.2026 against `reports/buckeye_test_sample_20260401.json`; fixes after the pilot in `IMPROVEMENT_PLAN.md` ("Исправлено до заморозки по итогам пилотов").
  - Note: added in the check; CLAIM-122. Decided 24.11.2026: CLAIM-122, place once, in Setup V-A after SET-A-05 (not in Method, not in Limitations).
- **M-C-09** [OPTIONAL] If refinement had failed the rule, only the reliability head would have been kept.
  - Support: `IMPROVEMENT_PLAN.md` §6.5.
- **M-C-10** [OPTIONAL] Hyperparameters were the defaults, without tuning. Their sensitivity was checked afterwards on training speakers only (RES-B-15).
  - Support: `IMPROVEMENT_PLAN.md` §6.5 ("подбор не проводился") and §9.4; `docs/BRQE_SENSITIVITY_RESULTS.md`.

### 4.D Long Recordings (target 110)

- **M-D-01** [REQUIRED] With the default VAD padding of 400 ms, short pauses are not detected, so a chunk seam can fall inside speech. The 0.5 s padding then contains a neighbour's speech without its text.
  - Support: (d) faster-whisper default speech_pad_ms = 400, `IMPROVEMENT_PLAN.md` §10.3 (pauses below about 1.2 s; microtest on 6 recordings, `docs/S1B_MICROTEST_FINDINGS.md`); `chunker.py` (a chunk's text is its own words only).
  - Note: design rationale from a small pilot that is not versioned. Do not give its numbers and do not call it the cause of the seam error (§10d).
- **M-D-02** [REQUIRED] Overlap-and-stitch (Algorithm 4) uses 30 ms VAD padding and extends each chunk with neighbouring words until they span at least 3 s on each side or the neighbour has no more words. It then aligns all chunks.
  - Support: (d) `PSEUDOCODE.md` Algorithm 4, lines 1–4; `scripts/seam_stitch.py` (SPEECH_PAD_MS = 30, MIN_OVERLAP_S = 3.0).
- **M-D-03** [REQUIRED] At each seam, the two tracks are joined at an anchor word. The anchor has the same normalized text in both tracks and both of its boundaries within 20 ms, and it is the closest such word to the seam. The first word of the earlier track and the last word of the later track are not used. Without an anchor, the cut falls at the seam time, and the timeline is made monotonic.
  - Support: (d) `scripts/seam_stitch.py` `stitch` (loops over a[1:] and b[:-1]; ANCHOR_TOL_S = 0.02).
  - Note: corrected to the code. The protocol and `PSEUDOCODE.md` say "not a track's outermost word"; the code excludes only the words far from the seam and allows the last word of the earlier track and the first word of the later one. Decided: as in the code; `PSEUDOCODE.md` corrected.
- **M-D-04** [REQUIRED] A long recording counts as failed when any of its chunks fails to align, and failures are reported beside errors.
  - Support: `docs/S1_LONG_RECORDINGS_PROTOCOL.md` (runs paragraph, failure rule; rule 3); `docs/S1B_RESULTS.md` §1.

---

## 5. Experimental Setup (target 650 words)

> Checked 24.11.2026 against the code, the reports and the PDFs. Author decisions were settled on 24.11.2026 (§10f).

### 5.A Corpora and Speaker Split (target 200)

- **SET-A-01** [REQUIRED] Read speech comes from TIMIT [Garofolo1993], in the NLTK sample of 160 utterances from 16 speakers, not the full corpus. Its phone boundaries were placed automatically and corrected by hand; its word boundaries were derived from the phone segments by a string alignment program.
  - Support: CLAIM-106 reason; `docs/CORPORA_TAXONOMY.md` line 32; (c) Garofolo1993, NISTIR 4930 scan, PDF pp. 17 and 62 (word boundaries by dynamic programming string alignment with the phonetic segments), p. 51 (phone boundaries "hand corrected").
  - Note: corrected. "Manual word boundaries" is not accurate for TIMIT. Decided 24.11.2026: "reference boundaries based on hand-corrected labels" everywhere our two corpora are meant.
- **SET-A-02** [REQUIRED] Spontaneous speech comes from the Buckeye corpus [Pitt2005]: conversational American English from 40 talkers from central Ohio, with word and phone labels that were aligned automatically and then corrected by hand.
  - Support: (c) Pitt2005 p. 89 (abstract: 307,000 words, 40 talkers, central Ohio) and PDF p. 4 (Entropics Aligner, then "hand-correcting the phonemic labels and their alignment"); LA line 125; `src/subtitle_workbench/buckeye.py` docstring (hand-corrected labels).
- **SET-A-03** [REQUIRED] The 40 Buckeye speakers were split at random, with a fixed seed, into 20 training and 20 test speakers. BRQE saw only the training speakers.
  - Support: (b) `reports/buckeye_split_20260401.json` (n_speakers = 40, test_speakers 20, train_speakers 20, seed = 20260401, method).
- **SET-A-04** [REQUIRED] Clips are maximal runs of at least three ordinary words without labelled silence, non-speech or unknown tokens, 1 to 30 s long. They get up to 0.25 s of adjoining silence and never extend into interviewer speech or noise.
  - Support: (d) `src/subtitle_workbench/buckeye.py` `segment_track` (min_words = 3, min_duration = 1.0, max_duration = 30.0, margin = 0.25), `is_regular_word` (`<sil>` ends a run).
  - Note: clip edges are our cuts, not ends of utterances. This makes our clips easier than full utterances (LIM-02).
- **SET-A-05** [REQUIRED] The test set has 50 random clips per test speaker. One clip with empty audio was excluded, leaving 999 clips.
  - Support: (b) `reports/buckeye/benchmark_results.json` config.sample (per_speaker = 50, n_utterances = 1000) and config.excluded_corpus_defects (s1901b_0119: empty audio); CLAIM-101 reason.
- **SET-A-06** [REQUIRED] Long recordings were built for each test speaker by joining that speaker's consecutive clips without inserted pauses until they reach at least 60, 300 or 600 s. Reference labels are shifted by each clip's offset, and shorter recordings are prefixes of longer ones.
  - Support: (d) `docs/S1_LONG_RECORDINGS_PROTOCOL.md`, data paragraph.
  - Note: all clips of the speaker are used, not the 50 test-sample clips ("test clips" was corrected).
- **SET-A-07** [REQUIRED] The joins between clips are not natural speech.
  - Support: `docs/S1_LONG_RECORDINGS_PROTOCOL.md` (data paragraph, "стыки клипов не являются естественной речью"; rule 5).
  - Note: repeated as a limit in LIM-04.
- **SET-A-08** [OPTIONAL] Buckeye has no official split, so splits differ between papers.
  - Support: (c) Chu2026FABench p. 1 ("Buckeye ships no official split, so every paper picks its own"); EVN line 13.
  - Note: an extra FA-Bench citation beyond rule 1. "Ours differs from FA-Bench's" was removed: it invites a comparison of splits. Use only if the Discussion citation (DIS-03) is dropped.
- **SET-A-09** [OPTIONAL] The tempo variants use 160 TIMIT and 200 Buckeye clips, time-stretched with pitch preserved by factors of 0.8 to 1.25.
  - Support: (b) `docs/S2_RESULTS.md` §1; CLAIM-111.
  - Note: only if DIS-13 is kept.

### 5.B Compared Modes (target 120)

- **SET-B-01** [REQUIRED] Five modes are compared:
  - B0: Whisper's own word timestamps;
  - B1: Whisper's words aligned by CTC with torchaudio MMS_FA [Pratap2024], [Hwang2023];
  - B2: Whisper's words aligned by MFA (no anchoring);
  - A1: the known transcript aligned by CTC;
  - A2: the known transcript anchored and aligned by MFA.
  - Support: (b) `reports/buckeye/benchmark_results.json` config.modes and modes.*.name; config.aligners.ctc.model = torchaudio.pipelines.MMS_FA; EVN line 83.
  - Note: B2 corrected: `pipeline.py` anchors only a known transcript; the frozen mode name "Whisper + anchoring + MFA" and the mode list in §0.2 are imprecise. A small table or one sentence.
- **SET-B-02** [REQUIRED] A2 and B2 are also run with the constant offset and with BRQE, giving nine modes in all.
  - Support: (b) config.modes (9 entries).
- **SET-B-03** [REQUIRED] B1 follows the WhisperX idea of aligning Whisper's text with a separate phoneme-level model [Bain2023]. The WhisperX and NFA programs themselves were not run.
  - Support: (d) `PSEUDOCODE.md`, notes under Algorithm 1; `IMPROVEMENT_PLAN.md` §10.1; (c) Bain2023, arXiv:2303.00747v2 pp. 1–2 (§2.4 forced phoneme alignment). The PDF at hand is the arXiv version, so "p. 4489" was removed.
- **SET-B-04** [OPTIONAL] Commercial services were not measured.
  - Support: `IMPROVEMENT_PLAN.md` §10.1.

### 5.C Metrics and Statistics (target 240)

- **SET-C-01** [REQUIRED] For each reference word matched to a predicted word, its start and end each give one boundary error. MAE averages these errors, and Acc@20 is the share within 20 ms, as in \eqref{eq:mae} and \eqref{eq:acc}. MAE was fixed as the primary metric before the test runs.
  - Support: (d) `FORMULAS.md` Eqs. 1–2; CLAIM-114 reason ("MAE stays the pre-registered primary metric").
- **SET-C-02** [REQUIRED] The 20 ms tolerance follows common practice in segmentation studies [Stolcke2014].
  - Support: (c) Stolcke2014 p. 5553 ("percentage of the automatically labeled boundaries … within 20 ms of the manually labeled boundaries, which has been widely used in previous studies"); LA line 199.
  - Note: Stolcke2014 measures phone boundaries.
- **SET-C-03** [REQUIRED] Predicted and reference words are paired by Needleman–Wunsch alignment of normalized words (match +2, mismatch −2, gap −1), and only identical words count as matched. Word coverage is the share of matched reference words, as in \eqref{eq:coverage}.
  - Support: (d) `FORMULAS.md` Eq. 3; `metrics.py::_align_token_sequences`.
- **SET-C-04** [REQUIRED] MAE and Acc@20 use matched words only, so word coverage is reported beside every scenario-B error.
  - Support: CLAIM-102 reason ("must be reported next to MAE"); `IMPROVEMENT_PLAN.md` §10.1.
- **SET-C-05** [REQUIRED] Matched-word MAE can favour systems that depend on recognition, because missed words drop out of it [Chu2026FABench]. Boundary F1 at 20 ms, as in \eqref{eq:f1}, therefore counts every predicted and every reference boundary, with the boundaries of failed clips as misses. We added it as a secondary check after the main results, under a protocol written before its numbers; MAE stays primary.
  - Support:
    - (c) Chu2026FABench pp. 1, 3 (one aligner's Buckeye MAE "drops by 9% to 14%" when scored on recognized words only; its TIMIT MAE does not move); EVN line 10;
    - (d) `FORMULAS.md` Eq. 3a;
    - CLAIM-114 reason ("Secondary analysis added after FA-Bench … say so in any paper wording");
    - `docs/F1_RESULTS.md` line 3 (protocol `docs/F1_PROTOCOL.md` committed before the numbers).
  - Note: positioning rule 4. This is the second permitted FA-Bench citation. Two sentences.
- **SET-C-06** [REQUIRED] Comparisons are tested speaker by speaker, as in \eqref{eq:speaker}. Each speaker's MAE is pooled over the clips scored by both modes, and the paired differences go into an exact two-sided Wilcoxon signed-rank test. p-values within each corpus and family (seven comparisons for MAE, five for F1) are adjusted by Holm's step-down procedure [Holm1979], as in \eqref{eq:holm}.
  - Support: (d) `FORMULAS.md` Eq. 4; `docs/E1_ANALYSIS_RESULTS.md` §1; `f1_results.json` tests_edge20 (five entries); (c) Holm1979 pp. 66–67 (procedure and Theorem 1), from EVN lines 75–76 (the scan has no text layer; not reread 24.11.2026). In F1 the speaker value is F1, not MAE. The tests pair clips, not identical word sets, where the two modes match different words.
  - Note: do not attribute the adjusted-p notation to Holm (EVN line 78).
- **SET-C-07** [REQUIRED] Speaker-level tests are used because errors of utterances from the same speaker can be correlated, and resampling single utterances does not handle such dependence [Liu2020Blockwise].
  - Support: (c) Liu2020Blockwise p. 596 ("this method fails in dealing with dependent data … ASR performance on utterances from the same speaker could be correlated"); p. 597 (blocks by speakers).
  - Note: our estimator is a speaker cluster bootstrap, not their blockwise bootstrap (manifest role: "not identical estimator").
- **SET-C-08** [REQUIRED] 95 % CIs come from a percentile bootstrap over speakers with 2,000 resamples.
  - Support: (d) `FORMULAS.md` Eq. 5; (b) `reports/buckeye/benchmark_results.json` bootstrap_resamples = 2000, seed = 42, config.ci_unit = speaker.
- **SET-C-09** [REQUIRED] A word counts as erroneous for the reliability evaluation when the larger error of its two uncorrected MFA boundaries exceeds 20 ms, as in \eqref{eq:label}. The score is evaluated by ROC-AUC and by a rejection curve: the MAE, after BRQE, of the matched words kept after rejecting the least reliable share. Both use matched words only.
  - Support: (d) `FORMULAS.md` Eq. 10; `scripts/speech_benchmark.py` `quality_estimation`; CLAIM-105 reason (label definition).
- **SET-C-14** [REQUIRED] MAE was the pre-registered primary metric; the speaker-level tests, boundary F1 and the boundary-group analyses are secondary and were added later.
  - Support: CLAIM-114 reason; `docs/E1_ANALYSIS_RESULTS.md`; decided 24.11.2026: said once, here (LIM-08 is optional).
- **SET-C-10** [OPTIONAL] With 20 speakers, an exact two-sided test reaches its smallest possible p-value, 2/2²⁰ ≈ 1.9 × 10⁻⁶, when all 20 differences have the same sign.
  - Support: `docs/F1_RESULTS.md` line 33; `IMPROVEMENT_PLAN.md` §6.5 (2/2²⁰ ≈ 1.907·10⁻⁶).
  - Note: helps the reader see why many p-values are identical.
- **SET-C-11** [OPTIONAL] Each predicted word is paired with at most one reference word, so a boundary cannot be counted twice. Lenient schemes that allow this changed reported phone-boundary scores by several percent [Strgar2022].
  - Support: (c) Strgar2022 arXiv p. 5 ("3-4%" supervised, "5-7%" unsupervised); EVN lines 102–103.
  - Note: reserve reference, only if the F1 definition is given (it is: SET-C-05).
- **SET-C-12** [OPTIONAL] Secondary descriptive analyses split boundaries into groups:
  - by whether both, one or none of the neighbouring words were recognized;
  - by position at the edges of our cut clips or inside them;
  - by signed start, end and duration errors.
  - Support: (d) `docs/FA_EXTRAS_PROTOCOL.md`; `docs/FA_EXTRAS_RESULTS.md` line 3 (protocol committed before numbers). The same-boundary recheck behind CLAIM-117 had no protocol; do not cover it with this statement.
  - Note: needed if RES-A-09 or RES-B-18 is used without explanation.
- **SET-C-13** [OPTIONAL] If Cliff's delta is reported, define it as in `FORMULAS.md` and add a reference for it.
  - Support: `FORMULAS.md` (note under Eq. 5).
  - Note: no Cliff reference is in `references.bib`, and `BIBLIOGRAPHY_CRITICALITY.md` recommends leaving delta out (§10d).

### 5.D Implementation (target 90)

- **SET-D-01** [REQUIRED] All runs used one laptop: AMD Ryzen 9 5900HX, NVIDIA GeForce RTX 3050 Laptop GPU with 4 GB memory, Windows 11. Whisper ran on the GPU; MFA 3.4.3, the CTC aligner and BRQE ran on the CPU.
  - Support: `docs/ARCHITECTURE.md` lines 5 and 95; `docs/RUNBOOK.md` line 3; (b) `reports/buckeye/benchmark_results.json` config.asr.device = cuda, hardware.platform and hardware.processor.
  - Note: CPU for CTC and BRQE: frozen JSON hardware.torch_cuda_available = false, whisper_cuda_available = true. The GPU model is not in the JSON (cuda_device_name = null; §10d); its platform string reads Windows-10-10.0.26340, a build number of Windows 11.
- **SET-D-02** [REQUIRED] Processing time was logged for transparency only and is not an evaluation metric.
  - Support: (b) `reports/buckeye/benchmark_results.json` runtime.note = "transparency only; not an evaluation target"; rule 5.
- **SET-D-03** [REQUIRED] Samples, splits, BRQE weights and the benchmark code were frozen under tags before the reported test runs; earlier runs that stopped on technical errors before any metric was written led only to technical fixes.
  - Support: CLAIM-101, 104, 106 sources and reasons (tags `bench-frozen-20261029`, `-29b`, `-29c`); `IMPROVEMENT_PLAN.md` "C3/D, первая попытка" to "D, третья попытка" (results are written at the end of a run); (b) config.mfa_retries = [].
  - Note: rewritten; "before the test runs" hid the stopped runs. The sentence on the integrity check is now SET-D-06. See also M-C-11 (pilots).
- **SET-D-06** [OPTIONAL] An integrity check regenerated the frozen tables byte for byte from the stored results.
  - Support: `ARTIFACT_VALIDATION.md` §1 (21.11.2026; `verify_frozen_evidence.py`, PASS_WITH_LIMITATIONS; six tables). It predates CLAIM-111…118, so "every claim's source" was removed.
- **SET-D-04** [OPTIONAL] Separate re-implementations of the analyses by the authors' own tools gave the same numbers:
  - speaker tests and intervals: 14 tests and 60 intervals recomputed from 503,898 boundary records;
  - boundary F1: 660 of 660 values;
  - boundary groups and tolerance sweep: 1,620 of 1,620 values.
  - Support: `docs/E1_ANALYSIS_RESULTS.md` §6; `docs/F1_RESULTS.md` §6; `docs/FA_EXTRAS_RESULTS.md` §6.
  - Note: "independent" was removed: the matching rules, normalizer and phone folding were shared, and no other research group took part (E1 §6). The CLAIM-117 recheck is not covered.
- **SET-D-05** [OPTIONAL] MFA was called once per speaker with one job to avoid two known issues of MFA 3.4.3.
  - Support: `IMPROVEMENT_PLAN.md` decisions D4 and D5; `docs/RUNBOOK.md` line 51.
  - Note: do not mention the parallel MFA of the sub-studies (author decision 09.11.2026, `IMPROVEMENT_PLAN.md` §10.10).

---

## 6. Results (target 1,000 words)

> Checked 24.11.2026 against `docs/CLAIM_LEDGER.csv` and the report JSON files. Author decisions were settled on 24.11.2026 (§10f).

### 6.A Boundary Accuracy with and without a Known Transcript (RQ1; target 380)

- **RES-A-01** [REQUIRED] Table I gives word-boundary MAE, Acc@20, word coverage and boundary F1 at 20 ms for all nine modes on both corpora. MAE and Acc@20 cover matched words only, so scenario A and scenario B values refer to different sets of boundaries; boundary F1 was added as a secondary metric.
  - Support: Table I plan (§9); CLAIM-114 and CLAIM-115 reasons; matched sets differ per `docs/E1_ANALYSIS_RESULTS.md` §1 ("Это не тест по идентичному набору слов").
- **RES-A-02** [REQUIRED] With a known transcript, MFA with speaker adaptation (A2) reaches a word-boundary MAE of 19.6 ms [95 % CI 17.8, 21.6] and Acc@20 of 71.1 % on spontaneous speech. CTC alignment of the same text (A1) gives 40.5 ms and 34.0 %.
  - Support: CLAIM-101. The point values cover each mode's aligned clips (A1 999, A2 997 of 999); the tests use the 997 common clips.
  - Note: CLAIM-101's "p < 0.001, Cliff's delta 0.86" is clip-paired. The paper's tests are speaker-level (RES-A-05; §10d).
- **RES-A-03** [REQUIRED] Without a transcript, the proposed pipeline (B2) gives a word-boundary MAE of 30.1 ms [25.9, 34.5] and Acc@20 of 69.0 % at a word coverage of 89.0 %. Whisper's timestamps (B0) give 126.5 ms (coverage 88.8 %) and Whisper with CTC (B1) 41.3 ms (coverage 89.0 %).
  - Support: CLAIM-102; B0 and B1 coverage (b) `reports/buckeye/benchmark_results.json` modes.{B0_whisper, B1_whisper_ctc}.word_metrics.coverage = 0.888, 0.8897.
  - Note: coverage is mandatory beside B numbers; RES-A-08 must follow closely (CLAIM-115 reason).
- **RES-A-04** [REQUIRED] On read speech (a TIMIT sample of 160 utterances and 16 speakers), MFA reaches 20.3 ms with the known transcript (A2) and 20.5 ms with Whisper's text (B2, coverage 97.6 %). CTC gives 36.9 ms in both scenarios (B1 coverage 97.6 %) and Whisper's timestamps 153.0 ms (coverage 97.4 %).
  - Support: CLAIM-106 (reason: NLTK sample, not the full LDC corpus); coverage (b) `reports/timit/benchmark_results.json` word_metrics.coverage: B0 0.9735, B1 and B2 0.9763.
- **RES-A-05** [REQUIRED] Speaker by speaker on Buckeye, MFA has a lower MAE than CTC with the known transcript for 20 of 20 speakers; B2 has a lower MAE than B0 for 20 and than B1 for 19 of 20 speakers (exact Wilcoxon, Holm p < 0.0001 in each case). On TIMIT the same three comparisons favour MFA for 15, 16 and 15 of 16 speakers (Holm p < 0.0004).
  - Support: (b) `reports/e1_analysis_20261102/analysis.json` corpora.buckeye.speaker_comparisons.{A2_vs_A1, B2_vs_B0, B2_vs_B1}.n_speakers_improved = 20, 20, 19 and .p_value_holm = 1.335e-05; corpora.timit: 15, 16, 15 and 0.000366, 0.000214, 0.000366. `docs/E1_ANALYSIS_RESULTS.md` intro (protocol fixed after the original results) and §2.
  - Note: CLAIM-119. Common clips (997 and 160), not identical word sets.
- **RES-A-06** [REQUIRED] The secondary boundary F1 at 20 ms, which charges missed and inserted words, gives the same conclusions on Buckeye: the known transcript beats Whisper's text (0.710 vs 0.624), and MFA beats CTC. Each difference holds for all 20 speakers (exact Wilcoxon, Holm p < 0.001).
  - Support: CLAIM-114.
  - Note: "secondary" must stay (CLAIM-114 reason).
- **RES-A-07** [OPTIONAL] Under this F1, CTC reaches 0.340 with the known transcript (A1) and 0.311 with Whisper's text (B1, word coverage 89.0 %) on Buckeye.
  - Support: (b) `reports/f1_20261123/f1_results.json` corpora.buckeye.modes.A1_ctc.edge20.f1 = 0.3398 and B1_whisper_ctc.edge20.f1 = 0.3105; `docs/F1_RESULTS.md` §1.
  - Note: **needs CLAIM before submission**. These are also Table I cells.
- **RES-A-08** [REQUIRED] Scored over all reference boundaries, the scenario-B recall at 20 ms of the MFA modes on Buckeye is 7.7 to 8.3 points below the matched-word Acc@20 (about 11 % relative), so matched-word scores for recognized text are optimistic. For the known transcript the gap is 0.3 points.
  - Support: CLAIM-115; recomputed from Acc@20 minus edge20.recall: B2 7.7, B2+const 7.7, B2+BRQE 8.3; A2 and A2+BRQE 0.3.
  - Note: "of the MFA modes" was added because B1 (3.8 points) and B0 (0.8 points) lie outside the range. CLAIM-115 carries this limit since 24.11.2026.
- **RES-A-09** [REQUIRED] A post-hoc observation, made without a protocol and with MFA before BRQE: on Buckeye, recognized text has fewer reference boundaries between two correctly recognized words than known text (74 % vs 89 %), and on the same such boundaries its error is larger (MAE 26.1 vs 17.6 ms; errors above 100 ms 3.2 % vs 1.4 %) at an equal median of 10.0 ms. On TIMIT the MAE on these boundaries is about the same (17.9 vs 17.8 ms). We do not attribute the loss to a cause.
  - Support: CLAIM-117 (24.11.2026 wording); shares `fa_extras.json` groups.M2I.share (0.741, 0.887); the rest `reports/claim117_recheck_20261124/output.txt` (n = 13,570 and 2,358 common boundaries).
  - Note: "post-hoc" must stay. The recheck is not independently checked. Do not write that the loss comes from recognition rather than alignment, and do not compare recall 0.728 with 0.731 (different boundary sets).
- **RES-A-10** [REQUIRED] Fig. 2 shows boundary F1 against tolerance. On Buckeye, F1 for Whisper's text with MFA rises only from 0.846 at 70 ms to 0.864 at 100 ms (word coverage 89.0 %), against 0.978 at 100 ms with the known transcript. Words that Whisper missed or misrecognized count as errors at every tolerance.
  - Support: (b) `reports/fa_extras_20261123/fa_extras.json` corpora.buckeye.modes.{B2_proposed, A2_proposed}.f1_sweep["70"], ["100"]; last sentence is the metric definition (`FORMULAS.md` Eq. 3a); coverage CLAIM-102.
  - Note: CLAIM-120. Tolerances above 100 ms were not computed, so "ceiling" and "levels off" are not used.
- **RES-A-11** [OPTIONAL] On Buckeye from 70 ms on, CTC with the known transcript (A1) has a higher F1 than MFA with Whisper's text (B2, word coverage 89.0 %): 0.850 vs 0.846 at 70 ms and 0.933 vs 0.864 at 100 ms. On TIMIT this happens only at 100 ms (0.964 vs 0.956, B2 word coverage 97.6 %).
  - Support: (b) fa_extras.json corpora.*.modes.{A1_ctc, B2_proposed}.f1_sweep["70"], ["90"], ["100"]; TIMIT at 90 ms 0.945 vs 0.949.
  - Note: **needs CLAIM before submission**; descriptive, no test. `docs/FA_EXTRAS_RESULTS.md` §3 says there is no crossing on TIMIT; its own JSON shows one at 100 ms. That document was corrected 24.11.2026.
- **RES-A-12** [OPTIONAL] On TIMIT, the F1 difference between known and recognized text is smaller (0.684 vs 0.661 at a word coverage of 97.6 %); the known transcript is better for 14 of 16 speakers (Holm p = 0.0009).
  - Support: (b) `reports/f1_20261123/f1_results.json` corpora.timit.modes.{A2_proposed, B2_proposed}.edge20.f1 and tests_edge20["A2_proposed - B2_proposed"] (n_worse = 14 counts speakers where the first mode is better, `F1_RESULTS.md` §6 item 9; one tie, one worse; p_value_holm = 0.000916).
  - Note: **needs CLAIM before submission**. Corpora differ in more than coverage; no explanation is given.
- **RES-A-13** [OPTIONAL] MFA failed on 2 of 999 Buckeye clips in both scenarios, at its beam limit. In boundary F1 these clips count as misses.
  - Support: CLAIM-101 reason; (b) `reports/f1_20261123/f1_results.json` corpora.buckeye.modes.A2_proposed.n_failed_clips = 2; `FORMULAS.md` Eq. 3a.

### 6.B Boundary Refinement and Reliability (RQ2; target 400)

- **RES-B-01** [REQUIRED] On the 20 Buckeye test speakers, BRQE lowers word MAE from 19.6 to 17.0 ms with the known transcript (A2) and from 30.1 to 27.7 ms with Whisper's text (B2, coverage 89.0 %). It raises Acc@20 from 71.1 % to 76.8 % and from 69.0 % to 74.9 %, respectively.
  - Support: CLAIM-103 (reason: inclusion decided by the pre-registered CV rule before test numbers existed). BRQE moves boundaries of the same words, so each before/after pair uses the same boundary set.
- **RES-B-02** [OPTIONAL] Against the constant-offset rival, the clip-paired difference is significant (Holm p < 0.001) with a small effect (Cliff's delta 0.23 for A2 and 0.17 for B2).
  - Support: CLAIM-103.
  - Note: needs a delta definition and a Cliff reference, which the bib lacks (SET-C-13). RES-B-03 can replace it.
- **RES-B-03** [REQUIRED] Speaker by speaker, BRQE has a lower word MAE than the constant offset for 20 of 20 test speakers in both scenarios (exact Wilcoxon, Holm p < 0.0001; B2 coverage 89.0 %).
  - Support: (b) `reports/e1_analysis_20261102/analysis.json` corpora.buckeye.speaker_comparisons.{A2brqe_vs_A2const, B2brqe_vs_B2const}.n_speakers_improved = 20, p_value_holm = 1.335e-05; `docs/E1_ANALYSIS_RESULTS.md` §2; evidence of accepted contribution 1 (`TITLE_KEYWORDS_RQ.md` line 59).
  - Note: CLAIM-119.
- **RES-B-04** [REQUIRED] Under the secondary boundary F1 at 20 ms, BRQE also beats the constant offset in both scenarios for all 20 speakers (exact Wilcoxon, Holm p < 0.001): 0.766 vs 0.707 with the known transcript, and 0.677 vs 0.621 with Whisper's text (word coverage 89.0 %).
  - Support: CLAIM-114.
- **RES-B-05** [OPTIONAL] The mean signed errors of MFA are small (within about ±6 ms for word starts and ends, both corpora), which leaves little for a constant offset to correct. BRQE lowers the mean absolute word-duration error on Buckeye from 28.1 to 24.6 ms (A2).
  - Support: (b) `reports/fa_extras_20261123/fa_extras.json` corpora.*.modes.{A2_proposed, B2_proposed}.signed (−6.15 to +6.33 ms); corpora.buckeye.modes.{A2_proposed, A2_brqe}.signed.mean_abs_duration_ms = 28.08, 24.58.
  - Note: **needs CLAIM before submission**. "Narrows the spread" was removed: no dispersion of signed errors was computed. If this is used to explain the source of the BRQE gain, RES-B-18 must be used as well.
- **RES-B-06** [REMOVED 24.11.2026] Rested on CLAIM-118, which is withdrawn from the paper. See RES-B-18.
- **RES-B-07** [OPTIONAL] On Buckeye, BRQE's F1 gain over MFA is largest at the 10 ms tolerance (0.582 vs 0.502 with the known transcript; 0.512 vs 0.439 with Whisper's text) and is gone at 100 ms (0.978 for both; 0.863 vs 0.864). Word coverage with Whisper's text is 89.0 %.
  - Support: (b) fa_extras.json corpora.buckeye.modes.{A2_brqe, A2_proposed, B2_brqe, B2_proposed}.f1_sweep["10"] to ["100"]; `docs/FA_EXTRAS_RESULTS.md` §3.
  - Note: **needs CLAIM before submission**; descriptive, no test. Readable from Fig. 2.
- **RES-B-08** [REQUIRED] On Buckeye test speakers, the reliability head detects words for which the larger of the two MFA boundary errors exceeds 20 ms, with ROC-AUC 0.756 (A2) and 0.749 (B2). Rejecting the 30 % least reliable words lowers word MAE from 17.0 to 14.7 ms (A2) and from 27.7 to 25.1 ms (B2, coverage 89.0 % before rejection), as Fig. 3 shows.
  - Support: CLAIM-105; Fig. 3 data (b) `reports/buckeye/benchmark_results.json` modes.{A2_brqe, B2_brqe}.quality_estimation.word_mae_after_rejection_ms.
- **RES-B-09** [REQUIRED] About half of the words carry the error label (positive rate 0.50–0.52).
  - Support: CLAIM-105 reason ("positive rate 0.50–0.52").
- **RES-B-10** [REQUIRED] The figures after rejection describe only the words that are kept. Use of the score for manual review was not measured.
  - Support: `docs/E1_ANALYSIS_RESULTS.md` §4, last paragraph; CLAIM-105 reason.
- **RES-B-11** [REQUIRED] BRQE, trained on spontaneous speech, does not significantly improve read speech. On TIMIT (160 utterances, 16 speakers), word MAE changes from 20.3 to 19.9 ms (A2) and from 20.5 to 20.1 ms (B2, coverage 97.63 %), clip-paired Holm p = 0.24–0.27, a negligible effect.
  - Support: CLAIM-104 (clip-paired Holm p); coverage as in RES-A-04.
  - Note: reported as a limitation, without attributing it to speaking style (CLAIM-104 reason).
- **RES-B-12** [OPTIONAL] Speaker by speaker, 11 or 12 of 16 TIMIT speakers improve, and no BRQE comparison on MAE is significant (Holm p = 0.467). Under the secondary boundary F1, the mean per-speaker gain over the constant offset (0.023 with the known transcript, 0.025 with Whisper's text, coverage 97.6 %) is not significant either (Holm p = 0.083; 10 of 16 speakers improve). This does not show that there is no effect.
  - Support: (b) `reports/e1_analysis_20261102/analysis.json` corpora.timit.speaker_comparisons.*brqe* (12, 12, 12, 11; p_value_holm = 0.4667); `docs/E1_ANALYSIS_RESULTS.md` §2; `reports/f1_20261123/f1_results.json` corpora.timit.tests_edge20 (mean_difference 0.0225 and 0.0248, n_worse = 10, p_value_holm = 0.0825).
  - Note: **needs CLAIM before submission**.
- **RES-B-13** [REQUIRED] On TIMIT, BRQE's F1 is higher than MFA's at tolerances of 10 and 20 ms and lower from 30 to 80 ms; at 30 ms it is 0.779 vs 0.792 with Whisper's text (coverage 97.6 %) and 0.800 vs 0.816 with the known transcript. At 90 and 100 ms the two differ by less than 0.002. No test was run.
  - Support: (b) `reports/fa_extras_20261123/fa_extras.json` corpora.timit.modes.{B2_brqe, B2_proposed, A2_brqe, A2_proposed}.f1_sweep["10"] to ["100"].
  - Note: CLAIM-120. "Worse from 30 ms on" was corrected: at 90 ms B is equal (0.94918) and A is higher with BRQE (0.97489 vs 0.97453).
- **RES-B-14** [OPTIONAL] With the known transcript and pitch-preserving tempo changes from 0.8 to 1.25, BRQE keeps a 2.8–3.5 ms gain over MFA on Buckeye (speaker-mean MAE on the original speech scale). On TIMIT it does not improve, and at a speed factor of 1.25 it is worse than MFA (21.8 vs 20.2 ms).
  - Support: CLAIM-113.
  - Note: use here or in DIS-14, not both. Means over speakers, so A2 at tempo 1.0 (18.2 ms) differs from the pooled value of CLAIM-101 (19.6 ms); `docs/S2_RESULTS.md` §1. Add "vocoder tempo is not natural fast speech" (CLAIM-111 reason).
- **RES-B-15** [REQUIRED] In 5-fold speaker cross-validation on the training speakers only, the inclusion rule held in both scenarios for all 9 configurations: the default and 8 that change one setting (epochs, window, hidden size or loss weight; one seed each). Word MAE moved by at most 0.5 ms from the default.
  - Support: (b) `reports/brqe_sensitivity_20261102/summary.json` rule_6_5_holds = "9/9", max_abs_word_mae_delta_vs_baseline_ms = 0.498; `docs/BRQE_SENSITIVITY_RESULTS.md`.
  - Note: CLAIM-121. No test among configurations. The default was not the lowest (6 epochs: 16.06 vs 16.46 ms in A).
- **RES-B-16** [OPTIONAL] On TIMIT, BRQE lowers word-end errors (20.74 to 18.89 ms, known text) but raises word-start errors (19.78 to 20.89 ms), while on Buckeye both are lower with BRQE (A2 starts 19.70 to 17.27 ms, ends 19.42 to 16.68 ms). Descriptive, no test.
  - Support: (b) `docs/E1_ANALYSIS_RESULTS.md` §4 table; `reports/e1_analysis_20261102/analysis.json` corpora.*.modes.*.breakdowns.
  - Note: **needs CLAIM before submission**.
- **RES-B-17** [OPTIONAL] On the 10-minute recordings that aligned (14 of 20 for A2, 8 of 20 for B2, coverage 91.4 %), the reliability score had ROC-AUC 0.740 (A2) and 0.731 (B2).
  - Support: (b) `docs/S1B_RESULTS.md` §2; `reports/s1b_long_20261103/analysis.json`.
  - Note: **needs CLAIM before submission**; survivors only.
- **RES-B-18** [USED, Discussion; CLAIM-126] About 40 % of BRQE's gain in recall at 20 ms on Buckeye falls on the edges of our cut clips (9 % of reference boundaries with Whisper's text, 11 % with the known transcript). These are clip edges, not ends of speech.
  - Support: (b) fa_extras.json corpora.buckeye.modes.{A2_proposed, A2_brqe, B2_proposed, B2_brqe}.groups.{M1B, M1E}: edge part of the gain 39 % (A2) and 38 % (B2); edge shares 0.108 and 0.089; `TITLE_KEYWORDS_RQ.md`, CLAIM-117 and 118.
  - Note: **needs CLAIM before submission**; descriptive. Required if any text explains the source of the BRQE gain; otherwise leave out. The 9 % in the withdrawn CLAIM-118 is the B2 share only.

### 6.C Long Recordings (RQ3; target 220)

- **RES-C-01** [REQUIRED] The seam check was pre-registered with a threshold of 10 ms and run on 20 one-minute recordings. It measures the excess word-boundary error near chunk seams relative to one-chunk alignment of the same words. The original chunking failed it (+111.8 ms for A2, +125.3 ms for B2). Overlap-and-stitch, run on the same recordings, passed it (−0.4 ms and −15.4 ms).
  - Support: CLAIM-107; both `seam_check.json` files (pass = false, true); threshold and "near" definition from (d) `FORMULAS.md` Eq. 12 (`eq:seam`); amendment 3 of `docs/S1B_SEAM_SAFE_PROTOCOL.md` (criterion unchanged, fixed before the full check).
  - Note: 19 recordings enter each stitch comparison (one-chunk alignment failed for s34 in A; s15 failed in B). The two checks use different seams (A 584 vs 526 near boundaries; B 482 vs 458), so "fell from … to …" is not a comparison on one set; "failed, then passed" is used. CLAIM-107 reworded 24.11.2026.
- **RES-C-10** [REQUIRED] The overlap-and-stitch design was selected on 6 of these 20 recordings, and the negative B2 value is not read as an improvement.
  - Support: (b) `docs/S1B_MICROTEST_FINDINGS.md` §1 (sample: s07, s09, s11, s20, s27, s34, s37); `seam_check.json` (stitch) results.B.near_mae_single_ms, near_mae_multi_ms.
  - Note: added in the check; CLAIM-122. The list names 7 speakers because the deterministic-failure recording differs by scenario (s34 in A, s07 in B). Decided 24.11.2026: CLAIM-122, here in Results only. One-chunk error behind the B2 value: 91.3 ms vs 75.9 ms with chunks (458 boundaries).
- **RES-C-02** [REQUIRED] With the known transcript, word MAE on recordings that align is 19.4, 19.2 and 20.4 ms at 1, 5 and 10 minutes (20, 17 and 14 of 20 recordings). On the same words aligned inside the 10-minute recording and in the 1-minute recording, the per-speaker difference is −0.2 ms [−1.2, 0.4] over 14 speakers. These figures cover surviving recordings only, and the absence of a length effect is not claimed.
  - Support: CLAIM-108 (reason: survivors only; 14 of 20 speakers); same-words definition `docs/S1_LONG_RECORDINGS_PROTOCOL.md` H3; `docs/S1B_RESULTS.md` §2–3 (Holm p = 1).
- **RES-C-03** [REQUIRED] Failed recordings rise with length (A2: 0, 3 and 6 of 20; B2: 2, 7 and 12 of 20). The share of failed chunks is 0 %, 1.5 % and 1.3 % for A2 and 4.8 %, 3.9 % and 4.6 % for B2.
  - Support: CLAIM-109; `docs/MFA_FAILURE_BACKLOG.md` §1 table (A2 0/62, 4/269, 7/533; B2 3/62, 10/257, 23/501); Fig. 4 (optional).
  - Note: CLAIM-109 gives the A2 range for 5 and 10 min only; the 0 of 62 at 1 min is stated so that "stays constant" is not implied.
- **RES-C-04** [REQUIRED] One failed chunk fails the whole recording, so a longer recording has more chances to fail. This explanation is descriptive and was not tested.
  - Support: CLAIM-109 (reason: "descriptive, not a tested hypothesis").
- **RES-C-05** [REQUIRED] Without word anchors, 15, 20 and 20 of 20 recordings fail at 1, 5 and 10 minutes. This ablation (A2) shows that the pipeline needs anchoring; the effect of anchoring on error cannot be tested.
  - Support: CLAIM-110.
- **RES-C-06** [REQUIRED] With Whisper's text, word MAE on the long recordings that aligned is 49.1, 52.2 and 51.6 ms at 1, 5 and 10 minutes (coverage 88.9 %, 89.6 % and 91.4 %; 18, 13 and 8 of 20 recordings).
  - Support: (b) `docs/S1B_RESULTS.md` §2; `reports/s1b_long_20261103/analysis.json` runs.{L01,L05,L10}_anchored.modes.B2_proposed.word.{mae_ms, coverage}.
  - Note: CLAIM-124. The comparison with short clips was removed: the words and recordings differ. Recommended to keep, because A2 without B2 could read as selective (§10d).
- **RES-C-07** [OPTIONAL] On the long recordings that aligned with the known transcript, word MAE with BRQE is 17.2, 17.0 and 18.0 ms against 19.4, 19.2 and 20.4 ms for A2 on the same recordings.
  - Support: (b) `docs/S1B_RESULTS.md` §2; analysis.json (A2_proposed and A2_brqe fail on the same recordings).
  - Note: **needs CLAIM before submission**; survivors; no test.
- **RES-C-08** [OPTIONAL] CTC alignment failed on none of the long recordings. Its word MAE over all 20 recordings is 43.3–45.1 ms (A1) and 44.9–47.5 ms (B1, coverage 88.7–91.1 %).
  - Support: (b) `docs/S1B_RESULTS.md` §2; analysis.json A1_ctc, B1_whisper_ctc.
  - Note: **needs CLAIM before submission**. Not comparable with the survivor-only MFA values; do not place them side by side without saying so.
- **RES-C-09** [OPTIONAL] A test for error drift between the first and the last two minutes of the 10-minute recordings was not significant for A2 (+3.79 ms, 95 % CI −1.72 to +11.65, 14 speakers, Holm p = 1) or B2 (−35.20 ms, −84.01 to −2.01, 8 speakers, Holm p = 0.44). By protocol, this does not establish that drift is absent.
  - Support: (b) `docs/S1B_RESULTS.md` §3 (H1, H2); `docs/S1_LONG_RECORDINGS_PROTOCOL.md` H1 (minutes [8, 10) minus [0, 2)).
  - Note: **needs CLAIM before submission**; survivors. B2 added so that only the better result is not shown.

---

## 7. Discussion (target 600 words, including Limitations)

> Checked 24.11.2026 against the CLAIMs, the report JSON files and the PDFs. Author decisions were settled on 24.11.2026 (§10f).

### 7.1 Interpretation (target 330)

- **DIS-01** [REQUIRED] On spontaneous speech, recognized text lowers boundary F1 at 20 ms from 0.710 to 0.624 (word coverage 89.0 %; secondary analysis). In a post-hoc look at the boundaries that both texts share, the error was also larger with recognized text (MAE 26.1 vs 17.6 ms) at an equal median of 10.0 ms, with more errors above 100 ms (3.2 % vs 1.4 %). The data do not show which part of the loss comes from recognition and which from alignment.
  - Support: CLAIM-114, CLAIM-102 (coverage), CLAIM-117 (24.11.2026 wording).
  - Note: rewritten. The advice "improve the transcript before the aligner" and "placed as well as" were removed (contribution 3: no advice, no causal claim). "Post-hoc" must stay. If RES-A-09 is used, keep only the first and last sentences.
- **DIS-02** [OPTIONAL] The order of systems depends on the tolerance: from 70 ms on, CTC with the known text has a higher F1 than MFA with Whisper's text on Buckeye (B2 word coverage 89.0 %; Fig. 2).
  - Support: (b) see RES-A-11.
  - Note: **needs CLAIM before submission**. "The transcript matters more than the aligner" was removed (descriptive, no test). Use here or in RES-A-11, not both.
- **DIS-03** [REQUIRED] Our MFA results and the order of MFA ahead of CTC alignment are consistent with recent benchmarks [Chu2026FABench], [Zolkepli2026], [McAuliffe2026], [Rousso2024]. Absolute values differ, as do boundary definitions, clips and speaker splits.
  - Support: CLAIM-116 (qualitative only; never say one benchmark is better); McAuliffe2026 Table 4 (MFA ahead of WhisperX, MMS, NeMo); Zolkepli2026 p. 12; Rousso2024 (MFA ahead of WhisperX and MMS, LA line 64).
  - Note: narrowed. CLAIM-116 rests on FA-Bench alone, and the place of Whisper's own timestamps behind CTC is not in all four works, so the third system and the F1 range 0.68–0.71 were removed. Rule 3, plural and short; the one Discussion citation of FA-Bench. Never write "confirm" or "validate".
- **DIS-04** [OPTIONAL] For example, mean MFA word-boundary errors of 19.93 and 21.75 ms on TIMIT and Buckeye [McAuliffe2026] and 19.1 and 21.0 ms [Zolkepli2026] are of the same order as ours (20.3 and 19.6 ms).
  - Support: (c) McAuliffe2026 p. 352, Table 4 (LA lines 151–152); Zolkepli2026 p. 12, Table 6 (EVN line 19); CLAIM-106 and CLAIM-101.
  - Note: qualitative only (different clips and preparation; LA line 164).
- **DIS-05** [REQUIRED] Whisper's timestamps are early on average: the mean signed start error is −115.0 ms on Buckeye and −147.5 ms on TIMIT, and the mean signed duration error is −21.3 and −10.3 ms (word coverage 88.8 % and 97.4 %). Per word, however, the mean absolute duration error is 86.4 and 101.2 ms, so a constant shift would not correct every word.
  - Support: (b) `reports/fa_extras_20261123/fa_extras.json` corpora.{buckeye, timit}.modes.B0_whisper.signed (86.45, rounded as in `docs/FA_EXTRAS_RESULTS.md` §4); coverage `benchmark_results.json`.
  - Note: CLAIM-125; descriptive, matched words only. "Shift whole words" was softened to a mean.
- **DIS-06** [OPTIONAL] A similar early shift of about 150 ms has been reported for Whisper [Chu2026FABench].
  - Support: (c) Chu2026FABench pp. 1, 4; EVN line 12.
  - Note: this would be a second FA-Bench citation in the Discussion. Merge it into DIS-03's citation or drop it (rule 1).
- **DIS-07** [REQUIRED] On average, CTC alignment starts words 39–46 ms late and ends them 15–23 ms early, so its words are about 60 ms too short. This is in line with the report that, on the forced CTC path, the first character frame falls a median 33 ms after the human word start and the last ends a median 26 ms before the human end, with a median 67 % of the frames inside a word blank [Zolkepli2026].
  - Support: (b) fa_extras.json corpora.*.modes.{A1_ctc, B1_whisper_ctc}.signed (start +38.8 to +45.6 ms, end −14.8 to −23.3 ms, duration −58.2 to −62.3 ms); `docs/FA_EXTRAS_RESULTS.md` §4. (c) Zolkepli2026 arXiv p. 4 (median 33 ms; "a median 67% of the frames inside a human word are blank"); EVN line 20.
  - Note: CLAIM-125. Our values are means, theirs are medians of character frames on TIMIT with MMS-300M; B1 coverage is 89.0 % and 97.6 %.
- **DIS-08** [OPTIONAL] CTC models have peaky output distributions, and MMS words were also found to be about 60 ms shorter than manual words on Buckeye and TIMIT [Huang2024].
  - Support: (c) Huang2024 pp. 1, 3 (Table 1, WDUR 181 vs 241 ms and 242 vs 305 ms); EVN lines 88–90.
  - Note: reserve reference.
- **DIS-09** [REQUIRED] BRQE lowers the error on spontaneous speech, but does not significantly improve read speech, where its F1 is lower than MFA's at tolerances from 30 to 80 ms. The module was trained on one corpus with one seed, and the cause of this gap between corpora was not tested.
  - Support: CLAIM-103, CLAIM-104, CLAIM-113; RES-B-13 (b); `IMPROVEMENT_PLAN.md` §10.1 ("обучение на одном корпусе и одном seed").
  - Note: rewritten without CLAIM-118. RES-B-13 **needs CLAIM before submission**. Do not interpret it as speech-style specificity (CLAIM-104 reason). Do not explain where the gain comes from unless RES-B-18 (about 40 % at the edges of cut clips) is used too.
- **DIS-10** [REQUIRED] One possible use of the reliability score is to mark words for review, as proposed for uncertainty ranges of boundaries [Kelley2026]. This use was not measured.
  - Support: CLAIM-105 reason (use "may be mentioned only as a possibility in the discussion"); (c) Kelley2026 arXiv p. 1 ("finding boundaries that should be reviewed").
  - Note: "instead of every word" was removed: it implies saved labour. The clause moved here from accepted contribution 1.
- **DIS-11** [REQUIRED] In a small pilot, seams fell inside speech when VAD found no pauses, so the chunk padding held a neighbour's speech without its text. An aligner that must place every token can then shift neighbouring intervals [Vaidya2026]. MFA failures on long recordings have also been reported: 5 of 16 files were aligned in [Rastorgueva2023].
  - Support: `IMPROVEMENT_PLAN.md` §10.3 (microtest on 6 recordings, descriptive); (c) Vaidya2026 arXiv p. 6 ("one mismatch can shift neighboring intervals"); Rastorgueva2023 PDF p. 2, Table 1 (= p. 5258).
  - Note: "seam errors came from" was removed; the mechanism was not tested. "In a small pilot" must stay.
- **DIS-12** [OPTIONAL] The long-recording evaluation cited here reports overall accuracy and the number of files aligned [Rastorgueva2023]. Our protocol reports seam error, length effect and chunk failures separately.
  - Support: positioning rule 5; CLAIM-107–110; Rastorgueva2023 Table 1 (200 ms precision and recall, files aligned).
  - Note: limited to one cited work; the general statement about long-form work and "shows which part to fix" were removed.
- **DIS-13** [REQUIRED] Under pitch-preserving time-stretching from 0.8 to 1.25, word coverage stays within 97.5–97.9 % (TIMIT) and 89.9–90.8 % (Buckeye), and known-text MFA error on the original time scale stays within 19.8–20.4 ms and 17.9–20.3 ms. In tests added after the numbers were known, only strong slowing raises the scaled error on spontaneous speech (+2.1 ms for A2 and +2.8 ms for A2 with BRQE at 0.8, Holm p = 0.026 and 0.004).
  - Support: CLAIM-111 (descriptive ranges, not an equivalence test), CLAIM-112 (the post-hoc marker must stay); `reports/s2_tempo_20261103/scaled_detail.json`.
  - Note: ranges are speaker means over 160 TIMIT and 200 Buckeye clips. On TIMIT the same post-hoc tests give Holm p < 0.05 for A2 and B2 at 1.1 and 1.25 and for both BRQE modes at 1.25 (signs of mean and median differ for A2 and B2); CLAIM-112 speaks of spontaneous speech only, so do not write "no effect on read speech". S2 gets one sentence. Add "vocoder tempo is not natural fast speech" here or in LIM-10.
- **DIS-14** [REQUIRED] Across these tempos and with the known text, BRQE keeps a 2.8–3.5 ms gain over MFA on Buckeye. On TIMIT it does not improve, and at 1.25 it is worse than MFA (21.8 vs 20.2 ms).
  - Support: CLAIM-113.
  - Note: drop if RES-B-14 is used.
- **DIS-15** [OPTIONAL] Replacing Whisper large-v3 with five smaller or faster Whisper variants gave no significant difference in word MAE of B2 or B2 with BRQE on Buckeye (all Holm p ≥ 0.94, all 95 % CIs including zero; word coverage 83.7–89.6 %, failed clips 2 to 17 of 999). This is not evidence of equivalence, and the recognized words differ between variants.
  - Support: (b) `docs/S3_RESULTS.md` ("Сравнения и ограничения"); `reports/s3_asr_size_20261106/analysis.json`.
  - Note: **needs CLAIM before submission**. Coverage and failure rates differ between variants (83.65–89.56 % coverage), so mention them if a number is given. Do not use the S3 figure (`ARTIFACT_VALIDATION.md` §2).

### 7.2 Limitations (target 270)

- **LIM-01** [REQUIRED] On Buckeye, matched-word Acc@20 for recognized text aligned by MFA is about 11 % (relative) above recall over all reference boundaries. Word coverage and boundary F1 are therefore reported beside these scores.
  - Support: CLAIM-115 (7.7–8.3 points; 0.3 points for the known transcript); see RES-A-08.
  - Note: "scores … are about 11 % optimistic" covered MAE too; the figure is for Acc@20 only.
- **LIM-02** [REQUIRED] Buckeye clips are runs of ordinary words without labelled silence, event tags, noise or interviewer speech, 1–30 s long, and may be easier than full conversational utterances.
  - Support: `src/subtitle_workbench/buckeye.py`; `literature/FABENCH_REPO_REVIEW.md` item 5 ("Скорее всего, наш набор проще"); `main.tex` Discussion comment.
- **LIM-03** [REQUIRED] Noise, reverberation and accented speech were not tested.
  - Support: `IMPROVEMENT_PLAN.md` §9.2 (S4 accent and S6 noise are not run and are reported as limitations).
  - Note: do not state the S4 and S6 hypotheses as expected results.
- **LIM-04** [REQUIRED] The long recordings were spliced from clips, so their joins are not natural speech and they stand in for lectures only partly. Their error figures cover surviving recordings.
  - Support: `docs/S1_LONG_RECORDINGS_PROTOCOL.md` rule 5; CLAIM-108 reason.
- **LIM-05** [REQUIRED] BRQE was trained on one spontaneous corpus with one seed and did not significantly improve read speech.
  - Support: CLAIM-104, CLAIM-113; `IMPROVEMENT_PLAN.md` §10.1.
- **LIM-06** [REQUIRED] B1 and A1 reproduce the alignment cores of WhisperX-style and MMS pipelines, not the WhisperX and NFA programs.
  - Support: `IMPROVEMENT_PLAN.md` §10.1; `PSEUDOCODE.md` notes.
- **LIM-07** [REQUIRED] TIMIT results come from the 160-utterance NLTK sample, not the full corpus.
  - Support: CLAIM-106 reason.
- **LIM-08** [OPTIONAL] The speaker-level tests, boundary F1 and the boundary-group analyses were added after the main results; the group analyses have no tests. The comparison on shared boundaries was post-hoc and without a protocol.
  - Support: `docs/E1_ANALYSIS_RESULTS.md` intro; CLAIM-114 and CLAIM-117 reasons; `docs/FA_EXTRAS_PROTOCOL.md` ("тестовые дикторы Buckeye уже много раз использованы").
  - Note: CLAIM-118 removed from the support. Do not name FA-Bench here, which would be a third Discussion mention.
- **LIM-09** [REQUIRED] No user study was run. The paper measures timing against reference boundaries based on hand-corrected labels, not comprehension, learning or accessibility benefit for viewers.
  - Support: `TITLE_KEYWORDS_RQ.md` lines 3 and 63; rule 5.
- **LIM-10** [OPTIONAL] Tempo was changed by a vocoder, which is not natural fast speech.
  - Support: CLAIM-111 reason.
- **LIM-11** [OPTIONAL] All data are English, and the speaker split, clip selection and boundary definitions differ from those of other benchmarks, so their numbers can be compared only in order of magnitude.
  - Support: CLAIM-116 reason; EVN line 14 (different clips, split, metric details, MFA version); LA line 164.
- **LIM-12** [OPTIONAL] Rankings on clean speech may not hold under degradation [Chu2026FABench].
  - Support: (c) Chu2026FABench p. 4 ("a clean-speech MAE ranking does not survive degradation").
  - Note: an extra FA-Bench citation, so use it only instead of DIS-03's.
- **LIM-13** [REMOVED] Dropped 24.11.2026: the pilots stand in Setup (M-C-11) and the selection of the design in Results (RES-C-10).
  - Support: M-C-11, RES-C-10.
  - Note: added in the check; **needs CLAIM before submission**. If M-C-11 and RES-C-10 stay in their sections, this can be dropped.

---

## 8. Conclusion (target 150 words)

> Checked 24.11.2026 against the CLAIMs. Author decisions were settled on 24.11.2026 (§10f).

- **CON-01** [REQUIRED] RQ1: On matched words of spontaneous speech, MFA placed word boundaries with an MAE of 19.6 ms using a known transcript, and of 30.1 ms using Whisper's text at 89.0 % word coverage, against 126.5 ms for Whisper's own timestamps at 88.8 % coverage. On read speech the two MFA values were 20.3 and 20.5 ms (coverage 97.6 % with Whisper's text).
  - Support: CLAIM-101, CLAIM-102, CLAIM-106; coverage as in RES-A-03 and RES-A-04.
  - Note: the A and B values cover different word sets; do not write "a known transcript reduces MAE by 10.5 ms". The difference that charges missed words is in CON-02.
- **CON-02** [REQUIRED] Under the secondary boundary F1 at 20 ms, the known transcript reached 0.710 and Whisper's text 0.624 (word coverage 89.0 %), a difference in the same direction for all 20 speakers.
  - Support: CLAIM-114, CLAIM-102 (coverage).
  - Note: "the loss came from recognition errors, not from alignment" and "about 9 points" were removed (CLAIM-117 refuted the first; the second was a rounding). No cause is stated.
- **CON-03** [REQUIRED] RQ2: On held-out spontaneous speech, BRQE beat a constant-offset correction for all 20 speakers under MAE and boundary F1, and its reliability score detected words with an MFA boundary more than 20 ms off with ROC-AUC 0.756 (A2) and 0.749 (B2). It did not significantly improve read speech.
  - Support: CLAIM-103, 105, 104, 114; speaker count under MAE (b) E1 (as in RES-B-03).
  - Note: CLAIM-119 for the MAE speaker count. "Significantly" restored (CLAIM-104).
- **CON-04** [REQUIRED] RQ3: On one-minute recordings, the original chunking raised the error near chunk seams by more than 100 ms, and overlap-and-stitch passed the pre-registered 10 ms check. Among recordings that aligned with the known transcript, word MAE was 19.4, 19.2 and 20.4 ms at 1, 5 and 10 minutes; failed recordings grew with length.
  - Support: CLAIM-107, CLAIM-108 (survivors only), CLAIM-109; RES-C-01 to RES-C-03.
  - Note: "rather than with length" and "removed the seam excess" were removed (no absence of a length effect is claimed; seams were checked at 60 s only).
- **CON-05** [REQUIRED] Future work should test the pipeline on natural lecture recordings with hand-corrected word boundaries, and on noisy and accented speech.
  - Support: `docs/S1_LONG_RECORDINGS_PROTOCOL.md` rule 5; `IMPROVEMENT_PLAN.md` §9.2; `TITLE_KEYWORDS_RQ.md` line 5 (no lecture corpus with manual boundaries).
  - Note: the one allowed future-work sentence (`main.tex` comment).
- **CON-06** [REMOVED 24.11.2026] Advice to spend effort on the transcript: rested on the old CLAIM-117 and breaks contribution 3 (no advice).

**Acknowledgment.** No statement is proposed: there is no supported funding or help to acknowledge. If one is added, write it in the third person.

---

## 9. Figures, tables, algorithms and equations plan

At most 3 data figures plus the pipeline diagram (`ARTIFACT_VALIDATION.md` §5). The ECDF is replaced by the F1-tolerance figure (`main.tex` Results A comment).

| ID | File | Section | Caption statement | Data source | Status |
|---|---|---|---|---|---|
| Fig. 1 | author's pipeline diagram (to draw) | III-A | M-A-09 | `PSEUDOCODE.md` Algorithm 1 | REQUIRED; author draws |
| Fig. 2 | `reports/fa_extras_20261123/f1_tolerance_en.pdf` | V-A, also V-B | "Boundary F1 against matching tolerance (10–100 ms) on Buckeye (left) and TIMIT (right); shaded bands are 95 % speaker-bootstrap intervals. Missed and inserted words count as errors, so missed words lower the curves for Whisper's text at every tolerance." | `fa_extras.json` corpora.*.modes.*.f1_sweep (f1, f1_ci_95; bands drawn from f1_ci_95, `scripts/render_fa_extras.py` lines 51–54) | REQUIRED. No hash manifest exists; figure produced at clean revision `49acdc5` (`FA_EXTRAS_RESULTS.md` line 3). Constant-offset modes are not drawn |
| Fig. 3 | `reports/e1_analysis_20261102/figures/reliability_retention_en.pdf` | V-B | "Word MAE of the words kept after rejecting the 0–50 % least reliable words by BRQE's reliability score, with known text (A2+BRQE) and Whisper's text (B2+BRQE), on TIMIT (left) and Buckeye (right). Y-axes differ." | `benchmark_results.json` modes.{A2_brqe, B2_brqe}.quality_estimation.word_mae_after_rejection_ms (both corpora) | REQUIRED. Hash matches `figure_manifest.json` (`ARTIFACT_VALIDATION.md` §1). Text quotes Buckeye numbers only (CLAIM-105); the TIMIT panel has no CLAIM (§10d) |
| Fig. 4 | `reports/s1b_long_20261103/figures/s1b_failures_en.pdf` | V-C | "Failed recordings of 20 (left) and share of unaligned chunks (right) for recordings of 1, 5 and 10 minutes. A recording fails when any chunk fails; A2 without anchors is hatched." | CLAIM-109, CLAIM-110 (values checked visually in `ARTIFACT_VALIDATION.md` §2) | OPTIONAL; otherwise RES-C-03 to RES-C-05 in text. No hash manifest |
| — | not used | — | `phone_group_mae` (empty "Other" defect), `s3_asr_size` (style defects), `speaker_brqe_gain` (too tall), `word_error_ecdf` (replaced) | `ARTIFACT_VALIDATION.md` §2 | Do not use |

**Table I (REQUIRED, V-A).**
- **Title:** "Word-Boundary Accuracy on Spontaneous (Buckeye) and Read (TIMIT) Speech."
- **Caption statement:** "MAE and Acc@20 use matched words only and must be read with word coverage. Boundary F1 at 20 ms counts missed and inserted words and was added as a secondary check. CIs are speaker-bootstrap 95 % intervals. B modes use Whisper's text; A modes use the known transcript. MAE and Acc@20 of A and B modes refer to different word sets; on Buckeye, matched-word Acc@20 of the B modes with MFA is 7.7 to 8.3 points above recall over all reference boundaries."
- **Caption support:** `FORMULAS.md` Eqs. 1–3a; CLAIM-114 and CLAIM-115 reasons.
- **Layout:** use `table*` (two columns wide) or one column with `\footnotesize`.

**Columns:** Mode, then for each corpus MAE [95 % CI] (ms), Acc@20 (%), Cov (%), F1@20. Optional: failed clips (Buckeye). The cell sources are:

| Column | Source field (per corpus `c` ∈ {buckeye, timit}, per mode `m`) |
|---|---|
| MAE, CI | `reports/{c}/benchmark_results.json` → modes.`m`.word_metrics.mae_ms, .ci_95 |
| Acc@20 | same → modes.`m`.word_metrics.acc_20ms |
| Cov | same → modes.`m`.word_metrics.coverage (matched / reference words in successfully scored clips). The alternative denominator over all attempted clips (Buckeye A2 99.61 %, B2 88.86 %) is in `docs/E1_ANALYSIS_RESULTS.md` §3; state which one is used |
| F1@20 | `reports/f1_20261123/f1_results.json` → corpora.`c`.modes.`m`.edge20.f1 (CI: .f1_ci_95) |
| Failed | `reports/{c}/benchmark_results.json` → modes.`m`.n_utterances_failed |

**Rows and values** (copied from the JSON fields above, rounded as in the CLAIMs). Mark: ✓ = covered by a CLAIM; ◇ = report value, covered by CLAIM-123.

| Mode | Buckeye MAE [CI] | Acc@20 | Cov | F1@20 | Fail | TIMIT MAE [CI] | Acc@20 | Cov | F1@20 |
|---|---|---|---|---|---|---|---|---|---|
| B0 Whisper | 126.5 ✓ [120.1, 133.1] ◇ | 6.9 ◇ | 88.8 ◇ | 0.063 ◇ | 1 ◇ | 153.0 ✓ [146.0, 160.7] ◇ | 2.1 ◇ | 97.35 ◇ | 0.020 ◇ |
| B1 Whisper + CTC | 41.3 ✓ [39.1, 43.8] ◇ | 34.3 ◇ | 89.0 ◇ | 0.311 ◇ | 1 ◇ | 36.9 ✓ [34.9, 39.2] ◇ | 34.4 ◇ | 97.63 ◇ | 0.335 ◇ |
| B2 Whisper + MFA | 30.1 [25.9, 34.5] ✓ | 69.0 ✓ | 89.0 ✓ | 0.624 ✓ | 2 ✓ | 20.5 ✓ [17.3, 25.5] ◇ | 67.9 ◇ | 97.63 ◇ | 0.661 ◇ |
| B2 + const | 30.1 [25.9, 34.4] ◇ | 68.7 ◇ | 89.0 ◇ | 0.621 ✓ | 2 ◇ | 20.5 [17.4, 25.6] ◇ | 67.1 ◇ | 97.63 ◇ | 0.654 ◇ |
| B2 + BRQE | 27.7 ✓ [23.6, 32.0] ◇ | 74.9 ✓ | 89.0 ✓ | 0.677 ✓ | 2 ◇ | 20.1 ✓ [17.0, 25.0] ◇ | 69.7 ◇ | 97.63 ◇ | 0.679 ◇ |
| A1 known + CTC | 40.5 ✓ [38.3, 42.8] ◇ | 34.0 ✓ | 99.98 ◇ | 0.340 ◇ | 0 ◇ | 36.9 ✓ [34.9, 39.2] ◇ | 34.4 ◇ | 100 ◇ | 0.344 ◇ |
| A2 known + MFA | 19.6 [17.8, 21.6] ✓ | 71.1 ✓ | 99.98 ◇ | 0.710 ✓ | 2 ✓ | 20.3 ✓ [17.3, 25.1] ◇ | 68.4 ◇ | 100 ◇ | 0.684 ◇ |
| A2 + const | 19.5 [17.7, 21.5] ◇ | 70.9 ◇ | 99.98 ◇ | 0.707 ✓ | 2 ◇ | 20.3 [17.4, 25.1] ◇ | 67.6 ◇ | 100 ◇ | 0.676 ◇ |
| A2 + BRQE | 17.0 ✓ [15.3, 18.9] ◇ | 76.8 ✓ | 99.98 ◇ | 0.766 ✓ | 2 ◇ | 19.9 ✓ [17.0, 24.6] ◇ | 69.9 ◇ | 100 ◇ | 0.699 ◇ |

Raw values for checking:
- Buckeye MAE: 126.52, 41.28, 30.13, 30.11, 27.67, 40.51, 19.56, 19.52, 16.97.
- TIMIT MAE: 152.98, 36.91, 20.46, 20.54, 20.08, 36.92, 20.26, 20.34, 19.89.
- Coverage: Buckeye 0.888, 0.8897 (all B), 0.9998 (all A); TIMIT 0.9735, 0.9763, 1.0.
- TIMIT failed clips: 0 for all modes (`n_utterances_failed`).
- Rounding note: A2 + const on TIMIT is 20.34, which rounds to 20.3, the same as A2 (20.26). Keep two decimals in this column if the difference must show.
- Checked 24.11.2026: all 117 values agree with the JSON fields. Cov stands in the column next to Acc@20 in every B row, and F1@20 is a column for both corpora, as the author asked. Cov is matched / reference words in successfully aligned clips (over all 999 clips: A2 99.61 %, B2 88.86 %).

**Algorithms.**
- Algorithm 1 `alg:pipeline` (III-A): REQUIRED.
- Algorithm 2 `alg:brqe` (III-C): REQUIRED.
- Algorithm 3 `alg:anchor`: OPTIONAL; M-B-02 and M-B-03 replace it.
- Algorithm 4 `alg:stitch`: OPTIONAL; M-D-02 and M-D-03 replace it.

All are in `latex/algorithms.tex`, written from `PSEUDOCODE.md`.

**Equation blocks** (labels from `latex/equations.tex`):
- Block 1, BRQE (III-C), REQUIRED: `eq:brqe-h`, `eq:brqe`, `eq:loss`, `eq:reliability`. `eq:const` is optional, or put it in words.
- Block 2, metrics (IV-C), REQUIRED: `eq:mae`, `eq:acc`, `eq:coverage`, `eq:f1`, `eq:label`.
- Optional: `eq:anchor` (III-B), `eq:interp` (III-B), `eq:speaker` and `eq:holm` (IV-C; can be put in words), `eq:seam` (V-C).
- Numbering note: Section III comes before IV, so the BRQE equations are numbered first. Always use `\eqref` so that dropping an optional equation renumbers itself.

---

## 10. Coverage checks

### (a) Research questions and contributions → statements

| Item | REQUIRED statements | OPTIONAL support |
|---|---|---|
| RQ1 (error, A vs B) | INT-10; RES-A-01 to RES-A-06, RES-A-08, RES-A-09, RES-A-10; DIS-01, DIS-03, DIS-05, DIS-07; LIM-01; CON-01, CON-02 | RES-A-07, A-11, A-12, A-13; DIS-02, DIS-04 |
| RQ2 (BRQE vs constant; reliability) | INT-11; M-C-01 to M-C-08; RES-B-01, B-03, B-04, B-06, B-08 to B-11, B-13, B-15; DIS-09, DIS-10, DIS-14; LIM-05; CON-03 | RES-B-02, B-05, B-07, B-12, B-14, B-16, B-17 |
| RQ3 (length, chunking, failures) | INT-12; M-D-01 to M-D-04; SET-A-06, SET-A-07; RES-C-01 to RES-C-05; DIS-11; LIM-04; CON-04 | RES-C-06 to C-09; DIS-12; Fig. 4 |
| Contribution 1 (refinement and reliability) | INT-13; RW-C-06; RES-B-01, B-03, B-04, B-06, B-08, B-11, B-13; CON-03 | RES-B-07 |
| Contribution 2 (long recordings) | INT-14; RW-B-10; RES-C-01 to RES-C-05; CON-04 | RES-C-06 to C-09 |
| Contribution 3 (cost of recognized text) | INT-15; RES-A-06, RES-A-08, RES-A-09; DIS-01; CON-02 | RES-A-10 (ceiling), RES-A-11, DIS-02 |
| RQ4, in one Discussion sentence (tempo, Whisper size) | DIS-13, DIS-14 | DIS-15 (S3; needs CLAIM), LIM-10 |

### (b) Selected references → statements

All 25 selected keys appear in at least one REQUIRED statement. No selected key is left uncited.

| Key | REQUIRED statements | OPTIONAL statements |
|---|---|---|
| Gernsbacher2015 | INT-01, RW-A-01 | — |
| Horlin2024 | INT-01, RW-A-02 | INT-18 |
| Thompson2026 | INT-02, RW-A-03 | — |
| Rastorgueva2023 | INT-03, RW-B-05, DIS-11 | DIS-12 |
| Kelley2026 | INT-04, RW-C-04, DIS-10 | — |
| Radford2023 | INT-05, RW-B-01, M-A-02 | — |
| McAuliffe2017 | INT-05, RW-B-06 | — |
| Pratap2024 | INT-05, RW-B-04, SET-B-01 | — |
| Hwang2023 | INT-05, RW-B-04, SET-B-01 | — |
| Rousso2024 | INT-06, RW-B-07, DIS-03 | — |
| McAuliffe2026 | INT-06, RW-B-07, DIS-03 | RW-B-12, DIS-04 |
| Zolkepli2026 | INT-06, RW-B-08, DIS-03, DIS-07 | RW-B-16, DIS-04 |
| Chu2026FABench | INT-06 (group), RW-B-08 (group), SET-C-05 (metric source), DIS-03 (one Discussion mention) | SET-A-08, DIS-06, LIM-12 (each would exceed rule 1; use only as a swap) |
| Vaidya2026 | RW-B-09, RW-C-05, DIS-11 | — |
| Nurym2026 | INT-09 | — |
| FasterWhisper | RW-B-01, M-A-02 | — |
| Yeh2025 | RW-B-02 | — |
| Bain2023 | RW-B-03, SET-B-03 | — |
| Stolcke2014 | RW-C-01, SET-C-02 | INT-16 |
| Cuozzo2018 | RW-C-02, RW-C-03 | INT-16 |
| SileroVAD | M-A-02 | — |
| Garofolo1993 | SET-A-01 | — |
| Pitt2005 | SET-A-02 | — |
| Holm1979 | SET-C-06 | — |
| Liu2020Blockwise | SET-C-07 | — |

**Optional by space (3).** Povey2011 (RW-B-11), Moreno1998 (RW-B-13), Mirzaei2018 (RW-A-05). All appear in OPTIONAL statements only.

**Reserve (8), OPTIONAL only:**
- Kelley2024 (RW-C-08; DIS-09 note);
- Mu2026 (RW-B-14);
- LeCunff2024 (RW-A-06);
- Huang2024 (DIS-08);
- Strgar2022 (SET-C-11);
- Sorenson2026 (RW-B-15);
- Rousso2026 (RW-B-16 note);
- Manenti2016: not used. It has **no entry in `references.bib`**, and its evidence asks for a check before use (EVN line 110). The 20 ms tolerance rests on Stolcke2014 instead.

**Non-selected keys.** No statement cites a dropped key (Malakul2023, Wagner2024, Kurzinger2020, Dror2018, Zhu2022, Raymond2002) or any key outside `references.bib`.

### (c) CLAIM-101…118 → use

| CLAIM | Used in | Remark |
|---|---|---|
| 101 | RES-A-02, RES-A-13, CON-01, Table I, SET-A-05 | Its p and delta are clip-paired; the paper uses speaker-level tests |
| 102 | RES-A-03, AB-07, INT-15, CON-01, Table I | Coverage 89.0 % beside every B number |
| 103 | RES-B-01, RES-B-02 (opt.), AB-04, INT-13, M-C-07, M-C-08, Table I | Delta optional (no Cliff reference) |
| 104 | RES-B-11, AB-08, INT-13, DIS-09, LIM-05, CON-03 | No speaking-style interpretation |
| 105 | RES-B-08, RES-B-09, AB-05, INT-13, DIS-10, CON-03 | Review use only as a possibility in the Discussion |
| 106 | RES-A-04, CON-01, SET-A-01, LIM-07, Table I | NLTK sample |
| 107 | RES-C-01, AB-06, INT-14, CON-04 | Pre-registered check C, 60 s |
| 108 | RES-C-02, LIM-04, INT-14 | Survivors only, 14 speakers |
| 109 | RES-C-03, RES-C-04, AB-06, INT-14, CON-04, Fig. 4 | Chunk explanation descriptive |
| 110 | RES-C-05, INT-14, Fig. 4 | Anchoring required |
| 111 | DIS-13, LIM-10, SET-A-09 | Descriptive ranges; vocoder |
| 112 | DIS-13 | Post-hoc marker kept |
| 113 | DIS-14 (or RES-B-14), DIS-09, LIM-05 | — |
| 114 | RES-A-06, RES-B-04, SET-C-05, INT-13, INT-15, AB-07, CON-02 | "Secondary, added after the main results" kept in each use |
| 115 | RES-A-08, LIM-01, Table I caption | See item 5 in (d) |
| 116 | DIS-03 | Qualitative, plural |
| 117 | RES-A-09, DIS-01, INT-15 (rewritten); CON-02 no longer uses it, CON-06 removed; AB-07 still uses the old wording | Post-hoc, no protocol, not a cause |
| 118 | none: withdrawn 24.11.2026; AB-04 still uses it and is to be rewritten in its check (RES-B-06 removed) | Do not use |

Every CLAIM is used.

### (d) Facts to double-check

**Sources and evidence**

1. **Pages read from full text, not yet in evidence files.** Gernsbacher2015, Horlin2024, Radford2023, Bain2023, Pratap2024, McAuliffe2017, Mirzaei2018 and LeCunff2024 were read from `Thesis/Article base/` PDFs via `pdftotext`. Add their notes to `docs/LITERATURE_ANNOTATIONS.md` before submission. Their versions and page numbering:
   - Radford2023 and Pratap2024 are arXiv versions, so their pages do not match ICML or JMLR pagination; Pratap2024 is cited by section.
   - Mirzaei2018 is a self-archived Kyoto copy.
   - Cuozzo2018 is an author copy (PDF pp. 1–9, not LNCS 448–456).
   - Rousso2024, Yeh2025, Kelley2026, Thompson2026, Hwang2023, Zolkepli2026, FA-Bench and Vaidya2026 pages are arXiv pages.
   - Journal or proceedings pages were checked from page footers for Gernsbacher (195), Horlin (2082), Liu2020 (596–597), Stolcke2014 (5552–5553), Rastorgueva2023 (5257–5258), McAuliffe2026 (347 = PDF p. 1, so Table 4 is p. 352), Pitt2005 (89) and McAuliffe2017 (498–499).
2. **Thompson2026 sample.** EVN says "216 validated DHH and hearing participants". The text says "216 validated participants". RW-A-03 uses only "216 participants".
3. **Stolcke2014 tolerance.** The 20 ms convention there is for phone boundaries on TIMIT (SET-C-02). A reviewer may want a word-level source. Manenti2016 (Buckeye phones) has no bib entry.
4. **Nurym2026 wording.** The 2026 paper left "caption accuracy (WER/CER)" open, not word timing (INT-09). Confirm the publication data before submission (`references.bib`: unpublished talk).

**Wording and caveats**

5. **CLAIM-115 placement.** The CLAIM-115 reason says "report next to every scenario-B number". This bank puts coverage beside every B number and the optimism caveat in the Table I caption and in LIM-01. Decide whether that is enough or whether each B sentence needs the caveat.
6. **Contribution 1 and CLAIM-105.** Accepted contribution 1 says "so a captioner can review a short list". The CLAIM-105 reason allows review use only as a possibility in the Discussion. The clause was moved to DIS-10. Confirm.
7. **CLAIM-118 wording.** The ledger reads "about 40 % of the recall gain"; `TITLE_KEYWORDS_RQ.md` reads "F1 recall gain". The ledger wording is used.
8. **"About 9 points".** CLAIM-114 gives 0.710 vs 0.624, a difference of 0.086 (`F1_RESULTS.md` §3). "About 9 points" is a rounding taken from the accepted contribution text.
9. **Clip-level versus speaker-level p-values.** CLAIM-101, 103 and 104 quote clip-paired p-values (`statistical_significance` in `benchmark_results.json`), while Setup describes speaker-level tests (E1). The paper must say which test each p comes from (`ARTIFACT_VALIDATION.md` §3). RES-A-05, RES-B-03 and RES-B-12 use the speaker-level values; add a CLAIM for them.

**Hardware and code**

10. **GPU and PyTorch.** The frozen `benchmark_results.json` records cuda_device_name = null and torch_cuda_available = false. The GPU model comes from `docs/ARCHITECTURE.md` and `RUNBOOK.md` only, and the PyTorch parts (CTC, BRQE) apparently ran without CUDA in the frozen run. SET-D-01 therefore says only that Whisper ran on the GPU and MFA on the CPU. Confirm before saying more.
11. **WebVTT.** The exporter exists (`export_karaoke_vtt`), but the API does not yet call BRQE or the stitch (`IMPROVEMENT_PLAN.md` §11.5). M-A-07 says "can be exported". Do not claim an end-to-end tool.
12. **Microtest rationale.** M-D-01 and DIS-11 rest on a 6-recording microtest whose folder (`reports/seam_micro/`) is not versioned. Keep "in a small pilot", or drop the mechanism.

**Numbers that need a CLAIM or a decision**

13. **Statements marked "needs CLAIM before submission":**
    - REQUIRED: RES-A-05, RES-A-10, RES-B-03, RES-B-13, RES-B-15, DIS-05, DIS-07, and the speaker count in INT-13, AB-04 and CON-03;
    - OPTIONAL: RES-A-07, A-11, A-12, RES-B-05, B-07, B-12, B-16, B-17, RES-C-06 to C-09, DIS-02, DIS-15;
    - Table I cells marked ◇.
14. **Possible selectivity.** S1b reports B2 long-recording MAE of 49.1–52.2 ms on survivors, much higher than 30.1 ms on clips, but no CLAIM covers it. Reporting A2 survivors (CLAIM-108) without B2 may look selective. A CLAIM for RES-C-06 is recommended.
15. **Valid numbers not written as statements.** These are not in any `docs/*_RESULTS.md`:
    - TIMIT reliability ROC-AUC 0.763 (A2) and 0.769 (B2), in `IMPROVEMENT_PLAN.md` line 270 and the verified `reports/timit/tables/table_quality_estimation.tex`;
    - the stitch anchor found at all 81 seams, in `IMPROVEMENT_PLAN.md` §10.5.
    Make CLAIMs if they are wanted. The Fig. 3 TIMIT panel shows the first item without a CLAIM.
16. **Abstract term.** Whether "F1" counts as a special character in the abstract; "F-score" is the safe form.
17. **Cliff's delta.** If kept (RES-B-02), it needs a reference that is not in the bib.
18. **Preprints.** Recheck Chu2026FABench, Zolkepli2026 and Vaidya2026 for published versions (`REFERENCE_AUDIT.md` §6).
19. **Table I rounding.** TIMIT A2 + const (20.34) and A2 (20.26) both round to 20.3, and B2 (20.46) and B2 + const (20.54) both round to 20.5. Use two decimals in the TIMIT MAE column if the order must be visible.
20. **Page budget.** The guide's 4,000–4,500 words for 6 pages is generous with 4 figures, 1 wide table, 2 algorithms and about 25 references. Expect to cut to about 3,600–3,900 words at layout.

### (e) Estimated total words

- **REQUIRED statement text:** about **4,730 words** of body (§0.3 table). That is about 11 % above the 4,250 target and within the 4,000–4,500 guide plus about 5 %.
- **Abstract:** about 200 words more.
- **Captions:** about 200 words more.
- **OPTIONAL surplus:** about 1,530 words.

Suggested first cuts if the layout overflows:
- INT-17, INT-18 and M-B-04;
- the second sentence of INT-13;
- RES-A-01, folded into the Table I caption;
- SET-A-07, merged with LIM-04;
- DIS-14, if RES-B-14 is used;
- Algorithm 3 and Algorithm 4, which are already optional.

### (f) Decisions of 24.11.2026

The author asked for the most favourable presentation and left the disputed points to the assistant, and all other points to its recommendations.

- **Kept, in one neutral sentence each:** pilots that touched test speakers (Setup), selection of the stitch design (Results), secondary analyses added later (Setup), no significant gain on read speech. Without them "unseen in training", "pre-registered" and "frozen" would mislead, and the repository shows them.
- **Not foregrounded:** details of stopped runs (SET-D-03 is one clause), LIM-08, LIM-13, LeCunff2024, the tempo result on TIMIT. If tempo is mentioned, do not write that read speech is unaffected.
- **CLAIMs:** 107 and 115 reworded, reason of 103 completed, 119–125 added. Optional statements marked "needs CLAIM" stay out of the paper.
- **§10d settled:** item 5 (coverage beside numbers, caveat in the Table I caption and LIM-01); 6 (no captioner clause); 7 (CLAIM-118 not used); 8 (no "about 9 points"); 9 (speaker-level p-values, CLAIM-119); 13; 14 (RES-C-06 in, CLAIM-124); 16 ("F-score" in the abstract); 17 (no Cliff's delta). Item 18 is not a rule of the conference, only good practice.
- **B2** is written "Whisper + MFA"; frozen files are untouched. CLAIM-116 is used in the paper as "MFA ahead of CTC".

### (g) Conference rules (text from the author, 24.11.2026)

Call for Papers: at least 10 references, at most 20 % self-citation, at least 30 % of references from Scopus or Web of Science, at most three authors with at most one faculty member, 4–6 pages, English. The guidelines text has no ban on preprints. IEEE requires original work not under review elsewhere, and a presentation by an author. Our plan: 25 references, 1 self-citation (4 %), 3 arXiv preprints; 18 are journal or proceedings papers (indexing of each was not checked; 8 are needed). Two authors, one faculty member.
