"""Montreal Forced Aligner (MFA) subprocess adapter and native Praat parser.

Provides:
- check_mfa_available: host PATH environment discovery
- parse_textgrid: pure-Python Praat long and short format parser with silence filtering,
  containment association, micro-phoneme duration enforcement, and temporal monotonicity
- run_mfa_batch: corpus staging batch runner executing MFA CLI in a single batch
  with automatic temporary staging cleanup and typed exceptions
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Final

from .models import PhonemeCue, WordToken

logger = logging.getLogger(__name__)

SILENCE_TOKENS: Final[set[str]] = {"", "<sil>", "sil", "sp"}


class MFAError(Exception):
    """Base exception for all Montreal Forced Aligner errors."""


class MFANotFoundError(MFAError):
    """Raised when the Montreal Forced Aligner executable is not accessible on PATH."""


class MFATimeoutError(MFAError):
    """Raised when the MFA subprocess execution exceeds timeout bounds."""


class MFAExecutionError(MFAError):
    """Raised when the MFA subprocess exits with a non-zero return code."""


class SubprocessRunner:
    """Subprocess runner abstraction for executing external CLI commands."""

    def run(
        self,
        cmd: list[str],
        timeout: float | None = None,
    ) -> subprocess.CompletedProcess[str]:
        _ensure_mfa_on_path()
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=True,
            timeout=timeout,
        )


def _ensure_mfa_on_path() -> None:
    """Discover standard user conda/micromamba MFA prefixes and add to PATH if present."""
    candidates = [
        Path.home() / ".mfa_env" / "Scripts" / "mfa.exe",
        Path.home() / ".mfa_env" / "bin" / "mfa",
    ]
    for c in candidates:
        if c.is_file():
            env_dir = c.parent.parent
            extra_paths = [
                str(env_dir / "Scripts"),
                str(env_dir / "Library" / "bin"),
                str(env_dir / "Library" / "usr" / "bin"),
                str(env_dir / "bin"),
                str(env_dir),
            ]
            for ep in reversed(extra_paths):
                if ep not in os.environ.get("PATH", ""):
                    os.environ["PATH"] = ep + ";" + os.environ.get("PATH", "")
            break


def check_mfa_available() -> bool:
    """Inspect host environment PATH for Montreal Forced Aligner ('mfa') binary."""
    _ensure_mfa_on_path()
    return shutil.which("mfa") is not None


def _clean_quoted_str(s: str) -> str:
    """Trim whitespace and strip Praat string double-quotes."""
    s = s.strip()
    if len(s) >= 2 and s.startswith('"') and s.endswith('"'):
        s = s[1:-1].replace('""', '"')
    return s.strip()


def _parse_raw_intervals(
    content: str,
) -> tuple[list[tuple[float, float, str]], list[tuple[float, float, str]]]:
    """Parse raw (xmin, xmax, text) intervals from Praat TextGrid long or short format."""
    words: list[tuple[float, float, str]] = []
    phones: list[tuple[float, float, str]] = []

    lines = [line.strip() for line in content.splitlines() if line.strip()]
    if not lines:
        return words, phones

    is_long_format = any(
        "xmin =" in line or "item [" in line or "intervals:" in line for line in lines[2:]
    )

    if is_long_format:
        current_tier: str | None = None
        cur_xmin: float | None = None
        cur_xmax: float | None = None

        for line in lines:
            if "name =" in line:
                raw_name = line.split("=", 1)[1]
                t_name = _clean_quoted_str(raw_name).lower()
                if "word" in t_name:
                    current_tier = "words"
                elif "phone" in t_name:
                    current_tier = "phones"
                else:
                    current_tier = None
                cur_xmin = None
                cur_xmax = None
                continue

            if current_tier is None:
                continue

            if line.startswith("xmin ="):
                try:
                    cur_xmin = float(line.split("=", 1)[1].strip())
                except ValueError:
                    cur_xmin = None
            elif line.startswith("xmax ="):
                try:
                    cur_xmax = float(line.split("=", 1)[1].strip())
                except ValueError:
                    cur_xmax = None
            elif line.startswith("text ="):
                raw_val = line.split("=", 1)[1]
                text_val = _clean_quoted_str(raw_val)
                if cur_xmin is not None and cur_xmax is not None:
                    if cur_xmax > cur_xmin and (cur_xmax - cur_xmin) >= 0.001:
                        if current_tier == "words":
                            words.append((cur_xmin, cur_xmax, text_val))
                        elif current_tier == "phones":
                            phones.append((cur_xmin, cur_xmax, text_val))
                cur_xmin = None
                cur_xmax = None
    else:
        # Praat short format parser
        tokens: list[str] = []
        idx = 0
        while idx < len(lines):
            line = lines[idx]
            if line.startswith('"') and line.count('"') % 2 != 0:
                collected = [line]
                idx += 1
                while idx < len(lines):
                    sub = lines[idx]
                    collected.append(sub)
                    idx += 1
                    if sub.count('"') % 2 != 0:
                        break
                tokens.append("\n".join(collected))
            else:
                tokens.append(line)
                idx += 1

        # Locate '<exists>'
        t_idx = 0
        while t_idx < len(tokens) and tokens[t_idx] != "<exists>":
            t_idx += 1
        if t_idx < len(tokens):
            t_idx += 1
        else:
            t_idx = 0

        if t_idx >= len(tokens):
            return words, phones

        try:
            num_tiers = int(tokens[t_idx])
            t_idx += 1
        except ValueError:
            return words, phones

        for _ in range(num_tiers):
            if t_idx >= len(tokens):
                break
            # Skip class (e.g. "IntervalTier")
            t_idx += 1
            if t_idx >= len(tokens):
                break
            tier_name = _clean_quoted_str(tokens[t_idx]).lower()
            t_idx += 1
            if t_idx >= len(tokens):
                break
            # Skip tier xmin, xmax
            t_idx += 2
            if t_idx >= len(tokens):
                break
            try:
                num_intervals = int(tokens[t_idx])
            except ValueError:
                break
            t_idx += 1

            target: list[tuple[float, float, str]] | None = None
            if "word" in tier_name:
                target = words
            elif "phone" in tier_name:
                target = phones

            for _ in range(num_intervals):
                if t_idx + 2 >= len(tokens):
                    break
                try:
                    int_xmin = float(tokens[t_idx])
                    int_xmax = float(tokens[t_idx + 1])
                except ValueError:
                    t_idx += 3
                    continue
                int_text = _clean_quoted_str(tokens[t_idx + 2])
                t_idx += 3
                if target is not None and int_xmax > int_xmin and (int_xmax - int_xmin) >= 0.001:
                    target.append((int_xmin, int_xmax, int_text))

    return words, phones


def parse_textgrid(
    textgrid_content: str,
    word_id_prefix: str | None = None,
) -> list[WordToken]:
    """Parse Praat TextGrid content into WordTokens with strictly contained PhonemeCues.

    Supports Praat long and short format, filters non-speech silence intervals,
    associates phoneme intervals within parent words, and enforces temporal monotonicity.
    """
    raw_words, raw_phones = _parse_raw_intervals(textgrid_content)

    valid_words = [
        (s, e, text)
        for (s, e, text) in raw_words
        if text.strip().lower() not in SILENCE_TOKENS and (e - s) >= 0.001
    ]
    valid_phones = [
        (s, e, text)
        for (s, e, text) in raw_phones
        if text.strip().lower() not in SILENCE_TOKENS and (e - s) >= 0.001
    ]

    if not valid_words:
        return []

    valid_words.sort(key=lambda item: (item[0], item[1]))
    valid_phones.sort(key=lambda item: (item[0], item[1]))

    word_tokens: list[WordToken] = []
    prefix = word_id_prefix or "word"

    for w_idx, (w_s, w_e, w_text) in enumerate(valid_words):
        w_phones: list[PhonemeCue] = []
        for p_s, p_e, p_text in valid_phones:
            p_mid = (p_s + p_e) / 2.0
            overlap = min(p_e, w_e) - max(p_s, w_s)
            is_contained = (w_s - 1e-4 <= p_mid <= w_e + 1e-4) or (
                overlap > 0 and overlap >= 0.5 * (p_e - p_s)
            )
            if is_contained:
                clamped_s = round(max(w_s, p_s), 4)
                clamped_e = round(min(w_e, p_e), 4)
                if clamped_e - clamped_s < 0.001:
                    clamped_e = round(clamped_s + 0.001, 4)
                    if clamped_e > w_e:
                        clamped_s = round(max(w_s, w_e - 0.001), 4)
                        clamped_e = round(w_e, 4)
                if clamped_e > clamped_s:
                    w_phones.append(
                        PhonemeCue(
                            phoneme=p_text,
                            start=clamped_s,
                            end=clamped_e,
                            confidence=1.0,
                        )
                    )

        w_phones.sort(key=lambda p: (p.start, p.end))

        word_tokens.append(
            WordToken(
                id=f"{prefix}_{w_idx:04d}",
                text=w_text,
                normalized=w_text.lower(),
                start=round(w_s, 4),
                end=round(w_e, 4),
                confidence=1.0,
                phonemes=w_phones,
            )
        )

    # Monotonic progression invariant
    for i in range(len(word_tokens) - 1):
        prev_w = word_tokens[i]
        curr_w = word_tokens[i + 1]
        if curr_w.start < prev_w.end:
            overlap = round(prev_w.end - curr_w.start, 4)
            if overlap <= 0.05:
                new_prev_end = round(curr_w.start, 4)
                if new_prev_end <= prev_w.start:
                    new_prev_end = round(prev_w.start + 0.001, 4)
                nudged_phones: list[PhonemeCue] = []
                for p in prev_w.phonemes:
                    p_start = max(prev_w.start, min(p.start, new_prev_end - 0.001))
                    p_end = max(p_start + 0.001, min(p.end, new_prev_end))
                    if p_end > p_start:
                        nudged_phones.append(
                            PhonemeCue(
                                p.phoneme,
                                round(p_start, 4),
                                round(p_end, 4),
                                p.confidence,
                            )
                        )
                word_tokens[i] = WordToken(
                    id=prev_w.id,
                    text=prev_w.text,
                    normalized=prev_w.normalized,
                    start=prev_w.start,
                    end=new_prev_end,
                    confidence=prev_w.confidence,
                    phonemes=nudged_phones,
                )

    return word_tokens


def run_mfa_batch(
    chunk_wavs: list[tuple[Path, str]],
    output_dir: Path | None = None,
    dictionary: str = "english_us_arpa",
    acoustic_model: str = "english_us_arpa",
    num_jobs: int = 4,
    timeout: float | None = None,
    runner: SubprocessRunner | None = None,
) -> list[list[WordToken]]:
    """Stage corpus and execute Montreal Forced Aligner in a single batch subprocess.

    Stages WAV files and transcript labels into a temporary directory, invokes
    the `mfa align` command once across all chunks, parses the resulting TextGrid
    files, and guarantees atomic cleanup of staging resources.
    """
    if not chunk_wavs:
        return []

    active_runner = runner or SubprocessRunner()

    if runner is None and not check_mfa_available():
        raise MFANotFoundError(
            "Montreal Forced Aligner ('mfa') executable not found on PATH. "
            "Please install MFA using Conda: "
            "'conda create -n aligner -c conda-forge montreal-forced-aligner && "
            "conda activate aligner && "
            "mfa model download acoustic english_us_arpa && "
            "mfa model download dictionary english_us_arpa'"
        )

    staging_root = Path(tempfile.mkdtemp(prefix="mfa_staging_"))
    corpus_dir = staging_root / "corpus"
    corpus_dir.mkdir(parents=True, exist_ok=True)

    target_out_dir = output_dir if output_dir is not None else (staging_root / "output")
    target_out_dir.mkdir(parents=True, exist_ok=True)

    try:
        # 1. Corpus Staging
        for idx, (wav_path, transcript) in enumerate(chunk_wavs):
            chunk_name = f"chunk_{idx:04d}"
            dest_wav = corpus_dir / f"{chunk_name}.wav"
            shutil.copyfile(wav_path, dest_wav)

            dest_lab = corpus_dir / f"{chunk_name}.lab"
            dest_lab.write_text(transcript.strip(), encoding="utf-8")

        # 2. Build CLI command
        cmd = [
            "mfa",
            "align",
            str(corpus_dir),
            dictionary,
            acoustic_model,
            str(target_out_dir),
            "--clean",
            "--single_speaker",
            "--num_jobs",
            str(num_jobs),
        ]

        # 3. Single Batch Execution
        try:
            active_runner.run(cmd, timeout=timeout)
        except FileNotFoundError as err:
            raise MFANotFoundError("Montreal Forced Aligner ('mfa') executable not found.") from err
        except subprocess.TimeoutExpired as err:
            raise MFATimeoutError(f"MFA execution timed out: {err}") from err
        except subprocess.CalledProcessError as err:
            raise MFAExecutionError(
                f"MFA execution failed with exit code {err.returncode}: {err.stderr}"
            ) from err

        # 4. Parse Generated TextGrids
        results: list[list[WordToken]] = []
        for idx in range(len(chunk_wavs)):
            tg_path = target_out_dir / f"chunk_{idx:04d}.TextGrid"
            if tg_path.is_file():
                content = tg_path.read_text(encoding="utf-8")
                chunk_words = parse_textgrid(content, word_id_prefix=f"chunk_{idx:04d}")
                results.append(chunk_words)
            else:
                logger.warning("MFA TextGrid missing for chunk %04d", idx)
                results.append([])

        return results

    finally:
        # Atomic Staging Cleanup
        shutil.rmtree(staging_root, ignore_errors=True)
