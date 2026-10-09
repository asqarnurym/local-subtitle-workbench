# Local Subtitle Alignment Workbench

An English-only scientific module for transferring checked subtitle timings from a
reference audio track to a related target audio track. It runs locally on the CPU
and exports WebVTT, semantic JSON-LD and an audit manifest. Author: Askar Nurym.

The implemented increment is audio-to-audio DTW timing transfer. Reference cues
must already match the reference recording. It does not recognize speech or
align arbitrary text to speech. Whisper-based transcription and a word alignment
backend remain proposed components of the wider workbench.

## Architecture

| Module | Responsibility | Contract |
| --- | --- | --- |
| `models.py` | Typed cues and configuration | Finite, ordered, non-overlapping English cue metadata |
| `audio.py` | PCM WAV reading and frame features | Mono PCM16, 16 kHz; 20 ms hop, 40 ms window |
| `dtw.py` | Banded dynamic programming | Monotone complete path; deterministic diagonal/up/left ties |
| `pipeline.py` | Time interpolation and manifest | Validated cues, SHA256 inputs, configuration and runtime metrics |
| `export.py` | Output formats | Escaped WebVTT payloads and schema.org `VideoObject`/`Clip` |
| `cli.py` | Local command interface | Clear validation errors, exit code 2, no overwrite |

The feature vector combines standardised log RMS energy with a low-weight
spectral centroid. DTW compares squared feature distances inside a band around
the scaled diagonal. Each reference frame maps to the median target frame on its
path; cue boundaries interpolate this monotone mapping. Endpoint anchoring
includes the complete recording. See [algorithm and contracts](docs/ALGORITHM.md).

## Installation

Requirements: Python 3.11 or 3.12 and `uv`. Initial dependency installation needs
package access; subsequent processing has no network, model downloads or API
calls. Python 3.13 is outside the tested compatibility range.

```sh
uv sync --locked
uv run --locked subtitle-workbench --help
```

`uv.lock` fixes dependency versions and distribution hashes. Run with a matching
Python interpreter: `uv sync --locked --python 3.11` or `--python 3.12`. The
package can also be installed from the CI wheel with `pip install wheel-file.whl`
after NumPy is available; the application has no development-tool dependency.

## Reproduce the synthetic demonstration

Use fresh output directories; the tool deliberately rejects existing output files.

```sh
uv run --locked python -m subtitle_workbench.demo --output demo-input
uv run --locked subtitle-workbench --reference demo-input/reference.wav --target demo-input/target.wav --cues demo-input/cues.json --output demo-output
uv run --locked python scripts/benchmark.py --oracle demo-input/oracle.json --timeline demo-output/timeline.jsonld
```

The six generated bursts are synthetic signals, not human speech. The target
transform is `target_time = 0.24 + 1.08 * reference_time`; the oracle records all
twelve expected cue boundaries. The benchmark reports mean/max absolute timing
error and the percentage inside a ±50 ms collar. These values verify this
controlled transform only. They do not demonstrate recognition quality or the
project's planned word-level speech target.

| Output | Purpose |
| --- | --- |
| `subtitles.vtt` | Millisecond-rounded subtitle cue timings with escaped text |
| `timeline.jsonld` | English `VideoObject` with `Clip` start/end offsets in seconds |
| `alignment-path.json` | Complete reference/target frame-index path for numerical audit |
| `manifest.json` | Input/output hashes, code fingerprint, parameters, versions, dimensions, path cost and stage RTF |

The JSON-LD context is a URI string; serialization never fetches it. No video
is processed in this increment; semantic metadata accompanies the corresponding
video asset and uses its audio track for numerical alignment.
Its local URN uses the target audio hash; this is an association identifier,
not a claim that a WAV file is a video or a publishable video download.

## Reference cue input

```json
{
  "language": "en",
  "cues": [{"id": "cue-1", "start": 0.66, "end": 1.06, "text": "Example English subtitle."}]
}
```

Times are seconds, IDs are unique ASCII letters/digits/underscore/hyphen, and
cues must be non-empty, ordered and non-overlapping within reference duration.
The language field declares English; the module does not perform language
detection. Strict PCM input avoids silent resampling. Convert unsupported
recordings explicitly before running and record the conversion parameters.

## Verification and continuous integration

```sh
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked pytest
uv run --locked python -m build --wheel --no-isolation
```

The [CI workflow](.github/workflows/ci.yml) runs on pushes and pull requests with
Python 3.11/3.12, performs these gates, installs the built wheel into a separate
environment, and runs the synthetic CLI demonstration with an offline socket
guard. Wheel and demonstration outputs are uploaded as job artifacts. A workflow
file is configuration; only a successful GitHub Actions run demonstrates the
hosted pipeline. GitHub run URLs are available from the repository's Actions tab.
The workflow pins uv 0.12.24, action revisions and the locked hatchling backend.
The build uses the restored environment rather than a separately resolved backend.
The smoke environment restores runtime dependencies directly from `uv.lock`
before installing the wheel offline with `--no-deps`. Dependency bootstrap may
use the package network; actual wheel processing runs with network sockets blocked.

Issues should include expected/actual behaviour, a minimal licensed input,
manifest configuration and input hashes. See [development process](docs/DEVELOPMENT.md)
and [verification protocol](docs/VALIDATION.md).

## Boundaries and next increment

| Current limitation | Engineering consequence / next step |
| --- | --- |
| Corresponding recordings and correct reference cues required | Evaluate independently timed English speech pairs before general use |
| Default 3,000 frames, 2,000,000 cells | At 20 ms hop, use segments of at most 60 seconds; segment long lectures explicitly |
| RMS/centroid features | Repeated speech, edits, long silence and changed acoustic conditions can confuse DTW |
| No ASR, phoneme model or confidence threshold | Add a separately verified local transcription/forced-alignment backend |
| No GUI/FastAPI service, SRT or streaming | CLI and WebVTT/JSON-LD are the implemented contract |
| Path cost and stage RTF | Neither is WER, ground-truth timing error or whole-system latency |

The proposed hardware baseline remains Ryzen 9 5900HX, 16 GB RAM and RTX 3050
Laptop 4 GB. This small increment uses NumPy on the CPU; GPU memory and Whisper
performance are not measured. The 497-hour, 50-day project estimate remains a
planning baseline, not an elapsed development log.

MIT license. See [LICENSE](LICENSE).
