"""Adversarial challenge test harness for Milestone 2 Increment 5.

Verifies:
- CLI align-speech: valid execution, missing audio, missing output, invalid engines.
- CLI subcommand align-dtw: valid execution, missing arguments, parameter boundaries, file errors.
- Backward compatibility: legacy root flags (--reference, --target, --cues, -o) without subcommand.
- Exit code 2 contract: ensures NO Python tracebacks printed to stderr under any violation.
- Python interface contract: main(argv) returns int exit codes without unhandled SystemExit.
- Empirical stress tests, property checks, and path heuristics.
"""

import json
import subprocess
import sys
import wave
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest

from subtitle_workbench.cli import main
from subtitle_workbench.demo import generate as generate_demo
from subtitle_workbench.models import WordToken


def create_pcm16_wav(
    path: Path,
    duration_sec: float = 2.0,
    sample_rate: int = 16000,
    frequency: float = 440.0,
) -> None:
    """Create a valid PCM16 mono WAV file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    num_frames = int(round(sample_rate * duration_sec))
    t = np.linspace(0, duration_sec, num_frames, endpoint=False)
    samples = (np.sin(2 * np.pi * frequency * t) * 16384).astype(np.int16)
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(samples.tobytes())


def make_mock_aligner(word_texts: list[str] | None = None) -> MagicMock:
    """Create a mock ForcedAligner returning valid reconciled WordTokens."""
    if word_texts is None:
        word_texts = ["test", "alignment", "system"]
    tokens = [
        WordToken(
            id=f"w_{i}",
            text=text,
            normalized=text.lower(),
            start=float(i * 0.5),
            end=float((i + 1) * 0.5),
            confidence=0.95,
            char_start=0,
            char_end=len(text),
        )
        for i, text in enumerate(word_texts)
    ]
    mock = MagicMock()
    mock.align_chunks.return_value = tokens
    return mock


# ============================================================================
# 1. align-speech Subcommand Verification
# ============================================================================


class TestAlignSpeechSubcommand:
    """Adversarial tests for align-speech subcommand."""

    def test_align_speech_valid_inline_transcript(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """Verify valid align-speech execution with inline transcript."""
        wav = tmp_path / "valid.wav"
        out = tmp_path / "out_speech_inline"
        create_pcm16_wav(wav, duration_sec=1.5)

        monkeypatch.setattr(
            "subtitle_workbench.pipeline.ForcedAligner",
            lambda: make_mock_aligner(["hello", "world"]),
        )

        code = main(
            [
                "align-speech",
                str(wav),
                "-o",
                str(out),
                "--transcript",
                "hello world",
                "--engine",
                "ctc",
            ]
        )

        assert code == 0
        captured = capsys.readouterr()
        metrics = json.loads(captured.out)
        assert metrics["word_count"] == 2
        assert (out / "manifest.json").is_file()
        assert (out / "subtitles.vtt").is_file()
        assert (out / "timeline.jsonld").is_file()
        assert (out / "alignment_raw.json").is_file()
        assert "Traceback" not in captured.err

    def test_align_speech_valid_transcript_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """Verify valid align-speech execution with external transcript file."""
        wav = tmp_path / "valid.wav"
        out = tmp_path / "out_speech_file"
        create_pcm16_wav(wav, duration_sec=1.5)

        transcript_file = tmp_path / "transcript.txt"
        transcript_file.write_text("speech recognition and alignment", encoding="utf-8")

        monkeypatch.setattr(
            "subtitle_workbench.pipeline.ForcedAligner",
            lambda: make_mock_aligner(["speech", "recognition", "and", "alignment"]),
        )

        code = main(
            [
                "align-speech",
                str(wav),
                "-o",
                str(out),
                "--transcript",
                str(transcript_file),
                "--engine",
                "auto",
            ]
        )

        assert code == 0
        captured = capsys.readouterr()
        metrics = json.loads(captured.out)
        assert metrics["word_count"] == 4
        assert "Traceback" not in captured.err

    def test_align_speech_custom_options(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """Verify align-speech with custom threshold parameters."""
        wav = tmp_path / "valid.wav"
        out = tmp_path / "out_speech_opts"
        create_pcm16_wav(wav, duration_sec=2.0)

        monkeypatch.setattr(
            "subtitle_workbench.pipeline.ForcedAligner",
            lambda: make_mock_aligner(["quick", "brown", "fox"]),
        )

        code = main(
            [
                "align-speech",
                str(wav),
                "-o",
                str(out),
                "--transcript",
                "quick brown fox",
                "--engine",
                "ctc",
                "--vad-silence-min-sec",
                "0.6",
                "--max-chunk-sec",
                "15.0",
                "--chunk-padding-sec",
                "0.25",
            ]
        )

        assert code == 0
        captured = capsys.readouterr()
        manifest_data = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
        assert manifest_data["config"]["vad_silence_min_sec"] == 0.6
        assert manifest_data["config"]["max_chunk_sec"] == 15.0
        assert manifest_data["config"]["chunk_padding_sec"] == 0.25
        assert "Traceback" not in captured.err

    def test_align_speech_missing_audio_argument(self, capsys: pytest.CaptureFixture) -> None:
        """Verify exit code 2 when audio_wav positional argument is omitted."""
        code = main(["align-speech", "-o", "some_out"])
        assert code == 2
        captured = capsys.readouterr()
        assert "error: the following arguments are required: audio_wav" in captured.err
        assert "Traceback" not in captured.err

    def test_align_speech_missing_output_flag(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """Verify exit code 2 when -o/--output argument is omitted."""
        wav = tmp_path / "dummy.wav"
        code = main(["align-speech", str(wav)])
        assert code == 2
        captured = capsys.readouterr()
        assert "error: the following arguments are required: -o/--output" in captured.err
        assert "Traceback" not in captured.err

    def test_align_speech_missing_all_required_arguments(
        self, capsys: pytest.CaptureFixture
    ) -> None:
        """Verify exit code 2 when align-speech is invoked with no arguments."""
        code = main(["align-speech"])
        assert code == 2
        captured = capsys.readouterr()
        assert "error: the following arguments are required: audio_wav, -o/--output" in captured.err
        assert "Traceback" not in captured.err

    @pytest.mark.parametrize(
        "invalid_engine",
        ["kaldi", "whisper", "deep_speech", "AUTO", "MFA", "CTC", ""],
    )
    def test_align_speech_invalid_engine(
        self, tmp_path: Path, invalid_engine: str, capsys: pytest.CaptureFixture
    ) -> None:
        """Verify exit code 2 when an invalid engine option is supplied."""
        wav = tmp_path / "dummy.wav"
        out = tmp_path / "dummy_out"
        code = main(["align-speech", str(wav), "-o", str(out), "--engine", invalid_engine])
        assert code == 2
        captured = capsys.readouterr()
        assert "error: argument --engine: invalid choice:" in captured.err
        assert "Traceback" not in captured.err

    def test_align_speech_nonexistent_audio_file(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """Verify exit code 2 when input audio does not exist on disk."""
        code = main(
            [
                "align-speech",
                str(tmp_path / "nonexistent.wav"),
                "-o",
                str(tmp_path / "out"),
            ]
        )
        assert code == 2
        captured = capsys.readouterr()
        assert "error: File not found:" in captured.err
        assert "Traceback" not in captured.err

    def test_align_speech_corrupt_audio_file(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """Verify exit code 2 when input audio is not a valid WAV file."""
        corrupt = tmp_path / "corrupt.wav"
        corrupt.write_bytes(b"NOT_A_WAV_HEADER_DATA_GARBAGE")
        code = main(["align-speech", str(corrupt), "-o", str(tmp_path / "out")])
        assert code == 2
        captured = capsys.readouterr()
        assert "error:" in captured.err
        assert "Traceback" not in captured.err

    @pytest.mark.parametrize(
        "param_flag,invalid_val",
        [
            ("--vad-silence-min-sec", "-0.5"),
            ("--vad-silence-min-sec", "0.0"),
            ("--max-chunk-sec", "-1.0"),
            ("--max-chunk-sec", "0.0"),
            ("--chunk-padding-sec", "-0.1"),
        ],
    )
    def test_align_speech_invalid_numeric_bounds(
        self, tmp_path: Path, param_flag: str, invalid_val: str, capsys: pytest.CaptureFixture
    ) -> None:
        """Verify exit code 2 when negative or zero thresholds are passed."""
        wav = tmp_path / "valid.wav"
        create_pcm16_wav(wav, duration_sec=1.0)
        code = main(
            [
                "align-speech",
                str(wav),
                "-o",
                str(tmp_path / "out"),
                param_flag,
                invalid_val,
            ]
        )
        assert code == 2
        captured = capsys.readouterr()
        assert "error:" in captured.err
        assert "Traceback" not in captured.err

    def test_align_speech_nonexistent_transcript_file(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """Verify exit code 2 when transcript file is missing."""
        wav = tmp_path / "valid.wav"
        create_pcm16_wav(wav, duration_sec=1.0)
        code = main(
            [
                "align-speech",
                str(wav),
                "-o",
                str(tmp_path / "out"),
                "--transcript",
                str(tmp_path / "missing.txt"),
            ]
        )
        assert code == 2
        captured = capsys.readouterr()
        assert "error: Transcript file not found:" in captured.err
        assert "Traceback" not in captured.err

    def test_align_speech_empty_transcript_string(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """Verify exit code 2 when transcript is an empty string or whitespace."""
        wav = tmp_path / "valid.wav"
        create_pcm16_wav(wav, duration_sec=1.0)
        code = main(
            [
                "align-speech",
                str(wav),
                "-o",
                str(tmp_path / "out"),
                "--transcript",
                "   ",
            ]
        )
        assert code == 2
        captured = capsys.readouterr()
        assert "error: transcript cannot be empty" in captured.err
        assert "Traceback" not in captured.err

    def test_align_speech_output_overwrite_protection(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """Verify exit code 2 when output directory already contains artifacts."""
        wav = tmp_path / "valid.wav"
        out = tmp_path / "existing_out"
        create_pcm16_wav(wav, duration_sec=1.0)

        monkeypatch.setattr(
            "subtitle_workbench.pipeline.ForcedAligner",
            lambda: make_mock_aligner(["hello"]),
        )

        first_code = main(
            [
                "align-speech",
                str(wav),
                "-o",
                str(out),
                "--transcript",
                "hello",
            ]
        )
        assert first_code == 0

        # Attempt to run again over same output directory
        second_code = main(
            [
                "align-speech",
                str(wav),
                "-o",
                str(out),
                "--transcript",
                "hello",
            ]
        )
        assert second_code == 2
        captured = capsys.readouterr()
        assert "error: output files already exist" in captured.err
        assert "Traceback" not in captured.err

    def test_align_speech_output_input_collision(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """Verify exit code 2 when output directory matches input audio path."""
        wav = tmp_path / "valid.wav"
        create_pcm16_wav(wav, duration_sec=1.0)

        code = main(
            [
                "align-speech",
                str(wav),
                "-o",
                str(wav),
                "--transcript",
                "hello",
            ]
        )
        assert code == 2
        captured = capsys.readouterr()
        assert "error:" in captured.err
        assert "Traceback" not in captured.err


# ============================================================================
# 2. align-dtw Subcommand Verification
# ============================================================================


class TestAlignDTWSubcommand:
    """Adversarial tests for align-dtw subcommand."""

    def test_align_dtw_valid_execution(self, tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
        """Verify valid align-dtw subcommand execution."""
        fixture_dir = tmp_path / "dtw_input"
        generate_demo(fixture_dir)
        out_dir = tmp_path / "dtw_out"

        code = main(
            [
                "align-dtw",
                str(fixture_dir / "reference.wav"),
                str(fixture_dir / "target.wav"),
                str(fixture_dir / "cues.json"),
                "-o",
                str(out_dir),
            ]
        )

        assert code == 0
        captured = capsys.readouterr()
        metrics = json.loads(captured.out)
        assert metrics["cue_count"] == 6
        assert (out_dir / "manifest.json").is_file()
        assert (out_dir / "subtitles.vtt").is_file()
        assert (out_dir / "timeline.jsonld").is_file()
        assert "Traceback" not in captured.err

    @pytest.mark.parametrize(
        "args,expected_missing",
        [
            (["align-dtw"], "ref_wav, target_wav, cues_json, -o/--output"),
            (["align-dtw", "ref.wav"], "target_wav, cues_json, -o/--output"),
            (["align-dtw", "ref.wav", "tgt.wav"], "cues_json, -o/--output"),
            (["align-dtw", "ref.wav", "tgt.wav", "cues.json"], "-o/--output"),
        ],
    )
    def test_align_dtw_missing_positional_arguments(
        self, args: list[str], expected_missing: str, capsys: pytest.CaptureFixture
    ) -> None:
        """Verify exit code 2 and descriptive message when arguments are missing."""
        code = main(args)
        assert code == 2
        captured = capsys.readouterr()
        assert f"error: the following arguments are required: {expected_missing}" in captured.err
        assert "Traceback" not in captured.err

    def test_align_dtw_nonexistent_files(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """Verify exit code 2 when DTW inputs do not exist."""
        code = main(
            [
                "align-dtw",
                str(tmp_path / "missing_ref.wav"),
                str(tmp_path / "missing_tgt.wav"),
                str(tmp_path / "missing_cues.json"),
                "-o",
                str(tmp_path / "out"),
            ]
        )
        assert code == 2
        captured = capsys.readouterr()
        assert "error:" in captured.err
        assert "Traceback" not in captured.err

    def test_align_dtw_malformed_cues_json(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """Verify exit code 2 when cues.json contains malformed JSON."""
        fixture_dir = tmp_path / "dtw_input"
        generate_demo(fixture_dir)
        (fixture_dir / "cues.json").write_text("invalid json content", encoding="utf-8")

        code = main(
            [
                "align-dtw",
                str(fixture_dir / "reference.wav"),
                str(fixture_dir / "target.wav"),
                str(fixture_dir / "cues.json"),
                "-o",
                str(tmp_path / "out"),
            ]
        )
        assert code == 2
        captured = capsys.readouterr()
        assert "error:" in captured.err
        assert "Traceback" not in captured.err

    @pytest.mark.parametrize(
        "flag,val,err_substr",
        [
            ("--band-seconds", "0.001", "band_seconds must be between 0.02 and 5.0"),
            ("--band-seconds", "10.0", "band_seconds must be between 0.02 and 5.0"),
            ("--spectral-weight", "-0.1", "spectral_weight must be between 0.0 and 1.0"),
            ("--spectral-weight", "1.5", "spectral_weight must be between 0.0 and 1.0"),
            ("--max-frames", "1", "max_frames must be an integer between 2 and 10000"),
            ("--max-frames", "20000", "max_frames must be an integer between 2 and 10000"),
            ("--max-cells", "1", "max_cells must be an integer between 2 and 5000000"),
            ("--max-cells", "10000000", "max_cells must be an integer between 2 and 5000000"),
        ],
    )
    def test_align_dtw_parameter_bounds(
        self, flag: str, val: str, err_substr: str, capsys: pytest.CaptureFixture
    ) -> None:
        """Verify exit code 2 when DTW parameters violate bounds."""
        code = main(
            [
                "align-dtw",
                "dummy_ref.wav",
                "dummy_tgt.wav",
                "dummy_cues.json",
                "-o",
                "dummy_out",
                flag,
                val,
            ]
        )
        assert code == 2
        captured = capsys.readouterr()
        assert f"error: {err_substr}" in captured.err
        assert "Traceback" not in captured.err


# ============================================================================
# 3. Backward Compatibility with Root Flags
# ============================================================================


class TestBackwardCompatibility:
    """Adversarial tests for backward compatibility with root flags."""

    def test_root_flags_valid_execution(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """Verify legacy root flags without subcommand succeed with exit code 0."""
        fixture_dir = tmp_path / "legacy_input"
        generate_demo(fixture_dir)
        out_dir = tmp_path / "legacy_out"

        code = main(
            [
                "--reference",
                str(fixture_dir / "reference.wav"),
                "--target",
                str(fixture_dir / "target.wav"),
                "--cues",
                str(fixture_dir / "cues.json"),
                "-o",
                str(out_dir),
            ]
        )

        assert code == 0
        captured = capsys.readouterr()
        metrics = json.loads(captured.out)
        assert metrics["cue_count"] == 6
        assert (out_dir / "manifest.json").is_file()
        assert "Traceback" not in captured.err

    @pytest.mark.parametrize(
        "args",
        [
            [],
            ["--reference", "ref.wav"],
            ["--target", "tgt.wav"],
            ["--cues", "cues.json"],
            ["-o", "out"],
            ["--reference", "ref.wav", "--target", "tgt.wav"],
            ["--reference", "ref.wav", "--target", "tgt.wav", "--cues", "cues.json"],
        ],
    )
    def test_root_flags_missing_arguments(
        self, args: list[str], capsys: pytest.CaptureFixture
    ) -> None:
        """Verify exit code 2 when any required root flag is missing."""
        code = main(args)
        assert code == 2
        captured = capsys.readouterr()
        assert (
            "error: missing required arguments: --reference, --target, --cues, -o/--output"
            in captured.err
        )
        assert "Traceback" not in captured.err

    def test_root_flags_unknown_argument(self, capsys: pytest.CaptureFixture) -> None:
        """Verify exit code 2 when an unknown root argument is given."""
        code = main(["--unknown-flag"])
        assert code == 2
        captured = capsys.readouterr()
        assert "error: unrecognized arguments: --unknown-flag" in captured.err
        assert "Traceback" not in captured.err

    def test_root_flags_invalid_subcommand_choice(self, capsys: pytest.CaptureFixture) -> None:
        """Verify exit code 2 when an invalid subcommand name is given."""
        code = main(["align-invalid", "foo", "bar"])
        assert code == 2
        captured = capsys.readouterr()
        assert "error: argument subcommand: invalid choice: 'align-invalid'" in captured.err
        assert "Traceback" not in captured.err


# ============================================================================
# 4. Exit Code 2 & Stderr Traceback Absence Contract
# ============================================================================


class TestExitCode2Contract:
    """Adversarial tests ensuring zero tracebacks and strict exit code 2 contract."""

    @pytest.mark.parametrize(
        "argv",
        [
            ["--nonexistent"],
            ["align-speech"],
            ["align-speech", "nonexistent.wav", "-o", "out"],
            ["align-speech", "-o", "out"],
            ["align-speech", "foo.wav", "-o", "out", "--engine", "unsupported"],
            ["align-dtw"],
            ["align-dtw", "ref.wav"],
            ["align-dtw", "ref.wav", "tgt.wav", "cues.json"],
            ["--reference", "ref.wav"],
            ["--output", "out"],
            ["align-speech", "foo.wav", "-o", "out", "--unknown-opt"],
            ["align-dtw", "r.wav", "t.wav", "c.json", "-o", "out", "--unknown-opt"],
        ],
    )
    def test_main_never_prints_traceback_on_error(
        self, argv: list[str], capsys: pytest.CaptureFixture
    ) -> None:
        """Verify main(argv) emits descriptive error: and NO Python traceback."""
        code = main(argv)
        assert code == 2
        captured = capsys.readouterr()
        assert "error:" in captured.err
        assert "Traceback (most recent call last):" not in captured.err
        assert "Traceback" not in captured.err


# ============================================================================
# 5. Python Callable Contract: main(argv) Returns int Without SystemExit
# ============================================================================


class TestMainAsCallableContract:
    """Verify main(argv) behaves as a pure function returning int."""

    def test_main_returns_int_type(self) -> None:
        """Verify return value is strictly an int instance."""
        code = main(["--bad-flag"])
        assert isinstance(code, int)
        assert code == 2

    def test_main_with_none_argument(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify main(None) parses sys.argv and returns int without unhandled SystemExit."""
        monkeypatch.setattr(sys, "argv", ["subtitle-workbench"])
        code = main(None)
        assert isinstance(code, int)
        assert code == 2

    def test_main_help_returns_zero_without_system_exit(
        self, capsys: pytest.CaptureFixture
    ) -> None:
        """Verify main(['--help']) returns 0 without raising SystemExit."""
        for help_args in [["--help"], ["-h"], ["align-speech", "-h"], ["align-dtw", "-h"]]:
            code = main(help_args)
            assert code == 0
            captured = capsys.readouterr()
            assert "usage: subtitle-workbench" in captured.out


# ============================================================================
# 6. Subprocess CLI Invocations
# ============================================================================


class TestSubprocessCLI:
    """Subprocess execution tests verifying CLI behavior under real python execution."""

    def test_subprocess_align_speech_missing_audio(self) -> None:
        """Verify subprocess returns 2 with error: on missing audio."""
        res = subprocess.run(
            [sys.executable, "-m", "subtitle_workbench", "align-speech", "-o", "out"],
            capture_output=True,
            text=True,
            check=False,
        )
        assert res.returncode == 2
        assert "error: the following arguments are required: audio_wav" in res.stderr
        assert "Traceback" not in res.stderr

    def test_subprocess_align_speech_invalid_engine(self) -> None:
        """Verify subprocess returns 2 with error: on invalid engine."""
        res = subprocess.run(
            [
                sys.executable,
                "-m",
                "subtitle_workbench",
                "align-speech",
                "foo.wav",
                "-o",
                "out",
                "--engine",
                "invalid",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        assert res.returncode == 2
        assert "error: argument --engine: invalid choice:" in res.stderr
        assert "Traceback" not in res.stderr

    def test_subprocess_align_dtw_missing_args(self) -> None:
        """Verify subprocess returns 2 with error: on missing dtw args."""
        res = subprocess.run(
            [sys.executable, "-m", "subtitle_workbench", "align-dtw"],
            capture_output=True,
            text=True,
            check=False,
        )
        assert res.returncode == 2
        assert "error: the following arguments are required:" in res.stderr
        assert "Traceback" not in res.stderr

    def test_subprocess_root_flags_missing_args(self) -> None:
        """Verify subprocess returns 2 on missing root flags."""
        res = subprocess.run(
            [sys.executable, "-m", "subtitle_workbench"],
            capture_output=True,
            text=True,
            check=False,
        )
        assert res.returncode == 2
        assert "error: missing required arguments:" in res.stderr
        assert "Traceback" not in res.stderr


# ============================================================================
# 7. Stress & Empirical Boundary Checks
# ============================================================================


class TestStressAndBoundaryChecks:
    """Empirical stress tests for edge cases and path heuristics."""

    def test_large_transcript_within_bounds_stress(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """Verify pipeline handles large transcripts within model limits (500 words)."""
        wav = tmp_path / "long_speech.wav"
        out = tmp_path / "long_out"
        create_pcm16_wav(wav, duration_sec=5.0)

        words = [f"word{i}" for i in range(500)]
        large_transcript = " ".join(words)
        assert len(large_transcript) < 4000

        monkeypatch.setattr(
            "subtitle_workbench.pipeline.ForcedAligner",
            lambda: make_mock_aligner(words[:50]),
        )

        code = main(
            [
                "align-speech",
                str(wav),
                "-o",
                str(out),
                "--transcript",
                large_transcript,
                "--engine",
                "ctc",
            ]
        )
        assert code == 0
        captured = capsys.readouterr()
        metrics = json.loads(captured.out)
        assert metrics["chunk_count"] >= 1
        assert (out / "manifest.json").is_file()

    def test_transcript_exceeding_4000_char_boundary_fails_gracefully(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """Document empirical finding: transcript > 4000 characters triggers ASRSegment limit.

        Because pipeline.py lines 283-291 places the full transcript into a single
        ASRSegment without pre-chunking, transcripts > 4000 characters exceed the
        validate_text() ceiling and return exit code 2 with descriptive error.
        """
        wav = tmp_path / "long_speech2.wav"
        out = tmp_path / "long_out2"
        create_pcm16_wav(wav, duration_sec=5.0)

        words = [f"word{i}" for i in range(800)]
        large_transcript = " ".join(words)
        assert len(large_transcript) > 4000

        code = main(
            [
                "align-speech",
                str(wav),
                "-o",
                str(out),
                "--transcript",
                large_transcript,
            ]
        )
        assert code == 2
        captured = capsys.readouterr()
        assert "error: text exceeds maximum length of 4000 characters" in captured.err
        assert "Traceback" not in captured.err

    def test_paths_with_spaces(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """Verify paths containing spaces work seamlessly."""
        space_dir = tmp_path / "path with spaces"
        space_dir.mkdir()
        wav = space_dir / "my audio file.wav"
        out = space_dir / "output target folder"
        create_pcm16_wav(wav, duration_sec=1.5)

        monkeypatch.setattr(
            "subtitle_workbench.pipeline.ForcedAligner",
            lambda: make_mock_aligner(["hello", "world"]),
        )

        code = main(
            [
                "align-speech",
                str(wav),
                "-o",
                str(out),
                "--transcript",
                "hello world",
            ]
        )
        assert code == 0
        assert (out / "manifest.json").is_file()

    def test_transcript_heuristic_finding_slash_in_single_line_text(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
    ) -> None:
        """Document empirical finding: single-line transcript with '/' is treated as missing file.

        Because pipeline.py lines 210-215 interprets any single-line transcript
        string containing '/' or '\\' as a file path, passing '24/7' or 'either/or'
        raises FileNotFoundError and exits with code 2.
        """
        wav = tmp_path / "audio.wav"
        out = tmp_path / "out"
        create_pcm16_wav(wav, duration_sec=1.0)

        code = main(
            [
                "align-speech",
                str(wav),
                "-o",
                str(out),
                "--transcript",
                "This is a 24/7 service",
            ]
        )
        # Returns exit code 2 with descriptive error
        assert code == 2
        captured = capsys.readouterr()
        assert "error: Transcript file not found:" in captured.err
        assert "Traceback" not in captured.err
