"""Token-span text normalization and reversible subtitle cue projection."""

import re
import unicodedata
from dataclasses import dataclass

from .export import milliseconds
from .models import Cue, WordToken, validate_text

CONTRACTIONS: dict[str, list[str]] = {
    # 'not' contractions
    "ain't": ["is", "not"],
    "aren't": ["are", "not"],
    "can't": ["can", "not"],
    "couldn't": ["could", "not"],
    "daren't": ["dare", "not"],
    "didn't": ["did", "not"],
    "doesn't": ["does", "not"],
    "don't": ["do", "not"],
    "hadn't": ["had", "not"],
    "hasn't": ["has", "not"],
    "haven't": ["have", "not"],
    "isn't": ["is", "not"],
    "mayn't": ["may", "not"],
    "mightn't": ["might", "not"],
    "mustn't": ["must", "not"],
    "needn't": ["need", "not"],
    "oughtn't": ["ought", "not"],
    "shan't": ["shall", "not"],
    "shouldn't": ["should", "not"],
    "wasn't": ["was", "not"],
    "weren't": ["were", "not"],
    "won't": ["will", "not"],
    "wouldn't": ["would", "not"],
    # 'verb' contractions
    "i'm": ["i", "am"],
    "you're": ["you", "are"],
    "he's": ["he", "is"],
    "she's": ["she", "is"],
    "it's": ["it", "is"],
    "we're": ["we", "are"],
    "they're": ["they", "are"],
    "there's": ["there", "is"],
    "here's": ["here", "is"],
    "that's": ["that", "is"],
    "what's": ["what", "is"],
    "who's": ["who", "is"],
    "where's": ["where", "is"],
    "when's": ["when", "is"],
    "why's": ["why", "is"],
    "how's": ["how", "is"],
    # 'have' contractions
    "i've": ["i", "have"],
    "you've": ["you", "have"],
    "we've": ["we", "have"],
    "they've": ["they", "have"],
    "could've": ["could", "have"],
    "should've": ["should", "have"],
    "would've": ["would", "have"],
    "might've": ["might", "have"],
    "must've": ["must", "have"],
    "who've": ["who", "have"],
    "what've": ["what", "have"],
    # 'will' contractions
    "i'll": ["i", "will"],
    "you'll": ["you", "will"],
    "he'll": ["he", "will"],
    "she'll": ["she", "will"],
    "it'll": ["it", "will"],
    "we'll": ["we", "will"],
    "they'll": ["they", "will"],
    "that'll": ["that", "will"],
    "there'll": ["there", "will"],
    "who'll": ["who", "will"],
    "what'll": ["what", "will"],
    "where'll": ["where", "will"],
    "when'll": ["when", "will"],
    "why'll": ["why", "will"],
    "how'll": ["how", "will"],
    # 'would' / 'had' contractions
    "i'd": ["i", "would"],
    "you'd": ["you", "would"],
    "he'd": ["he", "would"],
    "she'd": ["she", "would"],
    "it'd": ["it", "would"],
    "we'd": ["we", "would"],
    "they'd": ["they", "would"],
    "that'd": ["that", "would"],
    "there'd": ["there", "would"],
    "who'd": ["who", "would"],
    "what'd": ["what", "did"],
    "where'd": ["where", "did"],
    "when'd": ["when", "did"],
    "why'd": ["why", "did"],
    "how'd": ["how", "did"],
    # others
    "let's": ["let", "us"],
    "y'all": ["you", "all"],
}

ONES: dict[int, str] = {
    0: "zero",
    1: "one",
    2: "two",
    3: "three",
    4: "four",
    5: "five",
    6: "six",
    7: "seven",
    8: "eight",
    9: "nine",
    10: "ten",
    11: "eleven",
    12: "twelve",
    13: "thirteen",
    14: "fourteen",
    15: "fifteen",
    16: "sixteen",
    17: "seventeen",
    18: "eighteen",
    19: "nineteen",
}

TENS: dict[int, str] = {
    2: "twenty",
    3: "thirty",
    4: "forty",
    5: "fifty",
    6: "sixty",
    7: "seventy",
    8: "eighty",
    9: "ninety",
}

SCALES: list[tuple[int, str]] = [
    (1_000_000_000_000, "trillion"),
    (1_000_000_000, "billion"),
    (1_000_000, "million"),
    (1_000, "thousand"),
    (100, "hundred"),
]

ORDINALS: dict[str, str] = {
    "zero": "zeroth",
    "one": "first",
    "two": "second",
    "three": "third",
    "four": "fourth",
    "five": "fifth",
    "six": "sixth",
    "seven": "seventh",
    "eight": "eighth",
    "nine": "ninth",
    "ten": "tenth",
    "eleven": "eleventh",
    "twelve": "twelfth",
    "thirteen": "thirteenth",
    "fourteen": "fourteenth",
    "fifteen": "fifteenth",
    "sixteen": "sixteenth",
    "seventeen": "seventeenth",
    "eighteen": "eighteenth",
    "nineteen": "nineteenth",
    "twenty": "twentieth",
    "thirty": "thirtieth",
    "forty": "fortieth",
    "fifty": "fiftieth",
    "sixty": "sixtieth",
    "seventy": "seventieth",
    "eighty": "eightieth",
    "ninety": "ninetieth",
    "hundred": "hundredth",
    "thousand": "thousandth",
    "million": "millionth",
    "billion": "billionth",
    "trillion": "trillionth",
}

DIGIT_WORDS: dict[str, str] = {
    "0": "zero",
    "1": "one",
    "2": "two",
    "3": "three",
    "4": "four",
    "5": "five",
    "6": "six",
    "7": "seven",
    "8": "eight",
    "9": "nine",
}

PUNCT_LEFT = set(".,!?;:\"'()[]{}<>-—–_`~@#$%^&*+=|\\/«»“”‘’…„‚‹›¿¡€£¥₹₽₩\u2212")
PUNCT_RIGHT = set(".,!?;:\"'()[]{}<>-—–_`~@#$%^&*+=|\\/«»“”‘’…„‚‹›¿¡€£¥₹₽₩\u2212")


def _is_boundary_punct(c: str) -> bool:
    if c in PUNCT_LEFT:
        return True
    cat = unicodedata.category(c)
    return cat.startswith(("P", "S"))


def integer_to_words(n: int) -> list[str]:
    if n == 0:
        return ["zero"]
    if n < 0:
        return ["negative"] + integer_to_words(-n)
    words: list[str] = []
    for scale_val, scale_name in SCALES:
        if n >= scale_val:
            count = n // scale_val
            n %= scale_val
            words.extend(integer_to_words(count))
            words.append(scale_name)
    if n >= 20:
        tens_val = n // 10
        n %= 10
        words.append(TENS[tens_val])
    if 0 < n < 20:
        words.append(ONES[n])
    return words


def parse_number_to_words(token_str: str) -> list[str] | None:
    cleaned = token_str.replace(",", "").replace("\u2212", "-")
    ordinal_match = re.fullmatch(r"^(\d+)(st|nd|rd|th)$", cleaned, re.IGNORECASE)
    if ordinal_match:
        num = int(ordinal_match.group(1))
        words = integer_to_words(num)
        if words:
            last = words[-1]
            words[-1] = ORDINALS.get(last, last + "th")
        return words

    decimal_match = re.fullmatch(r"^(-?)(\d+)\.(\d+)$", cleaned)
    if decimal_match:
        sign, int_part, dec_part = decimal_match.groups()
        words = []
        if sign == "-":
            words.append("negative")
        words.extend(integer_to_words(int(int_part)))
        words.append("point")
        for digit in dec_part:
            words.append(DIGIT_WORDS.get(digit, digit))
        return words

    int_match = re.fullmatch(r"^(-?\d+)$", cleaned)
    if int_match:
        try:
            num = int(int_match.group(1))
            return integer_to_words(num)
        except ValueError:
            return None

    return None


@dataclass(frozen=True)
class TokenSpan:
    token: str
    normalized: str
    char_start: int
    char_end: int

    def __post_init__(self) -> None:
        validate_text(self.token, "token", allow_newlines=False)
        validate_text(self.normalized, "normalized", allow_newlines=False)
        if (
            isinstance(self.char_start, bool)
            or not isinstance(self.char_start, int)
            or self.char_start < 0
        ):
            raise ValueError("char_start must be a nonnegative integer")
        if (
            isinstance(self.char_end, bool)
            or not isinstance(self.char_end, int)
            or self.char_end < self.char_start
        ):
            raise ValueError("char_end must be an integer >= char_start")


def _process_word(token: str, char_start: int, char_end: int, results: list[TokenSpan]) -> None:
    clean_key = token.lower().replace("’", "'").replace("‘", "'")
    if clean_key in CONTRACTIONS:
        for norm_word in CONTRACTIONS[clean_key]:
            results.append(
                TokenSpan(
                    token=token,
                    normalized=norm_word,
                    char_start=char_start,
                    char_end=char_end,
                )
            )
        return

    num_words = parse_number_to_words(token)
    if num_words is not None:
        for norm_word in num_words:
            results.append(
                TokenSpan(
                    token=token,
                    normalized=norm_word,
                    char_start=char_start,
                    char_end=char_end,
                )
            )
        return

    norm_word = token.lower().replace("’", "'").replace("‘", "'")
    if re.fullmatch(r"^[a-z]+(\.[a-z]+)+$", norm_word):
        norm_word = norm_word.replace(".", "")
    norm_word = "".join(
        c for c in unicodedata.normalize("NFKD", norm_word) if not unicodedata.combining(c)
    )
    if not norm_word:
        norm_word = token.lower().replace("’", "'").replace("‘", "'")
    results.append(
        TokenSpan(
            token=token,
            normalized=norm_word,
            char_start=char_start,
            char_end=char_end,
        )
    )


def normalize_text_spans(text: str) -> list[TokenSpan]:
    if isinstance(text, bool) or not isinstance(text, str):
        raise ValueError("text must be a string")
    if any(0xD800 <= ord(c) <= 0xDFFF for c in text):
        raise ValueError("text must not contain surrogate characters")
    if any(
        (ord(c) < 32 and c not in "\t\n\r") or ord(c) == 127 or (128 <= ord(c) <= 159) for c in text
    ):
        raise ValueError("text must not contain control characters")

    results: list[TokenSpan] = []
    for match in re.finditer(r"\S+", text):
        c_start, c_end = match.start(), match.end()
        left = c_start
        right = c_end
        while left < right and _is_boundary_punct(text[left]):
            if text[left] in ("-", "\u2212") and left + 1 < right and text[left + 1].isdigit():
                break
            left += 1
        while right > left and _is_boundary_punct(text[right - 1]):
            right -= 1
        if left >= right:
            continue

        raw_token = text[left:right]
        if re.search(r"[^\s\-—–\u2212]+[\-—–\u2212]+[^\s\-—–\u2212]+", raw_token):
            for part in re.finditer(r"[^\s\-—–\u2212]+", raw_token):
                p_start = left + part.start()
                p_end = left + part.end()
                p_token = text[p_start:p_end]
                _process_word(p_token, p_start, p_end, results)
        else:
            _process_word(raw_token, left, right, results)

    return results


def _adjust_cue_timing(
    cue_start: float,
    cue_end: float,
    token_dur: float,
    prev_end: float | None,
) -> tuple[float, float]:
    """Ensure cue timings are ordered, non-overlapping, and do not collapse on ms rounding."""
    if prev_end is not None and cue_start < prev_end:
        cue_start = prev_end
    if cue_end <= cue_start:
        cue_end = round(cue_start + max(token_dur, 0.001), 3)
    while milliseconds(cue_end) <= milliseconds(cue_start):
        cue_end = round(cue_end + 0.001, 3)
    return cue_start, cue_end


def _extract_cue_id_and_text(raw_block: str, default_id: str) -> tuple[str, str]:
    cleaned_block = raw_block.replace("\t", " ")
    lines = [ln.strip() for ln in cleaned_block.splitlines() if ln.strip()]
    if not lines:
        return default_id, ""
    first = lines[0]
    is_id = False
    if len(lines) > 1 and first.isascii() and len(first) <= 128:
        if re.fullmatch(r"^(?:cue|id)[-_][A-Za-z0-9_-]+$", first, re.IGNORECASE):
            is_id = True
        elif re.fullmatch(r"^c\d+$", first, re.IGNORECASE):
            is_id = True
        elif re.fullmatch(r"^\d+$", first):
            is_id = True

    payload_lines = lines[1:] if is_id else lines
    payload_lines = [
        ln for ln in payload_lines if not re.match(r"^\d{1,2}:[0-9:.,]+\s*-->\s*[0-9:.,]+", ln)
    ]
    cue_id = first if is_id else default_id
    cue_text = "\n".join(payload_lines)
    return cue_id, cue_text


def project_tokens_to_cues(
    tokens: list[WordToken], original_text: str, id_prefix: str = "c"
) -> list[Cue]:
    if not isinstance(tokens, list) or any(not isinstance(t, WordToken) for t in tokens):
        raise ValueError("tokens must be a list of WordToken instances")
    if isinstance(original_text, bool) or not isinstance(original_text, str):
        raise ValueError("original_text must be a string")
    if (
        isinstance(id_prefix, bool)
        or not isinstance(id_prefix, str)
        or not id_prefix
        or len(id_prefix) > 64
        or any(not (c.isascii() and (c.isalnum() or c in "_-")) for c in id_prefix)
    ):
        raise ValueError("id_prefix must be a non-empty ASCII identifier")
    if any(0xD800 <= ord(c) <= 0xDFFF for c in original_text):
        raise ValueError("original_text must not contain surrogate characters")
    if any(
        (ord(c) < 32 and c not in "\t\n\r") or ord(c) == 127 or (128 <= ord(c) <= 159)
        for c in original_text
    ):
        raise ValueError("original_text must not contain control characters")

    if not tokens or not original_text.strip():
        return []

    block_matches = list(re.finditer(r"\S[^\n]*(?:\n(?!\s*\n)[^\n]*)*", original_text))
    if not block_matches:
        return []

    has_char_spans = all(t.char_start is not None for t in tokens)
    cues: list[Cue] = []
    cue_counter = 1
    used_ids: set[str] = set()

    def _allocate_id(candidate: str) -> str:
        base = candidate[:120]
        unique_id = base
        suffix = 1
        while unique_id in used_ids:
            unique_id = f"{base}_{suffix}"
            suffix += 1
        used_ids.add(unique_id)
        return unique_id

    if has_char_spans:
        for match in block_matches:
            b_start = match.start()
            b_end = match.end()
            raw_block = original_text[b_start:b_end].strip()

            b_tokens = [
                t for t in tokens if t.char_start is not None and b_start <= t.char_start < b_end
            ]
            if not b_tokens:
                continue

            raw_start = min(t.start for t in b_tokens)
            raw_end = max(t.end for t in b_tokens)
            token_dur = raw_end - raw_start
            prev_end = cues[-1].end if cues else None
            cue_start, cue_end = _adjust_cue_timing(raw_start, raw_end, token_dur, prev_end)

            cand_id, cue_text = _extract_cue_id_and_text(raw_block, f"{id_prefix}{cue_counter}")
            cue_counter += 1
            if not cue_text:
                continue
            final_id = _allocate_id(cand_id)
            cues.append(Cue(id=final_id, start=cue_start, end=cue_end, text=cue_text))
    else:
        if len(block_matches) == 1:
            raw_block = original_text.strip()
            raw_start = min(t.start for t in tokens)
            raw_end = max(t.end for t in tokens)
            token_dur = raw_end - raw_start
            cue_start, cue_end = _adjust_cue_timing(raw_start, raw_end, token_dur, None)
            cand_id, cue_text = _extract_cue_id_and_text(raw_block, f"{id_prefix}1")
            if cue_text:
                final_id = _allocate_id(cand_id)
                cues.append(Cue(id=final_id, start=cue_start, end=cue_end, text=cue_text))
        else:
            block_spans = [normalize_text_spans(m.group(0)) for m in block_matches]
            token_idx = 0
            for match, b_spans in zip(block_matches, block_spans, strict=True):
                count = len(b_spans)
                b_tokens = tokens[token_idx : token_idx + count]
                token_idx += count
                if not b_tokens:
                    continue
                raw_block = match.group(0).strip()
                cand_id, cue_text = _extract_cue_id_and_text(raw_block, f"{id_prefix}{cue_counter}")
                cue_counter += 1
                if not cue_text:
                    continue
                final_id = _allocate_id(cand_id)
                raw_start = min(t.start for t in b_tokens)
                raw_end = max(t.end for t in b_tokens)
                token_dur = raw_end - raw_start
                prev_end = cues[-1].end if cues else None
                cue_start, cue_end = _adjust_cue_timing(raw_start, raw_end, token_dur, prev_end)
                cues.append(
                    Cue(
                        id=final_id,
                        start=cue_start,
                        end=cue_end,
                        text=cue_text,
                    )
                )

    return cues
