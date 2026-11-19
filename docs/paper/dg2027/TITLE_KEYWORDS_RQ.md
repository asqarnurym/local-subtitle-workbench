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

## Contributions (for the Introduction)

1. A same-pipeline comparison of known-transcript and recognized-text alignment on manual word and phone boundaries of read and spontaneous speech, with speaker-level statistics and coverage reported beside every error.
2. A lightweight boundary refinement and reliability module trained only on disjoint speakers, frozen before testing, compared with a constant-offset rival, including its negative transfer result.
3. Evidence on long recordings that chunk seams, not length, drive the error, and that one failed chunk removes whole recordings; an overlap-and-stitch fix that passes a pre-registered seam check.

No claim of novelty for post-alignment correction itself (prior art: Stolcke et al. 2014), of learning benefit, or of accessibility impact on users.
