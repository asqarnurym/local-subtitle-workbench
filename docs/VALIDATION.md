# Verification protocol

| Check | Input / metric | What it establishes |
| --- | --- | --- |
| DTW unit oracle | Identical and expanded known feature sequences | Path recurrence, endpoints and monotonicity |
| Cue contracts | NaN/infinity/bool, overlap, range, IDs, controls | Invalid metadata is rejected |
| WAV contracts | Wrong rate/stereo/width, silence, truncation, excess frames | Media/resource boundary behaves explicitly |
| Export | Half-up rounding, carry to hours, escaped payloads, JSON-LD types | Serialization and timing units |
| CLI integration | Synthetic delayed/stretched waveform plus exact oracle | Full package path transfers controlled cue boundaries |
| Installed wheel | Separate environment, no source import, socket guard | Distributable package works without network processing |

The separate smoke environment first restores runtime dependencies from
`uv.lock` using `uv sync --locked --no-dev --no-install-project`. This installation
step may use package access. The local built wheel is then installed with
`uv pip install --offline --no-deps`; processing starts only after a socket guard
has disabled network creation and connection. Locked direct distribution URLs
avoid relying on cached registry metadata during the wheel installation.

Generate the synthetic fixtures from the committed generator, retain their SHA256
hashes and run the documented benchmark command. Default transformation: 240 ms
delay and 1.08 time scale, six cues and twelve boundaries. The local acceptance
bound is maximum error <=50 ms for this fixture. The test also checks unchanged
audio. This is a regression tolerance for synthetic data, not an official speech
accuracy result.

The manifest records input file names/hashes, complete configuration, package,
Python and NumPy versions, platform, evaluated cells, path length, durations,
feature frame counts and path cost. The complete
frame path is retained; the manifest hashes all three output data files. A source
fingerprint always identifies package code; a local repository revision/dirty
flag is included when available. Installed wheels retain the source fingerprint.
Hashes and parameters identify reproducible inputs. Outputs are deterministic
apart from platform metadata in the manifest.

For the next speech benchmark, use licensed English recordings and independently
annotated cue/word boundaries. Record annotator protocol and inter-annotator
agreement, sample-rate conversion, model versions and hardware. Report mean
absolute boundary error (MAE) and the share of boundaries within 20 ms, as
defined in the Individual Master's Plan. It has not been evaluated by this
synthetic cue-boundary test. No accessibility user study is claimed.
