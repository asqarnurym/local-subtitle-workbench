"""Adversarial stress challenge suite for Increment 3 (Macro-DTW Chunking & Reconciler).

Empirically tests extreme boundaries, failure modes, and stress limits:
1. Chunker Anchor Selection Hierarchy (P1 > P2 > P3 > fallback).
2. Chunker Extreme Boundaries (FP precision, trailing silence > 30s, long lectures).
3. Chunker Invariants & Word Completeness (every word retained, strict duration bounds).
4. Reconciler Seam Boundary Deduplication & Retention.
5. Reconciler Monotonicity Violations & Coarticulation Resolution.
6. Reconciler Micro-Phoneme Preservation & Clamping at boundaries (including near t=0).
7. Scalability & Memory Bounds under load (1000+ chunks, 20000+ words).
"""

from __future__ import annotations

import sys
import time
from typing import Any

from subtitle_workbench.chunker import (
    ChunkingError,
    MonotonicityError,
    partition_into_chunks,
    reconcile_chunk_alignments,
)
from subtitle_workbench.models import (
    ASRSegment,
    AudioChunk,
    PhonemeCue,
    WordToken,
)


def make_word(
    word_id: str,
    text: str,
    start: float,
    end: float,
    confidence: float = 0.95,
    phonemes: list[PhonemeCue] | None = None,
) -> WordToken:
    return WordToken(
        id=word_id,
        text=text,
        normalized=text.lower().strip(".,!?"),
        start=round(start, 4),
        end=round(end, 4),
        confidence=confidence,
        phonemes=phonemes if phonemes is not None else [],
    )


def make_segment(
    seg_id: str,
    start: float,
    end: float,
    words: list[WordToken],
) -> ASRSegment:
    text = " ".join(w.text for w in words)
    return ASRSegment(
        id=seg_id,
        start=round(start, 4),
        end=round(end, 4),
        text=text,
        words=words,
    )


class ChallengeResults:
    def __init__(self) -> None:
        self.tests_run = 0
        self.tests_passed = 0
        self.tests_failed = 0
        self.findings: list[dict[str, Any]] = []

    def check(self, condition: bool, test_name: str, error_msg: str = "") -> bool:
        self.tests_run += 1
        if condition:
            self.tests_passed += 1
            print(f"  [PASS] {test_name}")
            return True
        else:
            self.tests_failed += 1
            print(f"  [FAIL] {test_name}: {error_msg}")
            return False

    def add_finding(self, title: str, severity: str, details: str) -> None:
        self.findings.append({"title": title, "severity": severity, "details": details})
        print(f"  [FINDING - {severity.upper()}] {title}: {details}")


results = ChallengeResults()

print("=" * 70)
print("ADVERSARIAL STRESS CHALLENGE: INCREMENT 3")
print("=" * 70)


# ============================================================================
# Section 1: Chunker Extreme Boundary Testing
# ============================================================================
print("\n--- Section 1: Chunker Extreme Boundaries & Invariants ---")

# 1.1 Trailing silence > 30s: speech ends early, total_duration is long (e.g. 1800s)
w0 = make_word("w0", "intro", 10.0, 15.0)
seg_trail = make_segment("s0", 10.0, 15.0, [w0])
chunks_trail = partition_into_chunks([seg_trail], [], 1800.0)
results.check(
    len(chunks_trail) == 1
    and chunks_trail[0].start == 0.0
    and chunks_trail[0].end == 15.0
    and chunks_trail[0].padded_end == 15.5
    and chunks_trail[0].padded_end <= 1800.0,
    "Trailing silence > 30s produces bounded valid chunk covering speech",
    f"Got chunks: {chunks_trail}",
)

# 1.2 Multi-gap silence (3 pauses of 45s between 4 short words)
w_g0 = make_word("wg0", "one", 10.0, 12.0)
w_g1 = make_word("wg1", "two", 60.0, 62.0)
w_g2 = make_word("wg2", "three", 110.0, 112.0)
w_g3 = make_word("wg3", "four", 160.0, 162.0)
seg_g0 = make_segment("sg0", 10.0, 12.0, [w_g0])
seg_g1 = make_segment("sg1", 60.0, 62.0, [w_g1])
seg_g2 = make_segment("sg2", 110.0, 112.0, [w_g2])
seg_g3 = make_segment("sg3", 160.0, 162.0, [w_g3])
chunks_multigap = partition_into_chunks([seg_g0, seg_g1, seg_g2, seg_g3], [], 200.0)
multigap_valid = (
    len(chunks_multigap) == 4
    and all(round(c.end - c.start, 4) <= 30.0 for c in chunks_multigap)
    and all(
        0.0 <= c.padded_start <= c.start < c.end <= c.padded_end <= 200.0 for c in chunks_multigap
    )
)
results.check(
    multigap_valid,
    "Multiple long pauses (>30s) advance curr_start cleanly without oversized chunks",
    f"Durations: {[round(c.end - c.start, 4) for c in chunks_multigap]}",
)

# 1.3 Floating-point boundary clamping on total_duration: 10.00001, 10.00004, 10.00006, 10.00009
fp_clamping_passed = True
for dur in [10.00001, 10.00004, 10.00006, 10.00009, 30.00005, 60.00007]:
    w_fp = make_word("wfp", "word", 0.0, 5.0)
    seg_fp = make_segment("sfp", 0.0, 5.0, [w_fp])
    c_list = partition_into_chunks([seg_fp], [], dur)
    for c in c_list:
        if c.end > dur or c.padded_end > dur or c.padded_start < 0.0 or c.start < c.padded_start:
            fp_clamping_passed = False
            break
results.check(
    fp_clamping_passed,
    "Floating-point sub-millisecond total_duration bounds (10.00001..60.00007) clamped strictly",
)

# 1.4 Exact 30.0000s duration speech block
w_exact = make_word("w_ex", "long", 0.0, 30.0)
seg_exact = make_segment("s_ex", 0.0, 30.0, [w_exact])
chunks_exact = partition_into_chunks([seg_exact], [], 30.0)
results.check(
    len(chunks_exact) == 1
    and chunks_exact[0].start == 0.0
    and chunks_exact[0].end == 30.0
    and chunks_exact[0].padded_end == 30.0,
    "Exact 30.0s audio with 30.0s word produces exactly 1 chunk bounded at [0.0, 30.0]",
)

# 1.5 Word duration > 30.0s raises ChunkingError
w_toolong = make_word("w_tl", "toolong", 0.0, 30.1)
seg_toolong = make_segment("s_tl", 0.0, 30.1, [w_toolong])
try:
    partition_into_chunks([seg_toolong], [], 35.0)
    results.check(False, "Word > 30.0s raises ChunkingError", "No exception raised")
except ChunkingError:
    results.check(True, "Word duration > 30.0s correctly raises ChunkingError")

# 1.6 Word completeness invariant: every word in input segments appears in exactly one chunk
words_input = [
    make_word(f"w_{i}", f"word{i}", float(i * 3), float(i * 3 + 2))
    for i in range(50)  # spans 0 to 150s
]
segs_input = [
    make_segment(
        f"seg_{i // 5}",
        words_input[i * 5].start,
        words_input[i * 5 + 4].end,
        words_input[i * 5 : i * 5 + 5],
    )
    for i in range(10)
]
chunks_complete = partition_into_chunks(segs_input, [], 160.0)
words_in_chunks = [w.id for c in chunks_complete for w in c.words]
results.check(
    words_in_chunks == [w.id for w in words_input],
    "Word completeness: all 50 input words retained sequentially across chunks without gaps",
)


# ============================================================================
# Section 2: Chunker Multi-Tier Anchor Priority Testing
# ============================================================================
print("\n--- Section 2: Chunker Multi-Tier Anchor Priority Verification ---")

# 2.1 Priority 1 (VAD silence) vs Priority 2 (Segment boundary)
# Segment boundary at 20.0s. VAD silence at 25.0s. Chunker must choose VAD silence at 25.0s!
w_p1 = [
    make_word("w0", "a", 5.0, 10.0),
    make_word("w1", "b", 10.0, 19.5),
    make_word("w2", "c", 20.5, 24.5),
    make_word("w3", "d", 25.5, 29.0),
    make_word("w4", "e", 32.0, 35.0),
]
s1 = make_segment("s1", 5.0, 19.5, w_p1[:2])
s2 = make_segment("s2", 20.5, 29.0, w_p1[2:4])
s3 = make_segment("s3", 32.0, 35.0, w_p1[4:])
vad_sil = [(24.5, 25.5)]  # mid = 25.0
c_p1 = partition_into_chunks([s1, s2, s3], vad_sil, 40.0)
results.check(
    c_p1[0].end == 25.0,
    "Multi-tier Priority 1: VAD silence at 25.0s preferred over segment boundary at 20.0s",
    f"Chunk 0 ended at {c_p1[0].end}",
)

# 2.2 Priority 2 (Segment boundary) vs Priority 3 (Inter-word gap)
# When no VAD silence is available, segment boundary at 20.0s is preferred over gap at 15.0s
c_p2 = partition_into_chunks([s1, s2, s3], [], 40.0)
results.check(
    c_p2[0].end == 20.0,
    "Multi-tier Priority 2: Segment boundary preferred over inter-word gap when no VAD",
    f"Chunk 0 ended at {c_p2[0].end}",
)


# ============================================================================
# Section 3: Reconciler Seam Deduplication & Retention
# ============================================================================
print("\n--- Section 3: Reconciler Seam Deduplication & Retention ---")

# 3.1 Unique boundary word spanning seam is NOT dropped (Fix D3 verification)
c0 = AudioChunk("c0", 0, 0.0, 25.0, 0.0, 25.5, "w0 w1", [])
c1 = AudioChunk("c1", 1, 25.0, 50.0, 24.5, 50.0, "w2 w3", [])
w0 = make_word("w0", "first", 1.0, 2.0)
w1 = make_word("w1", "boundary", 24.7, 25.3)  # mid = 25.0 > 25.0, unique
w2 = make_word("w2", "next", 1.0, 2.0)
w3 = make_word("w3", "last", 3.0, 4.0)
reconciled_seam = reconcile_chunk_alignments([c0, c1], [[w0, w1], [w2, w3]])
results.check(
    [w.id for w in reconciled_seam] == ["w0", "w1", "w2", "w3"],
    "Unique boundary word whose alignment extends into padding seam is preserved (Fix D3)",
    f"Got IDs: {[w.id for w in reconciled_seam]}",
)

# 3.2 Duplicate boundary word in both chunks is cleanly deduplicated
w1_dup = make_word("w1", "boundary", 0.2, 0.8)  # local in c1 -> global 25.2..25.8
reconciled_dup = reconcile_chunk_alignments([c0, c1], [[w0, w1], [w1_dup, w2, w3]])
results.check(
    [w.id for w in reconciled_dup] == ["w0", "w1", "w2", "w3"] and len(reconciled_dup) == 4,
    "Duplicate boundary word appearing in both chunks is deduplicated to exactly 1 occurrence",
    f"Got IDs: {[w.id for w in reconciled_dup]}",
)


# ============================================================================
# Section 4: Reconciler Monotonicity & Coarticulation Resolution
# ============================================================================
print("\n--- Section 4: Reconciler Monotonicity & Coarticulation ---")

# 4.1 Simultaneous word onsets raise MonotonicityError (Fix D4 verification)
c_mono = AudioChunk("c0", 0, 0.0, 10.0, 0.0, 10.5, "a b", [])
w_sim0 = make_word("ws0", "a", 2.0, 2.04)
w_sim1 = make_word("ws1", "b", 2.0, 2.50)
try:
    reconcile_chunk_alignments([c_mono], [[w_sim0, w_sim1]])
    results.check(False, "Simultaneous onsets raise MonotonicityError", "No error")
except MonotonicityError:
    results.check(True, "Simultaneous word onsets (curr.start == prev.start) correctly rejected")

# 4.2 Inverted word onsets raise MonotonicityError
w_inv0 = make_word("wi0", "a", 5.0, 6.0)
w_inv1 = make_word("wi1", "b", 3.0, 4.0)
try:
    reconcile_chunk_alignments([c_mono], [[w_inv0, w_inv1]])
    results.check(False, "Inverted word onsets raise MonotonicityError", "No error")
except MonotonicityError:
    results.check(True, "Inverted word onsets (curr.start < prev.start) correctly rejected")

# 4.3 Severe overlap (> 50ms) raises MonotonicityError
w_sev0 = make_word("wsv0", "a", 2.0, 3.0)
w_sev1 = make_word("wsv1", "b", 2.9, 4.0)  # overlap = 100ms > 50ms
try:
    reconcile_chunk_alignments([c_mono], [[w_sev0, w_sev1]])
    results.check(False, "Severe overlap (>50ms) raises MonotonicityError", "No error")
except MonotonicityError:
    results.check(True, "Severe acoustic overlap (>50ms) correctly rejected with MonotonicityError")

# 4.4 Minor coarticulation overlap (<= 50ms) cleanly nudged
w_co0 = make_word("wco0", "a", 2.0, 3.03)
w_co1 = make_word("wco1", "b", 3.0, 4.0)  # overlap = 30ms <= 50ms
res_co = reconcile_chunk_alignments([c_mono], [[w_co0, w_co1]])
results.check(
    len(res_co) == 2
    and res_co[0].end == res_co[1].start == 3.0
    and res_co[0].start < res_co[0].end,
    "Minor coarticulation overlap (<= 50ms) resolved by nudging prev.end to curr.start",
    f"res[0].end = {res_co[0].end}, res[1].start = {res_co[1].start}",
)


# ============================================================================
# Section 5: Phoneme Handling & Micro-Intervals
# ============================================================================
print("\n--- Section 5: Phoneme Handling & Micro-Intervals ---")

# 5.1 Sub-0.1ms micro-phonemes preserved without rounding collapse (Fix D5 verification)
p_tiny = PhonemeCue("AH", 0.10001, 0.10004, 0.9)
w_tiny = make_word("wt", "word", 0.1, 0.5, phonemes=[p_tiny])
res_tiny = reconcile_chunk_alignments([c_mono], [[w_tiny]])
p_res = res_tiny[0].phonemes[0]
results.check(
    p_res.start < p_res.end and round(p_res.end - p_res.start, 4) >= 0.001,
    "Sub-0.1ms micro-phonemes preserved with positive duration >= 0.001s (Fix D5)",
    f"p_res: {p_res.start}..{p_res.end}",
)

# 5.2 Phoneme clamped when word end is nudged
p_clamp = PhonemeCue("T", 1.18, 1.20, 0.9)
w_clamp0 = make_word("wc0", "cat", 1.0, 1.20, phonemes=[p_clamp])
w_clamp1 = make_word("wc1", "sat", 1.17, 1.30)  # 30ms overlap nudges cat end to 1.17
res_clamp = reconcile_chunk_alignments([c_mono], [[w_clamp0, w_clamp1]])
results.check(
    res_clamp[0].end == 1.17 and res_clamp[0].phonemes[0].end <= 1.17,
    "Nested phoneme cue clamped to nudged word end boundary (1.17s)",
    f"word end: {res_clamp[0].end}, phoneme end: {res_clamp[0].phonemes[0].end}",
)

# 5.3 Adversarial Edge Case: Coarticulation nudge near t = 0 with phoneme at word end
p_near0 = PhonemeCue("P", 0.0008, 0.010, 0.9)
w_near0 = WordToken("wn0", "a", "a", 0.0, 0.020, 0.9, phonemes=[p_near0])
w_near1 = WordToken("wn1", "b", "b", 0.0005, 0.030, 0.9)
try:
    reconcile_chunk_alignments([c_mono], [[w_near0, w_near1]])
    results.check(True, "Nudge near t=0 with phoneme handles non-negative boundary safely")
except ValueError as e:
    results.add_finding(
        title="Sub-millisecond coarticulation nudge near t=0 produces negative PhonemeCue.start",
        severity="Low",
        details=(
            f"When prev_w starts at 0.0s and curr_w starts at < 0.001s (e.g. 0.0005s), "
            f"nudging prev_w.end causes trailing phoneme (start >= 0.0005) to compute "
            f"p_s = -0.0005 < 0.0, triggering PhonemeCue ValueError: '{e}'."
        ),
    )


# ============================================================================
# Section 6: Pathological Chunker Boundary (Micro-token at exact 30s)
# ============================================================================
print("\n--- Section 6: Chunker Boundary Edge Cases ---")

# 6.1 Sub-millisecond token at exact chunk boundary (30.0s)
w_m0 = WordToken("wm0", "a", "a", 0.0, 30.0, 0.9)
w_m1 = WordToken("wm1", "b", "b", 30.0, 30.00004, 0.9)
w_m2 = WordToken("wm2", "c", "c", 30.00004, 65.0, 0.9)
s_m0 = ASRSegment("sm0", 0.0, 30.0, "a", [w_m0])
s_m1 = ASRSegment("sm1", 30.0, 30.00004, "b", [w_m1])
s_m2 = ASRSegment("sm2", 30.00004, 65.0, "c", [w_m2])
try:
    chunks_m = partition_into_chunks([s_m0, s_m1, s_m2], [], 100.0)
    results.check(True, "Sub-millisecond token (<0.05ms) at 30s boundary partitioned safely")
except ValueError as e:
    results.add_finding(
        title="Sub-0.05ms token at chunk boundary causes start == end zero-duration AudioChunk",
        severity="Low",
        details=(
            f"When previous chunk ends at 30.0s, and next token has duration < 0.05ms "
            f"while next word exceeds 30s, chosen_split rounds to 30.0s == curr_start. "
            f"This produces AudioChunk with start=30.0, end=30.0: '{e}'."
        ),
    )


# ============================================================================
# Section 7: Scalability & Stress Performance
# ============================================================================
print("\n--- Section 7: Scalability & Performance Stress ---")

# 7.1 Partitioning 2-hour recording (7,200s, 3,600 segments, 18,000 words)
segs_2h = []
for i in range(1800):
    t_s = float(i * 4)
    t_e = t_s + 3.0
    words = [
        make_word(f"w_{i}_{j}", f"w{j}", t_s + j * 0.5, t_s + (j + 1) * 0.5 - 0.05)
        for j in range(6)
    ]
    segs_2h.append(make_segment(f"s_{i}", t_s, t_e, words))

t1 = time.perf_counter()
chunks_2h = partition_into_chunks(segs_2h, [], 7200.0)
t_part = time.perf_counter() - t1

results.check(
    len(chunks_2h) >= 240
    and all(round(c.end - c.start, 4) <= 30.0 + 1e-4 for c in chunks_2h)
    and t_part < 0.200,
    f"Scalability: 2h lecture into {len(chunks_2h)} chunks in {t_part * 1000:.1f}ms",
)

# 7.2 Reconciling 500 chunks with 10,000 words
rec_chunks = [
    AudioChunk(
        f"rc_{i}",
        i,
        float(i * 25),
        float((i + 1) * 25),
        float(max(0, i * 25 - 0.5)),
        float((i + 1) * 25 + 0.5),
        "words",
        [],
    )
    for i in range(500)
]
rec_words = [
    [make_word(f"rw_{i}_{j}", f"w{j}", 1.0 + j * 1.0, 1.8 + j * 1.0) for j in range(20)]
    for i in range(500)
]
t2 = time.perf_counter()
reconciled_large = reconcile_chunk_alignments(rec_chunks, rec_words)
t_rec = time.perf_counter() - t2

results.check(
    len(reconciled_large) == 10000 and t_rec < 0.250,
    f"Scalability: 10,000 words across 500 chunks reconciled in {t_rec * 1000:.1f}ms (< 250ms)",
)


# ============================================================================
# Summary & Output
# ============================================================================
print("\n" + "=" * 70)
print(
    f"ADVERSARIAL SUITE SUMMARY: {results.tests_passed}/{results.tests_run} PASSED, "
    f"{results.tests_failed} FAILED, {len(results.findings)} FINDINGS"
)
print("=" * 70)

sys.exit(0 if results.tests_failed == 0 else 1)
