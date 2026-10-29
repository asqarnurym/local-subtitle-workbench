"""BRQE: Boundary Refinement & Quality Estimation after forced alignment.

A small 1D-CNN looks at a log-mel window (+-100 ms, 5 ms hop) centred on each MFA word
or phone boundary and predicts (1) a correction dt to the boundary and (2) the
probability that the uncorrected boundary is more than 20 ms from the manual
reference. A constant-offset refiner (median shift per boundary kind, learned on the
same training speakers) is the mandatory simple rival (docs/IMPROVEMENT_PLAN.md §6).

Training targets come only from manually annotated corpora (Buckeye train speakers);
training on forced-alignment ("silver") boundaries would teach the model MFA itself.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import wave
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from .metrics import _align_token_sequences
from .models import PhonemeCue, WordToken
from .phone_sets import fold_phones

SAMPLE_RATE = 16000
HOP_SAMPLES = 80  # 5 ms
N_FFT = 400  # 25 ms
N_MELS = 64
HALF_WINDOW = 20  # frames each side -> +-100 ms
WINDOW = 2 * HALF_WINDOW + 1
MAX_SHIFT_S = 0.1  # regression targets beyond +-100 ms are not refinable
ERROR_THRESHOLD_S = 0.02
MIN_DURATION_S = 0.005

KINDS = ("word_start", "word_end", "phone_start", "phone_end")
N_SCALARS = 6  # is_start, is_word, scenario_b, log duration, sub-frame offset, bias


@dataclass(frozen=True)
class Boundary:
    """One predicted boundary, optionally paired with its manual reference time."""

    utt: str
    time: float
    kind: str  # one of KINDS
    scenario: str  # "A" or "B"
    duration: float  # duration of the token the boundary belongs to
    ref: float | None = None
    speaker: str = ""


# ---------------------------------------------------------------------------
# Audio features
# ---------------------------------------------------------------------------


def read_wav_mono(path: Path | str) -> np.ndarray:
    with wave.open(str(path), "rb") as w:
        if w.getframerate() != SAMPLE_RATE or w.getsampwidth() != 2 or w.getnchannels() != 1:
            raise ValueError(f"{path}: expected 16 kHz mono PCM16")
        raw = w.readframes(w.getnframes())
    return np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0


class MelExtractor:
    """Log-mel (64 bands, 25 ms window, 5 ms hop), per-utterance mean/variance normalized."""

    def __init__(self) -> None:
        import torchaudio

        self._mel = torchaudio.transforms.MelSpectrogram(
            sample_rate=SAMPLE_RATE,
            n_fft=N_FFT,
            win_length=N_FFT,
            hop_length=HOP_SAMPLES,
            n_mels=N_MELS,
            center=True,
        )

    def __call__(self, samples: np.ndarray) -> np.ndarray:
        import torch

        with torch.inference_mode():
            mel = self._mel(torch.from_numpy(np.ascontiguousarray(samples)))
        logmel = np.log(mel.numpy() + 1e-6)
        mu = logmel.mean(axis=1, keepdims=True)
        sd = logmel.std(axis=1, keepdims=True) + 1e-5
        return ((logmel - mu) / sd).astype(np.float32)  # (N_MELS, frames)


def window_at(mel: np.ndarray, t: float) -> tuple[np.ndarray, float]:
    """Mel window centred on the frame nearest to ``t`` and the sub-frame offset (frames)."""
    pos = t * SAMPLE_RATE / HOP_SAMPLES
    centre = int(round(pos))
    lo, hi = centre - HALF_WINDOW, centre + HALF_WINDOW + 1
    n = mel.shape[1]
    out = np.zeros((N_MELS, WINDOW), dtype=np.float32)
    src_lo, src_hi = max(lo, 0), min(hi, n)
    if src_hi > src_lo:
        out[:, src_lo - lo : src_hi - lo] = mel[:, src_lo:src_hi]
    return out, pos - centre


def scalar_features(b: Boundary, offset_frames: float) -> np.ndarray:
    return np.array(
        [
            1.0 if b.kind.endswith("start") else 0.0,
            1.0 if b.kind.startswith("word") else 0.0,
            1.0 if b.scenario == "B" else 0.0,
            float(np.log(max(b.duration, 1e-3))),
            float(offset_frames),
            1.0,
        ],
        dtype=np.float32,
    )


# ---------------------------------------------------------------------------
# Boundaries from predictions (+ references for training / evaluation)
# ---------------------------------------------------------------------------


def boundaries_for_utterance(
    utt: str,
    scenario: str,
    words: list[WordToken],
    phones: list[PhonemeCue] | None,
    ref_words: list[WordToken] | None = None,
    ref_phones: list[PhonemeCue] | None = None,
    speaker: str = "",
) -> list[Boundary]:
    """All word and phone boundaries of one prediction; matched ones carry ``ref``.

    Order: for each word (start, end), then for each folded phone (start, end).
    Matching is the benchmark's own (word keys via the reference normalizer, phones
    after folding to 39 labels), so training pairs are exactly the evaluated pairs.
    """
    out: list[Boundary] = []

    def add(pred: list, ref: list | None, tier: str) -> None:
        pairs = _align_token_sequences(pred, ref)[0] if ref else []
        ref_of = {id(p): r for p, r in pairs}
        for tok in pred:
            r = ref_of.get(id(tok))
            dur = tok.end - tok.start
            for kind, t, rt in (
                (f"{tier}_start", tok.start, r.start if r else None),
                (f"{tier}_end", tok.end, r.end if r else None),
            ):
                out.append(Boundary(utt, t, kind, scenario, dur, rt, speaker))

    add(words, ref_words, "word")
    if phones:
        add(fold_phones(phones), fold_phones(ref_phones) if ref_phones else None, "phone")
    return out


# ---------------------------------------------------------------------------
# Refiners
# ---------------------------------------------------------------------------


class ConstantRefiner:
    """Median shift (reference - predicted) per (kind, scenario) on training boundaries."""

    name = "const"

    def __init__(self, offsets: dict[str, float] | None = None) -> None:
        self.offsets = dict(offsets or {})

    def fit(self, boundaries: Iterable[Boundary]) -> ConstantRefiner:
        groups: dict[str, list[float]] = {}
        for b in boundaries:
            if b.ref is not None and abs(b.ref - b.time) <= MAX_SHIFT_S:
                groups.setdefault(f"{b.kind}|{b.scenario}", []).append(b.ref - b.time)
        self.offsets = {k: float(np.median(v)) for k, v in sorted(groups.items())}
        return self

    def predict(self, boundaries: Sequence[Boundary], mels: dict[str, np.ndarray] | None = None):
        shift = np.array([self.offsets.get(f"{b.kind}|{b.scenario}", 0.0) for b in boundaries])
        return shift, np.full(len(boundaries), np.nan)


def _build_net(hidden: int = 128, dropout: float = 0.2):
    import torch
    from torch import nn

    class BRQENet(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.conv = nn.Sequential(
                nn.Conv1d(N_MELS, 96, 5, padding=2),
                nn.BatchNorm1d(96),
                nn.ReLU(),
                nn.Conv1d(96, 96, 5, padding=2),
                nn.BatchNorm1d(96),
                nn.ReLU(),
                nn.Conv1d(96, 32, 3, padding=1),
                nn.ReLU(),
            )
            self.mlp = nn.Sequential(
                nn.Linear(32 * WINDOW + N_SCALARS, hidden),
                nn.ReLU(),
                nn.Dropout(dropout),
            )
            self.reg = nn.Linear(hidden, 1)
            self.cls = nn.Linear(hidden, 1)

        def forward(self, x: torch.Tensor, s: torch.Tensor):
            h = self.conv(x).flatten(1)
            h = self.mlp(torch.cat([h, s], dim=1))
            # Shift in seconds, bounded to +-MAX_SHIFT_S; logit of P(|error| > 20 ms)
            return MAX_SHIFT_S * torch.tanh(self.reg(h)).squeeze(1), self.cls(h).squeeze(1)

    return BRQENet()


@dataclass
class TrainConfig:
    epochs: int = 12
    batch_size: int = 512
    lr: float = 1e-3
    weight_decay: float = 1e-4
    cls_weight: float = 0.5
    seed: int = 20260401
    hidden: int = 128
    dropout: float = 0.2


class BRQERefiner:
    """1D-CNN with a shift head and a reliability head."""

    name = "brqe"

    def __init__(self, config: TrainConfig | None = None) -> None:
        self.config = config or TrainConfig()
        self.net = None

    def _tensors(self, boundaries: Sequence[Boundary], mels: dict[str, np.ndarray]):
        x = np.empty((len(boundaries), N_MELS, WINDOW), dtype=np.float32)
        s = np.empty((len(boundaries), N_SCALARS), dtype=np.float32)
        for i, b in enumerate(boundaries):
            x[i], off = window_at(mels[b.utt], b.time)
            s[i] = scalar_features(b, off)
        return x, s

    def fit(self, boundaries: Sequence[Boundary], mels: dict[str, np.ndarray]) -> BRQERefiner:
        import torch

        cfg = self.config
        torch.manual_seed(cfg.seed)
        rng = np.random.default_rng(cfg.seed)
        train = [b for b in boundaries if b.ref is not None]
        if not train:
            raise ValueError("No matched boundaries to train on")
        x, s = self._tensors(train, mels)
        err = np.array([b.ref - b.time for b in train], dtype=np.float32)
        reg_mask = (np.abs(err) <= MAX_SHIFT_S).astype(np.float32)
        y_cls = (np.abs(err) > ERROR_THRESHOLD_S).astype(np.float32)
        y_reg = np.clip(err, -MAX_SHIFT_S, MAX_SHIFT_S)

        self.net = _build_net(cfg.hidden, cfg.dropout)
        opt = torch.optim.AdamW(self.net.parameters(), lr=cfg.lr, weight_decay=cfg.weight_decay)
        bce = torch.nn.BCEWithLogitsLoss()
        n = len(train)
        for _ in range(cfg.epochs):
            self.net.train()
            order = rng.permutation(n)
            for i in range(0, n, cfg.batch_size):
                idx = order[i : i + cfg.batch_size]
                xb, sb = torch.from_numpy(x[idx]), torch.from_numpy(s[idx])
                shift, logit = self.net(xb, sb)
                m = torch.from_numpy(reg_mask[idx])
                # L1 on seconds, scaled to ms so both losses are O(1)
                reg_loss = (
                    ((shift - torch.from_numpy(y_reg[idx])).abs() * 1000.0 * m).sum()
                    / m.sum().clamp(min=1.0)
                    / 20.0
                )
                cls_loss = bce(logit, torch.from_numpy(y_cls[idx]))
                loss = reg_loss + cfg.cls_weight * cls_loss
                opt.zero_grad()
                loss.backward()
                opt.step()
        self.net.eval()
        return self

    def predict(self, boundaries: Sequence[Boundary], mels: dict[str, np.ndarray]):
        import torch

        if self.net is None:
            raise RuntimeError("BRQE model is not trained or loaded")
        if not boundaries:
            return np.zeros(0), np.zeros(0)
        x, s = self._tensors(boundaries, mels)
        shifts, probs = [], []
        with torch.inference_mode():
            for i in range(0, len(boundaries), 4096):
                sh, lg = self.net(
                    torch.from_numpy(x[i : i + 4096]), torch.from_numpy(s[i : i + 4096])
                )
                shifts.append(sh.numpy())
                probs.append(torch.sigmoid(lg).numpy())
        return np.concatenate(shifts).astype(np.float64), np.concatenate(probs).astype(np.float64)

    # -- persistence -------------------------------------------------------
    def save(self, path: Path | str, extra: dict[str, Any] | None = None) -> str:
        import torch

        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        torch.save(self.net.state_dict(), path)
        meta = {
            "model": "BRQE 1D-CNN",
            "config": dataclasses.asdict(self.config),
            "features": {
                "n_mels": N_MELS,
                "hop_samples": HOP_SAMPLES,
                "n_fft": N_FFT,
                "window_frames": WINDOW,
                "max_shift_s": MAX_SHIFT_S,
            },
            "weights_sha256": _sha256(path),
            **(extra or {}),
        }
        path.with_suffix(".json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
        return meta["weights_sha256"]

    @classmethod
    def load(cls, path: Path | str) -> BRQERefiner:
        import torch

        path = Path(path)
        meta = json.loads(path.with_suffix(".json").read_text(encoding="utf-8"))
        if meta.get("weights_sha256") != _sha256(path):
            raise ValueError(f"BRQE weights {path} do not match their recorded sha256")
        cfg = TrainConfig(**meta["config"])
        self = cls(cfg)
        self.net = _build_net(cfg.hidden, cfg.dropout)
        self.net.load_state_dict(torch.load(path, map_location="cpu", weights_only=True))
        self.net.eval()
        return self


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ---------------------------------------------------------------------------
# Applying a refiner to aligned words
# ---------------------------------------------------------------------------


def _shifted(tokens: list, starts: np.ndarray, ends: np.ndarray, p_err: np.ndarray | None):
    """New token list with shifted times; keeps order, never inverts or overlaps tokens."""
    s, e = starts.copy(), ends.copy()
    for i in range(1, len(tokens)):
        if s[i] < e[i - 1]:  # overlap after shifting: meet in the middle
            mid = 0.5 * (s[i] + e[i - 1])
            s[i], e[i - 1] = mid, mid
    out = []
    for i, tok in enumerate(tokens):
        ns, ne = max(0.0, float(s[i])), float(e[i])
        if ne - ns < MIN_DURATION_S:
            ns, ne = tok.start, tok.end
        conf = tok.confidence if p_err is None else float(np.clip(1.0 - p_err[i], 0.0, 1.0))
        out.append(dataclasses.replace(tok, start=round(ns, 4), end=round(ne, 4), confidence=conf))
    return out


def refine_prediction(
    refiner: ConstantRefiner | BRQERefiner,
    utt: str,
    scenario: str,
    words: list[WordToken],
    phones: list[PhonemeCue] | None,
    mels: dict[str, np.ndarray],
) -> tuple[list[WordToken], list[PhonemeCue] | None]:
    """Refine word and phone boundaries of one prediction.

    Word confidence becomes 1 - max P(error > 20 ms) over its two boundaries (BRQE only).
    Phones are folded to 39 labels first, as in evaluation.
    """
    folded = fold_phones(phones) if phones else None
    bounds = boundaries_for_utterance(utt, scenario, words, phones)
    shift, prob = refiner.predict(bounds, mels)
    nw = len(words)
    w_start, w_end = shift[0 : 2 * nw : 2], shift[1 : 2 * nw : 2]
    w_p = None
    if len(prob) and not np.all(np.isnan(prob)):
        w_p = np.maximum(prob[0 : 2 * nw : 2], prob[1 : 2 * nw : 2])
    new_words = _shifted(
        words,
        np.array([w.start for w in words]) + w_start,
        np.array([w.end for w in words]) + w_end,
        w_p,
    )
    new_phones = None
    if folded:
        p_start, p_end = shift[2 * nw :: 2], shift[2 * nw + 1 :: 2]
        new_phones = _shifted(
            folded,
            np.array([p.start for p in folded]) + p_start,
            np.array([p.end for p in folded]) + p_end,
            None,
        )
    return new_words, new_phones


# ---------------------------------------------------------------------------
# Quality-estimation metrics (numpy, no extra dependencies)
# ---------------------------------------------------------------------------


def roc_auc(labels: np.ndarray, scores: np.ndarray) -> float | None:
    """Area under the ROC curve via the rank statistic (ties averaged)."""
    labels = np.asarray(labels, dtype=bool)
    pos, neg = labels.sum(), (~labels).sum()
    if pos == 0 or neg == 0:
        return None
    order = np.argsort(scores, kind="mergesort")
    ranks = np.empty(len(scores), dtype=np.float64)
    sorted_scores = np.asarray(scores)[order]
    i = 0
    while i < len(scores):
        j = i
        while j + 1 < len(scores) and sorted_scores[j + 1] == sorted_scores[i]:
            j += 1
        ranks[order[i : j + 1]] = 0.5 * (i + j) + 1.0
        i = j + 1
    return float((ranks[labels].sum() - pos * (pos + 1) / 2) / (pos * neg))


def pr_auc(labels: np.ndarray, scores: np.ndarray) -> float | None:
    """Average precision (area under the precision-recall curve, step interpolation)."""
    labels = np.asarray(labels, dtype=bool)
    if labels.sum() == 0:
        return None
    order = np.argsort(-np.asarray(scores), kind="mergesort")
    hits = labels[order]
    tp = np.cumsum(hits)
    precision = tp / np.arange(1, len(hits) + 1)
    return float((precision * hits).sum() / hits.sum())
