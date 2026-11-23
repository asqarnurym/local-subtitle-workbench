# Formulas for the DG 2027 paper

Written 21.11.2026 from the implementation (sources named per formula). LaTeX is ready to paste; the same equations are in `equations.tex`. **Required** = the paper is not reproducible or its numbers cannot be read without it. **Desirable** = include if space allows.

## Evaluation (required)

**Eq. 1. Boundary error.** For every reference word matched to a predicted word, both its start and its end give one boundary error (ms). Source: `metrics.py::evaluate_alignment_boundaries`.

```latex
e_b = 1000\,\lvert \hat{t}_b - t_b \rvert, \qquad b \in \mathcal{B}
```

**Eq. 2. MAE and Acc@20 ms** over the set of boundaries $\mathcal{B}$ of a mode (pooled over all scored clips). Source: same; `BOUNDARY_EPSILON_MS` only guards float rounding.

```latex
\mathrm{MAE} = \frac{1}{\lvert\mathcal{B}\rvert}\sum_{b\in\mathcal{B}} e_b, \qquad
\mathrm{Acc@20} = \frac{100}{\lvert\mathcal{B}\rvert}\sum_{b\in\mathcal{B}} \mathbb{1}\left[e_b \le 20\right]
```

**Eq. 3. Word coverage.** Predicted and reference words are paired by Needleman–Wunsch alignment of normalized words (match +2, mismatch −2, gap −1); only identical words count as matched. Source: `metrics.py::_align_token_sequences`.

```latex
\mathrm{Cov} = \frac{N_{\text{matched}}}{N_{\text{reference}}}
```

**Eq. 3a. Boundary F1 (robustness check, required since CLAIM-114…116).** Every word gives two boundaries. $H_\tau$ = boundaries of matched words with $e_b \le \tau$; $N^{\text{ref}}$, $N^{\text{pred}}$ = all reference and all predicted boundaries, failed clips included (their reference boundaries are misses). Missed words lower recall, inserted words lower precision. Main $\tau = 20$ ms. Source: `scripts/f1_analysis.py`, `docs/F1_PROTOCOL.md`.

```latex
P_\tau = \frac{H_\tau}{N^{\text{pred}}}, \qquad
R_\tau = \frac{H_\tau}{N^{\text{ref}}}, \qquad
F_{1,\tau} = \frac{2P_\tau R_\tau}{P_\tau + R_\tau} = \frac{2H_\tau}{N^{\text{pred}} + N^{\text{ref}}}
```

**Eq. 4. Speaker-level comparison.** Speaker value = pooled MAE of that speaker on clips scored in both modes; paired difference per speaker; exact two-sided Wilcoxon signed-rank test over speakers; Holm correction over the $K$ comparisons of a family. Source: `scripts/analyze_speaker_errors.py` (E1), `exact_signed_rank`, `metrics.py::bonferroni_holm_adjustment`.

```latex
\mathrm{MAE}_s = \frac{\sum_{b\in\mathcal{B}_s} e_b}{\lvert\mathcal{B}_s\rvert}, \qquad
d_s = \mathrm{MAE}_s^{\text{prop}} - \mathrm{MAE}_s^{\text{base}}, \qquad
p^{\text{Holm}}_{(k)} = \max_{j\le k}\,\min\!\bigl(1,\,(K-j+1)\,p_{(j)}\bigr)
```

**Eq. 5. Speaker-cluster bootstrap CI.** Resample the $S$ speakers with replacement ($R=2000$, seed 42), recompute pooled MAE, take the 2.5 and 97.5 percentiles. Source: `metrics.py::clustered_bootstrap_ci` (frozen `ci_unit = speaker`). In words is enough; formula optional.

Note for the text: the frozen tables also contain clip-paired Wilcoxon tests with Holm and Cliff's δ (CLAIM-103 quotes δ). If δ is cited, add its definition (desirable):

```latex
\delta = \frac{\#\{(i,j): x_i > y_j\} - \#\{(i,j): x_i < y_j\}}{n\,m}
```

## Method (required: Eq. 8–10; desirable: Eq. 6–7, 11)

**Eq. 6. Banded anchoring recurrence (scenario A).** $r_i$ reference word, $h_j$ ASR word; σ = +2 for identical normalized words, −1 otherwise; gap $g=-1$; cells only where $\lvert j - i\,m/n\rvert \le w$, $w=\max(50,\ 0.1\max(n,m),\ \lvert n-m\rvert+1)$. Source: `anchoring.py::banded_sequence_alignment`.

```latex
S(i,j) = \max\begin{cases}
S(i-1,j-1) + \sigma(r_i,h_j)\\
S(i-1,j) + g\\
S(i,j-1) + g
\end{cases}, \qquad \lvert j - i\,m/n \rvert \le w
```

**Eq. 7. Interpolation of unanchored words.** A run of unanchored words $k=i..k'$ between anchors gets the interval $[t^{\text{end}}_{a}, t^{\text{start}}_{b}]$ split proportionally to character length $\ell_k$. Source: `anchor_transcript`.

```latex
\tau_k = \bigl(t^{\text{start}}_b - t^{\text{end}}_a\bigr)\,\frac{\ell_k}{\sum_{q} \ell_q}
```

**Eq. 8. BRQE heads.** $X_b$: 64×41 log-mel window (±100 ms, 5 ms hop) at boundary $b$; $z_b$: six scalars (start/end, word/phone, scenario, log duration, sub-frame offset, bias). Three 1-D convolutions, then an MLP (hidden 128, dropout 0.2). $\Delta_{\max} = 0.1$ s. Source: `refiner.py::_build_net`.

```latex
h_b = \mathrm{MLP}\bigl([\,\mathrm{CNN}(X_b);\, z_b\,]\bigr), \qquad
\Delta_b = \Delta_{\max}\tanh\bigl(w_r^{\top}h_b\bigr), \qquad
p_b = \sigma\bigl(w_c^{\top}h_b\bigr), \qquad
t'_b = t_b + \Delta_b
```

**Eq. 9. BRQE training loss.** Target $\epsilon_b = t^{\text{ref}}_b - t_b$ (s). Regression only on boundaries with $\lvert\epsilon_b\rvert \le 0.1$ s ($\mathcal{B}_r$); L1 in ms scaled by 1/20 so both terms are of order one; $\lambda = 0.5$. Source: `BRQERefiner.fit`.

```latex
\mathcal{L} = \frac{1}{20}\cdot\frac{1}{\lvert\mathcal{B}_r\rvert}\sum_{b\in\mathcal{B}_r} 1000\,\lvert \Delta_b - \epsilon_b \rvert
\;+\; \lambda \cdot \mathrm{BCE}\bigl(p_b,\ \mathbb{1}[\lvert\epsilon_b\rvert > 0.02]\bigr)
```

**Eq. 10. Word reliability and its evaluation.** Score per word; evaluation label from the uncorrected MFA word; ROC-AUC, PR-AUC and the rejection curve (MAE of the remaining words after rejecting the fraction $q$ with the lowest $\rho_w$). Source: `refine_prediction`, `speech_benchmark.py::quality_estimation`.

```latex
\rho_w = 1 - \max\bigl(p_{w}^{\text{start}},\, p_{w}^{\text{end}}\bigr), \qquad
y_w = \mathbb{1}\bigl[\max(e_w^{\text{start}}, e_w^{\text{end}}) > 20\ \text{ms}\bigr]
```

**Eq. 11. Constant-offset rival.** Median correction per boundary kind $k$ and scenario $c$ on training boundaries. Source: `ConstantRefiner.fit`.

```latex
\delta_{k,c} = \operatorname*{median}_{\,b \in \mathcal{B}^{\text{train}}_{k,c},\ \lvert\epsilon_b\rvert \le 0.1\,\text{s}} \epsilon_b
```

## Sub-studies (desirable, only if the section is included)

**Eq. 12. Seam cost (S1b, check C).** Words whose reference start lies within 1 s of a seam; pre-registered threshold 10 ms. Source: `scripts/s1b_seam_check.py`.

```latex
\Delta_{\text{seam}} = \mathrm{MAE}^{\text{chunked}}_{\text{near}} - \mathrm{MAE}^{\text{one chunk}}_{\text{near}}, \qquad
\text{near: } \lvert t^{\text{ref}} - t^{\text{seam}} \rvert \le 1\ \text{s}
```

**Eq. 13. Tempo mapping (S2).** Pitch-preserving time-stretch by factor $r$; reference times are mapped the same way; errors are reported on the original scale by multiplying by $r$. Source: `scripts/tempo.py`, `docs/S2_RESULTS.md`.

```latex
t' = t / r, \qquad e^{\text{orig}} = r\, e'
```

Confirmed against `scripts/s2_scaled_detail.py`: playing at rate r divides every interval by r, and the protocol reports the error multiplied by r. The scaled tests were added after the numbers were known (CLAIM-112 keeps that marker).

## Not to include

- Formulas for VAD, Whisper decoding or MFA internals (HMM/GMM, fMLLR): cite the sources instead.
- Any formula of an idea that was not run (`IMPROVEMENT_CANDIDATES.md`, `ROBUSTNESS_AUDIT_PLAN.md`).
