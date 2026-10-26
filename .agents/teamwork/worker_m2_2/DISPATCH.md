## 2026-10-26T04:41:17Z
You are worker_m2_2. Your working directory is C:\Users\nurym\Desktop\local-subtitle-workbench\.agents\teamwork\worker_m2_2.
Your parent orchestrator conversation ID is d7780ee7-0d12-43b1-8cad-0dd6f3550ad6.

MANDATORY FIRST STEP:
Read C:\Users\nurym\Desktop\local-subtitle-workbench\.agents\teamwork\ORIGINAL_REQUEST.md under header ## 2026-10-26T03:14:07Z.
Read C:\Users\nurym\Desktop\local-subtitle-workbench\.agents\teamwork\orchestrator_3\DISPATCH.md.
Read C:\Users\nurym\Desktop\local-subtitle-workbench\.agents\teamwork\orchestrator_3\SCOPE.md.
Read C:\Users\nurym\Desktop\local-subtitle-workbench\.agents\teamwork\reviewer_m2_1\handoff.md.
Read C:\Users\nurym\Desktop\local-subtitle-workbench\.agents\teamwork\challenger_m2_1\handoff.md.

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

ZERO-EMOJI DISCIPLINE:
Strictly no emojis or graphical Unicode icons anywhere in code, comments, docstrings, logs, git commits, or reports. Pure clean ASCII formatting only ([+], [-], [*], [OK], [FAIL], ->, |).

MILESTONE 2 ITERATION 2 TASKS:
1. Fix Real-Mode Pipeline Output Deserialization in `scripts/speech_benchmark.py`:
   - In lines ~615-640, `run_speech_pipeline(utt.wav_path, output_dir=p_tmp, engine=...)` returns the manifest dictionary and writes `alignment_raw.json` inside `p_tmp`.
   - Read `raw_file = Path(p_tmp) / "alignment_raw.json"`.
   - Deserialize JSON into `WordToken` instances with nested `PhonemeCue` instances:
     ```python
     raw_data = json.loads(raw_file.read_text(encoding="utf-8"))
     pred_words = []
     for wd in raw_data.get("words", []):
         word_phones = [
             PhonemeCue(
                 phoneme=pd["phoneme"],
                 start=float(pd["start"]),
                 end=float(pd["end"]),
                 confidence=float(pd.get("confidence", 1.0)),
             )
             for pd in wd.get("phonemes", [])
         ]
         pred_words.append(
             WordToken(
                 id=wd["id"],
                 text=wd["text"],
                 normalized=wd["normalized"],
                 start=float(wd["start"]),
                 end=float(wd["end"]),
                 confidence=float(wd.get("confidence", 1.0)),
                 phonemes=word_phones,
                 char_start=wd.get("char_start"),
                 char_end=wd.get("char_end"),
             )
         )
     pred_phones = [p for w in pred_words for p in w.phonemes]
     ```
   - In line ~603, construct `WhisperTranscriber(device=None if device == "auto" else device, compute_type="int8")`.

2. Fix Memory Profiling Fallback in `get_peak_host_ram_mb()`:
   - Change `except ImportError:` to `except Exception:` on the psutil block so any runtime failure or missing attribute safely falls back to Tier 2 Windows ctypes.

3. Fix CLI Exit Codes and Argument Validation in `scripts/speech_benchmark.py`:
   - Validate `--seed >= 0` and `--bootstrap-resamples >= 1`.
   - In `main()`: catch `(BenchmarkError, ValueError, Exception)` and exit with code 1 (`sys.stderr.write(f"error: {e}\n"); return 1`), ensuring exit code 2 is reserved strictly for argparse syntax errors.

4. Unit & Integration Tests in `tests/test_benchmark.py`:
   - Add integration test for the real production execution path (`run_benchmark(corpus="synthetic", offline_synthetic=False, ...)`) using monkeypatching of `run_speech_pipeline` to write fixture `alignment_raw.json` or mock transcriber/aligner, ensuring word and phoneme extraction from `alignment_raw.json` is verified.
   - Add test verifying `--seed -1` exits with code 1.

5. Acceptance & Amend Commit:
   - Run `uv run --locked pytest tests/test_benchmark.py` (must pass 100%).
   - Run `uv run python scripts/speech_benchmark.py --offline-synthetic --output-dir dist/benchmark_demo`.
   - Run `uv run --locked pytest` (all tests pass).
   - Run `uv run --locked ruff check .` and `uv run --locked ruff format --check .`.
   - Amend git commit 2 on `feature/increment-6-speech-benchmark`:
     `git add scripts/speech_benchmark.py tests/test_benchmark.py`
     `git commit --amend -m "feat(benchmark): implement clustered bootstrap, paired Wilcoxon tests, and benchmark runner"`

OUTPUT:
Write detailed implementation and verification report to `C:\Users\nurym\Desktop\local-subtitle-workbench\.agents\teamwork\worker_m2_2\handoff.md`.
Send completion message to parent orchestrator (d7780ee7-0d12-43b1-8cad-0dd6f3550ad6).
