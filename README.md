# Local Subtitle Alignment Workbench

An offline subtitle synchronization pipeline that produces word- and phone-level timestamps for educational lecture audio on a consumer laptop. Author: Askar Nurym (Astana IT University).

The reference pipeline is: Silero-VAD → Faster-Whisper ASR → coarse word-level anchoring of the known transcript (banded sequence alignment, scenario A) → pause-anchored chunking → forced alignment (Montreal Forced Aligner, Kaldi GMM-HMM, with speaker adaptation, G2P for out-of-vocabulary words and boundary fine-tuning) → global monotonic reconciliation → WebVTT, schema.org JSON-LD and SHA-256 manifests. No step is skipped and no engine silently falls back to another.

## Pipeline

```
 Audio (16 kHz mono PCM16 WAV)        [optional] known transcript (scenario A)
        │                                        │
        ▼                                        │
 1. Silero-VAD pauses (strict: a VAD error stops the run)
        │                                        │
        ▼                                        │
 2. Faster-Whisper large-v3 word timestamps (GPU via CTranslate2 when available)
        │                                        │
        ▼                                        ▼
 3. Scenario A: banded word-sequence alignment of transcript ↔ ASR words
    (coarse "downsample-then-align" stage; anchors + interpolation, stats reported)
    Scenario B: ASR words are used directly
        │
        ▼
 4. Pause-anchored chunking (≤ 30 s, 0.5 s overlap padding)
        │
        ▼
 5. Forced alignment of all chunks in ONE call
    ├─ mfa : Montreal Forced Aligner (per-speaker corpus, --g2p_model_path, --fine_tune)
    └─ ctc : torchaudio MMS_FA CTC trellis (baseline; explicit choice only)
        │
        ▼
 6. Global monotonic reconciliation → WebVTT karaoke, JSON-LD, manifest
```

| Module | Responsibility |
| --- | --- |
| `asr.py` | Faster-Whisper ASR and Silero-VAD; CUDA detection through CTranslate2 and registration of pip-installed cuBLAS/cuDNN DLLs on Windows |
| `anchoring.py` | Coarse alignment of a known transcript to ASR words (banded DP over words) |
| `chunker.py` | Pause-anchored chunk partitioning and seam reconciliation |
| `mfa_wrapper.py` | MFA corpus staging (one `mfa align` call for many utterances) and TextGrid parsing |
| `aligner.py` | `ForcedAligner` facade: batch alignment (`align_requests`) and strict single-recording alignment |
| `pipeline.py` | `prepare_alignment_job` (stages 1-4) and `run_speech_pipeline` (complete pipeline + export) |
| `metrics.py` | Boundary MAE, Acc@20ms, cluster bootstrap CI, paired Wilcoxon + Holm |
| `phone_sets.py` | Folding of TIMIT/Buckeye/ARPAbet phones to the 39-phone set |
| `corpora.py`, `buckeye.py` | TIMIT `.wrd/.phn`, Buckeye native `.words/.phones` (clip segmentation), TextGrid loaders |
| `api.py` | FastAPI service (`/health`, `/info`, `/align-speech`) |

## Evaluation status

- **No citable results exist yet.** Earlier pilot runs were discarded: their references were MFA alignments and the proposed mode received the reference transcript while the baseline did not. See `docs/IMPROVEMENT_PLAN.md`.
- **Metrics (Individual Master's Plan):** mean absolute boundary error (word and phone level, start and end boundaries) with cluster bootstrap 95% CI, and the share of boundaries within 20 ms. Coverage (matched reference words) is reported next to every mode.
- **Benchmark modes:** scenario B (no transcript): `B0_whisper`, `B1_whisper_ctc`, `B2_proposed`; scenario A (transcript known): `A1_ctc`, `A2_proposed`. Proposed vs. baseline comparisons are paired by utterance ID.
- **Reference corpora:** gold = TIMIT (free NLTK sample, or full LDC93S1) and Buckeye (free, registration); silver = LibriSpeech test-clean and L2-ARCTIC (their boundaries come from forced alignment and are reported as agreement, not accuracy).
- **Synthetic self-test:** `--offline-synthetic` simulates predictions to test metric and table code. It never runs models and is never citable.

## Installation

Python 3.11 or 3.12 and `uv`.

```sh
uv sync --locked                       # base (DTW, exporters, CLI, benchmark harness)
uv sync --locked --extra speech        # Faster-Whisper, torch/torchaudio, CUDA 12 runtime for CTranslate2
uv sync --locked --extra api           # FastAPI service
uv sync --locked --all-extras
```

### Montreal Forced Aligner (required for the proposed pipeline)

MFA is installed with Conda (it is not available as a wheel):

```powershell
conda create -n mfa -c conda-forge montreal-forced-aligner
conda activate mfa
mfa model download acoustic english_us_arpa
mfa model download dictionary english_us_arpa
mfa model download g2p english_us_arpa
```

`mfa` must be on `PATH` (or installed under `~/.mfa_env`). If `--engine mfa` is requested and MFA is missing, the run stops with an error.

See `docs/RUNBOOK.md` for GPU verification and the full benchmark procedure.

## Usage

```sh
# Scenario B: no transcript (Whisper output is aligned)
uv run subtitle-workbench align-speech lecture.wav -o out_b/

# Scenario A: known transcript
uv run subtitle-workbench align-speech lecture.wav -o out_a/ --transcript-file lecture.txt
uv run subtitle-workbench align-speech clip.wav -o out_c/ --transcript-text "known text"

# Baseline engine (explicit)
uv run subtitle-workbench align-speech lecture.wav -o out_ctc/ --engine ctc

# Audio-to-audio timing transfer (separate DTW tool)
uv run subtitle-workbench align-dtw ref.wav target.wav cues.json -o out_dtw/

# REST API
uv run uvicorn subtitle_workbench.api:app --host 127.0.0.1 --port 8000
```

## Verification

```sh
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked pytest          # unit tests never load real models (see tests/conftest.py)
uv run --locked python -m build --wheel --no-isolation
```

## Hardware

Target: AMD Ryzen 9 5900HX, 16 GB RAM, NVIDIA RTX 3050 Laptop GPU (4 GB), Windows 11. Whisper runs on the GPU through CTranslate2; it is unloaded before alignment. MFA runs on the CPU. Everything runs locally without network services.

## License

MIT License. See [LICENSE](LICENSE). Corpora keep their own licenses (TIMIT sample: CC BY-NC-SA; Buckeye: non-commercial).
