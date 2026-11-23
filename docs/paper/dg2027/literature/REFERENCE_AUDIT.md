# Bibliography audit for the DG 2027 paper (21.11.2026)

Inputs: the audited pool `docs/paper/references.bib` (43 entries, `docs/LITERATURE_MANIFEST.json`, `docs/LITERATURE_AUDIT_20261106.md`), the author's archives (`Thesis/Article base` 62 PDFs, `Thesis/Conference Articles`, `Prototype/selected_articles_conference`, `literature/pdf`), and a new web search on 21.11.2026. Output: `docs/paper/dg2027/latex/references.bib` (36 entries, compiles with IEEEtran). Evidence: older sources in `docs/LITERATURE_ANNOTATIONS.md`, new ones in `EVIDENCE_NEW_SOURCES.md`.

## 1. Main finding: the research gap must be reworded

**FA-Bench** (Chu et al., arXiv, Oct 2026) evaluates word and phone boundaries on TIMIT and Buckeye with held-out speakers under two tracks — reference transcript vs recognizer output — for 21 open systems and 9 APIs. This is the comparison behind our RQ1 and gap item 1 (`IMPROVEMENT_PLAN.md` §10.1: "known text vs ASR rarely compared in one pipeline on manual boundaries"). That item can no longer be presented as a gap.

What still holds and is ours:
1. **BRQE**: a lightweight learned refinement plus a per-boundary reliability score, trained only on disjoint speakers, frozen before testing, compared with a constant-offset rival, with a negative transfer result on read speech (CLAIM-103…105). Closest prior work: boundary correction over HMM (Stolcke2014), CNN boundary refinement (Cuozzo2018, not yet read), ensemble confidence intervals (Kelley2026). None of these reports a reliability head evaluated by ROC-AUC and a rejection curve on held-out spontaneous-speech speakers — state it as a difference, not as a first.
2. **Long recordings**: chunk seams, not length, drive the error; one failed chunk removes whole recordings; overlap-and-stitch passes a pre-registered seam check (CLAIM-107…110). FuseAlign (2026) independently notes that a globally constrained decoder lets one mismatch shift neighbouring words — consistent with our seam mechanism.
3. **RQ1 becomes a consistency check, not a contribution**: our numbers agree in order with FA-Bench, Zolkepli2026 and McAuliffe2026 (MFA about 19–22 ms; Whisper timestamps about 120–150 ms; torchaudio MMS about 37–42 ms), obtained in one local pipeline with speaker-level exact tests and coverage beside every error.

Also required by FA-Bench: our scenario-B MAE is computed on matched words only; FA-Bench shows this can make recognition-dependent systems look 9–14 % better on Buckeye. Report coverage next to every B number (already a project rule) and name this as a limitation. **Done 23.11.2026:** boundary F1 at 20 ms that charges missed and inserted words gives the same conclusions on Buckeye; matched-word B scores are about 11 % optimistic (`docs/F1_RESULTS.md`). In the paper this becomes a robustness check, not an open limitation.

Recommended updates (author's decision): contributions in `TITLE_KEYWORDS_RQ.md` (done there as a proposal), gap item 1 in `IMPROVEMENT_PLAN.md` §10.1 (marked there), the Introduction plan in `latex/main.tex`.

## 2. Selected references (36)

Status: **R** = full text read and evidence recorded; **R\*** = read earlier, evidence in `LITERATURE_ANNOTATIONS.md`; **TODO** = not read, needs the author.

| Section | Key | Why needed | Status |
|---|---|---|---|
| Intro: captions and access | Gernsbacher2015 | Captions benefit many viewers | R\* (manifest) |
| | Horlin2024 | Captions matter for disabled and neurodivergent students | R\* |
| | LeCunff2024 | Transcript errors complicate learning for neurodivergent students | R\* |
| | Thompson2026 | Caption timing affects DHH viewers (seconds scale) | R |
| | Mirzaei2018 | Synchronized captions; word-level sync use case | R\* |
| | Malakul2023 | Auto-subtitles in education (optional) | R\* |
| | Nurym2026 | Previous DG 2026 work: accuracy left open | TODO status |
| ASR and timestamps | Radford2023 | Whisper | R\* |
| | FasterWhisper | Implementation used (CTranslate2, int8) | R (README) |
| | SileroVAD | VAD used | R (README) |
| | Bain2023 | WhisperX: ASR text + CTC alignment (our B1 idea) | R\* |
| | Yeh2025 | Whisper timestamps are coarse; stricter tolerances | R |
| | Wagner2024 | CrisperWhisper timestamps (optional) | R\* |
| Forced alignment | Povey2011 | Kaldi under MFA | R |
| | McAuliffe2017 | MFA | R\* |
| | McAuliffe2026 | MFA accuracy 2026 on TIMIT/Buckeye | R\* |
| | Pratap2023 | MMS (our CTC baselines) | R\* |
| | Rastorgueva2023 | NFA for subtitles; MFA fails on long files | R\* |
| | Rousso2024 | MFA vs WhisperX vs MMS on TIMIT/Buckeye | R\* |
| | Chu2026FABench | Same two-track comparison; metric critique | R |
| | Zolkepli2026 | MFA most precise; why CTC starts late | R |
| | Zhu2022 | Neural aligners (Charsiu) | R\* |
| | Kelley2024 | Neural aligner with sub-frame interpolation | R |
| | Vaidya2026 | Long-form, ASR-transcript aligner; presence head | R |
| | Mu2026 | Neural aligner on long spliced speech (optional) | R\* |
| Refinement and reliability | Stolcke2014 | Boundary correction over HMM (prior art) | R\* |
| | Cuozzo2018 | CNN boundary refinement (closest prior art) | **TODO: obtain** |
| | Kelley2026 | Per-boundary uncertainty for review | R |
| Long recordings | Moreno1998 | Recursive alignment of very long audio | R\* |
| | Kurzinger2020 | CTC segmentation of long audio (optional) | R\* |
| Corpora | Garofolo1993 | TIMIT | R\* (scan) |
| | Pitt2005 | Buckeye | R\* |
| | Raymond2002 | Buckeye annotator consistency (only if the 20 ms context is discussed) | R\* |
| Statistics | Holm1979 | Holm correction used | **TODO: read** |
| | Liu2020Blockwise | Utterances within a speaker are dependent | R\* |
| | Dror2018 | Choice of paired tests (optional) | R\* |

For 6 pages, 22–26 citations are realistic. The "optional" rows are the first to drop.

## 3. Pool entries not used in the paper (kept for the dissertation)

Sumi2025, Ingavelez2022, Sweller2020, Mayer2020 (actually Castro-Alonso et al. 2021), Kruger2016, Machacek2023, McKinnon2026, Belkhouja2022, Sun2023, Baevski2020, Malik2021, Borah2026 (actually Miao et al. 2022), Teng2024, Hsu2021, Gandhi2023, Gong2023, Cooper2024 (actually Le Cunff et al. 2025), Skulmowski2022 (actually Castro-Alonso and de Koning 2020), ITU1998, EBU2007. Reasons are in the manifest `role` fields: outside the measured question, not evaluated here, or broadcast audio-video thresholds that do not define subtitle accuracy. New reserve: Multilingual2026, RefFree2026, Manenti2016.

## 4. Gaps searched and how they were closed

| Gap | Result |
|---|---|
| Recent (2025–2026) aligner benchmarks on manual boundaries | Closed: Chu2026FABench, Zolkepli2026, McAuliffe2026 |
| Kaldi primary source | Closed: Povey2011 |
| Reliability or uncertainty of individual boundaries | Closed: Kelley2026; Vaidya2026 (presence head) |
| Neural boundary refinement prior art | Partly: Kelley2024 read; Cuozzo2018 needs manual access |
| Whisper word-timestamp accuracy (recent) | Closed: Yeh2025; FA-Bench Whisper rows |
| Caption timing and users (recent) | Closed: Thompson2026 (seconds-scale caveat) |
| Holm original | Open: JSTOR only |
| Software citations | Closed: SileroVAD, FasterWhisper |

## 5. Age and type (for information; the conference sets no quotas)

Of 36: 2026 — 9, 2024–2025 — 8, 2020–2023 — 7, 2011–2018 — 7, before 2010 — 5 (Moreno1998, Raymond2002, Pitt2005, Garofolo1993, Holm1979). Preprints: Chu2026FABench, Zolkepli2026, Vaidya2026 (cite as arXiv; check for published versions before submission). Software: 2.

## 6. Before submission

1. Read Holm1979 and Cuozzo2018 through a library; complete Cuozzo's given names.
2. Confirm the DG 2026 paper's publication data (Nurym2026).
3. Re-check the three preprints for published versions.
4. Every cited claim in the text must point to a quote or note in `EVIDENCE_NEW_SOURCES.md` or `LITERATURE_ANNOTATIONS.md`.
