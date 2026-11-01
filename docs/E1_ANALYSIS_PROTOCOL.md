# E1a/b: speaker-level statistics and descriptive error analysis

Fixed on 2026-11-02 before executing this supplementary analysis. The original
clip-level results are already known; this is not a claim of preregistration
before seeing the original experiment. No model, sample or hypothesis is selected
using the new results.

## Inputs and scope

Use all 160 TIMIT utterances (16 speakers) and all 999 valid Buckeye test clips
(20 speakers) from the frozen manifests, all nine modes, their saved predictions
and the reference snapshot of 2026-11-01. Verify the archive before analysis and
preserve the original reports, weights and ledger. No models are executed.

## Speaker-level paired tests

- Keep the same seven comparisons as the frozen benchmark. Holm adjustment is
  applied to those seven tests within each corpus. Report adjusted p-values and
  decisions at both 0.05 (benchmark convention) and 0.01 (integrity-policy check).
- For each comparison, take the intersection of successfully scored clip IDs.
  Both methods use the same clips. Within each speaker and method, pool absolute
  errors of all matched word start/end boundaries in those clips; their mean is
  that speaker's MAE. Each speaker then contributes one paired observation.
  The methods can match different numbers of words; record both denominators.
- Test baseline-minus-proposed MAE with the exact two-sided Wilcoxon signed-rank
  sign-permutation distribution. Discard zero differences (Wilcox convention),
  average ranks for ties, and retain ties in the exact null distribution. Compute
  differences first and round them to 9 decimal places in milliseconds solely
  to avoid subtraction-roundoff artifacts in ranking. Keep unrounded means too.
- The main implementation uses dynamic programming on doubled integer ranks.
  Independently verify it using SciPy's exhaustive sign permutations, not its
  asymptotic approximation or the tie-free exact shortcut.
- Clip-level tests remain as originally recorded, separately labelled. The new
  speaker tests have a different experimental unit and are not replacements
  hidden inside the original manifests. The signed-rank null concerns a symmetric
  difference distribution centered at zero; this is not proof of perceptual benefit.

## Confidence intervals and descriptive breakdowns

- Report word/phone MAE and Acc@20ms, with 95% percentile CIs from 2,000 speaker
  cluster bootstrap resamples (seed 42). Pool boundary sums/counts within each
  resampled speaker; use the frozen threshold `20 + 1e-4` milliseconds.
- Verify point values and existing MAE CIs against the frozen summaries. Acc@20ms
  CIs are additional results. Distinguish original coverage conditional on scoring
  success from coverage over all reference tokens in attempted valid clips.
- Describe start/end errors, signed bias, folded phone labels and broad phonetic
  groups; word length bins 0 / 1–3 / 4–6 / 7+ alphabetic characters in the normalized
  reference; reference word duration bins <100 / 100–200 / 200–400 / >=400 ms.
  The 0 bin covers any nonalphabetic tokens. All bins are retained with counts. These are descriptive, not additional
  significance tests. Silences/closures follow the frozen phone folding rules.
- List the ten worst successfully scored clips per mode, with failures in a
  separate list. Do not discard outliers. Do not publish reference transcripts.
- Plot full word-error ECDFs (symlog axis including zero), speaker improvements,
  start/end MAE, reliability rejection curves, phone groups and word duration.
  Retention curves describe selected remaining words, not manual correction.

## Independent verification and delivery

Export a local boundary ledger with mode, clip/speaker, tier, start/end, matched
prediction/reference indices, reference phone label/duration/length, and signed
error. Phone indices refer to the frozen folded sequences. Verify ledger values
against saved timestamps, aggregate them separately, check exact p-values with
SciPy and CIs with direct cluster resampling, and validate the plot files.

Libraries for checking/rendering run in an isolated environment: NumPy 2.4.6,
SciPy 1.17.1, Matplotlib 3.11.2, Pillow 13.0.0. The main project lockfile is not
changed. Figures are exported in English and Russian as 300-dpi PNG and vector
PDF. Version the summaries, verification report, tables and figures; keep the
large boundary ledger local, hash it in the analysis manifest.

Sources for the statistical convention:
[SciPy Wilcoxon documentation](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.wilcoxon.html)
and [PermutationMethod](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.PermutationMethod.html).
SciPy documents both subtraction-roundoff issues and the need for permutation
evaluation when ties or zeros occur. Independent verification uses the installed,
recorded SciPy version with an explicit exhaustive permutation configuration.
