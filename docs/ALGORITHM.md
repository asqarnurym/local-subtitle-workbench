# Alignment algorithm and input contract

1. Inspect WAV metadata before loading. Accept uncompressed 16-bit mono PCM at
   16,000 Hz. Reject short, silent/very quiet, truncated or oversized recordings.
2. Require finite cue values: `0 <= start < end <= reference duration`. Enforce
   unique IDs and non-overlapping order. Require declared English.
3. Extract centred 40 ms Hann-windowed spectral centroid and log RMS every
   20 ms. Standardise energy independently per recording; weight centroid by
   `spectral_weight / Nyquist`. Feature extraction is deterministic.
4. Compute DTW with squared Euclidean distances. A band of ±`band_seconds / hop`
   target frames surrounds `j = i * (M-1)/(N-1)`. Both recordings' endpoints
   are included. Valid moves are diagonal, vertical and horizontal; ties prefer
   that order. Store one byte per visited cell plus two compact band cost rows.
5. For each reference frame, use the median target time encountered on the path.
   A cumulative maximum preserves monotonicity. Interpolate cue boundaries
   linearly; anchor recording start/end, then validate mapped cue order again.
6. Convert seconds to milliseconds with decimal half-up rounding. A cue that
   collapses at that resolution is rejected. Escape `&`, `<` and `>` in WebVTT.

| Bound | Default | Hard ceiling / behaviour |
| --- | --- | --- |
| Frame count per recording | 3,000 | 10,000; inspected before reading WAV data |
| Evaluated DTW cells | 2,000,000 | 5,000,000; checked before predecessor allocation |
| Band width | 0.5 seconds | 5 seconds; no silent unbounded fallback |
| Cue input size | 2 MB | Rejected before JSON loading |
| Cue text length | 4,000 characters | Rejected; no embedded controls/blank paragraphs |
| Sample rate | 16 kHz | Reject mismatch; no implicit resampling |

Runtime is O(visited band cells) for dynamic programming. Backpointer memory is
O(visited cells); input/features and cost rows are O(N + M). The band is a
resource and modelling assumption. A finite path can still be a poor acoustic
match. Reference timestamps inside long silence or repeated acoustic patterns
remain ambiguous; independent reference validation is required.

The generated timing oracle checks known time transformation. It is separate
from the DTW cost: distance minimization alone cannot establish ground-truth
accuracy. Arbitrary transcript-to-audio alignment needs a speech/phoneme backend.
