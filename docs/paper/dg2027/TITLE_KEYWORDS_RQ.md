# Title, keywords, affiliation and research questions (DG 2027)

Draft 21.11.2026 for the author's decision. Constraints: DG rules forbid symbols, special characters and math in the title and abstract; the title must not promise what was not measured (no lecture corpus with manual boundaries, no user study, no guarantee of sub-20 ms accuracy).

## Title

**Recommended (in `latex/main.tex`):**
> Word Boundary Accuracy and Reliability Estimation in Forced Alignment for Accessible Educational Video

Why: names the two measured things (boundary accuracy, reliability), the method family (forced alignment) and the purpose that links to the thesis topic and the 2026 paper, without claiming that lectures were evaluated. 15 words, no symbols.

Alternatives:
1. *Known Transcript Versus Speech Recognition Text in Forced Alignment for Caption Timing* — strongest on scenario A/B; omits BRQE.
2. *Learned Boundary Refinement and Reliability Estimation for Forced Alignment of Spontaneous Speech* — strongest on BRQE; loses the accessibility link.
3. *How Accurate Are Word Timings for Captions* — catchy, but question mark is a special character and it is vague.

Avoid: "phoneme-accurate", "sub-20 ms", "real-time", "lecture" as evaluated data, "novel framework", "end-to-end platform".

## Keywords (10, IEEE style, lower case)

forced alignment, word boundary accuracy, speech-text alignment, automatic speech recognition, Montreal Forced Aligner, boundary refinement, reliability estimation, captions, accessibility, educational video

## Authors and affiliation (as in the DG 2026 paper, confirmed by the author)

1st Askar Nurym — School of Software Engineering, Astana IT University, Astana, Kazakhstan — 255453@astanait.edu.kz
2nd Tamara Zhukabayeva — School of Software Engineering, Astana IT University, Astana, Kazakhstan — t.zhukabayeva@astanait.edu.kz

The blind version removes both blocks and any self-identifying sentence; the DG 2026 paper is then cited in the third person.

## Research questions

Derived from `IMPROVEMENT_PLAN.md` §10.1 (RQ1–RQ4), narrowed to what the 6-page paper reports. Each is answerable from approved claims only.

- **RQ1.** How large is the word- and phone-boundary error of open pipelines that combine speech recognition with forced alignment, measured against manual boundaries on read (TIMIT) and spontaneous (Buckeye) English speech, and how much does a known transcript reduce it compared with recognized text? *Evidence:* CLAIM-101, 102, 106 (with word coverage for scenario B).
- **RQ2.** Does a lightweight learned post-alignment module reduce forced-alignment boundary error more than a constant-offset correction on held-out speakers, and does its reliability score separate boundaries that are more than 20 ms off? *Evidence:* CLAIM-103, 104 (negative transfer to read speech), 105.
- **RQ3.** On recordings of one to ten minutes, how do recording length and chunking affect boundary error and the share of failed alignments? *Evidence:* CLAIM-107…110.

RQ4 (tempo, Whisper size) is answered in one sentence in the Discussion (CLAIM-111…113 and the S3 result), not as a research question, to fit 6 pages.

What makes them valid: each names the population (English read and spontaneous speech), the comparison (A vs B; BRQE vs constant offset; lengths), the measure (MAE, Acc@20 ms, coverage, ROC-AUC, failures) and the reference (manual boundaries, held-out speakers).

## Update 21.11.2026 after the literature search

FA-Bench (Chu et al., arXiv, Oct 2026) already compares a reference transcript with recognizer output on TIMIT and Buckeye with held-out speakers (`literature/REFERENCE_AUDIT.md` §1). RQ1 stays as a question, but contribution 1 below is reworded as an independent consistency check, and the paper's weight moves to BRQE and long recordings. The original wording is kept below for reference.

**Proposed contributions (replace the list below if the author agrees):**
1. A lightweight boundary refinement and reliability module trained only on disjoint speakers and frozen before testing, compared with a constant-offset rival on held-out spontaneous speech, with its negative transfer to read speech reported.
2. Evidence on one- to ten-minute recordings that chunk seams, not length, drive the error and that one failed chunk removes whole recordings; an overlap-and-stitch fix that passes a pre-registered seam check.
3. Known-transcript and recognized-text alignment measured in one local pipeline with speaker-level exact tests and coverage beside every error; the numbers agree in order with recent independent benchmarks.

## Positioning after FA-Bench (proposal 23.11.2026, author's decision)

Author's requirement (23.11.2026): the paper must not read as a check of someone else's preprint and must not lose its own value.

**Rules for the text.**
1. FA-Bench is one of several recent evaluations (Chu2026FABench, Zolkepli2026, McAuliffe2026), cited together in Related Work and once in the Discussion. It is never named in the abstract, the title or the contributions. The words "verify", "validate", "replicate" or "confirm FA-Bench" are not used.
2. Agreement goes in our favour, plural and short: "Our MFA and Whisper figures are consistent with recent benchmarks [..]" (CLAIM-116). It supports our numbers; it is not a result.
3. The type of paper differs and is stated: those works *rank existing systems*; this paper *proposes and tests additions to an alignment pipeline for captioning* (a refinement and reliability module, an overlap-and-stitch scheme for long recordings) and measures what the choice of transcript costs inside that pipeline.
4. The F1 analysis is our robustness check against a known criticism of MAE, cited to its source: "Because matched-word MAE can favour recognition-based systems [Chu2026], we also report boundary F1 that charges missed and inserted words; all conclusions hold (CLAIM-114), and matched-word scores for recognized text are about 11 % optimistic (CLAIM-115)." That is what a careful paper does, not a check of their work.
5. Gap = what our paper does that none of the read works does (checked against EVIDENCE_NEW_SOURCES.md; state as a difference, never "first"):
   - a learned post-alignment module that also outputs a per-boundary reliability score, evaluated by ROC-AUC and a rejection curve on held-out speakers of spontaneous speech (Cuozzo2018: refinement only, read single-speaker TTS data; Kelley2026: ensemble intervals around a neural aligner; FuseAlign: word presence, not boundary error);
   - the cost of chunk seams and of chunk failures on 1–10 minute recordings measured against manual boundaries (long-form aligners — NFA, LLM-ForcedAligner, FuseAlign — report accuracy, not where it is lost);
   - speaker-level exact tests for every comparison (FA-Bench reports none; text search for Wilcoxon, bootstrap and confidence intervals found nothing).

**Proposed contributions v2 (replace the list below if the author agrees).**
1. A lightweight boundary refinement and reliability module for forced alignment, trained only on disjoint speakers and frozen before testing. On held-out spontaneous speech it beats a constant-offset rival under both MAE and boundary F1, mostly at speech-segment edges, and its reliability score detects boundaries more than 20 ms off (ROC-AUC 0.75). Its negative transfer to read speech is reported.
2. Evidence on one- to ten-minute recordings that chunk seams, not length, drive the error and that one failed chunk removes whole recordings, with an overlap-and-stitch scheme that passes a pre-registered seam check.
3. A measurement, inside one local captioning pipeline with speaker-level tests, of what recognized text costs compared with a known transcript, and where the cost arises: on boundaries between correctly recognized words both scenarios are equally accurate, so the loss comes from recognition, not alignment.

Why this is stronger than "a same-pipeline comparison": item 3 now ends in a practical finding for captioning (improve the transcript, not the aligner), which the benchmarks do not state for a pipeline; items 1–2 are methods, not measurements of existing tools.

## Contributions (for the Introduction)

1. A same-pipeline comparison of known-transcript and recognized-text alignment on manual word and phone boundaries of read and spontaneous speech, with speaker-level statistics and coverage reported beside every error.
2. A lightweight boundary refinement and reliability module trained only on disjoint speakers, frozen before testing, compared with a constant-offset rival, including its negative transfer result.
3. Evidence on long recordings that chunk seams, not length, drive the error, and that one failed chunk removes whole recordings; an overlap-and-stitch fix that passes a pre-registered seam check.

No claim of novelty for post-alignment correction itself (prior art: Stolcke et al. 2014), of learning benefit, or of accessibility impact on users.
