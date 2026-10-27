"""Phone-set folding so that reference and aligner phone boundaries can be compared.

Reference corpora and aligners use different inventories:

* TIMIT: 61 phones; stops are split into closure + release ("bcl b").
* Buckeye: TIMIT-like lowercase labels plus nasalized vowels ("aan", "ehn"),
  glottal stops ("tq") and noise markers.
* MFA ``english_us_arpa``: ARPAbet with lexical stress digits ("AH0").

All are folded to the 39-phone set of Lee & Hon (1989), the convention used by
TIMIT phone-boundary benchmarks (e.g. FA-Bench). TIMIT/Buckeye stop closures are
merged with their release into one stop interval because ARPAbet aligners model
a stop as a single phone. Labels without a phonetic counterpart (glottal stop,
silence, noise) are removed.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

from .models import PhonemeCue

# Lee & Hon (1989) 61 -> 39 folding (after closure merging and q removal)
_FOLD_39: dict[str, str] = {
    "ao": "aa",
    "ax": "ah",
    "ax-h": "ah",
    "axr": "er",
    "hv": "hh",
    "ix": "ih",
    "el": "l",
    "em": "m",
    "en": "n",
    "nx": "n",
    "eng": "ng",
    "zh": "sh",
    "ux": "uw",
    # Flap: ARPAbet dictionaries spell it as /t/ (most frequent) or /d/
    "dx": "t",
}

_CLOSURES: dict[str, set[str]] = {
    "bcl": {"b"},
    "dcl": {"d", "jh"},
    "gcl": {"g"},
    "pcl": {"p"},
    "tcl": {"t", "ch"},
    "kcl": {"k"},
}
_CLOSURE_DEFAULT: dict[str, str] = {
    "bcl": "b",
    "dcl": "d",
    "gcl": "g",
    "pcl": "p",
    "tcl": "t",
    "kcl": "k",
}

_DROP: set[str] = {
    "h#",
    "pau",
    "epi",
    "q",
    "tq",
    "sil",
    "sp",
    "spn",
    "",
    "<sil>",
    "{b_trans}",
    "{e_trans}",
}

_NASALIZED_VOWEL = re.compile(r"^(aa|ae|ah|ao|aw|ay|eh|er|ey|ih|iy|ow|oy|uh|uw)n$")
_STRESS = re.compile(r"[0-2]$")


def fold_label(label: str) -> str | None:
    """Fold one phone label (any supported inventory) to the 39-phone set."""
    p = label.strip().lower()
    p = _STRESS.sub("", p)
    if p in _DROP or p.startswith("<") or p.startswith("{"):
        return None
    m = _NASALIZED_VOWEL.match(p)
    if m:
        p = m.group(1)
    if p in _CLOSURE_DEFAULT:
        p = _CLOSURE_DEFAULT[p]
    return _FOLD_39.get(p, p)


def fold_phones(cues: Iterable[PhonemeCue]) -> list[PhonemeCue]:
    """Merge closure+release pairs, fold labels to 39 phones, drop non-phones."""
    seq = sorted(cues, key=lambda c: (c.start, c.end))
    out: list[PhonemeCue] = []
    i = 0
    while i < len(seq):
        cur = seq[i]
        lab = cur.phoneme.strip().lower()
        if lab in _CLOSURES and i + 1 < len(seq):
            nxt = seq[i + 1]
            nlab = nxt.phoneme.strip().lower()
            if nlab in _CLOSURES[lab] and abs(nxt.start - cur.end) < 1e-6:
                folded = fold_label(nlab)
                if folded is not None:
                    out.append(PhonemeCue(folded, cur.start, nxt.end, min(cur.confidence, 1.0)))
                i += 2
                continue
        folded = fold_label(lab)
        if folded is not None:
            out.append(PhonemeCue(folded, cur.start, cur.end, cur.confidence))
        i += 1
    return out


__all__ = ["fold_label", "fold_phones"]
