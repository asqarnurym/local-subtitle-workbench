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

- **RQ1.** How large is the word- and phone-boundary error of open pipelines that combine speech recognition with forced alignment, measured against manual boundaries on read (TIMIT) and spontaneous (Buckeye) English speech, and how much does a known transcript reduce it compared with recognized text? *Evidence:* CLAIM-101, 102, 106 (with word coverage for scenario B), robustness under boundary F1 CLAIM-114, 115; where B loses CLAIM-117.
- **RQ2.** Does a lightweight learned post-alignment module reduce forced-alignment boundary error more than a constant-offset correction on held-out speakers, and does its reliability score separate boundaries that are more than 20 ms off? *Evidence:* CLAIM-103, 104 (negative transfer to read speech), 105, 114; where BRQE gains CLAIM-118.
- **RQ3.** On recordings of one to ten minutes, how do recording length and chunking affect boundary error and the share of failed alignments? *Evidence:* CLAIM-107…110.

RQ4 (tempo, Whisper size) is answered in one sentence in the Discussion (CLAIM-111…113 and the S3 result), not as a research question, to fit 6 pages.

What makes them valid: each names the population (English read and spontaneous speech), the comparison (A vs B; BRQE vs constant offset; lengths), the measure (MAE, Acc@20 ms, coverage, ROC-AUC, failures) and the reference (manual boundaries, held-out speakers).

## Positioning (accepted direction 23.11.2026)

The author asked for the presentation that shows the work in its best light, within what the evidence supports, and never as a check of another group's preprint. History: the first list (21.11) led with the A vs B comparison; after FA-Bench (arXiv, Sep–Oct 2026) that comparison alone is no longer a gap, so the weight moved to the methods and to a practical finding.

**Rules for the text.**
1. FA-Bench is one of several recent evaluations (Chu2026FABench, Zolkepli2026, McAuliffe2026, Rousso2024), cited together in Related Work and once in the Discussion. Never in the title, abstract or contributions; never "verify", "validate", "replicate" or "confirm" another work.
2. Type of paper, said once in the Introduction: those works rank existing aligners and recognizers on short utterances; this paper proposes and tests additions to a local captioning pipeline and measures what the transcript choice costs inside it.
3. Agreement supports our numbers, plural and short, in the Discussion: "our MFA and Whisper figures are consistent with recent benchmarks [..]" (CLAIM-116).
4. Boundary F1 is our robustness check against a known weakness of matched-word MAE, cited to its source; MAE stays the pre-registered primary metric (CLAIM-114, 115).
5. Gap = what we do that none of the read works does, stated as a difference, never "first" (sources in `literature/EVIDENCE_NEW_SOURCES.md`):
   - learned refinement that also gives a per-boundary reliability score, evaluated on held-out speakers of spontaneous speech (Cuozzo2018: refinement only, read single-speaker data; Kelley2026: ensemble intervals around a neural aligner; FuseAlign: word presence, not boundary error);
   - where accuracy is lost on 1–10 minute recordings (seams, chunk failures), against manual boundaries (long-form aligners report accuracy, not where it is lost);
   - speaker-level exact tests for every comparison.
6. Keep honest edges visible: negative transfer to read speech (CLAIM-104, 113), survivors only in S1b, scenario-B matched-word optimism (CLAIM-115). Stating limits plainly is part of the best light for reviewers.

## Contributions (for the Introduction; accepted 23.11.2026)

1. **Refinement and reliability for forced alignment.** A lightweight module, trained only on speakers disjoint from the test set and frozen before testing, that corrects word boundaries and scores their reliability. On held-out spontaneous speech it beats a constant-offset correction under both error and boundary F1 for all 20 test speakers, with the largest corrections at the ends of speech segments, where the aligner is least accurate; its reliability score flags boundaries more than 20 ms off (ROC-AUC 0.75), so a captioner can review a short list instead of every word. Its limits on read speech are reported. *Evidence:* CLAIM-103, 105, 114, 118 (candidate), 104; 20 of 20 speakers on MAE: `reports/e1_analysis_20261102/analysis.json` speaker_comparisons (B2brqe_vs_B2const, A2brqe_vs_A2const).
2. **Long recordings.** On recordings of one to ten minutes, accuracy is lost at chunk seams, not with length, and a single failed chunk removes a whole recording; an overlap-and-stitch scheme passes a pre-registered seam check. *Evidence:* CLAIM-107…110.
3. **What a recognized transcript costs.** Inside one local pipeline that runs on a 4 GB laptop GPU, with speaker-level tests and a metric that charges missed words, recognized text costs about 9 points of boundary F1 on spontaneous speech, and the cost comes from recognition, not alignment: boundaries between correctly recognized words are placed equally well in both scenarios. For captioning, effort is better spent on the transcript than on the aligner. *Evidence:* CLAIM-101, 102, 114, 115, 117 (candidate).

No claim of novelty for post-alignment correction itself (prior art: Stolcke2014, Cuozzo2018), of learning benefit, or of accessibility impact on users.

## CLAIM-117 and 118 (approved 23.11.2026, in `docs/CLAIM_LEDGER.csv`)

- **CLAIM-117.** On Buckeye test speakers, boundaries between two correctly recognized words are placed equally well with recognized and with known text (recall at 20 ms 0.728 vs 0.731); recognized text has fewer such boundaries (74 % vs 89 % of reference boundaries), so the scenario-B loss comes from recognition, not alignment. Descriptive, no test.
- **CLAIM-118.** BRQE's largest corrections are at the ends of speech segments, where MFA is least accurate: on Buckeye, recall at 20 ms of the segment-final boundary rises from 0.41–0.44 to 0.75–0.76, and segment edges (9 % of boundaries) give about 40 % of the F1 recall gain; on read speech (TIMIT) the gain is at segment edges only. Descriptive, no test.
