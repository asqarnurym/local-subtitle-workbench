# Frozen experiment evidence

Audited on **2026-11-01** on the source-of-truth laptop. This archive implements
step E1c of the improvement plan. It preserves completed runs; it does not run
models, recompute accuracy, or add new significance tests.

## Versioned evidence

| Run | Evaluation set | Execution revision | Archived files |
| --- | --- | --- | --- |
| [TIMIT](../reports/timit/benchmark_results.json) | NLTK sample: 160 utterances, 16 speakers | `bench-frozen-20261029` / `4da927644e83c7bd1e3a5ab9054040e831289132` | Original results, original manifest, three LaTeX tables |
| [Buckeye](../reports/buckeye/benchmark_results.json) | 999 clips, 20 test speakers; one empty-audio clip excluded | `bench-frozen-20261029c` / `c6ef73824b140aec8fe1ca8b8f9d3e38c1866518` | Original results, original manifest, three LaTeX tables |

The split, fixed samples, BRQE CV/final reports and model files were already
versioned. The new [audit inventory](../reports/frozen_evidence_audit_20261101.json)
records exact file hashes, the checks performed, and a snapshot of the local
reference annotation hashes. The [claim ledger](CLAIM_LEDGER.csv) continues to use
the approved wording of CLAIM-101 through CLAIM-106. All six claims' evidence
paths now resolve to versioned files.

Only the selected summaries, manifests, tables and audit inventory are newly
included from `reports/`. Per-clip `benchmark_predictions.json` and
`benchmark_utterances.json`, training-run outputs, corpora and pilot outputs remain
local and ignored. **A Git clone is not a complete backup of the experiment.**
Keep these local files: the next analysis needs them. The original manifests
retain their hashes even though these large outputs are not in Git.

## Checks performed

- All three output hashes in each original manifest match the local files: nine
  files across TIMIT, Buckeye test and the BRQE training-data run.
- All **4,159 input audio hashes** match: 160 TIMIT, 999 Buckeye test and 3,000
  Buckeye train. Sample hashes, the split hash, BRQE weight and constant-offset
  hashes match their recorded values.
- Run revisions match their tags (or the recorded completion revision for the
  training-data run). Recorded execution worktrees for these three runs are clean.
  Package source fingerprints are reconstructed from Git using the observed
  per-file LF/CRLF styles; the audit records the styles and a normalized-LF hash.
- Configurations agree between each summary and manifest. Per-mode row and
  prediction IDs agree with the input IDs; failure counts agree with summaries.
  This covers **1,440 TIMIT**, **8,991 Buckeye test** and **6,000 train** metric rows.
- Buckeye train/test speaker sets are disjoint (20 each), evaluated IDs equal the
  fixed sample minus the recorded empty clip, and CV held-out folds partition
  the training speakers. The excluded clip is still a header-only WAV.
- Saved BRQE weights match both evaluation runs, the model metadata and the final
  training report. Metadata also agrees on the training sample and split.
- All **six saved LaTeX tables** reproduce from their corresponding summaries
  using the current table generator (text comparison with newline normalization).
- The six `MODEL_EXECUTION` ledger rows have valid CSV structure and existing
  evidence paths. This check resolves sources; it does not re-evaluate every
  numeric statement or approve new wording.

`.gitattributes` disables newline conversion for frozen evidence, samples and
model JSON metadata. Nine already tracked JSON blobs consequently acquire their
original CRLF bytes in this commit; their JSON content and on-disk bytes are
unchanged. Old execution tags are retained. This matters because manifests hash
file bytes, and automatic Git conversion would otherwise invalidate those hashes
after a checkout on another platform.

## Limits of the audit

The outcome is **PASS_WITH_LIMITATIONS**, not an assertion of complete historical
reproducibility or a new scientific result.

1. **Reference annotation hashes were absent from the original manifests.** The
   inventory snapshots **4,319 current reference files** (`.wrd`, `.phn`,
   `.TextGrid`) on 2026-11-01. These hashes protect subsequent analysis against
   unnoticed changes, but cannot prove that annotations were unchanged since the
   October runs. Original manifests and timestamps have not been rewritten.
2. The package fingerprint covers `src/subtitle_workbench/*.py`, not benchmark
   scripts, the lockfile or externally cached model weights. The recorded Git
   revision identifies tracked scripts and dependency declarations; exact hashes
   of the historical Whisper/CTC/MFA cached weights were not recorded.
3. **The final BRQE training report records a dirty worktree.** That flag is
   preserved. Its source fingerprint agrees with the training/CV revision, and the
   saved model hash matches both evaluation manifests, but the report cannot
   identify all historical uncommitted changes. This audit does not retroactively
   certify a clean original final training execution. A subsequent clean control
   run exactly reproduced the saved model (R2 below).
4. The BRQE training-data run recorded its Git revision at completion; the earlier
   start revision and this limitation are already described in plan §6.5.
5. Statistical tests currently use clip-level pairs, whereas confidence intervals
   cluster by speaker. Speaker-level tests and detailed error analysis remain the
   next work item. Coverage and failures must accompany boundary-accuracy claims.
6. Older strategy documents contain historical targets and untested hypotheses.
   For empirical statements use the approved ledger and these frozen runs, not
   an unverified promise in an earlier strategy document.

## Repeat the integrity audit

From the repository root on the laptop, with its local corpora and per-clip files:

```powershell
uv run --locked --all-extras python scripts/verify_frozen_evidence.py
```

The script checks the fixed October runs and compares current annotation hashes
against the committed reference snapshot. A mismatch stops the check. The baseline
and original run files are read-only. To save a separate report with the recheck
timestamp, choose an ignored destination:

```powershell
uv run --locked --all-extras python scripts/verify_frozen_evidence.py --output reports/evidence_recheck.json
```

The new report's timestamp identifies the integrity check, not a model run.
Missing local files or a mismatch stop the audit with an error. No speech model
is loaded, and no files are fetched from model hubs or corpus services.

## Implementation checks

On 2026-11-01, `ruff check .` and `pytest -m "not model"` with `--all-extras`
passed (**754 tests**). Regression tests cover byte changes caused by newline
conversion, paths escaping the repository, accidental output overwrite, and a
changed annotation being rejected without overwriting the baseline. Independent
read-only review found a missing reference-snapshot comparison; it was fixed,
tested and reviewed again before committing.

## R1: replay of the saved metrics (2026-11-01)

The [R1 report](../reports/r1_metric_replay_20261101.json) records a completed replay
of TIMIT and Buckeye from their saved predictions and current reference annotations,
after the integrity preflight. **All saved fields matched exactly**, with their
original rounding, seed 42 and 2,000 bootstrap resamples:

| Corpus | Modes | Per-clip metric rows | Clip-level statistical comparisons | Differences |
| --- | --- | --- | --- | --- |
| TIMIT | 9 | 1,440 | 7 | 0 |
| Buckeye | 9 | 8,991 | 7 | 0 |

This includes word/phone MAE, Acc@20ms, MAE confidence intervals, matched counts,
coverage, failures, reliability-head metrics and rejection curves, and the original
Wilcoxon/Holm comparison outputs. It adds no new statistical hypotheses and does
not independently validate the scoring implementation. Historical reference
hashes are still unavailable, but the saved results agree with today's references.

The replay ran from clean revision `e77772f9b9e68a679c9be480aa76e9de4b18bedf`;
the Git revision and clean status were identical at the end. It took 75.948 seconds
including preflight; none of the 4,374 protected artifact, annotation, code and
dependency files changed. No speech model was run. Before execution, ruff and
all 757 non-model tests passed. The separate R2 control training run below adds
evidence for the saved model's reproducibility.

The replay report is versioned; recomputed rows, full summaries, differences and
preflight details remain local under `reports/r1_replay_20261101/`, with their
hashes in the report. To repeat the check, choose a fresh ignored directory:

```powershell
uv run --locked --all-extras python scripts/replay_frozen_metrics.py --output-dir reports/r1_replay_recheck
```

The command requires a clean worktree. It refuses an existing output directory
and checks the original artifact and annotation hashes before replaying metrics.

## R2–R3: clean BRQE reproduction and independent checking (2026-11-01)

One control training run from clean revision
`d59d77a5623a8cab7b5a1ac235197591b13d24a9` reproduced the original model with
**EXACT_MATCH**. See the [complete reproduction report](../reports/r2_brqe_reproduction_20261101.json)
and [separate saved-model check](../reports/r2_brqe_independent_20261101.json).

The wrapper verified 15 file/declaration comparisons against the original
training revision, kept all frozen hyperparameters and seed, and used only the
same 3,000 clips from 20 training speakers. It reused saved MFA alignments;
Whisper and MFA were not rerun. Training had 382,270 matched boundaries out of
461,850. The new training report records a clean worktree; the wrapper recorded
the same clean revision at both start and end. All 7,389 protected original
artifact, annotation, training-audio, script and dependency files were unchanged.
Before this model run, ruff and all 760 non-model tests passed.

| Check | Result |
| --- | --- |
| Learned parameters and non-learned buffers | All 22 tensors equal; shape, dtype and finite values checked |
| Constant-offset rival | Equal |
| Boundary-shift head | 461,850 outputs compared; 0 differences |
| Reliability head | 461,850 outputs compared; 0 differences |
| Maximum absolute difference, either head | 0, with no numerical tolerance |
| Checkpoint file SHA-256 | Equal: `93c7c959e6232799daa646ed87d9c333cc01f898ad22e30fa03c02cbb824aa19` |

Independence here means a **separate verification process and comparison path**,
not a separately developed implementation of the neural architecture. The checker
revalidates the archive, reloads both saved checkpoints, rebuilds the train-only
features, and directly calls the frozen networks. It performs no fitting and does
not call `BRQERefiner.predict` or reuse inference outputs from the training process.
It compares both heads over all training boundaries, including unmatched ones.
The dataset loader and architecture remain the frozen implementations. Final
validation in another process also reread the model tensors and artifact hashes.

Training took 465.0 seconds; the independent check took 76.284 seconds; total
control time including integrity checks was 567.382 seconds. The recorded
environment is Python 3.11.17, NumPy 2.4.6, torch 2.14.1, torchaudio 2.11.0,
CPU training with eight torch threads. Timings are transparency records only.

The control weights and detailed logs remain local under
`reports/r2_brqe_control_20261101/`; their hashes are in the versioned report.
The two archived reports are exact byte copies of the generated reports. The
original weights, benchmark outputs, tags and approved claims were not replaced.
The old `dirty=true` is retained: the new clean run demonstrates reproducibility
of the exact saved model, rather than certifying the old worktree retrospectively.
The missing historical annotation hashes remain a documented limitation.

To repeat the control, first run the documented lint/tests and commit any changes,
then choose a fresh ignored directory:

```powershell
uv run --locked --all-extras python -X faulthandler -u scripts/reproduce_brqe.py --output-dir reports/r2_brqe_recheck
```

The independent checker can also be invoked separately on saved control weights,
using a fresh report path and a clean worktree:

```powershell
uv run --locked --all-extras python -X faulthandler -u scripts/check_brqe_reproduction.py --control-dir reports/r2_brqe_control_20261101/model --output reports/r2_brqe_control_20261101/independent_recheck.json
```
