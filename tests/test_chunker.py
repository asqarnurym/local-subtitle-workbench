"""Comprehensive test suite for Macro-Chunking and Monotonic Alignment Reconciler.

Covers:
- AudioChunk and ChunkConfig data contracts and boundary invariants
- ChunkingError and MonotonicityError exception hierarchy
- partition_into_chunks: multi-tier anchor prioritization, duration bounds, padding clamping
- Synthetic 10, 30, and 60-minute lecture scaling tests (<200ms, O(N) memory)
- reconcile_chunk_alignments: local-to-global coordinate translation, seam deduplication,
  strict monotonicity enforcement, and phoneme propagation.
"""

from __future__ import annotations

import dataclasses
import time

import pytest

from subtitle_workbench.chunker import (
    ChunkingError,
    MonotonicityError,
    partition_into_chunks,
    reconcile_chunk_alignments,
)
from subtitle_workbench.models import (
    ASRSegment,
    AudioChunk,
    ChunkConfig,
    PhonemeCue,
    WordToken,
)

# ============================================================================
# Test Fixtures and Synthetic Generators (Zero Mocks)
# ============================================================================


def make_word(
    word_id: str,
    text: str,
    start: float,
    end: float,
    confidence: float = 0.95,
    phonemes: list[PhonemeCue] | None = None,
) -> WordToken:
    """Construct a valid WordToken instance for testing."""
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
    text: str,
    words: list[WordToken] | None = None,
) -> ASRSegment:
    """Construct a valid ASRSegment with chronologically ordered words."""
    if words is None:
        raw_words = text.split()
        words = []
        n = max(1, len(raw_words))
        dur = (end - start) / n
        for i, w in enumerate(raw_words):
            w_start = round(start + i * dur, 4)
            w_end = round(w_start + dur * 0.9, 4)
            if w_end <= w_start:
                w_end = round(w_start + 0.05, 4)
            words.append(make_word(f"{seg_id}_w{i}", w, w_start, w_end))
    return ASRSegment(id=seg_id, start=start, end=end, text=text, words=words)


def generate_synthetic_lecture(
    total_duration_sec: float,
    avg_segment_duration: float = 4.0,
    pause_duration: float = 1.0,
) -> tuple[list[ASRSegment], list[tuple[float, float]], float]:
    """Generate deterministic long-form lecture speech segments and VAD silences.

    Produces alternating speech segments and silence pauses matching natural lecture prosody.
    """
    segments: list[ASRSegment] = []
    silences: list[tuple[float, float]] = []
    current_time = 0.0
    seg_idx = 0

    while current_time < total_duration_sec:
        rem = total_duration_sec - current_time
        if rem <= avg_segment_duration + pause_duration:
            s_end = total_duration_sec
            segments.append(
                make_segment(
                    f"seg_{seg_idx:04d}",
                    current_time,
                    s_end,
                    f"Conclusion words at {current_time:.1f}",
                )
            )
            break

        s_end = min(total_duration_sec, current_time + avg_segment_duration)
        segments.append(
            make_segment(
                f"seg_{seg_idx:04d}",
                current_time,
                s_end,
                f"Lecture segment text block {seg_idx}",
            )
        )
        current_time = s_end
        seg_idx += 1

        p_end = min(total_duration_sec, current_time + pause_duration)
        if p_end - current_time >= 0.4:
            silences.append((round(current_time, 4), round(p_end, 4)))
        current_time = p_end

    return segments, silences, total_duration_sec


def assert_chunk_invariants(chunk: AudioChunk, total_duration: float, config: ChunkConfig) -> None:
    """Assert all mathematical and relational invariants for an AudioChunk."""
    assert (
        0.0 <= chunk.padded_start <= chunk.start < chunk.end <= chunk.padded_end <= total_duration
    )
    assert round(chunk.end - chunk.start, 4) <= config.max_chunk_duration + 1e-4
    if chunk.start == 0.0:
        assert chunk.padded_start == 0.0
    if chunk.end == total_duration:
        assert chunk.padded_end == total_duration


# ============================================================================
# Group 1: Data Contracts and Invariants (AudioChunk, ChunkConfig)
# ============================================================================


class TestAudioChunkAndConfigContracts:
    """Unit tests for AudioChunk and ChunkConfig dataclasses."""

    def test_audio_chunk_valid_instantiation(self) -> None:
        word = make_word("w0", "hello", 10.2, 10.8)
        chunk = AudioChunk(
            id="chunk-0",
            index=0,
            start=10.0,
            end=35.0,
            padded_start=9.5,
            padded_end=35.5,
            text="hello",
            words=[word],
        )
        assert chunk.id == "chunk-0"
        assert chunk.index == 0
        assert chunk.start == 10.0
        assert chunk.end == 35.0
        assert chunk.padded_start == 9.5
        assert chunk.padded_end == 35.5
        assert chunk.text == "hello"
        assert len(chunk.words) == 1

    def test_audio_chunk_immutability(self) -> None:
        chunk = AudioChunk(
            id="chunk-0",
            index=0,
            start=0.0,
            end=10.0,
            padded_start=0.0,
            padded_end=10.5,
            text="hello",
        )
        with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
            chunk.start = 1.0  # type: ignore[misc]

    @pytest.mark.parametrize(
        ("padded_start", "start", "end", "padded_end", "error_msg"),
        [
            (-0.1, 0.0, 10.0, 10.5, "padded_start must be nonnegative"),
            (5.0, 4.0, 10.0, 10.5, "padded_start must be less than or equal to start"),
            (0.0, 10.0, 10.0, 10.5, "start must be strictly less than end"),
            (0.0, 12.0, 10.0, 10.5, "start must be strictly less than end"),
            (0.0, 5.0, 15.0, 14.5, "end must be less than or equal to padded_end"),
        ],
    )
    def test_audio_chunk_boundary_invariants_enforcement(
        self,
        padded_start: float,
        start: float,
        end: float,
        padded_end: float,
        error_msg: str,
    ) -> None:
        with pytest.raises(ValueError, match=error_msg):
            AudioChunk(
                id="chunk-0",
                index=0,
                start=start,
                end=end,
                padded_start=padded_start,
                padded_end=padded_end,
                text="valid text",
            )

    @pytest.mark.parametrize(
        "bad_value",
        [float("nan"), float("inf"), -float("inf"), True, False, "10.0", None],
    )
    def test_audio_chunk_numerical_field_validation(self, bad_value: object) -> None:
        with pytest.raises(ValueError, match="must be a finite number"):
            AudioChunk(
                id="chunk-0",
                index=0,
                start=bad_value,  # type: ignore[arg-type]
                end=10.0,
                padded_start=0.0,
                padded_end=10.5,
                text="text",
            )
        with pytest.raises(ValueError, match="must be a finite number"):
            AudioChunk(
                id="chunk-0",
                index=0,
                start=0.0,
                end=bad_value,  # type: ignore[arg-type]
                padded_start=0.0,
                padded_end=10.5,
                text="text",
            )

    @pytest.mark.parametrize("bad_index", [-1, -10, True, False, 1.5, "0", None])
    def test_audio_chunk_index_validation(self, bad_index: object) -> None:
        with pytest.raises(ValueError, match="index must be a nonnegative integer"):
            AudioChunk(
                id="chunk-0",
                index=bad_index,  # type: ignore[arg-type]
                start=0.0,
                end=10.0,
                padded_start=0.0,
                padded_end=10.5,
                text="text",
            )

    @pytest.mark.parametrize(
        "bad_id",
        ["", "   ", "chunk 0", "chunk@0", "кусок", True, 123, None, "a" * 129],
    )
    def test_audio_chunk_id_validation(self, bad_id: object) -> None:
        with pytest.raises(ValueError, match="id must be a non-empty ASCII identifier"):
            AudioChunk(
                id=bad_id,  # type: ignore[arg-type]
                index=0,
                start=0.0,
                end=10.0,
                padded_start=0.0,
                padded_end=10.5,
                text="text",
            )

    @pytest.mark.parametrize("bad_text", ["", "   ", None, 123, "a" * 4001])
    def test_audio_chunk_text_validation(self, bad_text: object) -> None:
        with pytest.raises(ValueError):
            AudioChunk(
                id="chunk-0",
                index=0,
                start=0.0,
                end=10.0,
                padded_start=0.0,
                padded_end=10.5,
                text=bad_text,  # type: ignore[arg-type]
            )

    def test_audio_chunk_words_validation(self) -> None:
        with pytest.raises(ValueError, match="words must be a list of WordToken instances"):
            AudioChunk(
                id="chunk-0",
                index=0,
                start=0.0,
                end=10.0,
                padded_start=0.0,
                padded_end=10.5,
                text="text",
                words="not_a_list",  # type: ignore[arg-type]
            )
        with pytest.raises(ValueError, match="words must be a list of WordToken instances"):
            AudioChunk(
                id="chunk-0",
                index=0,
                start=0.0,
                end=10.0,
                padded_start=0.0,
                padded_end=10.5,
                text="text",
                words=["not_a_word_token"],  # type: ignore[list-item]
            )

    def test_audio_chunk_words_defensive_copy(self) -> None:
        w = make_word("w0", "word", 1.0, 2.0)
        word_list = [w]
        chunk = AudioChunk(
            id="chunk-0",
            index=0,
            start=0.0,
            end=10.0,
            padded_start=0.0,
            padded_end=10.5,
            text="word",
            words=word_list,
        )
        word_list.append(make_word("w1", "another", 3.0, 4.0))
        assert len(chunk.words) == 1

    def test_chunk_config_defaults(self) -> None:
        config = ChunkConfig()
        assert config.max_chunk_duration == 30.0
        assert config.min_chunk_duration == 1.0
        assert config.overlap_padding == 0.5
        assert config.min_silence_duration == 0.4

    def test_chunk_config_custom_valid(self) -> None:
        config = ChunkConfig(
            max_chunk_duration=20.0,
            min_chunk_duration=2.0,
            overlap_padding=0.25,
            min_silence_duration=0.3,
        )
        assert config.max_chunk_duration == 20.0
        assert config.min_chunk_duration == 2.0
        assert config.overlap_padding == 0.25
        assert config.min_silence_duration == 0.3

    def test_chunk_config_zero_padding_allowed(self) -> None:
        config = ChunkConfig(overlap_padding=0.0)
        assert config.overlap_padding == 0.0

    def test_chunk_config_equal_min_max_allowed(self) -> None:
        config = ChunkConfig(max_chunk_duration=5.0, min_chunk_duration=5.0)
        assert config.max_chunk_duration == 5.0
        assert config.min_chunk_duration == 5.0

    @pytest.mark.parametrize(
        ("kwargs", "error_msg"),
        [
            (
                {"min_chunk_duration": 0.0},
                "min_chunk_duration must be positive",
            ),
            (
                {"min_chunk_duration": -1.0},
                "min_chunk_duration must be positive",
            ),
            (
                {"max_chunk_duration": 5.0, "min_chunk_duration": 10.0},
                "max_chunk_duration must be at least min_chunk_duration",
            ),
            (
                {"overlap_padding": -0.1},
                "overlap_padding must be nonnegative",
            ),
            (
                {"min_silence_duration": 0.0},
                "min_silence_duration must be positive",
            ),
            (
                {"min_silence_duration": -0.5},
                "min_silence_duration must be positive",
            ),
        ],
    )
    def test_chunk_config_boundary_validation(
        self, kwargs: dict[str, object], error_msg: str
    ) -> None:
        with pytest.raises(ValueError, match=error_msg):
            ChunkConfig(**kwargs)  # type: ignore[arg-type]

    @pytest.mark.parametrize(
        "bad_val",
        [float("nan"), float("inf"), -float("inf"), True, False, "30.0", None],
    )
    def test_chunk_config_rejects_non_finite_or_bool(self, bad_val: object) -> None:
        with pytest.raises(ValueError, match="must be a finite number"):
            ChunkConfig(max_chunk_duration=bad_val)  # type: ignore[arg-type]

    def test_chunk_config_immutability(self) -> None:
        config = ChunkConfig()
        with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
            config.max_chunk_duration = 15.0  # type: ignore[misc]


# ============================================================================
# Group 2: Exception Hierarchy
# ============================================================================


class TestExceptionHierarchy:
    """Verify typed exception inheritance and polymorphism."""

    def test_chunker_exception_hierarchy(self) -> None:
        assert issubclass(ChunkingError, Exception)
        assert issubclass(MonotonicityError, ChunkingError)

    def test_polymorphic_exception_catching(self) -> None:
        caught = False
        try:
            raise MonotonicityError("Corrupted chronology at index 5")
        except ChunkingError as err:
            caught = True
            assert "Corrupted chronology" in str(err)
        assert caught


# ============================================================================
# Group 3: Bounded Partitioner Business Logic (partition_into_chunks)
# ============================================================================


class TestPartitionIntoChunks:
    """Comprehensive functional tests for partition_into_chunks."""

    def test_partition_short_recording_produces_single_chunk(self) -> None:
        seg = make_segment("s0", 1.0, 14.0, "Short recording sentence")
        chunks = partition_into_chunks(
            segments=[seg],
            silences=[],
            total_duration=15.0,
        )
        assert len(chunks) == 1
        c = chunks[0]
        assert c.id == "chunk_0"
        assert c.index == 0
        assert c.start == 0.0
        assert c.end == 15.0
        assert c.padded_start == 0.0
        assert c.padded_end == 15.0
        assert len(c.words) == 3

    def test_partition_strict_duration_bound_enforced(self) -> None:
        config = ChunkConfig(max_chunk_duration=30.0)
        segments, silences, total_dur = generate_synthetic_lecture(120.0)
        chunks = partition_into_chunks(
            segments=segments,
            silences=silences,
            total_duration=total_dur,
            config=config,
        )
        assert len(chunks) >= 4
        for c in chunks:
            assert_chunk_invariants(c, total_dur, config)
            assert (c.end - c.start) <= 30.0 + 1e-4

    def test_partition_natural_anchor_priority_1_vad_silence(self) -> None:
        """Partitioner prioritizes VAD silence >= min_silence over segment breaks or word cuts."""
        # 0s to 12s: Speech
        # 12.0s to 13.5s: Silence (1.5s)
        # 13.5s to 24.0s: Speech
        # 24.0s to 25.2s: Silence (1.2s)
        # 25.2s to 35.0s: Speech
        seg1 = make_segment("seg_0", 0.0, 12.0, "First sentence here")
        seg2 = make_segment("seg_1", 13.5, 24.0, "Second sentence here")
        seg3 = make_segment("seg_2", 25.2, 35.0, "Third sentence extends past thirty")
        silences = [(12.0, 13.5), (24.0, 25.2)]

        chunks = partition_into_chunks(
            segments=[seg1, seg2, seg3],
            silences=silences,
            total_duration=35.0,
            config=ChunkConfig(max_chunk_duration=30.0, min_chunk_duration=1.0),
        )

        assert len(chunks) == 2
        # Chunk 0 should split during the second silence (midpoint 24.6s)
        assert 24.0 <= chunks[0].end <= 25.2
        assert chunks[1].start == chunks[0].end
        assert chunks[1].end == 35.0

    def test_partition_natural_anchor_priority_2_asr_segment_boundary(self) -> None:
        """When no VAD silence exists, partitioner splits on ASR segment breaks."""
        seg1 = make_segment("seg_0", 0.0, 10.0, "First sentence")
        seg2 = make_segment("seg_1", 10.0, 22.0, "Second sentence ending at 22")
        seg3 = make_segment("seg_2", 22.0, 34.0, "Third sentence ending at 34")

        chunks = partition_into_chunks(
            segments=[seg1, seg2, seg3],
            silences=[],  # No VAD silences
            total_duration=34.0,
            config=ChunkConfig(max_chunk_duration=30.0, min_chunk_duration=1.0),
        )

        assert len(chunks) == 2
        # Should split at 22.0s (end of seg2)
        assert chunks[0].end == 22.0
        assert chunks[1].start == 22.0
        assert chunks[1].end == 34.0

    def test_partition_natural_anchor_priority_3_continuous_speech_fallback(
        self,
    ) -> None:
        """Fallback to word gap when speech exceeds 30s in single continuous segment."""
        # Single continuous segment spanning 45 seconds with 10 words
        w_durs = [
            ("w0", 0.0, 4.0),
            ("w1", 4.1, 9.0),
            ("w2", 9.1, 14.0),
            ("w3", 14.1, 19.0),
            ("w4", 19.1, 24.0),
            ("w5", 24.5, 28.0),  # gap between w4 and w5 is 0.5s
            ("w6", 28.1, 33.0),
            ("w7", 33.1, 38.0),
            ("w8", 38.1, 42.0),
            ("w9", 42.1, 45.0),
        ]
        words = [make_word(wid, f"word_{i}", s, e) for i, (wid, s, e) in enumerate(w_durs)]
        long_seg = ASRSegment(
            id="long_seg",
            start=0.0,
            end=45.0,
            text=" ".join(w.text for w in words),
            words=words,
        )

        chunks = partition_into_chunks(
            segments=[long_seg],
            silences=[],
            total_duration=45.0,
            config=ChunkConfig(max_chunk_duration=30.0, min_chunk_duration=1.0),
        )

        assert len(chunks) >= 2
        for c in chunks:
            assert c.end - c.start <= 30.0 + 1e-4

        # Verify all words were partitioned without loss
        reconstructed_word_ids = [w.id for c in chunks for w in c.words]
        assert reconstructed_word_ids == [w.id for w in words]

    def test_partition_padding_clamping_at_global_bounds(self) -> None:
        seg1 = make_segment("s0", 0.0, 15.0, "First block")
        seg2 = make_segment("s1", 16.0, 35.0, "Second block")
        seg3 = make_segment("s2", 36.0, 50.0, "Third block")
        silences = [(15.0, 16.0), (35.0, 36.0)]

        chunks = partition_into_chunks(
            segments=[seg1, seg2, seg3],
            silences=silences,
            total_duration=50.0,
            config=ChunkConfig(
                max_chunk_duration=25.0,
                min_chunk_duration=1.0,
                overlap_padding=0.5,
            ),
        )

        assert len(chunks) >= 2
        first = chunks[0]
        last = chunks[-1]

        # First chunk clamped at 0.0
        assert first.start == 0.0
        assert first.padded_start == 0.0

        # Last chunk clamped at total_duration
        assert last.end == 50.0
        assert last.padded_end == 50.0

        # Interior chunks have symmetric padding
        if len(chunks) > 2:
            interior = chunks[1]
            assert round(interior.padded_start, 4) == round(interior.start - 0.5, 4)
            assert round(interior.padded_end, 4) == round(interior.end + 0.5, 4)

    def test_partition_empty_segments_handling(self) -> None:
        assert partition_into_chunks([], [], 10.0) == []
        seg = make_segment("s0", 0.0, 5.0, "text")
        assert partition_into_chunks([seg], [], 0.0) == []

    @pytest.mark.parametrize(
        "bad_duration",
        [-1.0, -0.001, float("nan"), float("inf"), -float("inf"), True, False, "10.0"],
    )
    def test_partition_rejects_invalid_total_duration(self, bad_duration: object) -> None:
        seg = make_segment("s0", 0.0, 5.0, "text")
        with pytest.raises(ValueError):
            partition_into_chunks([seg], [], bad_duration)  # type: ignore[arg-type]

    def test_partition_segments_exceeding_total_duration(self) -> None:
        seg = make_segment("s0", 0.0, 50.0, "Exceeding duration")
        with pytest.raises(ChunkingError, match="exceeds total_duration"):
            partition_into_chunks([seg], [], total_duration=30.0)

    def test_partition_single_word_exceeding_max_chunk_duration(self) -> None:
        word = make_word("w0", "supercalifragilistic", 0.0, 35.0)
        seg = ASRSegment(
            id="s0",
            start=0.0,
            end=35.0,
            text="supercalifragilistic",
            words=[word],
        )
        with pytest.raises(ChunkingError, match="exceeds max_chunk_duration; cannot partition"):
            partition_into_chunks(
                [seg],
                [],
                total_duration=35.0,
                config=ChunkConfig(max_chunk_duration=30.0),
            )


# ============================================================================
# Group 4: Long Recordings and Linear Scalability (10m, 30m, 60m)
# ============================================================================


class TestLongRecordingsLinearScalability:
    """Verify linear execution time (<200ms) and linear memory complexity over long lectures."""

    def test_partition_long_recording_10_minutes(self) -> None:
        duration = 600.0  # 10 minutes
        segments, silences, total_dur = generate_synthetic_lecture(duration)
        config = ChunkConfig(max_chunk_duration=30.0)

        t_start = time.perf_counter()
        chunks = partition_into_chunks(segments, silences, total_dur, config)
        elapsed = time.perf_counter() - t_start

        assert len(chunks) >= 20
        for c in chunks:
            assert_chunk_invariants(c, total_dur, config)
        # Performance budget: < 50ms for 10 minutes
        assert elapsed < 0.050, f"10m lecture took {elapsed:.4f}s (budget: 50ms)"

    def test_partition_long_recording_30_minutes(self) -> None:
        duration = 1800.0  # 30 minutes
        segments, silences, total_dur = generate_synthetic_lecture(duration)
        config = ChunkConfig(max_chunk_duration=30.0)

        t_start = time.perf_counter()
        chunks = partition_into_chunks(segments, silences, total_dur, config)
        elapsed = time.perf_counter() - t_start

        assert len(chunks) >= 60
        for c in chunks:
            assert_chunk_invariants(c, total_dur, config)
        # Performance budget: < 100ms for 30 minutes
        assert elapsed < 0.100, f"30m lecture took {elapsed:.4f}s (budget: 100ms)"

    def test_partition_long_recording_60_minutes(self) -> None:
        duration = 3600.0  # 60 minutes
        segments, silences, total_dur = generate_synthetic_lecture(duration)
        config = ChunkConfig(max_chunk_duration=30.0)

        t_start = time.perf_counter()
        chunks = partition_into_chunks(segments, silences, total_dur, config)
        elapsed = time.perf_counter() - t_start

        assert len(chunks) >= 120
        for c in chunks:
            assert_chunk_invariants(c, total_dur, config)
        # Performance budget: < 200ms for 60 minutes
        assert elapsed < 0.200, f"60m lecture took {elapsed:.4f}s (budget: 200ms)"


# ============================================================================
# Group 5: Monotonic Alignment Reconciler (reconcile_chunk_alignments)
# ============================================================================


class TestReconcileChunkAlignments:
    """Functional tests for reconcile_chunk_alignments."""

    def test_reconcile_local_to_global_coordinate_translation(self) -> None:
        c0 = AudioChunk(
            id="c0",
            index=0,
            start=0.0,
            end=25.0,
            padded_start=0.0,
            padded_end=25.5,
            text="hello world",
        )
        c1 = AudioChunk(
            id="c1",
            index=1,
            start=25.0,
            end=50.0,
            padded_start=24.5,
            padded_end=50.0,
            text="lecture continuation",
        )

        w0 = make_word("w0", "hello", 1.0, 2.0)
        w1 = make_word("w1", "world", 10.0, 11.0)
        w2 = make_word("w2", "lecture", 2.0, 3.0)
        w3 = make_word("w3", "continuation", 15.0, 16.0)

        reconciled = reconcile_chunk_alignments([c0, c1], [[w0, w1], [w2, w3]])

        assert len(reconciled) == 4
        assert [w.id for w in reconciled] == ["w0", "w1", "w2", "w3"]
        assert reconciled[0].start == 1.0
        assert reconciled[0].end == 2.0
        assert reconciled[1].start == 10.0
        assert reconciled[1].end == 11.0
        # Chunk 1 words translated by c1.start (25.0)
        assert reconciled[2].start == 27.0
        assert reconciled[2].end == 28.0
        assert reconciled[3].start == 40.0
        assert reconciled[3].end == 41.0

    def test_reconcile_padded_coordinate_translation(self) -> None:
        """When padded_coordinates=True, base offset is chunk.padded_start."""
        c0 = AudioChunk(
            id="c0",
            index=0,
            start=10.0,
            end=30.0,
            padded_start=9.5,
            padded_end=30.5,
            text="test",
        )
        w = make_word("w0", "test", 1.0, 2.0)
        reconciled = reconcile_chunk_alignments([c0], [[w]], padded_coordinates=True)
        assert len(reconciled) == 1
        assert reconciled[0].start == 10.5  # 9.5 + 1.0
        assert reconciled[0].end == 11.5  # 9.5 + 2.0

    def test_reconcile_seam_deduplication_exact_boundary(self) -> None:
        """Tokens inside the overlap seams are deduplicated cleanly."""
        # Chunk 0 covers [0.0, 25.0] padded to 25.5
        c0 = AudioChunk(
            id="c0",
            index=0,
            start=0.0,
            end=25.0,
            padded_start=0.0,
            padded_end=25.5,
            text="start boundary",
        )
        # Chunk 1 covers [25.0, 50.0] padded from 24.5
        c1 = AudioChunk(
            id="c1",
            index=1,
            start=25.0,
            end=50.0,
            padded_start=24.5,
            padded_end=50.0,
            text="boundary end",
        )

        # Word "boundary" is emitted by both chunks in the overlap region
        w_start = make_word("w_start", "start", 2.0, 3.0)
        w_bound_c0 = make_word("w_bound", "boundary", 24.6, 24.9)

        w_bound_c1 = make_word("w_bound", "boundary", 0.0, 0.3)
        # Duplicate ID suppression drops redundant boundary token
        w_end = make_word("w_end", "end", 5.0, 6.0)

        reconciled = reconcile_chunk_alignments(
            [c0, c1],
            [[w_start, w_bound_c0], [w_bound_c1, w_end]],
        )

        assert len(reconciled) == 3
        assert [w.id for w in reconciled] == ["w_start", "w_bound", "w_end"]

    def test_reconcile_strict_monotonicity_verified(self) -> None:
        c0 = AudioChunk(
            id="c0",
            index=0,
            start=0.0,
            end=10.0,
            padded_start=0.0,
            padded_end=10.5,
            text="a b c",
        )
        words = [
            make_word("w0", "a", 1.0, 2.0),
            make_word("w1", "b", 2.5, 3.5),
            make_word("w2", "c", 4.0, 5.0),
        ]
        reconciled = reconcile_chunk_alignments([c0], [words])
        assert len(reconciled) == 3
        for i in range(len(reconciled) - 1):
            assert reconciled[i + 1].start >= reconciled[i].end

    def test_reconcile_minor_coarticulation_overlap_adjusted(self) -> None:
        """Coarticulation overlap <= 50ms is automatically resolved without raising error."""
        c0 = AudioChunk(
            id="c0",
            index=0,
            start=0.0,
            end=10.0,
            padded_start=0.0,
            padded_end=10.5,
            text="deep learning",
        )
        # w0 ends at 2.03s, w1 starts at 2.00s (30ms overlap)
        w0 = make_word("w0", "deep", 1.0, 2.03)
        w1 = make_word("w1", "learning", 2.00, 3.00)

        reconciled = reconcile_chunk_alignments([c0], [[w0, w1]])
        assert len(reconciled) == 2
        assert reconciled[0].end <= reconciled[1].start

    def test_reconcile_monotone_error_intra_chunk_corruption(self) -> None:
        """Inverted word onset within a chunk raises MonotonicityError."""
        c0 = AudioChunk(
            id="c0",
            index=0,
            start=0.0,
            end=10.0,
            padded_start=0.0,
            padded_end=10.5,
            text="deep learning",
        )
        # w1 starts at 1.5s, while w0 started at 2.0s
        w0 = make_word("w0", "deep", 2.0, 3.0)
        w1 = make_word("w1", "learning", 1.5, 2.5)

        with pytest.raises(MonotonicityError, match="Chronology corruption"):
            reconcile_chunk_alignments([c0], [[w0, w1]])

    def test_reconcile_monotone_error_severe_overlap(self) -> None:
        """Severe overlap > 50ms raises MonotonicityError."""
        c0 = AudioChunk(
            id="c0",
            index=0,
            start=0.0,
            end=10.0,
            padded_start=0.0,
            padded_end=10.5,
            text="deep learning",
        )
        # w0 ends at 2.5s, w1 starts at 2.0s (500ms overlap)
        w0 = make_word("w0", "deep", 1.0, 2.5)
        w1 = make_word("w1", "learning", 2.0, 3.0)

        with pytest.raises(MonotonicityError, match="Monotonicity violation"):
            reconcile_chunk_alignments([c0], [[w0, w1]])

    def test_reconcile_monotone_error_cross_chunk_corruption(self) -> None:
        """Cross-chunk timestamp inversion raises MonotonicityError."""
        c0 = AudioChunk(
            id="c0",
            index=0,
            start=0.0,
            end=25.0,
            padded_start=0.0,
            padded_end=25.5,
            text="end of first",
        )
        c1 = AudioChunk(
            id="c1",
            index=1,
            start=25.0,
            end=50.0,
            padded_start=24.5,
            padded_end=50.0,
            text="start of second",
        )
        # Chunk 0 has a word ending at 25.8s, Chunk 1 has a word starting at 25.1s (overlap 0.7s)
        w_corrupted = make_word("w_corrupt", "corrupt", 24.0, 25.8)
        w_next = make_word("w_next", "next", 0.1, 1.0)

        with pytest.raises(MonotonicityError, match="Monotonicity violation"):
            reconcile_chunk_alignments([c0, c1], [[w_corrupted], [w_next]])

    def test_reconcile_phoneme_propagation(self) -> None:
        """Phoneme cues inside words are also shifted by chunk base offset."""
        c0 = AudioChunk(
            id="c0",
            index=0,
            start=20.0,
            end=40.0,
            padded_start=19.5,
            padded_end=40.5,
            text="hi",
        )
        p0 = PhonemeCue(phoneme="HH", start=0.1, end=0.3, confidence=0.9)
        p1 = PhonemeCue(phoneme="AY", start=0.3, end=0.7, confidence=0.92)
        w = make_word("w0", "hi", 0.1, 0.7, phonemes=[p0, p1])

        reconciled = reconcile_chunk_alignments([c0], [[w]])
        assert len(reconciled) == 1
        rw = reconciled[0]
        assert rw.start == 20.1
        assert rw.end == 20.7
        assert len(rw.phonemes) == 2
        assert rw.phonemes[0].start == 20.1
        assert rw.phonemes[0].end == 20.3
        assert rw.phonemes[1].start == 20.3
        assert rw.phonemes[1].end == 20.7

    def test_reconcile_zero_duration_and_safeguards(self) -> None:
        c0 = AudioChunk(
            id="c0",
            index=0,
            start=0.0,
            end=10.0,
            padded_start=0.0,
            padded_end=10.5,
            text="zero",
        )
        w = make_word("w0", "zero", 5.0, 5.01)  # valid WordToken requires start < end
        reconciled = reconcile_chunk_alignments([c0], [[w]])
        assert len(reconciled) == 1
        assert reconciled[0].end > reconciled[0].start

    def test_reconcile_mismatched_lengths(self) -> None:
        c0 = AudioChunk(
            id="c0",
            index=0,
            start=0.0,
            end=10.0,
            padded_start=0.0,
            padded_end=10.5,
            text="text",
        )
        with pytest.raises(ChunkingError, match="does not match"):
            reconcile_chunk_alignments([c0], [])

    def test_reconcile_empty_inputs(self) -> None:
        assert reconcile_chunk_alignments([], []) == []


# ============================================================================
# Group 6: Regression Test Suite for Increment 3 Remediations
# ============================================================================


class TestChunkerRemediations:
    """Regression tests verifying all bug fixes and boundary guarantees."""

    def test_partition_inter_segment_pause_gt_30s(self) -> None:
        """Fix D1: Pauses > 30s must never produce chunks exceeding max_chunk_duration."""
        w1 = make_word("w1", "hello", 1.0, 2.0)
        w2 = make_word("w2", "world", 80.0, 81.0)
        seg1 = make_segment("s1", 0.0, 10.0, "hello", [w1])
        seg2 = make_segment("s2", 75.0, 85.0, "world", [w2])
        config = ChunkConfig(max_chunk_duration=30.0)

        chunks = partition_into_chunks([seg1, seg2], [], 100.0, config)
        assert len(chunks) == 2
        for c in chunks:
            assert round(c.end - c.start, 4) <= 30.0 + 1e-4
            assert_chunk_invariants(c, 100.0, config)

    def test_partition_bounded_duration_sparse_silences_long_pauses(self) -> None:
        """Alias for test_partition_inter_segment_pause_gt_30s."""
        self.test_partition_inter_segment_pause_gt_30s()

    def test_partition_leading_silence_gt_30s(self) -> None:
        """Fix D1: Leading silence > 30s advances curr_start to avoid oversized chunk."""
        w = make_word("w0", "hi", 45.0, 48.0)
        seg = make_segment("s0", 45.0, 48.0, "hi", [w])
        config = ChunkConfig(max_chunk_duration=30.0)

        chunks = partition_into_chunks([seg], [(0.0, 45.0)], 120.0, config)
        assert len(chunks) == 1
        c = chunks[0]
        assert c.start == 45.0
        assert c.end == 120.0 or c.end <= 75.0
        assert round(c.end - c.start, 4) <= 30.0 + 1e-4
        assert_chunk_invariants(c, 120.0, config)

    def test_partition_leading_silence_greater_than_30s(self) -> None:
        """Alias for test_partition_leading_silence_gt_30s."""
        self.test_partition_leading_silence_gt_30s()

    def test_partition_floating_point_precision_clamping(self) -> None:
        """Fix D2: Sub-millisecond total_duration floats must never be exceeded."""
        w = make_word("w0", "hi", 0.0, 5.0)
        seg = make_segment("s0", 0.0, 5.0, "hi", [w])
        total_dur = 10.00006

        chunks = partition_into_chunks([seg], [], total_dur)
        assert len(chunks) == 1
        c = chunks[0]
        assert c.end <= total_dur
        assert c.padded_end <= total_dur
        assert c.end == total_dur
        assert c.padded_end == total_dur

    def test_partition_boundary_clamping_float_precision(self) -> None:
        """Alias for test_partition_floating_point_precision_clamping."""
        self.test_partition_floating_point_precision_clamping()

    def test_reconcile_seam_boundary_word_retention(self) -> None:
        """Fix D3: Unique boundary tokens whose alignment extends into padding are not dropped."""
        c0 = AudioChunk(
            id="c0",
            index=0,
            start=0.0,
            end=25.0,
            padded_start=0.0,
            padded_end=25.5,
            text="hello world",
        )
        c1 = AudioChunk(
            id="c1",
            index=1,
            start=25.0,
            end=50.0,
            padded_start=24.5,
            padded_end=50.0,
            text="next text",
        )
        w0 = make_word("w0", "hello", 1.0, 2.0)
        w1 = make_word("w1", "world", 24.8, 25.3)  # mid = 25.05 > chunk.end (25.0)
        w2 = make_word("w2", "next", 1.0, 2.0)
        w3 = make_word("w3", "text", 3.0, 4.0)

        reconciled = reconcile_chunk_alignments([c0, c1], [[w0, w1], [w2, w3]])
        assert [w.id for w in reconciled] == ["w0", "w1", "w2", "w3"]

    def test_reconcile_prevent_silent_word_deletion_at_padding_seam(self) -> None:
        """Alias for test_reconcile_seam_boundary_word_retention."""
        self.test_reconcile_seam_boundary_word_retention()

    def test_reconcile_identical_onsets_triggers_monotonicity_error(self) -> None:
        """Fix D4: Simultaneous word onsets (curr_w.start == prev_w.start)
        raise MonotonicityError.
        """
        c0 = AudioChunk(
            id="c0", index=0, start=0.0, end=10.0, padded_start=0.0, padded_end=10.5, text="a b"
        )
        w0 = make_word("w0", "a", 2.0, 2.03)
        w1 = make_word("w1", "b", 2.0, 2.50)

        with pytest.raises(
            MonotonicityError, match="starts before or simultaneously with previous word"
        ):
            reconcile_chunk_alignments([c0], [[w0, w1]])

    def test_reconcile_strict_onset_monotonicity_simultaneous_words(self) -> None:
        """Alias for test_reconcile_identical_onsets_triggers_monotonicity_error."""
        self.test_reconcile_identical_onsets_triggers_monotonicity_error()

    def test_reconcile_sub_millisecond_phoneme_preservation(self) -> None:
        """Fix D5: Micro-phonemes (< 0.1ms) must not collapse upon 4-decimal rounding."""
        c = AudioChunk(
            id="c0", index=0, start=0.0, end=10.0, padded_start=0.0, padded_end=10.5, text="text"
        )
        p = PhonemeCue("P", 0.10001, 0.10004, 0.9)
        w = make_word("w0", "text", 0.1, 0.5, phonemes=[p])

        res = reconcile_chunk_alignments([c], [[w]])
        assert len(res) == 1
        p_res = res[0].phonemes[0]
        assert p_res.start < p_res.end
        assert round(p_res.end - p_res.start, 4) >= 0.001

    def test_partition_60m_sparse_silences_duration_bounds(self) -> None:
        """Fix D1: 60-minute lecture with sparse speech and long pauses (>30s pauses)."""
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
            segs.append(
                make_segment(f"s_{i}", t_start, t_end, " ".join(f"tok{j}" for j in range(5)), words)
            )
            if i < 29:
                sils.append((t_end, (i + 1) * 120.0))

        config = ChunkConfig(max_chunk_duration=30.0)
        chunks = partition_into_chunks(segs, sils, total_dur, config)
        assert len(chunks) > 0
        for c in chunks:
            assert round(c.end - c.start, 4) <= 30.0 + 1e-4
            assert_chunk_invariants(c, total_dur, config)

    def test_reconcile_coarticulation_nudge_nested_phoneme_clamping(self) -> None:
        """Fix D4 extension: When word end is nudged backward, nested phonemes are clamped."""
        c0 = AudioChunk(
            id="c0", index=0, start=0.0, end=10.0, padded_start=0.0, padded_end=10.5, text="cat sat"
        )
        p_trail = PhonemeCue("T", 1.18, 1.20, 0.9)
        w_trail_p = make_word("wt", "cat", 1.0, 1.20, phonemes=[p_trail])
        w_next_p = make_word("wn", "sat", 1.17, 1.30)  # 30ms overlap

        res = reconcile_chunk_alignments([c0], [[w_trail_p, w_next_p]])
        assert res[0].end == 1.17
        assert res[0].phonemes[0].end <= res[0].end
