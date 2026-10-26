"""Reference speech corpora loaders and synthetic benchmark generator.

Provides parsers for TIMIT phonetic (.phn) and word (.wrd) alignments,
Buckeye Speech Corpus Praat TextGrids, and an offline synthetic dataset generator
for reproducible deterministic benchmarking.
"""

from __future__ import annotations

import math
import wave
from pathlib import Path

import numpy as np

from .metrics import CorpusFormatError
from .mfa_wrapper import parse_textgrid
from .models import PhonemeCue, WordToken
from .text_norm import normalize_text_spans

TIMIT_SILENCE_TOKENS = {"h#", "pau", "epi"}

BUCKEYE_NON_SPEECH = {
    "{b_trans}",
    "{e_trans}",
    "<iver>",
    "<laugh>",
    "<vocnoise>",
    "<noise>",
    "sil",
    "<sil>",
    "unknown",
    "<exclude>",
}


def parse_timit_phn(phn_path: Path | str, sample_rate: int = 16000) -> list[PhonemeCue]:
    """Parse a TIMIT .phn file into a list of PhonemeCue instances.

    Converts integer sample boundaries to seconds (t = s / sample_rate),
    filters silence markers ('h#', 'pau', 'epi'), and validates monotonicity.
    """
    if sample_rate <= 0:
        raise CorpusFormatError(f"sample_rate must be positive, got {sample_rate}")

    path = Path(phn_path)
    if not path.is_file():
        raise FileNotFoundError(f"TIMIT .phn file not found: {path}")

    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except OSError as err:
        raise CorpusFormatError(f"Failed to read {path}: {err}") from err

    cues: list[PhonemeCue] = []
    prev_end: int | None = None

    lines = content.splitlines()
    for line_idx, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not stripped:
            continue
        parts = stripped.split()
        if len(parts) != 3:
            raise CorpusFormatError(
                f"Malformed TIMIT .phn line {line_idx} in {path.name}: "
                f"expected 3 tokens, got {len(parts)}"
            )

        try:
            start_sample = int(parts[0])
            end_sample = int(parts[1])
        except ValueError as err:
            raise CorpusFormatError(
                f"Non-integer sample boundary on line {line_idx} in {path.name}"
            ) from err

        phone = parts[2]
        if start_sample < 0:
            raise CorpusFormatError(
                f"Negative start sample {start_sample} on line {line_idx} in {path.name}"
            )
        if start_sample >= end_sample:
            raise CorpusFormatError(
                f"Non-positive interval [{start_sample}, {end_sample}] "
                f"on line {line_idx} in {path.name}"
            )
        if prev_end is not None and start_sample < prev_end:
            raise CorpusFormatError(
                f"Non-monotonic timestamp on line {line_idx} in {path.name}: "
                f"start {start_sample} < previous end {prev_end}"
            )
        prev_end = end_sample

        if phone.lower() in TIMIT_SILENCE_TOKENS:
            continue

        t_start = round(start_sample / float(sample_rate), 6)
        t_end = round(end_sample / float(sample_rate), 6)
        cues.append(
            PhonemeCue(
                phoneme=phone,
                start=t_start,
                end=t_end,
                confidence=1.0,
            )
        )

    return cues


def parse_timit_wrd(wrd_path: Path | str, sample_rate: int = 16000) -> list[WordToken]:
    """Parse a TIMIT .wrd file into a list of WordToken instances.

    Converts integer sample boundaries to seconds (t = s / sample_rate),
    normalizes words, assigns valid ASCII identifiers, and validates monotonicity.
    """
    if sample_rate <= 0:
        raise CorpusFormatError(f"sample_rate must be positive, got {sample_rate}")

    path = Path(wrd_path)
    if not path.is_file():
        raise FileNotFoundError(f"TIMIT .wrd file not found: {path}")

    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except OSError as err:
        raise CorpusFormatError(f"Failed to read {path}: {err}") from err

    words: list[WordToken] = []
    prev_end: int | None = None

    lines = content.splitlines()
    w_idx = 0
    for line_idx, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not stripped:
            continue
        parts = stripped.split()
        if len(parts) != 3:
            raise CorpusFormatError(
                f"Malformed TIMIT .wrd line {line_idx} in {path.name}: "
                f"expected 3 tokens, got {len(parts)}"
            )

        try:
            start_sample = int(parts[0])
            end_sample = int(parts[1])
        except ValueError as err:
            raise CorpusFormatError(
                f"Non-integer sample boundary on line {line_idx} in {path.name}"
            ) from err

        word_text = parts[2]
        if start_sample < 0:
            raise CorpusFormatError(
                f"Negative start sample {start_sample} on line {line_idx} in {path.name}"
            )
        if start_sample >= end_sample:
            raise CorpusFormatError(
                f"Non-positive interval [{start_sample}, {end_sample}] "
                f"on line {line_idx} in {path.name}"
            )
        if prev_end is not None and start_sample < prev_end:
            raise CorpusFormatError(
                f"Non-monotonic timestamp on line {line_idx} in {path.name}: "
                f"start {start_sample} < previous end {prev_end}"
            )
        prev_end = end_sample

        spans = normalize_text_spans(word_text)
        norm_text = " ".join(s.normalized for s in spans) if spans else word_text.lower()
        if not norm_text:
            norm_text = word_text.lower()

        t_start = round(start_sample / float(sample_rate), 6)
        t_end = round(end_sample / float(sample_rate), 6)

        words.append(
            WordToken(
                id=f"w_{w_idx:04d}",
                text=word_text,
                normalized=norm_text,
                start=t_start,
                end=t_end,
                confidence=1.0,
                char_start=0,
                char_end=len(word_text),
            )
        )
        w_idx += 1

    return words


def parse_buckeye_textgrid(textgrid_path: Path | str) -> list[WordToken]:
    """Parse a Buckeye Speech Corpus Praat TextGrid file.

    Ingests intervals using mfa_wrapper.parse_textgrid and filters Buckeye
    non-speech artifact tokens ({B_TRANS}, {E_TRANS}, <IVER>, <LAUGH>, etc.).
    """
    path = Path(textgrid_path)
    if not path.is_file():
        raise FileNotFoundError(f"Buckeye TextGrid file not found: {path}")

    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except OSError as err:
        raise CorpusFormatError(f"Failed to read {path}: {err}") from err

    raw_tokens = parse_textgrid(content)

    cleaned_words: list[WordToken] = []
    for w in raw_tokens:
        w_norm = w.normalized.strip().lower()
        w_raw = w.text.strip().lower()
        if w_norm in BUCKEYE_NON_SPEECH or w_raw in BUCKEYE_NON_SPEECH:
            continue

        clean_phones = [
            p
            for p in w.phonemes
            if p.phoneme.strip().lower() not in BUCKEYE_NON_SPEECH
            and p.phoneme.strip().lower() not in {"", "<sil>", "sil", "sp"}
        ]

        cleaned_words.append(
            WordToken(
                id=w.id,
                text=w.text,
                normalized=w.normalized,
                start=w.start,
                end=w.end,
                confidence=w.confidence,
                phonemes=clean_phones,
                char_start=w.char_start,
                char_end=w.char_end,
            )
        )

    return cleaned_words


_SYNTHETIC_UTTERANCES = [
    (
        "spk01_utt01",
        [
            ("she", [(1600, 4000, "sh"), (4000, 6400, "iy")]),
            ("had", [(7200, 8800, "hh"), (8800, 10400, "ae"), (10400, 12000, "d")]),
            (
                "dark",
                [
                    (12800, 14400, "d"),
                    (14400, 16800, "aa"),
                    (16800, 18000, "r"),
                    (18000, 19200, "k"),
                ],
            ),
            ("suit", [(20000, 22400, "s"), (22400, 24800, "uw"), (24800, 26400, "t")]),
        ],
        32000,
    ),
    (
        "spk01_utt02",
        [
            (
                "water",
                [
                    (1600, 3200, "w"),
                    (3200, 5600, "aa"),
                    (5600, 6400, "t"),
                    (6400, 7200, "er"),
                ],
            ),
            ("all", [(8000, 10400, "ao"), (10400, 12800, "l")]),
            ("year", [(13600, 16000, "y"), (16000, 18400, "ih"), (18400, 20000, "r")]),
        ],
        24000,
    ),
    (
        "spk01_utt03",
        [
            ("ask", [(1600, 4000, "ae"), (4000, 5600, "s"), (5600, 6400, "k")]),
            ("me", [(7200, 8800, "m"), (8800, 11200, "iy")]),
            ("to", [(12000, 13600, "t"), (13600, 15200, "uw")]),
            (
                "carry",
                [
                    (16000, 17600, "k"),
                    (17600, 20000, "ae"),
                    (20000, 21600, "r"),
                    (21600, 23200, "iy"),
                ],
            ),
        ],
        25600,
    ),
    (
        "spk02_utt01",
        [
            ("an", [(1600, 3200, "ae"), (3200, 4800, "n")]),
            ("oily", [(5600, 8800, "oy"), (8800, 10400, "l"), (10400, 12000, "iy")]),
            ("rag", [(12800, 15200, "r"), (15200, 17600, "ae"), (17600, 19200, "g")]),
            ("like", [(20000, 21600, "l"), (21600, 24800, "ay"), (24800, 26400, "k")]),
        ],
        28800,
    ),
    (
        "spk02_utt02",
        [
            ("that", [(1600, 3200, "dh"), (3200, 5600, "ae"), (5600, 6400, "t")]),
            ("suit", [(7200, 9600, "s"), (9600, 12000, "uw"), (12000, 13600, "t")]),
            (
                "looks",
                [
                    (14400, 16000, "l"),
                    (16000, 18400, "uh"),
                    (18400, 20000, "k"),
                    (20000, 20800, "s"),
                ],
            ),
        ],
        24000,
    ),
    (
        "spk02_utt03",
        [
            (
                "clean",
                [
                    (1600, 3200, "k"),
                    (3200, 4800, "l"),
                    (4800, 7200, "iy"),
                    (7200, 8000, "n"),
                ],
            ),
            ("and", [(8800, 11200, "ae"), (11200, 12000, "n"), (12000, 12800, "d")]),
            (
                "bright",
                [
                    (13600, 15200, "b"),
                    (15200, 16800, "r"),
                    (16800, 20000, "ay"),
                    (20000, 21600, "t"),
                ],
            ),
        ],
        24000,
    ),
    (
        "spk03_utt01",
        [
            (
                "speech",
                [
                    (1600, 4000, "s"),
                    (4000, 5600, "p"),
                    (5600, 7200, "iy"),
                    (7200, 8800, "ch"),
                ],
            ),
            ("time", [(9600, 11200, "t"), (11200, 14400, "ay"), (14400, 16000, "m")]),
            (
                "alignment",
                [
                    (16800, 18400, "ah"),
                    (18400, 20000, "l"),
                    (20000, 23200, "ay"),
                    (23200, 24800, "n"),
                    (24800, 26400, "t"),
                ],
            ),
        ],
        28800,
    ),
    (
        "spk03_utt02",
        [
            (
                "models",
                [
                    (1600, 3200, "m"),
                    (3200, 5600, "aa"),
                    (5600, 6400, "d"),
                    (6400, 7200, "l"),
                    (7200, 8000, "z"),
                ],
            ),
            (
                "estimate",
                [
                    (8800, 10400, "eh"),
                    (10400, 12000, "s"),
                    (12000, 13600, "t"),
                    (13600, 15200, "ah"),
                    (15200, 16000, "m"),
                    (16000, 16800, "ey"),
                    (16800, 17600, "t"),
                ],
            ),
            (
                "boundaries",
                [
                    (18400, 20000, "b"),
                    (20000, 23200, "aw"),
                    (23200, 24000, "n"),
                    (24000, 24800, "d"),
                    (24800, 26400, "er"),
                    (26400, 27200, "iy"),
                    (27200, 28000, "z"),
                ],
            ),
        ],
        30400,
    ),
    (
        "spk03_utt03",
        [
            (
                "fast",
                [
                    (1600, 4000, "f"),
                    (4000, 6400, "ae"),
                    (6400, 7200, "s"),
                    (7200, 8000, "t"),
                ],
            ),
            ("and", [(8800, 10400, "ae"), (10400, 11200, "n"), (11200, 12000, "d")]),
            (
                "accurate",
                [
                    (12800, 15200, "ae"),
                    (15200, 16800, "k"),
                    (16800, 17600, "y"),
                    (17600, 20000, "er"),
                    (20000, 21600, "ah"),
                    (21600, 22400, "t"),
                ],
            ),
        ],
        25600,
    ),
    (
        "spk03_utt04",
        [
            (
                "local",
                [
                    (1600, 3200, "l"),
                    (3200, 5600, "ow"),
                    (5600, 6400, "k"),
                    (6400, 7200, "l"),
                ],
            ),
            (
                "subtitle",
                [
                    (8000, 10400, "s"),
                    (10400, 12000, "ah"),
                    (12000, 12800, "b"),
                    (12800, 13600, "t"),
                    (13600, 15200, "ay"),
                    (15200, 16000, "t"),
                    (16000, 16800, "l"),
                ],
            ),
            (
                "workbench",
                [
                    (17600, 19200, "w"),
                    (19200, 21600, "er"),
                    (21600, 22400, "k"),
                    (22400, 23200, "b"),
                    (23200, 24800, "eh"),
                    (24800, 25600, "n"),
                    (25600, 27200, "ch"),
                ],
            ),
        ],
        30400,
    ),
]


def _generate_synthetic_audio(total_samples: int, sample_rate: int = 16000) -> bytes:
    """Generate modulated sinusoidal speech-like waveform with RMS >= 1e-4."""
    t = np.arange(total_samples, dtype=np.float64) / float(sample_rate)
    carrier = np.sin(2.0 * math.pi * 320.0 * t) + 0.4 * np.sin(2.0 * math.pi * 640.0 * t)
    envelope = 0.5 + 0.5 * np.sin(2.0 * math.pi * 4.0 * t)
    signal = 0.25 * carrier * envelope
    pcm = np.clip(signal * 32767.0, -32768.0, 32767.0).astype(np.int16)
    return pcm.tobytes()


def _format_praat_textgrid(
    words_spec: list[tuple[str, list[tuple[int, int, str]]]],
    total_samples: int,
    sample_rate: int = 16000,
) -> str:
    """Format Praat long-form TextGrid content for speech words and phones."""
    total_sec = total_samples / float(sample_rate)

    word_intervals: list[tuple[float, float, str]] = []
    cur_sec = 0.0
    for w_text, p_list in words_spec:
        w_start = p_list[0][0] / float(sample_rate)
        w_end = p_list[-1][1] / float(sample_rate)
        if w_start > cur_sec:
            word_intervals.append((cur_sec, w_start, ""))
        word_intervals.append((w_start, w_end, w_text))
        cur_sec = w_end
    if cur_sec < total_sec:
        word_intervals.append((cur_sec, total_sec, ""))

    phone_intervals: list[tuple[float, float, str]] = []
    cur_sec = 0.0
    for _w_text, p_list in words_spec:
        for p_start_s, p_end_s, p_name in p_list:
            p_start = p_start_s / float(sample_rate)
            p_end = p_end_s / float(sample_rate)
            if p_start > cur_sec:
                phone_intervals.append((cur_sec, p_start, "sil"))
            phone_intervals.append((p_start, p_end, p_name))
            cur_sec = p_end
    if cur_sec < total_sec:
        phone_intervals.append((cur_sec, total_sec, "sil"))

    lines: list[str] = [
        'File type = "ooTextFile"',
        'Object class = "TextGrid"',
        "",
        "xmin = 0.0",
        f"xmax = {total_sec:.6f}",
        "tiers? <exists>",
        "size = 2",
        "item []:",
        "    item [1]:",
        '        class = "IntervalTier"',
        '        name = "words"',
        "        xmin = 0.0",
        f"        xmax = {total_sec:.6f}",
        f"        intervals: size = {len(word_intervals)}",
    ]
    for idx, (xmin, xmax, text) in enumerate(word_intervals, start=1):
        lines.extend(
            [
                f"        intervals [{idx}]:",
                f"            xmin = {xmin:.6f}",
                f"            xmax = {xmax:.6f}",
                f'            text = "{text}"',
            ]
        )

    lines.extend(
        [
            "    item [2]:",
            '        class = "IntervalTier"',
            '        name = "phones"',
            "        xmin = 0.0",
            f"        xmax = {total_sec:.6f}",
            f"        intervals: size = {len(phone_intervals)}",
        ]
    )
    for idx, (xmin, xmax, text) in enumerate(phone_intervals, start=1):
        lines.extend(
            [
                f"        intervals [{idx}]:",
                f"            xmin = {xmin:.6f}",
                f"            xmax = {xmax:.6f}",
                f'            text = "{text}"',
            ]
        )

    return "\n".join(lines) + "\n"


def stage_synthetic_benchmark(target_dir: Path | str) -> Path:
    """Generate 10 offline synthetic utterances with exact ground-truth boundaries.

    Writes paired .wav, .phn, .wrd, and .TextGrid files for each utterance.
    WAV files are valid uncompressed mono PCM16 at 16000 Hz with RMS >= 1e-4.
    """
    out_dir = Path(target_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    sample_rate = 16000

    for utt_id, words_spec, total_samples in _SYNTHETIC_UTTERANCES:
        wav_path = out_dir / f"{utt_id}.wav"
        pcm_bytes = _generate_synthetic_audio(total_samples, sample_rate)
        with wave.open(str(wav_path), "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(pcm_bytes)

        phn_lines: list[str] = []
        cur_sample = 0
        for _w_text, p_list in words_spec:
            w_start = p_list[0][0]
            if w_start > cur_sample:
                phn_lines.append(f"{cur_sample} {w_start} h#")
            for p_start, p_end, p_name in p_list:
                phn_lines.append(f"{p_start} {p_end} {p_name}")
            cur_sample = p_list[-1][1]
        if cur_sample < total_samples:
            phn_lines.append(f"{cur_sample} {total_samples} h#")

        phn_path = out_dir / f"{utt_id}.phn"
        phn_path.write_text("\n".join(phn_lines) + "\n", encoding="utf-8")

        wrd_lines: list[str] = []
        for w_text, p_list in words_spec:
            w_start = p_list[0][0]
            w_end = p_list[-1][1]
            wrd_lines.append(f"{w_start} {w_end} {w_text}")

        wrd_path = out_dir / f"{utt_id}.wrd"
        wrd_path.write_text("\n".join(wrd_lines) + "\n", encoding="utf-8")

        tg_content = _format_praat_textgrid(words_spec, total_samples, sample_rate)
        tg_path = out_dir / f"{utt_id}.TextGrid"
        tg_path.write_text(tg_content, encoding="utf-8")

    return out_dir
