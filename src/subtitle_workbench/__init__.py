__version__ = "0.1.0"

from .aligner import (
    ForcedAligner,
    align_chunks,
)
from .asr import (
    ASRError,
    ASRInferenceError,
    AudioFormatError,
    VRAMAllocationError,
    WhisperTranscriber,
    extract_vad_silences,
)
from .audio import (
    get_duration,
    slice_wav,
)
from .chunker import (
    ChunkingError,
    MonotonicityError,
    partition_into_chunks,
    reconcile_chunk_alignments,
)
from .ctc_aligner import (
    CTCAlignerError,
    CTCAlignerUnavailableError,
    TorchAudioAligner,
    align_ctc_trellis,
    backtrack,
    get_trellis,
)
from .export import (
    export_jsonld,
    export_karaoke_vtt,
    export_raw_alignment,
    format_vtt_timestamp,
    generate_manifest,
)
from .mfa_wrapper import (
    MFAError,
    MFAExecutionError,
    MFANotFoundError,
    MFATimeoutError,
    SubprocessRunner,
    check_mfa_available,
    parse_textgrid,
    run_mfa_batch,
)
from .models import (
    AlignmentResult,
    ASRSegment,
    AudioChunk,
    ChunkConfig,
    Config,
    Cue,
    PhonemeCue,
    WordToken,
)
from .pipeline import (
    align,
    run_speech_pipeline,
)
from .provenance import (
    code_provenance,
    sha256,
)
from .text_norm import (
    TokenSpan,
    normalize_text_spans,
    normalize_transcript,
    project_tokens_to_cues,
)

__all__ = [
    "ASRError",
    "ASRInferenceError",
    "ASRSegment",
    "AlignmentResult",
    "AudioChunk",
    "AudioFormatError",
    "CTCAlignerError",
    "CTCAlignerUnavailableError",
    "ChunkConfig",
    "ChunkingError",
    "Config",
    "Cue",
    "ForcedAligner",
    "MFAError",
    "MFAExecutionError",
    "MFANotFoundError",
    "MFATimeoutError",
    "MonotonicityError",
    "PhonemeCue",
    "SubprocessRunner",
    "TokenSpan",
    "TorchAudioAligner",
    "VRAMAllocationError",
    "WhisperTranscriber",
    "WordToken",
    "align",
    "align_chunks",
    "align_ctc_trellis",
    "backtrack",
    "check_mfa_available",
    "code_provenance",
    "export_jsonld",
    "export_karaoke_vtt",
    "export_raw_alignment",
    "extract_vad_silences",
    "format_vtt_timestamp",
    "generate_manifest",
    "get_duration",
    "get_trellis",
    "normalize_text_spans",
    "normalize_transcript",
    "parse_textgrid",
    "partition_into_chunks",
    "project_tokens_to_cues",
    "reconcile_chunk_alignments",
    "run_mfa_batch",
    "run_speech_pipeline",
    "sha256",
    "slice_wav",
]
