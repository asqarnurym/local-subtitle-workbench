# Project: Local Subtitle Alignment Workbench — Increment 3: Macro-DTW Chunking & Alignment Reconciler

## Architecture
Continuous educational recordings (10–60 minutes) exceed DTW memory bounds ($O(T \times U)$ quadratic growth) and trigger buffer overflow in audio loaders (`Config.max_frames = 3000`, 60s). Increment 3 introduces macro-segmentation:
1. Continuous audio is partitioned into sequential chunks bounded by $L \le 30.0$s using multi-tier anchor selection (Priority 1: Silero-VAD silences $\ge 0.4$s; Priority 2: ASR segment boundaries; Priority 3: inter-word pause fallback).
2. Each chunk receives symmetric overlap padding ($\Delta_{pad} = 0.5$s) clamped to $[0.0, \text{total\_duration}]$.
3. Local forced alignment operates independently per chunk with linear memory bounds.
4. `reconcile_chunk_alignments` translates local timestamps to global coordinates ($t_{\text{global}} = \text{chunk.start} + t_{\text{local}}$), deduplicates words across overlap padding seams, and strictly enforces global monotonicity ($w_{i+1}.\text{start} \ge w_i.\text{start}$), raising `MonotonicityError` if chronological integrity is violated.

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | `AudioChunk` Model | Immutable dataclass with fields `id`, `index`, `start`, `end`, `padded_start`, `padded_end`, `text`, `words` and strict invariants $0.0 \le \text{padded\_start} \le \text{start} < \text{end} \le \text{padded\_end}$ | M1 | R1 |
| 2 | `ChunkConfig` Model | Immutable dataclass with `max_chunk_duration=30.0`, `min_chunk_duration=1.0`, `overlap_padding=0.5`, `min_silence_duration=0.4` and parameter validation | M1 | R1 |
| 3 | Package Exports (Models) | Export `AudioChunk`, `ChunkConfig` in `src/subtitle_workbench/__init__.py` | M1 | R1 |
| 4 | Chunker Exceptions | `ChunkingError(Exception)` and `MonotonicityError(ChunkingError)` exception hierarchy | M2 | R2 |
| 5 | Bounded Partitioning | `partition_into_chunks` enforcing chunk duration $\text{end} - \text{start} \le \text{max\_chunk\_duration}$ | M2 | R2 |
| 6 | Multi-tier Anchor Selection | Anchor selection priority: 1) VAD silences $\ge \text{min\_silence}$, 2) ASR segment breaks, 3) inter-word acoustic pause fallback | M2 | R2 |
| 7 | Overlap Padding & Clamping | Symmetric padding with $\text{padded\_start} = \max(0.0, \text{start} - \text{pad})$ and $\text{padded\_end} = \min(T, \text{end} + \text{pad})$ | M2 | R2 |
| 8 | Global Timeline Transformation | Translate chunk-local timestamps to global coordinates: $t_{\text{global}} = \text{chunk.start} + t_{\text{local}}$ (for words and phonemes) | M2 | R2 |
| 9 | Overlap Seam Deduplication | Cleanly discard redundant tokens in leading/trailing padding seams | M2 | R2 |
| 10 | Monotonicity Enforcement | Guarantee chronological word ordering; raise `MonotonicityError` on timestamp reversal | M2 | R2 |
| 11 | Package Exports (Chunker) | Export `partition_into_chunks`, `reconcile_chunk_alignments`, `ChunkingError`, `MonotonicityError` in `src/subtitle_workbench/__init__.py` | M2 | R2 |
| 12 | Comprehensive Test Suite | Unit, contract, boundary, synthetic 10–60 min lecture scalability in `tests/test_chunker.py` with zero business logic mocks | M3 | R3 |
| 13 | SDLC Audit Report | Complete `docs/increments/INCREMENT_3_MACRO_DTW_CHUNKING.md` from template | M4 | R4 |
| 14 | Quality Gate & Packaging | Zero test regressions (314+ new tests pass), zero ruff issues, clean wheel build, git commit | M4 | AC |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M1 | Data Models & Contracts | Implement `AudioChunk` and `ChunkConfig` in `src/subtitle_workbench/models.py`; export in `__init__.py` | none | DONE |
| M2 | Chunker & Reconciler Logic | Implement `ChunkingError`, `MonotonicityError`, `partition_into_chunks`, `reconcile_chunk_alignments` in `src/subtitle_workbench/chunker.py`; export in `__init__.py` | M1 | DONE |
| M3 | Comprehensive Test Suite | Implement `tests/test_chunker.py` covering all positive, negative, boundary, and long-lecture cases | M1, M2 | DONE |
| M4 | SDLC Report & Verification | Create `docs/increments/INCREMENT_3_MACRO_DTW_CHUNKING.md`, run all gates, build wheel, commit | M1, M2, M3 | DONE |

## Interface Contracts
### `src/subtitle_workbench/models.py`
```python
@dataclass(frozen=True)
class AudioChunk:
    id: str
    index: int
    start: float
    end: float
    padded_start: float
    padded_end: float
    text: str
    words: list[WordToken] = field(default_factory=list)


@dataclass(frozen=True)
class ChunkConfig:
    max_chunk_duration: float = 30.0
    min_chunk_duration: float = 1.0
    overlap_padding: float = 0.5
    min_silence_duration: float = 0.4
```

### `src/subtitle_workbench/chunker.py`
```python
class ChunkingError(Exception): ...


class MonotonicityError(ChunkingError): ...


def partition_into_chunks(
    segments: list[ASRSegment],
    silences: list[tuple[float, float]],
    total_duration: float,
    config: ChunkConfig | None = None,
) -> list[AudioChunk]: ...


def reconcile_chunk_alignments(
    chunks: list[AudioChunk],
    chunk_aligned_words: list[list[WordToken]],
) -> list[WordToken]: ...
```

## Code Layout
- Models: `src/subtitle_workbench/models.py`
- Chunker: `src/subtitle_workbench/chunker.py`
- Package Exports: `src/subtitle_workbench/__init__.py`
- Tests: `tests/test_chunker.py`
- Documentation: `docs/increments/INCREMENT_3_MACRO_DTW_CHUNKING.md`
