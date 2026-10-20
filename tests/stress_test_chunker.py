"""Empirical stress-test harness for partition_into_chunks.

Stress-tests:
1. Long lectures (60+ minutes) with dense silences.
2. Long lectures (60+ minutes) with zero silences (continuous uninterrupted speech).
3. Long lectures (60+ minutes) with sparse silences and long pauses (>30s silence intervals).
4. Leading silence (>30s silence before first word).
5. Micro-segments (sub-second segments, 50ms-100ms) with and without gaps.
6. Exact 30.0s boundary conditions (segments ending at exact multiples of 30.0s).
7. Non-standard silence intervals (overlapping, zero-length, adjacent, inverted,
   negative, out of bounds).
8. Strict invariant verification:
   - 0.0 <= padded_start <= start < end <= padded_end <= total_duration
   - end - start <= max_chunk_duration (30.0s)
   - padded_start == 0.0 if start == 0.0
   - padded_end == total_duration if end == total_duration
9. Randomized property-based stress tests with pseudo-random seeds.
"""

from __future__ import annotations

import random
import sys
import time
from typing import Any

from subtitle_workbench.chunker import partition_into_chunks
from subtitle_workbench.models import (
    ASRSegment,
    AudioChunk,
    ChunkConfig,
    WordToken,
)


def make_word(
    word_id: str,
    text: str,
    start: float,
    end: float,
    confidence: float = 0.95,
) -> WordToken:
    """Helper to construct a valid WordToken."""
    return WordToken(
        id=word_id,
        text=text,
        normalized=text.lower().strip(".,!?"),
        start=round(start, 4),
        end=round(end, 4),
        confidence=confidence,
    )


def make_segment(
    seg_id: str,
    start: float,
    end: float,
    words: list[WordToken],
) -> ASRSegment:
    """Helper to construct a valid ASRSegment."""
    text = " ".join(w.text for w in words)
    return ASRSegment(
        id=seg_id,
        start=round(start, 4),
        end=round(end, 4),
        text=text,
        words=words,
    )


def check_chunk_invariants(
    chunk: AudioChunk, total_duration: float, config: ChunkConfig
) -> list[str]:
    """Check invariants and return a list of error descriptions (empty if all pass)."""
    errors: list[str] = []
    dur = round(chunk.end - chunk.start, 4)
    max_dur = config.max_chunk_duration

    # Invariant 1: duration bound
    if dur > max_dur + 1e-4:
        errors.append(
            f"Duration bound violated: chunk {chunk.id} [{chunk.start:.4f}, {chunk.end:.4f}] "
            f"duration={dur:.4f}s exceeds max_chunk_duration={max_dur:.4f}s"
        )

    # Invariant 2: relational ordering
    if not (
        0.0 <= chunk.padded_start <= chunk.start < chunk.end <= chunk.padded_end <= total_duration
    ):
        errors.append(
            f"Relational invariant violated: 0.0 <= {chunk.padded_start:.4f} <= {chunk.start:.4f} "
            f"< {chunk.end:.4f} <= {chunk.padded_end:.4f} <= {total_duration:.4f}"
        )

    # Invariant 3: boundary clamping
    if chunk.start == 0.0 and chunk.padded_start != 0.0:
        errors.append(
            f"Clamping violation: start is 0.0 but padded_start is {chunk.padded_start:.4f}"
        )
    if chunk.end == total_duration and chunk.padded_end != total_duration:
        errors.append(
            f"Clamping violation: end is {total_duration:.4f} but "
            f"padded_end is {chunk.padded_end:.4f}"
        )

    return errors


# ============================================================================
# Empirical Stress Tests
# ============================================================================


def test_suite_dense_silences_60min() -> dict[str, Any]:
    """1. 60+ minute lecture with dense silences (every 2 seconds)."""
    total_dur = 3600.0
    segs: list[ASRSegment] = []
    sils: list[tuple[float, float]] = []

    for i in range(1800):
        t_start = i * 2.0
        t_speech_end = t_start + 1.2
        t_sil_end = t_start + 2.0
        w = make_word(f"w_{i}", "lecture", t_start, t_speech_end)
        segs.append(make_segment(f"s_{i}", t_start, t_speech_end, [w]))
        sils.append((round(t_speech_end, 4), round(t_sil_end, 4)))

    cfg = ChunkConfig()
    t0 = time.perf_counter()
    chunks = partition_into_chunks(segs, sils, total_dur, cfg)
    elapsed = time.perf_counter() - t0

    all_errors: list[str] = []
    for c in chunks:
        all_errors.extend(check_chunk_invariants(c, total_dur, cfg))

    return {
        "name": "60m_dense_silences",
        "chunks_count": len(chunks),
        "elapsed_sec": elapsed,
        "errors": all_errors,
        "passed": len(all_errors) == 0,
    }


def test_suite_zero_silences_60min() -> dict[str, Any]:
    """2. 60+ minute lecture with zero silences (continuous speech)."""
    total_dur = 3600.0
    segs: list[ASRSegment] = []

    # 180 segments of 20 seconds each, contiguous
    for i in range(180):
        t_start = i * 20.0
        t_end = (i + 1) * 20.0
        words: list[WordToken] = []
        for j in range(20):
            w_start = t_start + j * 1.0
            w_end = w_start + 0.95
            words.append(make_word(f"w_{i}_{j}", "word", w_start, w_end))
        segs.append(make_segment(f"s_{i}", t_start, t_end, words))

    cfg = ChunkConfig()
    t0 = time.perf_counter()
    chunks = partition_into_chunks(segs, [], total_dur, cfg)
    elapsed = time.perf_counter() - t0

    all_errors: list[str] = []
    for c in chunks:
        all_errors.extend(check_chunk_invariants(c, total_dur, cfg))

    return {
        "name": "60m_zero_silences",
        "chunks_count": len(chunks),
        "elapsed_sec": elapsed,
        "errors": all_errors,
        "passed": len(all_errors) == 0,
    }


def test_suite_sparse_silences_with_long_pauses_60min() -> dict[str, Any]:
    """3. 60+ minute lecture with sparse speech and long pauses (>30s pauses)."""
    total_dur = 3600.0
    segs: list[ASRSegment] = []
    sils: list[tuple[float, float]] = []

    # 30 speech blocks separated by 110s pauses
    for i in range(30):
        t_start = i * 120.0
        t_end = t_start + 10.0
        words = [
            make_word(f"w_{i}_{j}", f"tok{j}", t_start + j * 2.0, t_start + (j + 1) * 2.0 - 0.1)
            for j in range(5)
        ]
        segs.append(make_segment(f"s_{i}", t_start, t_end, words))
        if i < 29:
            sils.append((t_end, (i + 1) * 120.0))

    cfg = ChunkConfig()
    t0 = time.perf_counter()
    chunks = partition_into_chunks(segs, sils, total_dur, cfg)
    elapsed = time.perf_counter() - t0

    all_errors: list[str] = []
    for c in chunks:
        all_errors.extend(check_chunk_invariants(c, total_dur, cfg))

    return {
        "name": "60m_sparse_silences_long_pauses",
        "chunks_count": len(chunks),
        "elapsed_sec": elapsed,
        "errors": all_errors,
        "passed": len(all_errors) == 0,
    }


def test_suite_leading_silence_gt_30s() -> dict[str, Any]:
    """4. Recording starting with >30s silence before first speech."""
    total_dur = 120.0
    # First word starts at 45.0s
    w0 = make_word("w0", "intro", 45.0, 48.0)
    w1 = make_word("w1", "lecture", 48.2, 51.0)
    seg = make_segment("s0", 45.0, 51.0, [w0, w1])

    cfg = ChunkConfig()
    t0 = time.perf_counter()
    chunks = partition_into_chunks([seg], [(0.0, 45.0)], total_dur, cfg)
    elapsed = time.perf_counter() - t0

    all_errors: list[str] = []
    for c in chunks:
        all_errors.extend(check_chunk_invariants(c, total_dur, cfg))

    return {
        "name": "leading_silence_gt_30s",
        "chunks_count": len(chunks),
        "elapsed_sec": elapsed,
        "errors": all_errors,
        "passed": len(all_errors) == 0,
    }


def test_suite_micro_segments() -> dict[str, Any]:
    """5. Micro-segments (50ms - 100ms) with small gaps."""
    total_dur = 120.0
    segs: list[ASRSegment] = []

    # 1000 micro-segments of 60ms each
    for i in range(1000):
        t_start = i * 0.1
        t_end = t_start + 0.06
        w = make_word(f"w_{i}", "m", t_start, t_end)
        segs.append(make_segment(f"s_{i}", t_start, t_end, [w]))

    cfg = ChunkConfig()
    t0 = time.perf_counter()
    chunks = partition_into_chunks(segs, [], total_dur, cfg)
    elapsed = time.perf_counter() - t0

    all_errors: list[str] = []
    for c in chunks:
        all_errors.extend(check_chunk_invariants(c, total_dur, cfg))

    return {
        "name": "micro_segments",
        "chunks_count": len(chunks),
        "elapsed_sec": elapsed,
        "errors": all_errors,
        "passed": len(all_errors) == 0,
    }


def test_suite_exact_30s_boundaries() -> dict[str, Any]:
    """6. Segments aligned exactly at 30.0s boundaries."""
    total_dur = 300.0  # 10 chunks of 30.0s
    segs: list[ASRSegment] = []

    for i in range(10):
        t_start = i * 30.0
        t_end = (i + 1) * 30.0
        w = make_word(f"w_{i}", "boundary", t_start + 1.0, t_end - 1.0)
        segs.append(make_segment(f"s_{i}", t_start, t_end, [w]))

    cfg = ChunkConfig()
    t0 = time.perf_counter()
    chunks = partition_into_chunks(segs, [], total_dur, cfg)
    elapsed = time.perf_counter() - t0

    all_errors: list[str] = []
    for c in chunks:
        all_errors.extend(check_chunk_invariants(c, total_dur, cfg))

    return {
        "name": "exact_30s_boundaries",
        "chunks_count": len(chunks),
        "elapsed_sec": elapsed,
        "errors": all_errors,
        "passed": len(all_errors) == 0,
    }


def test_suite_pathological_silences() -> dict[str, Any]:
    """7. Non-standard silence intervals: overlapping, zero-length, adjacent,
    inverted, negative, out of bounds.
    """
    total_dur = 100.0
    w0 = make_word("w0", "first", 5.0, 10.0)
    w1 = make_word("w1", "second", 20.0, 25.0)
    w2 = make_word("w2", "third", 50.0, 55.0)
    seg0 = make_segment("s0", 5.0, 10.0, [w0])
    seg1 = make_segment("s1", 20.0, 25.0, [w1])
    seg2 = make_segment("s2", 50.0, 55.0, [w2])

    pathological_silences = [
        (10.0, 15.0),  # standard
        (12.0, 18.0),  # overlapping
        (18.0, 20.0),  # adjacent to previous
        (25.0, 25.0),  # zero-length
        (30.0, 26.0),  # inverted
        (-10.0, 5.0),  # negative
        (110.0, 120.0),  # beyond total duration
    ]

    cfg = ChunkConfig()
    t0 = time.perf_counter()
    chunks = partition_into_chunks([seg0, seg1, seg2], pathological_silences, total_dur, cfg)
    elapsed = time.perf_counter() - t0

    all_errors: list[str] = []
    for c in chunks:
        all_errors.extend(check_chunk_invariants(c, total_dur, cfg))

    return {
        "name": "pathological_silences",
        "chunks_count": len(chunks),
        "elapsed_sec": elapsed,
        "errors": all_errors,
        "passed": len(all_errors) == 0,
    }


def test_suite_randomized_fuzzing(num_trials: int = 50) -> dict[str, Any]:
    """8. Randomized property-based fuzzing testing invariants across arbitrary configurations."""
    rng = random.Random(42)
    trial_errors: list[str] = []
    total_chunks = 0
    t0 = time.perf_counter()

    for trial in range(num_trials):
        total_dur = rng.uniform(30.0, 600.0)
        num_segments = rng.randint(1, 40)
        segs: list[ASRSegment] = []
        cur_t = rng.uniform(0.0, 10.0)

        for s_idx in range(num_segments):
            if cur_t >= total_dur - 2.0:
                break
            seg_dur = rng.uniform(0.5, min(28.0, total_dur - cur_t))
            seg_end = cur_t + seg_dur
            num_w = rng.randint(1, 10)
            words: list[WordToken] = []
            w_step = (seg_end - cur_t) / num_w
            for w_idx in range(num_w):
                ws = cur_t + w_idx * w_step
                we = ws + w_step * 0.9
                if we <= ws:
                    we = ws + 0.05
                words.append(make_word(f"t{trial}_s{s_idx}_w{w_idx}", f"w{w_idx}", ws, we))
            segs.append(make_segment(f"t{trial}_s{s_idx}", cur_t, seg_end, words))
            # Next gap can be small or large (0.1s to 50.0s)
            gap = rng.choice([rng.uniform(0.1, 2.0), rng.uniform(5.0, 45.0)])
            cur_t = seg_end + gap

        if not segs:
            continue

        # Random silences
        sils: list[tuple[float, float]] = []
        for _ in range(rng.randint(0, 15)):
            s_start = rng.uniform(-5.0, total_dur + 10.0)
            s_end = s_start + rng.uniform(-2.0, 10.0)
            sils.append((round(s_start, 4), round(s_end, 4)))

        cfg = ChunkConfig(
            max_chunk_duration=rng.choice([20.0, 25.0, 30.0]),
            min_chunk_duration=rng.choice([1.0, 2.0]),
            overlap_padding=rng.choice([0.0, 0.25, 0.5]),
        )

        try:
            chunks = partition_into_chunks(segs, sils, total_dur, cfg)
            total_chunks += len(chunks)
            for c in chunks:
                errs = check_chunk_invariants(c, total_dur, cfg)
                if errs:
                    trial_errors.append(f"Trial {trial} (dur={total_dur:.1f}s): {errs[0]}")
                    break
        except Exception as e:
            trial_errors.append(f"Trial {trial} raised unexpected {type(e).__name__}: {e}")

    elapsed = time.perf_counter() - t0
    return {
        "name": f"randomized_fuzzing_{num_trials}_trials",
        "chunks_count": total_chunks,
        "elapsed_sec": elapsed,
        "errors": trial_errors,
        "passed": len(trial_errors) == 0,
    }


def run_all_stress_tests() -> list[dict[str, Any]]:
    """Run all stress tests and return the result summaries."""
    suites = [
        test_suite_dense_silences_60min,
        test_suite_zero_silences_60min,
        test_suite_sparse_silences_with_long_pauses_60min,
        test_suite_leading_silence_gt_30s,
        test_suite_micro_segments,
        test_suite_exact_30s_boundaries,
        test_suite_pathological_silences,
        test_suite_randomized_fuzzing,
    ]

    results: list[dict[str, Any]] = []
    print("=" * 70)
    print("RUNNING EMPIRICAL STRESS TESTS FOR partition_into_chunks")
    print("=" * 70)

    for suite_fn in suites:
        res = suite_fn()
        status = "PASS" if res["passed"] else "FAIL"
        print(
            f"[{status}] {res['name']}: {res['chunks_count']} chunks in {res['elapsed_sec']:.4f}s"
        )
        if not res["passed"]:
            for err in res["errors"][:5]:
                print(f"       -> {err}")
            if len(res["errors"]) > 5:
                print(f"       -> ... and {len(res['errors']) - 5} more errors")
        results.append(res)

    print("=" * 70)
    passed_count = sum(1 for r in results if r["passed"])
    print(f"SUMMARY: {passed_count}/{len(results)} suites passed.")
    print("=" * 70)
    return results


if __name__ == "__main__":
    results = run_all_stress_tests()
    all_passed = all(r["passed"] for r in results)
    sys.exit(0 if all_passed else 1)
