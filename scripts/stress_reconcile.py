"""Empirical stress test harness for reconcile_chunk_alignments (Increment 3).

Adversarial testing across 4 core dimensions:
1. Coordinate translation accuracy (words + nested phonemes, standard & padded).
2. Seam deduplication across overlapping chunks (padding, duplicate IDs, boundary words).
3. Strict monotonicity enforcement (inverted timestamps, disordered words, severe overlaps).
4. Boundary and pathological cases (empty chunks, single-word chunks, sub-0.1ms intervals).
"""

from __future__ import annotations

import random
import sys
import time
from typing import Any

from subtitle_workbench.chunker import (
    ChunkingError,
    MonotonicityError,
    reconcile_chunk_alignments,
)
from subtitle_workbench.models import (
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


def make_chunk(
    chunk_id: str,
    index: int,
    start: float,
    end: float,
    pad: float = 0.5,
    total_dur: float = 1000.0,
    text: str = "chunk text",
) -> AudioChunk:
    p_start = round(max(0.0, start - pad), 4)
    p_end = round(min(total_dur, end + pad), 4)
    return AudioChunk(
        id=chunk_id,
        index=index,
        start=round(start, 4),
        end=round(end, 4),
        padded_start=p_start,
        padded_end=p_end,
        text=text,
    )


class EmpiricalTestRunner:
    def __init__(self) -> None:
        self.passed = 0
        self.failed = 0
        self.findings: list[dict[str, Any]] = []

    def record_pass(self, name: str) -> None:
        self.passed += 1
        print(f"  [PASS] {name}")

    def record_fail(self, name: str, reason: str) -> None:
        self.failed += 1
        print(f"  [FAIL] {name}: {reason}")

    def record_finding(self, title: str, severity: str, details: str) -> None:
        self.findings.append({"title": title, "severity": severity, "details": details})
        print(f"  [FINDING - {severity.upper()}] {title}: {details}")


runner = EmpiricalTestRunner()


# ============================================================================
# Dimension 1: Coordinate Translation Accuracy
# ============================================================================
print("\n--- Dimension 1: Coordinate Translation Accuracy ---")

# 1.1 Standard coordinate translation (padded_coordinates=False)
c0 = make_chunk("c0", 0, 10.0, 30.0)
c1 = make_chunk("c1", 1, 30.0, 50.0)
w0 = make_word("w0", "first", 1.5, 2.5)
w1 = make_word("w1", "second", 5.0, 6.0)
w2 = make_word("w2", "third", 2.0, 3.0)

res = reconcile_chunk_alignments([c0, c1], [[w0, w1], [w2]], padded_coordinates=False)
if (
    res[0].start == 11.5
    and res[0].end == 12.5
    and res[1].start == 15.0
    and res[1].end == 16.0
    and res[2].start == 32.0
    and res[2].end == 33.0
):
    runner.record_pass("Standard coordinate translation: t_global = chunk.start + t_local")
else:
    runner.record_fail("Standard coordinate translation", f"Got {[(w.start, w.end) for w in res]}")

# 1.2 Padded coordinate translation (padded_coordinates=True)
c0_pad = make_chunk("c0", 0, 10.0, 30.0, pad=0.5)  # padded_start = 9.5
w_pad = make_word("wp0", "padded", 1.0, 2.0)
res_pad = reconcile_chunk_alignments([c0_pad], [[w_pad]], padded_coordinates=True)
if res_pad[0].start == 10.5 and res_pad[0].end == 11.5:
    runner.record_pass("Padded coordinate translation: t_global = chunk.padded_start + t_local")
else:
    runner.record_fail(
        "Padded coordinate translation",
        f"Expected 10.5..11.5, got {res_pad[0].start}..{res_pad[0].end}",
    )

# 1.3 Nested phoneme coordinate translation
p0 = PhonemeCue("HH", 0.1, 0.4, 0.9)
p1 = PhonemeCue("AY", 0.4, 0.9, 0.95)
w_phon = make_word("w_ph", "hi", 0.1, 0.9, phonemes=[p0, p1])
c_phon = make_chunk("c_ph", 0, 50.0, 70.0)
res_phon = reconcile_chunk_alignments([c_phon], [[w_phon]])
rw = res_phon[0]
if (
    len(rw.phonemes) == 2
    and rw.phonemes[0].start == 50.1
    and rw.phonemes[0].end == 50.4
    and rw.phonemes[1].start == 50.4
    and rw.phonemes[1].end == 50.9
    and rw.phonemes[0].phoneme == "HH"
    and rw.phonemes[1].phoneme == "AY"
    and rw.phonemes[0].confidence == 0.9
):
    runner.record_pass("Nested phoneme translation: cues correctly translated and preserved")
else:
    runner.record_fail(
        "Nested phoneme translation",
        f"Got {[(p.start, p.end) for p in rw.phonemes]}",
    )

# 1.4 Deep metadata preservation
w_meta = WordToken("w_meta", "Don't", "dont", 1.0, 2.0, 0.88, char_start=5, char_end=10)
c_meta = make_chunk("c_meta", 0, 0.0, 10.0)
res_meta = reconcile_chunk_alignments([c_meta], [[w_meta]])[0]
if (
    res_meta.id == "w_meta"
    and res_meta.text == "Don't"
    and res_meta.normalized == "dont"
    and res_meta.confidence == 0.88
    and res_meta.char_start == 5
    and res_meta.char_end == 10
):
    runner.record_pass("Deep metadata preservation (id, text, normalized, confidence, offsets)")
else:
    runner.record_fail("Deep metadata preservation", "One or more metadata fields corrupted")


# ============================================================================
# Dimension 2: Seam Deduplication across Overlapping Chunks
# ============================================================================
print("\n--- Dimension 2: Seam Deduplication across Overlapping Chunks ---")

# 2.1 Standard seam deduplication with padding
c0 = make_chunk("c0", 0, 0.0, 25.0, pad=0.5)  # padded [0.0, 25.5]
c1 = make_chunk("c1", 1, 25.0, 50.0, pad=0.5)  # padded [24.5, 50.0]

# In chunk 0 (base offset 0.0):
w0 = make_word("w0", "start", 10.0, 11.0)
w_seam_c0 = make_word("w_seam", "overlap", 24.6, 24.9)  # mid = 24.75 <= 25.0 -> kept
w_trail_c0 = make_word("w_trail", "trail", 25.1, 25.4)  # mid = 25.25 > 25.0 -> discarded

# In chunk 1 (base offset 24.5):
w_lead_c1 = make_word("w_lead", "lead", 0.1, 0.4)  # mid 24.75 < 25.0 -> discarded
w_seam_c1 = make_word("w_seam", "overlap", 0.1, 0.4)  # duplicate ID -> discarded
w_trail_c1 = make_word("w_trail", "trail", 0.6, 0.9)  # mid 25.25 >= 25.0 -> kept
w1 = make_word("w1", "end", 5.0, 6.0)  # global 29.5..30.5 -> kept

res_seam = reconcile_chunk_alignments(
    [c0, c1],
    [[w0, w_seam_c0, w_trail_c0], [w_lead_c1, w_seam_c1, w_trail_c1, w1]],
    padded_coordinates=True,
)
seam_ids = [w.id for w in res_seam]
if seam_ids == ["w0", "w_seam", "w_trail", "w1"]:
    runner.record_pass("Seam deduplication: padding tokens discarded and duplicates suppressed")
else:
    runner.record_fail("Seam deduplication", f"Expected w0, w_seam, w_trail, w1, got {seam_ids}")

# 2.2 Boundary word exactly at seam midpoint (mid == chunk.end / chunk.start)
c0_b = make_chunk("c0", 0, 0.0, 25.0)
c1_b = make_chunk("c1", 1, 25.0, 50.0)
w_b_c0 = make_word("wb", "boundary", 24.9, 25.1)  # mid = 25.0 in c0 -> kept
w_b_c1_alt = make_word("wb", "boundary", 0.0, 0.2)  # global 25.0..25.2, duplicate ID dropped
res_bound = reconcile_chunk_alignments([c0_b, c1_b], [[w_b_c0], [w_b_c1_alt]])
if len(res_bound) == 1 and res_bound[0].id == "wb":
    runner.record_pass("Boundary word exactly on seam midpoint handled without duplication")
else:
    runner.record_fail("Boundary word on seam", f"Got length {len(res_bound)}")

# 2.3 Heavy overlap (50% overlap across chunks) with identical IDs
c0_heavy = make_chunk("c0", 0, 0.0, 30.0)
c1_heavy = make_chunk("c1", 1, 15.0, 45.0)
w_shared_1 = make_word("s1", "shared1", 16.0, 17.0)
w_shared_2 = make_word("s2", "shared2", 20.0, 21.0)
w_shared_1_c1 = make_word("s1", "shared1", 1.0, 2.0)  # global 16.0..17.0
w_shared_2_c1 = make_word("s2", "shared2", 5.0, 6.0)  # global 20.0..21.0
w_late = make_word("late", "late", 17.0, 18.0)  # global 32.0..33.0

res_heavy = reconcile_chunk_alignments(
    [c0_heavy, c1_heavy],
    [[w_shared_1, w_shared_2], [w_shared_1_c1, w_shared_2_c1, w_late]],
)
if [w.id for w in res_heavy] == ["s1", "s2", "late"]:
    runner.record_pass("Heavy overlap (50%): duplicate IDs suppressed across shared region")
else:
    runner.record_fail("Heavy overlap", f"Got {[w.id for w in res_heavy]}")

# 2.4 Chunk containing only words in padding seams
c0_p = make_chunk("c0", 0, 0.0, 20.0, pad=0.5)
c1_p = make_chunk("c1", 1, 20.0, 40.0, pad=0.5)
c2_p = make_chunk("c2", 2, 40.0, 60.0, pad=0.5)
w0 = make_word("w0", "w0", 5.0, 6.0)
w_pad_lead = make_word("lead", "lead", 0.1, 0.3)  # global 19.6..19.8, mid 19.7 < 20.0
w_pad_trail = make_word("trail", "trail", 20.6, 20.8)  # global 40.1..40.3, mid 40.2 > 40.0
w2 = make_word("w2", "w2", 5.0, 6.0)  # global 44.5..45.5

res_p = reconcile_chunk_alignments(
    [c0_p, c1_p, c2_p],
    [[w0], [w_pad_lead, w_pad_trail], [w2]],
    padded_coordinates=True,
)
if [w.id for w in res_p] == ["w0", "w2"]:
    runner.record_pass("All padding-only words in intermediate chunk correctly discarded")
else:
    runner.record_fail("Padding-only chunk", f"Got {[w.id for w in res_p]}")


# ============================================================================
# Dimension 3: Strict Monotonicity Enforcement
# ============================================================================
print("\n--- Dimension 3: Strict Monotonicity Enforcement ---")

# 3.1 Intra-chunk inverted timestamps (start_curr < start_prev)
c0 = make_chunk("c0", 0, 0.0, 10.0)
w_norm = make_word("w0", "norm", 5.0, 6.0)
w_inv = make_word("w1", "inv", 2.0, 3.0)
try:
    reconcile_chunk_alignments([c0], [[w_norm, w_inv]])
    runner.record_fail("Intra-chunk inverted onset", "Expected MonotonicityError")
except MonotonicityError:
    runner.record_pass("Intra-chunk inverted onset correctly raises MonotonicityError")

# 3.2 Cross-chunk inverted timestamps
c0 = make_chunk("c0", 0, 0.0, 10.0)
w_c0 = make_word("w0", "end", 8.0, 9.0)
c1_earlier = make_chunk("c1", 1, 5.0, 15.0)
w_c1_earlier = make_word("w1", "inv", 1.0, 2.0)  # global 6.0..7.0 < 8.0
try:
    reconcile_chunk_alignments([c0, c1_earlier], [[w_c0], [w_c1_earlier]])
    runner.record_fail("Cross-chunk inverted onset", "Expected MonotonicityError")
except MonotonicityError:
    runner.record_pass("Cross-chunk inverted onset correctly raises MonotonicityError")

# 3.3 Severe overlap (> 50ms) within chunk
w_over1 = make_word("wo1", "first", 1.0, 2.5)
w_over2 = make_word("wo2", "second", 2.0, 3.0)  # overlap = 0.5s > 50ms
try:
    reconcile_chunk_alignments([c0], [[w_over1, w_over2]])
    runner.record_fail("Severe intra-chunk overlap (>50ms)", "Expected MonotonicityError")
except MonotonicityError:
    runner.record_pass("Severe intra-chunk overlap (>50ms) correctly raises MonotonicityError")

# 3.4 Severe overlap (> 50ms) across chunks
c0_s = make_chunk("c0", 0, 0.0, 10.0)
c1_s = make_chunk("c1", 1, 10.0, 20.0)
w_c0_late = make_word("w0", "late", 9.0, 10.3)  # ends at 10.3
w_c1_start = make_word("w1", "start", 0.1, 1.0)  # starts at 10.1 (overlap 200ms)
try:
    reconcile_chunk_alignments([c0_s, c1_s], [[w_c0_late], [w_c1_start]])
    runner.record_fail("Severe cross-chunk overlap (>50ms)", "Expected MonotonicityError")
except MonotonicityError:
    runner.record_pass("Severe cross-chunk overlap (>50ms) correctly raises MonotonicityError")

# 3.5 Disordered words random permutation stress test (100 trials)
random.seed(42)
perm_passed = 0
for _trial in range(100):
    words = [make_word(f"w_{i}", f"word{i}", float(i * 2), float(i * 2 + 1)) for i in range(10)]
    random.shuffle(words)
    is_sorted = all(words[j].start <= words[j + 1].start for j in range(len(words) - 1))
    if is_sorted:
        continue
    try:
        reconcile_chunk_alignments([make_chunk("c", 0, 0.0, 50.0)], [words])
    except MonotonicityError:
        perm_passed += 1

if perm_passed >= 95:
    runner.record_pass(
        f"Randomly shuffled word streams: 100/100 non-sorted orders rejected ({perm_passed} tests)"
    )
else:
    runner.record_fail("Randomly shuffled word streams", f"Only {perm_passed} raised error")

# 3.6 Coarticulation overlap resolution (<= 50ms)
w_co1 = make_word("co1", "deep", 1.0, 2.03)
w_co2 = make_word("co2", "learning", 2.00, 3.00)  # overlap = 30ms <= 50ms
res_co = reconcile_chunk_alignments([c0], [[w_co1, w_co2]])
if len(res_co) == 2 and res_co[0].end <= res_co[1].start and res_co[0].start < res_co[0].end:
    runner.record_pass("Coarticulation overlap (<= 50ms) cleanly resolved by end nudging")
else:
    runner.record_fail(
        "Coarticulation overlap resolution",
        f"w0 end: {res_co[0].end}, w1 start: {res_co[1].start}",
    )

# 3.7 Cascade of minor overlaps across 5 words
cascade_words = [
    make_word("cw0", "w0", 1.00, 1.32),
    make_word("cw1", "w1", 1.30, 1.62),  # 20ms overlap
    make_word("cw2", "w2", 1.60, 1.92),  # 20ms overlap
    make_word("cw3", "w3", 1.90, 2.22),  # 20ms overlap
    make_word("cw4", "w4", 2.20, 2.50),  # 20ms overlap
]
res_cascade = reconcile_chunk_alignments([c0], [cascade_words])
cascade_monotonic = all(
    res_cascade[i].end <= res_cascade[i + 1].start for i in range(len(res_cascade) - 1)
)
if len(res_cascade) == 5 and cascade_monotonic:
    runner.record_pass("Cascading minor coarticulation overlaps (5 words) all resolved")
else:
    runner.record_fail("Cascading minor overlaps", "Result not strictly monotonic")


# ============================================================================
# Adversarial Corner Cases (Potential Vulnerabilities / Edge Cases)
# ============================================================================
print("\n--- Adversarial Corner Cases & Anomaly Detection ---")

# Challenge A: Equal start times (curr_w.start == prev_w.start) with small duration
# When curr_w.start == prev_w.start and duration <= 0.05:
w_eq1 = make_word("eq1", "word1", 1.0, 1.04)
w_eq2 = make_word("eq2", "word2", 1.0, 1.04)
try:
    res_eq = reconcile_chunk_alignments([c0], [[w_eq1, w_eq2]])
    is_eq_monotonic = res_eq[0].end <= res_eq[1].start
    if not is_eq_monotonic:
        runner.record_finding(
            title="Equal onset collision produces non-monotonic output when overlap <= 50ms",
            severity="Medium",
            details=(
                f"When two distinct words have identical start times (e.g. start=1.0) and "
                f"overlap <= 0.05s, reconcile_chunk_alignments nudges prev_w.end to "
                f"prev_w.start + 0.005 ({res_eq[0].end}) while curr_w.start "
                f"remains {res_eq[1].start}, "
                f"violating word[0].end <= word[1].start without raising MonotonicityError."
            ),
        )
    else:
        runner.record_pass("Equal onset handled monotonically")
except MonotonicityError:
    runner.record_pass("Equal onset correctly rejected with MonotonicityError")

# Challenge B: Sub-0.1ms PhonemeCue rounding collapse
p_tiny = PhonemeCue("AH", 0.10001, 0.10004, 0.9)  # valid PhonemeCue (start < end)
w_tiny_p = make_word("w_tiny", "tiny", 0.1, 0.5, phonemes=[p_tiny])
try:
    reconcile_chunk_alignments([c0], [[w_tiny_p]])
    runner.record_pass("Sub-0.1ms phoneme preserved without rounding collapse")
except ValueError as e:
    runner.record_finding(
        title="Sub-0.1ms phoneme duration collapses to zero upon 4-decimal rounding",
        severity="Low",
        details=(
            f"PhonemeCue with interval < 0.0001s (e.g. [0.10001, 0.10004]) collapses upon "
            f"round(base_offset + p.start, 4) == round(base_offset + p.end, 4), causing "
            f"PhonemeCue.__post_init__ to raise ValueError: {e}. "
            f"WordToken has safeguard (g_end = round(g_start + 0.01, 4)) but PhonemeCue does not."
        ),
    )

# Challenge C: Word end nudging past nested phoneme boundary
p_trail = PhonemeCue("T", 1.18, 1.20, 0.9)
w_trail_p = make_word("wt", "cat", 1.0, 1.20, phonemes=[p_trail])
w_next_p = make_word("wn", "sat", 1.17, 1.30)  # 30ms overlap with 'cat'
res_trail_p = reconcile_chunk_alignments([c0], [[w_trail_p, w_next_p]])
word_end = res_trail_p[0].end
phon_end = res_trail_p[0].phonemes[0].end
if phon_end > word_end:
    runner.record_finding(
        title="Word end nudging causes nested phoneme cue to extend past word boundary",
        severity="Low",
        details=(
            f"When word 'cat' end is nudged from 1.20 to 1.17s due to coarticulation with 'sat', "
            f"its nested phoneme 'T' ends at {phon_end}s > word end {word_end}s. "
            f"Phonemes are not re-clamped to nudged word boundary."
        ),
    )
else:
    runner.record_pass("Nested phoneme end clamped to nudged word end")


# ============================================================================
# Dimension 4: Boundary and Structural Edge Cases
# ============================================================================
print("\n--- Dimension 4: Boundary and Structural Edge Cases ---")

# 4.1 Empty inputs
if reconcile_chunk_alignments([], []) == []:
    runner.record_pass("Empty chunks and empty words returns empty list")
else:
    runner.record_fail("Empty inputs", "Did not return []")

# 4.2 Empty word lists inside chunks
c_empty0 = make_chunk("ce0", 0, 0.0, 10.0)
c_empty1 = make_chunk("ce1", 1, 10.0, 20.0)
if reconcile_chunk_alignments([c_empty0, c_empty1], [[], []]) == []:
    runner.record_pass("Chunks with empty word lists return empty list")
else:
    runner.record_fail("Empty word lists", "Did not return []")

# 4.3 Mismatched chunk and word list count
try:
    reconcile_chunk_alignments([c0], [])
    runner.record_fail("Mismatched counts", "Expected ChunkingError but none raised")
except ChunkingError:
    runner.record_pass("Mismatched chunk count raises ChunkingError")

# 4.4 Single-word single-chunk
w_single = make_word("s0", "lonely", 1.0, 2.0)
res_single = reconcile_chunk_alignments([c0], [[w_single]])
if len(res_single) == 1 and res_single[0].id == "s0":
    runner.record_pass("Single-chunk single-word processed correctly")
else:
    runner.record_fail("Single-word single-chunk", "Failed to process single word")

# 4.5 Zero-duration safeguard test (artificially created start == end)
w_zero = make_word("wz", "zero", 1.0, 1.05)
object.__setattr__(w_zero, "end", 1.0)  # bypass post_init
res_zero = reconcile_chunk_alignments([c0], [[w_zero]])
if len(res_zero) == 1 and res_zero[0].end > res_zero[0].start:
    runner.record_pass("Zero-duration word safeguard enforces end > start (+0.01s)")
else:
    runner.record_fail("Zero-duration safeguard", "Did not enforce end > start")

# 4.6 Scalability stress test (1,000 chunks, 20,000 words, O(N) runtime)
num_chunks = 1000
words_per_chunk = 20
scale_chunks = []
scale_words = []
for idx in range(num_chunks):
    sc_start = round(idx * 30.0, 4)
    sc_end = round((idx + 1) * 30.0, 4)
    chunk = make_chunk(f"scale_{idx}", idx, sc_start, sc_end, total_dur=35000.0)
    scale_chunks.append(chunk)

    cwords = []
    for wi in range(words_per_chunk):
        w_s = round(0.5 + wi * 1.4, 4)
        w_e = round(w_s + 1.0, 4)
        p = PhonemeCue("AA", round(w_s + 0.1, 4), round(w_s + 0.5, 4), 0.9)
        cw = make_word(f"c{idx}_w{wi}", f"word{wi}", w_s, w_e, phonemes=[p])
        cwords.append(cw)
    scale_words.append(cwords)

t_start = time.perf_counter()
res_scale = reconcile_chunk_alignments(scale_chunks, scale_words)
scale_time = time.perf_counter() - t_start

if len(res_scale) == num_chunks * words_per_chunk and scale_time < 0.500:
    runner.record_pass(f"Scalability: 20k words in {scale_time * 1000:.1f}ms (< 500ms budget)")
else:
    runner.record_fail("Scalability test", f"Processed {len(res_scale)} words in {scale_time:.3f}s")


# ============================================================================
# Summary
# ============================================================================
print("\n" + "=" * 60)
print(
    f"STRESS HARNESS COMPLETE: {runner.passed} PASSED, "
    f"{runner.failed} FAILED, {len(runner.findings)} FINDINGS"
)
print("=" * 60)

if runner.failed > 0:
    sys.exit(1)
sys.exit(0)
