"""Macro-segmentation and global monotonic alignment reconciler.

Partitions continuous audio into bounded chunks (L <= 30s) using multi-level
anchor selection (VAD silences -> sentence segment boundaries -> word pauses)
and symmetric context overlap padding (0.5s), then reconciles local alignments
into a strictly monotonic document timeline without boundary duplication.
"""

from __future__ import annotations

from .models import (
    ASRSegment,
    AudioChunk,
    ChunkConfig,
    PhonemeCue,
    WordToken,
    finite_number,
)


class ChunkingError(Exception):
    """Base exception for all chunking, macro-segmentation, and reconciliation errors."""


class MonotonicityError(ChunkingError):
    """Raised when word timestamp chronology or global monotonicity invariant is violated."""


def aligner_text(word: WordToken) -> str:
    """Text handed to the forced aligner for one word.

    Words containing digits are spelled out ("42" -> "forty two") because acoustic
    dictionaries have no pronunciation for digits; other words keep their surface
    form so that dictionary entries such as contractions are used.
    """
    if any(c.isdigit() for c in word.text) and word.normalized:
        return word.normalized
    return word.text


def partition_into_chunks(
    segments: list[ASRSegment],
    silences: list[tuple[float, float]],
    total_duration: float,
    config: ChunkConfig | None = None,
) -> list[AudioChunk]:
    """Partition ASR segments into bounded AudioChunks with symmetric overlap padding.

    Anchors are selected hierarchically:
      1. VAD silences (duration >= min_silence_duration).
      2. ASR sentence segment boundaries.
      3. Inter-word pause boundaries (fallback on continuous speech).
    """
    cfg = config if config is not None else ChunkConfig()
    total_dur = finite_number(total_duration, "total_duration")
    if total_dur < 0.0:
        raise ValueError("total_duration must be nonnegative")
    if total_dur == 0.0 or not segments:
        return []

    # Validate segments
    for seg in segments:
        if not isinstance(seg, ASRSegment):
            raise ChunkingError(f"Expected ASRSegment, got {type(seg).__name__}")
        if seg.end > total_dur + 1e-4:
            raise ChunkingError(
                f"Segment '{seg.id}' end timestamp ({seg.end:.2f}s) "
                f"exceeds total_duration ({total_dur:.2f}s)"
            )
        if seg.start < 0.0:
            raise ChunkingError(
                f"Segment '{seg.id}' start timestamp ({seg.start:.2f}s) is negative"
            )

    sorted_segments = sorted(segments, key=lambda s: (s.start, s.end))
    all_words: list[WordToken] = []
    for seg in sorted_segments:
        all_words.extend(seg.words)

    if not all_words:
        return []

    # Filter and sort VAD silences
    valid_silences: list[tuple[float, float]] = []
    for s_start, s_end in silences:
        dur = s_end - s_start
        if dur >= cfg.min_silence_duration - 1e-6 and 0.0 <= s_start < s_end:
            valid_silences.append((s_start, s_end))
    valid_silences.sort(key=lambda s: (s[0], s[1]))

    chunks: list[AudioChunk] = []
    curr_start = 0.0
    chunk_idx = 0
    word_ptr = 0
    num_words = len(all_words)

    while curr_start < total_dur and word_ptr < num_words:
        # Advance curr_start over empty silence when remaining speech cannot fit from curr_start
        if all_words[word_ptr].start > curr_start:
            if (
                all_words[word_ptr].start >= curr_start + cfg.max_chunk_duration
                or all_words[word_ptr].end > curr_start + cfg.max_chunk_duration
            ):
                curr_start = all_words[word_ptr].start

        max_end = min(total_dur, curr_start + cfg.max_chunk_duration)

        # Check if remaining speech fits entirely in this chunk
        if total_dur - curr_start <= cfg.max_chunk_duration:
            split_point = total_dur
            chunk_words = all_words[word_ptr:]
            word_ptr = num_words
        else:
            chosen_split: float | None = None

            # 1. Search Priority 1: VAD Silences
            candidate_silences = [
                s
                for s in valid_silences
                if (curr_start + cfg.min_chunk_duration) <= ((s[0] + s[1]) / 2.0) <= max_end
            ]

            for s in reversed(candidate_silences):
                mid = round((s[0] + s[1]) / 2.0, 4)
                has_before = any(w.end <= mid for w in all_words[word_ptr:])
                has_after = any(w.start >= mid for w in all_words[word_ptr:])
                if has_before and has_after:
                    chosen_split = mid
                    break

            # 2. Search Priority 2: ASR Segment Boundaries
            if chosen_split is None:
                candidate_seg_splits: list[float] = []
                for idx in range(len(sorted_segments) - 1):
                    s_curr = sorted_segments[idx]
                    s_next = sorted_segments[idx + 1]
                    seg_split = (
                        (s_curr.end + s_next.start) / 2.0
                        if s_next.start >= s_curr.end
                        else s_curr.end
                    )
                    if curr_start + cfg.min_chunk_duration <= seg_split <= max_end:
                        if any(w.end <= seg_split for w in all_words[word_ptr:]) and any(
                            w.start >= seg_split for w in all_words[word_ptr:]
                        ):
                            candidate_seg_splits.append(seg_split)

                if candidate_seg_splits:
                    chosen_split = round(candidate_seg_splits[-1], 4)

            # 3. Search Priority 3: Fallback on Inter-Word Gaps
            if chosen_split is None:
                word_candidates: list[tuple[float, float]] = []  # (gap, split_point)
                for w_i in range(word_ptr, num_words - 1):
                    w_curr = all_words[w_i]
                    w_next = all_words[w_i + 1]
                    w_split = (
                        (w_curr.end + w_next.start) / 2.0
                        if w_next.start >= w_curr.end
                        else w_curr.end
                    )
                    if curr_start + cfg.min_chunk_duration <= w_split <= max_end:
                        gap = max(0.0, w_next.start - w_curr.end)
                        word_candidates.append((gap, w_split))

                if word_candidates:
                    # Sort primarily by gap duration descending, secondarily by proximity to max_end
                    word_candidates.sort(key=lambda item: (item[0], item[1]))
                    chosen_split = round(word_candidates[-1][1], 4)

            # Safety fallback if no candidate satisfied min_chunk_duration
            if chosen_split is None:
                furthest_w_idx = word_ptr
                for w_i in range(word_ptr, num_words):
                    if all_words[w_i].end <= max_end:
                        furthest_w_idx = w_i
                    else:
                        break
                if furthest_w_idx > word_ptr:
                    chosen_split = round(all_words[furthest_w_idx].end, 4)
                else:
                    # Single word exceeds max_end or boundary
                    w_len = all_words[word_ptr].end - all_words[word_ptr].start
                    if w_len > cfg.max_chunk_duration:
                        raise ChunkingError(
                            f"Word '{all_words[word_ptr].text}' duration ({w_len:.2f}s) "
                            f"exceeds max_chunk_duration; cannot partition"
                        )
                    chosen_split = round(all_words[word_ptr].end, 4)

            split_point = chosen_split

            # Slice words up to split_point
            next_ptr = word_ptr
            while next_ptr < num_words and all_words[next_ptr].end <= split_point:
                next_ptr += 1
            if next_ptr == word_ptr and word_ptr < num_words:
                next_ptr = word_ptr + 1

            chunk_words = all_words[word_ptr:next_ptr]
            word_ptr = next_ptr

        if not chunk_words:
            break

        chunk_end = round(split_point, 4)
        if chunk_end > total_dur or split_point >= total_dur:
            chunk_end = total_dur

        padded_start = round(max(0.0, curr_start - cfg.overlap_padding), 4)
        if curr_start == 0.0:
            padded_start = 0.0
        padded_start = min(curr_start, padded_start)

        padded_end = round(min(total_dur, chunk_end + cfg.overlap_padding), 4)
        if padded_end > total_dur or chunk_end == total_dur:
            padded_end = total_dur
        padded_end = max(chunk_end, padded_end)
        chunk_text = " ".join(aligner_text(w) for w in chunk_words)

        chunk = AudioChunk(
            id=f"chunk_{chunk_idx}",
            index=chunk_idx,
            start=curr_start,
            end=chunk_end,
            padded_start=padded_start,
            padded_end=padded_end,
            text=chunk_text,
            words=chunk_words,
        )
        chunks.append(chunk)

        curr_start = chunk_end
        chunk_idx += 1

    return chunks


def reconcile_chunk_alignments(
    chunks: list[AudioChunk],
    chunk_aligned_words: list[list[WordToken]],
    padded_coordinates: bool = False,
) -> list[WordToken]:
    """Reconcile local chunk alignments into a globally monotonic word sequence.

    Translates coordinates, cleanly discards boundary overlap seams, and guarantees
    word[i+1].start >= word[i].end chronology.
    """
    if len(chunks) != len(chunk_aligned_words):
        raise ChunkingError(
            f"Chunk count ({len(chunks)}) does not match "
            f"aligned word list count ({len(chunk_aligned_words)})"
        )
    if not chunks:
        return []

    # Count occurrences of each word ID across all chunks for unique boundary detection
    word_id_counts: dict[str, int] = {}
    for c_words in chunk_aligned_words:
        for w in c_words:
            word_id_counts[w.id] = word_id_counts.get(w.id, 0) + 1

    reconciled: list[WordToken] = []
    seen_ids: set[str] = set()
    num_chunks = len(chunks)

    for c_idx, (chunk, words) in enumerate(zip(chunks, chunk_aligned_words, strict=True)):
        base_offset = chunk.padded_start if padded_coordinates else chunk.start

        for w in words:
            g_start = round(base_offset + w.start, 4)
            g_end = round(base_offset + w.end, 4)

            # Safeguard: zero-duration or inverted timestamps
            if g_end <= g_start:
                g_end = round(g_start + 0.01, 4)
            if g_start < 0.0:
                g_start = 0.0
                if g_end <= g_start:
                    g_end = round(g_start + 0.01, 4)

            mid = (g_start + g_end) / 2.0
            is_unique = word_id_counts[w.id] == 1

            # Overlap Seam Deduplication:
            # Discard tokens belonging to leading overlap padding of chunk > 0
            if c_idx > 0 and mid < chunk.start:
                if not is_unique or g_end <= chunk.start:
                    continue
            # Discard tokens belonging to trailing overlap padding of chunk < last
            if c_idx < num_chunks - 1 and mid > chunk.end:
                if not is_unique or g_start >= chunk.end:
                    continue

            # Duplicate ID suppression
            if w.id in seen_ids:
                continue

            seen_ids.add(w.id)

            # Reconcile phonemes with micro-phoneme duration safeguard (>= 0.001s)
            reconciled_phonemes = []
            for p in w.phonemes:
                p_start = round(base_offset + p.start, 4)
                p_end = round(base_offset + p.end, 4)
                if p_end <= p_start:
                    p_end = round(p_start + 0.001, 4)
                reconciled_phonemes.append(
                    PhonemeCue(
                        phoneme=p.phoneme,
                        start=p_start,
                        end=p_end,
                        confidence=p.confidence,
                    )
                )

            reconciled.append(
                WordToken(
                    id=w.id,
                    text=w.text,
                    normalized=w.normalized,
                    start=g_start,
                    end=g_end,
                    confidence=w.confidence,
                    phonemes=reconciled_phonemes,
                    char_start=w.char_start,
                    char_end=w.char_end,
                )
            )

    # Monotonicity Verification & Resolution
    for i in range(len(reconciled) - 1):
        prev_w = reconciled[i]
        curr_w = reconciled[i + 1]

        # Onset corruption: strict onset monotonicity (simultaneous words not allowed)
        if curr_w.start <= prev_w.start:
            raise MonotonicityError(
                f"Chronology corruption at index {i + 1}: word '{curr_w.text}' "
                f"(start={curr_w.start:.4f}) starts before or simultaneously with "
                f"previous word '{prev_w.text}' (start={prev_w.start:.4f})"
            )

        # Minor coarticulation overlap resolution vs severe overlap
        if curr_w.start < prev_w.end:
            overlap = round(prev_w.end - curr_w.start, 4)
            if overlap <= 0.05:
                # Nudge prev_w.end to eliminate overlap
                new_prev_end = curr_w.start
                if new_prev_end <= prev_w.start:
                    new_prev_end = round(prev_w.start + 0.005, 4)

                # Clamp nested phonemes to new_prev_end
                nudged_phonemes = []
                for p in prev_w.phonemes:
                    p_e = min(new_prev_end, p.end)
                    p_s = min(p.start, p_e - 0.001) if p_e <= p.start else p.start
                    nudged_phonemes.append(PhonemeCue(p.phoneme, p_s, p_e, p.confidence))

                reconciled[i] = WordToken(
                    id=prev_w.id,
                    text=prev_w.text,
                    normalized=prev_w.normalized,
                    start=prev_w.start,
                    end=new_prev_end,
                    confidence=prev_w.confidence,
                    phonemes=nudged_phonemes,
                    char_start=prev_w.char_start,
                    char_end=prev_w.char_end,
                )
            else:
                raise MonotonicityError(
                    f"Monotonicity violation at index {i + 1}: word '{curr_w.text}' "
                    f"[{curr_w.start:.4f}, {curr_w.end:.4f}] overlaps previous word "
                    f"'{prev_w.text}' [{prev_w.start:.4f}, {prev_w.end:.4f}] by {overlap:.4f}s"
                )

    return reconciled
