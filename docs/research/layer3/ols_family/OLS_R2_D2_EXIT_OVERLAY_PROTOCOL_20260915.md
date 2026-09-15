# OLS Layer3 D2 — First Same-Window R²-Deterioration Exit Overlay A/B Protocol

## Question

Does the D1-supported warning — two consecutive decreases in active-authority OLS fit R² while the authority window remains unchanged — improve tail risk when used as one causal early-exit overlay, without an unacceptable gross-return sacrifice?

This is a frozen Layer3 research A/B. It is not a new entry model, router, sizing rule, leverage rule, or production permission.

## Frozen authority and baseline

- Symbol: `000852.SH`.
- Years: 2020–2025 only.
- Canonical 5m data identity remains the D0/D1 pinned six yearly shards at public data ref `1d760ea9525eb3688b70a4aa0f2b5b207af16a17`.
- Private OLS source identity remains ref `67effb80f51228f6129dca5c4f7971a0bb6c7f15`.
- Baseline engine identity is the unchanged D0 public engine (`ols_drawdown_d0.py` blob `b50cd14dccbd895082a1ff8915a70edf8645d828`) plus session adapter blob `2af497297e47628a1efec7bea6117767a766b530`.
- D1 public event implementation is `ols_r2_d1.py` blob `a0c26ec302ea6561d9a2b88a075d5fccb1f2bfc6`.
- D1 empirical authority is fixed to run `34964393250`, private branch `runs/public-research/34964393250-1`, result path `research/public-runs/34964393250-1/ols-d1/study/RESULTS.json`, blob `f35ae2ff402c90b54d318b49bd678c5398a60493`.
- That D1 record grants D2 authority, passes coverage / exit-lead / same-window guards in 5/5 exit families, and freezes `authority_window_equal_across_event_three_bars` as the same-window sensitivity.
- Five baseline exit families are replayed unchanged: `qualification_reset`, `first_opposite_close`, `two_opposite_closes`, `prior_extreme_break`, `frozen_midline_break`.

No baseline exit family is selected as a winner before this run.

## Overlay treatment

For each baseline executable non-flat same-direction segment:

1. detect the first bar `t` satisfying `R²_t < R²_{t-1} < R²_{t-2}` **and** `authority_window_t = authority_window_{t-1} = authority_window_{t-2}` within that same baseline segment;
2. keep the baseline position for the return already owned on bar `t`;
3. become flat from the next executable bar `t+1`;
4. remain flat until that original baseline segment naturally ends;
5. allow re-entry only when the frozen baseline starts a new non-flat segment.

The same-window requirement is not a post-result parameter choice. It is a pre-outcome semantic guard inherited from D1 so that W12 and W24 R² levels are never treated as a continuous deterioration sequence across a window switch.

Only the first eligible warning in a baseline segment can act. There is no PE threshold, no R² magnitude threshold, no parameter search, no same-run retuning, and no immediate re-entry rescue. Path efficiency is descriptive only.

## Timing semantics

The OLS features at close `t` are causal and prior-only. Baseline return ownership remains `open_t -> open_{t+1}`. Therefore a close-`t` warning may only alter executable position starting on the next bar. The warning bar itself must remain identical to baseline.

## Side-specific exit audit

D1's earlier `exit_trigger` field was an OR across up/down lifecycle exits. D2 therefore separately records the current held side's own lifecycle exit trigger. This audit is descriptive and does not alter treatment.

## Outputs

For every exit family report baseline vs overlay gross total return, MaxDD, worst-20 mean drawdown depth, gross-return retention, exposure, trade count, warned segments, effective early exits, positive-remainder forgone fraction, median removed baseline remainder return, and side-specific exit lead statistics. Per-warned-segment evidence is retained privately.

Zero transaction costs remain a diagnostic assumption only.

## Preregistered adjudication

The decision gates are unchanged from the first D2 preregistration and were fixed before any D2 outcome was opened. D2 is `SUPPORTED_AS_D2_EXIT_OVERLAY_CANDIDATE` only if all five conditions hold:

1. MaxDD relative depth improves by at least 20% in at least 3/5 exit families.
2. Mean worst-20 drawdown depth improves by at least 10% in at least 3/5 exit families.
3. Gross total return retention is at least 75% in at least 4/5 exit families.
4. `frozen_midline_break` specifically has MaxDD improvement at least 25% and gross-return retention at least 70%.
5. No exit family has MaxDD relative depth worsening worse than 5%.

Passing grants only permission for a separately preregistered D2b transaction-cost / robustness validation. It grants no production authority and no right to change entry, routing, sizing, leverage, or the baseline exit families.

Failing is a valid scientific result and must not be rescued by post-hoc thresholds.
