# Two-Wave v0.8.0 — Preflight Amendment A

Status: frozen before the first real V0800-B execution. This is a clarification/control amendment, not a result-driven scientific rescue and not a replacement of the parent v0.8.0 protocol.

## Why this amendment exists

Two pre-run ambiguities were found during the merged-runner audit and are resolved before any real market-data result is observed.

First, the parent protocol writes `d(W)=t1-t0` and informally calls the value a number of bars. Mathematically, with pivot bars indexed by integers, `t1-t0` is the number of **bar intervals** between the two low-pivot occurrence bars. If someone instead counts the inclusive K-line observations from the first pivot bar through the last pivot bar, that count is `d+1`. The primary matching variable remains `d=t1-t0`; no formula or candidate boundary is changed. V0800-B must additionally report the derived inclusive span-row histogram so the terminology cannot be confused later.

Second, the parent protocol explicitly retains historical `rho=2.0` as a legacy control, while the initial V0800-B runner only emitted the four new candidate rhos. The first real V0800-B run must therefore report `rho=2.0` alongside the four candidates as a **historical-width reference only**. It is not a v0.8 candidate, cannot win, cannot alter the candidate family, and cannot authorize morphology acceptance.

## Frozen interpretation

For an A-wave `L0 -> H0 -> L1` with occurrence-bar indices `t0 < tH < t1`:

`d = (tH-t0) + (t1-tH) = t1-t0` bar intervals.

The inclusive number of observed bar rows from `L0` through `L1` is:

`span_rows = d + 1`.

All same-scale comparisons continue to use `d`, not `span_rows`:

`max(d_prev,d_cur)/min(d_prev,d_cur) <= rho`.

Candidate rhos remain exactly `1.25`, `4/3`, `sqrt(2)`, and `1.50`. Historical `2.00` is emitted only as `legacy_control_rho`.

## Authority boundary

This amendment does not open 2026, does not use future outcomes, returns, PnL, positions, costs, execution labels, or trading authority. V0800-B still cannot select a rho winner. `morphology_acceptance` remains false and all historical Two-Wave failures remain unchanged.
