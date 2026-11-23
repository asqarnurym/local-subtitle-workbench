# Pseudocode for the DG 2027 paper

Written 21.11.2026 from the code at commit `e33ebe1`. Every step names its source so the paper text can be checked against the implementation. Constants are the frozen values (`bench-frozen-20261029c`). The LaTeX version for the paper is `algorithms.tex` in this folder (`algorithm` + `algpseudocode`; the IEEE template allows it).

Recommendation for 6 pages: **Algorithm 1** (pipeline) and **Algorithm 2** (BRQE inference) in the paper; Algorithm 3 (anchoring) only if space allows, otherwise one equation (Eq. 6 in `FORMULAS.md`); Algorithm 4 (stitch) belongs to the S1b paragraph only if S1b gets more than a few lines.

## Algorithm 1. Proposed alignment pipeline (one recording)

Source: `src/subtitle_workbench/pipeline.py` (`prepare_alignment_job`, `run_speech_pipeline`), `scripts/speech_benchmark.py` (staging per speaker), `src/subtitle_workbench/refiner.py` (`refine_prediction`).

```
Input:  audio x (16 kHz mono), optional transcript T, speaker id s
Output: word and phone boundaries with a reliability score per word

1:  P ← SileroVAD(x)                                   ▷ pauses ≥ 0.4 s
2:  H ← Whisper-large-v3(x) with word timestamps        ▷ always run; int8_float16
3:  if T is given then                                  ▷ scenario A
4:      W ← AnchorTranscript(T, H, |x|)                 ▷ Algorithm 3
5:  else                                                ▷ scenario B
6:      W ← words of H
7:  C ← PartitionIntoChunks(W, P, max 30 s, padding 0.5 s)
        ▷ cut priority: VAD pause midpoint > ASR segment boundary > widest inter-word gap
8:  A ← MFA-align(C) in one call per speaker
        ▷ english_us_arpa acoustic model and dictionary, G2P for OOV words,
        ▷ speaker adaptation, --fine_tune, num_jobs = 1; a failure is recorded, never replaced
9:  A ← Reconcile(A) into one monotonic timeline        ▷ chunk → global time
10: (A′, r) ← BRQE(x, A)                                ▷ Algorithm 2
11: return A′, r                                        ▷ exported as WebVTT, JSON-LD
```

Notes for the text:
- In the benchmark every clip is shorter than 30 s, so step 7 yields one chunk; chunking matters only for long recordings (S1b, Algorithm 4).
- Baselines replace steps 8–10: B0 returns Whisper word times; B1 and A1 replace MFA with the MMS_FA CTC trellis (`torchaudio.pipelines.MMS_FA`). The programs WhisperX and NFA themselves were not run; B1 follows the WhisperX idea (ASR text + CTC alignment).
- The constant-offset rival replaces step 10 with a median shift per boundary kind and scenario (`ConstantRefiner`).

## Algorithm 2. BRQE inference

Source: `src/subtitle_workbench/refiner.py` (`MelExtractor`, `window_at`, `scalar_features`, `BRQENet`, `refine_prediction`, `_shifted`).

```
Input:  audio x; aligned tokens (words, then phones folded to 39 labels) with times
Output: refined tokens; word reliability ρ_w = 1 − max(p_start, p_end)

1:  M ← log-mel(x): 64 bands, 25 ms window, 5 ms hop; per-utterance mean/variance norm.
2:  for each boundary b with time t_b (start and end of every word and phone) do
3:      X_b ← M[:, c−20 … c+20], c = round(t_b / 5 ms)           ▷ ±100 ms, zero-padded
4:      z_b ← [is_start, is_word, scenario_B, log duration, t_b/5ms − c, 1]
5:      (Δ_b, ℓ_b) ← BRQENet(X_b, z_b)                             ▷ Eq. 8
6:      t_b′ ← t_b + Δ_b ;  p_b ← σ(ℓ_b)
7:  for consecutive tokens i−1, i: if start_i′ < end_{i−1}′ then both ← midpoint
8:  a token whose refined duration < 5 ms keeps its original times
9:  ρ_w ← 1 − max(p_start(w), p_end(w)) for every word w
10: return refined tokens, ρ
```

Training (once, 20 training speakers of Buckeye, 3000 clips, manual boundaries): targets `e_b = t_ref − t_b`; loss in Eq. 9; AdamW, lr 1e‑3, weight decay 1e‑4, batch 512, 12 epochs, seed 20260401, hidden 128, dropout 0.2. Inclusion was decided by the pre-registered 5-fold speaker CV rule before any test number existed (`IMPROVEMENT_PLAN.md` §6.5).

## Algorithm 3. Transcript anchoring (scenario A)

Source: `src/subtitle_workbench/anchoring.py` (`banded_sequence_alignment`, `anchor_transcript`).

```
Input:  reference words R[1..n] (normalized), ASR words H[1..m] with times, duration D
Output: approximate times for every reference word

1:  band ← max(50, 0.1·max(n, m), |n − m| + 1)
2:  fill S(i, j) by Eq. 6 only for |j − i·m/n| ≤ band             ▷ O(n·band)
3:  backtrace; keep exact matches (i, j) on the best path as candidate anchors
4:  keep an anchor only if it starts after the previous anchor's end   ▷ monotonic
5:  for each run of unanchored words between anchors a and b do
6:      spread them over [end(a), start(b)] proportionally to their character length
7:  return times for R
```

## Algorithm 4. Overlap-and-stitch for long recordings (S1b)

Source: `scripts/seam_stitch.py`; parameters `SPEECH_PAD_MS = 30`, `MIN_OVERLAP_S = 3.0`, `ANCHOR_TOL_S = 0.02`.

```
1:  P ← SileroVAD(x) with speech padding 30 ms                   ▷ default 400 ms hid pauses
2:  C ← PartitionIntoChunks(...) as in Algorithm 1
3:  extend each chunk with neighbouring words until ≥ 3 s of overlap on each side;
    its audio ends in the gap after the outermost added word
4:  align all chunks (MFA, one call per speaker)
5:  for each seam between tracks k and k+1 do
6:      anchor ← word aligned in both tracks with the same text and both boundaries
                 within 20 ms, closest to the seam; the first word of the earlier track
                 and the last word of the later track are excluded
7:      keep track k up to the anchor and track k+1 after it
8:      if no anchor exists then cut at the seam time (logged)
9:  enforce a monotonic timeline
```
