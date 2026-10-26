# Forensic Integrity Audit Report: Milestone 1 Iteration 2

**Auditor**: auditor_m1_iter2_1  
**Target**: Amended commit daefa6a on branch `feature/increment-6-speech-benchmark`  
**Parent Orchestrator**: d7780ee7-0d12-43b1-8cad-0dd6f3550ad6  
**Profile**: General Project  
**Integrity Mode**: Development  
**Discipline**: Pure ASCII formatting only ([+], [-], [*], [OK], [FAIL], ->, |)  
**Verdict**: CLEAN  

---

## 1. Observation

1. **Commit and Working Tree Inspection:**
   - Command: `git status`
     * Branch: `feature/increment-6-speech-benchmark`
     * Working tree: Clean for all source, test, script, and documentation directories. Only `.agents/teamwork/` metadata modified/untracked.
   - Command: `git show --stat daefa6a`
     * Commit: `daefa6a3e0804e6903eda837323c6b92d490da49`
     * Commit Message: `feat(benchmark): implement reference corpora loaders and boundary evaluation metrics`
     * Changed Files:
       - `scripts/download_reference_corpora.py` (78 insertions)
       - `src/subtitle_workbench/__init__.py` (34 insertions)
       - `src/subtitle_workbench/corpora.py` (624 insertions)
       - `src/subtitle_workbench/metrics.py` (449 insertions)
       - `tests/test_benchmark.py` (601 insertions)
       - `tests/test_metrics_stress.py` (247 insertions)
       - Total: 6 files changed, 2033 insertions(+).

2. **Source Code and Algorithm Verification:**
   - In `src/subtitle_workbench/corpora.py`:
     * Line 64: `if len(parts) != 3:` in `parse_timit_phn` strictly rejects lines with token counts other than 3, raising `CorpusFormatError`.
     * Line 140: `if len(parts) != 3:` in `parse_timit_wrd` strictly rejects lines with token counts other than 3, raising `CorpusFormatError`.
     * Lines 60-62 & 136-138: Empty and whitespace-only lines are safely bypassed via `if not stripped: continue`.
   - In `src/subtitle_workbench/metrics.py`:
     * Line 32: `BOUNDARY_EPSILON_MS: float = 1e-4` defined as a precision tolerance.
     * Lines 257-259:
       ```python
       acc_20 = float(np.mean(errors <= (20.0 + BOUNDARY_EPSILON_MS)) * 100.0)
       acc_50 = float(np.mean(errors <= (50.0 + BOUNDARY_EPSILON_MS)) * 100.0)
       acc_100 = float(np.mean(errors <= (100.0 + BOUNDARY_EPSILON_MS)) * 100.0)
       ```
     * Lines 366-368: Exact standard normal CDF helper using `math.erf`:
       ```python
       def _standard_normal_cdf(x: float) -> float:
           return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))
       ```
     * Lines 435-440: Wilcoxon continuity correction deviation non-negative clamp:
       ```python
       deviation = max(0.0, abs(w_stat - mean_w) - 0.5)
       z = deviation / math.sqrt(var_w) if var_w > 0.0 else 0.0
       p_val = 2.0 * (1.0 - _standard_normal_cdf(abs(z)))
       p_val = max(0.0, min(1.0, float(p_val)))
       ```
   - In `tests/test_metrics_stress.py`:
     * All 10 stress tests pass cleanly with 0 `@pytest.mark.xfail` markers.
   - In `tests/test_benchmark.py`:
     * All 19 benchmark unit tests pass cleanly in 0.73s.

3. **Byte-by-Byte Pure ASCII & Zero-Emoji Verification:**
   - Scanned byte values across all 6 files in commit `daefa6a` and the commit message:
     * `src/subtitle_workbench/corpora.py`: 0 non-ASCII bytes (`byte <= 127`).
     * `src/subtitle_workbench/metrics.py`: 0 non-ASCII bytes (`byte <= 127`).
     * `tests/test_benchmark.py`: 0 non-ASCII bytes (`byte <= 127`).
     * `tests/test_metrics_stress.py`: 0 non-ASCII bytes (`byte <= 127`).
     * `scripts/download_reference_corpora.py`: 0 non-ASCII bytes (`byte <= 127`).
     * `src/subtitle_workbench/__init__.py`: 0 non-ASCII bytes (`byte <= 127`).
     * Commit message `daefa6a`: 0 non-ASCII bytes (`byte <= 127`).

4. **Pre-populated Verification Artifacts:**
   - Searched for pre-populated `*.log`, `*result*`, and `*output*` artifacts outside virtual environment and git directories.
   - Result: 0 pre-populated result artifacts found.

5. **Automated Verification Gates:**
   - Command: `uv run --locked pytest`
     * Result: `666 passed, 1 skipped in 16.01s` (Exit code: 0).
   - Command: `uv run --locked ruff check .`
     * Result: `All checks passed!` (Exit code: 0).
   - Command: `uv run --locked ruff format --check .`
     * Result: `361 files already formatted` (Exit code: 0).
   - Command: `uv run --locked pytest tests/test_benchmark.py tests/test_metrics_stress.py -v`
     * Result: `29 passed in 2.99s` (Exit code: 0).

6. **Adversarial Empirical Stress Verification:**
   - Parser token count boundary tests:
     * TIMIT lines with 1, 2, 4, 5 tokens all raise `CorpusFormatError` with `expected 3 tokens, got {n}`.
   - IEEE-754 precision boundary tests across base offsets (0s, 1s, 10s, 100s, 3600s):
     * Exact 320 samples (20.0 ms) -> Acc@20ms == 100.0%.
     * Excess 321 samples (20.0625 ms) -> Acc@20ms == 0.0%.
     * Exact 800 samples (50.0 ms) -> Acc@50ms == 100.0%.
     * Excess 801 samples (50.0625 ms) -> Acc@50ms == 0.0%.
   - Wilcoxon exact null symmetry tests:
     * Even pairs $N \in [2, 4, 6, 8, 10, 20]$ with symmetric differences evaluated to $p = 1.0$ and $\text{Cliff's Delta} = 0.0$.

---

## 2. Logic Chain

1. From Observation 1 and 2, the three defects identified during Iteration 1 review were:
   a) Lenient token count checking (`< 3` rather than `!= 3`) in `corpora.py`.
   b) IEEE-754 binary64 rounding discrepancy at the exact 20.0 ms sample boundary in `metrics.py`.
   c) Wilcoxon continuity correction depression under exact null symmetry in `metrics.py`.
2. As verified in Observation 2, the modifications in commit `daefa6a` provide genuine algorithmic corrections:
   - Line token validation now uses `len(parts) != 3`, properly rejecting both under-tokenized and over-tokenized lines.
   - `BOUNDARY_EPSILON_MS = 1e-4` absorbs ULP rounding at the exact boundary while being 625 times smaller than a single 16 kHz sample ($0.0625$ ms), preventing false negatives and false positives.
   - Clamping `deviation = max(0.0, abs(w_stat - mean_w) - 0.5)` guarantees that deviations $\le 0.5$ yield $z = 0.0 \implies p = 1.0$, completely resolving the null symmetry depression anomaly.
3. From Observation 3, 100% pure ASCII byte compliance was independently proven across all modified code, comments, docstrings, tests, and the git commit message, strictly adhering to the project Zero-Emoji rule.
4. From Observation 4, no pre-populated logs or fabricated result artifacts exist in the repository.
5. From Observation 5, all automated verification gates pass without error (666 tests passed, 0 ruff lint errors, 0 ruff format errors).
6. From Observation 6, adversarial stress tests confirmed that the implementations withstand edge cases, high base timestamps, and exact mathematical boundaries.
7. Therefore, the work product satisfies all integrity and functional requirements without facade implementations, hardcoded shortcuts, or regressions.

---

## 3. Caveats

1. The test suite skips 1 test (`tests/test_asr.py::test_whisper_transcriber_real_model_optional`) because `faster-whisper` and CUDA model weights are not installed in the standard CPU test environment. This is the intended offline isolation behavior defined in the project configuration.
2. The empirical benchmark suite was verified using the offline synthetic generator (`stage_synthetic_benchmark`). Evaluation against full proprietary TIMIT (LDC93S1) and Buckeye speech corpora requires external licensed assets.

---

## 4. Conclusion

Amended commit `daefa6a` on branch `feature/increment-6-speech-benchmark` is fully compliant with all architectural, mathematical, and integrity standards:
- [OK] Hardcoded test results: None detected.
- [OK] Facade implementations: None detected (all methods use genuine dynamic programming, ranking, and statistical calculations).
- [OK] Pre-populated artifacts: None detected.
- [OK] Zero-Emoji / Non-ASCII discipline: Pure ASCII verified byte-by-byte (0 non-ASCII bytes).
- [OK] Automated test suite: 100% pass rate (666 passed, 1 skipped).
- [OK] Linter and formatter: 0 errors across 361 files.
- [OK] Boundary condition fixes: Validated empirically across all target edge cases.

Forensic Verdict: **CLEAN**

---

## 5. Verification Method

To independently reproduce the forensic audit:

1. **Verify git commit and working tree:**
   ```powershell
   git status
   git log -n 1 --stat daefa6a
   ```

2. **Verify byte-by-byte pure ASCII compliance:**
   ```powershell
   uv run python -c "files = ['src/subtitle_workbench/corpora.py', 'src/subtitle_workbench/metrics.py', 'tests/test_benchmark.py', 'tests/test_metrics_stress.py', 'scripts/download_reference_corpora.py', 'src/subtitle_workbench/__init__.py']; [print(f'{f}: OK') for f in files if not any(b > 127 for b in open(f, 'rb').read())]"
   ```

3. **Run automated test suite and linter:**
   ```powershell
   uv run --locked pytest
   uv run --locked ruff check .
   uv run --locked ruff format --check .
   ```

4. **Run targeted benchmark and stress tests:**
   ```powershell
   uv run --locked pytest tests/test_benchmark.py tests/test_metrics_stress.py -v
   ```

5. **Run adversarial boundary checks:**
   ```powershell
   uv run python -c "from subtitle_workbench.metrics import evaluate_alignment_boundaries, paired_wilcoxon_test; from subtitle_workbench.models import WordToken; ref = [WordToken(id='w0', text='a', normalized='a', start=1.0, end=1.5, confidence=1.0)]; pred = [WordToken(id='w0', text='a', normalized='a', start=1.020, end=1.520, confidence=1.0)]; res = evaluate_alignment_boundaries(pred, ref); assert res.acc_20ms == 100.0; w = paired_wilcoxon_test([11.0, 9.0], [10.0, 10.0]); assert w.p_value == 1.0; print('[OK] Verified')"
   ```

### Invalidation Conditions
- Any occurrence of non-ASCII bytes in project code, comments, docstrings, or commit messages.
- Any test failure in `pytest`.
- Any parse of TIMIT lines with != 3 tokens without raising `CorpusFormatError`.
- Exact 20.0 ms shift failing to achieve Acc@20ms == 100.0%.
- Wilcoxon continuity correction yielding p < 1.0 on symmetric null samples.
