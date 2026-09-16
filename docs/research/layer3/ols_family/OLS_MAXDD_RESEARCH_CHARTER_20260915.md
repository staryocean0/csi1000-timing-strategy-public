# OLS Layer3 — MaxDD-first research charter

Status: **ACTIVE AUTHORITY FOR THE OLS MAXDD-FIRST RESEARCH THREAD**

## 1. Why this thread exists

The prior D0→D1→D2 sequence is closed as follows:

- D0 established that exit persistence materially amplifies drawdown and that large drawdowns often contain substantial fit-quality deterioration.
- D1 established that two consecutive active-authority R² declines are useful as an early-warning diagnostic.
- D2 rejected the specific hard mapping `first two-down warning -> flat from next executable bar -> remain flat until original baseline segment ends` as a general exit-overlay candidate. The authoritative D2 result is `NOT_SUPPORTED_AS_D2_EXIT_OVERLAY_CANDIDATE`; `d2b_authority=false`.

This does **not** erase the diagnostic information found in D1. It means only that the tested action mapping was too coarse and too costly.

## 2. Research objective

The research objective is elevated from testing a particular R² exit trigger to understanding and controlling the strategy's failure regimes.

**Primary objective: reduce maximum drawdown and tail drawdown.**

**Secondary objective: after risk has been materially reduced, recover as much gross return as possible without re-opening the same failure mechanism.**

The ordering is binding. A candidate with higher return but essentially unchanged MaxDD is not a successful solution to this thread. A candidate with lower return may remain valuable if it materially lowers MaxDD and improves tail stability.

## 3. Research question

> In which causally observable market/model states does the frozen OLS explosive-channel tool produce its largest losses, what mechanisms are common across those states, and what is the lightest intervention that can reduce those losses without unnecessarily discarding profitable trend continuation?

The following are candidate explanatory variables, not presumed answers:

- fit R² level;
- R² persistence / consecutive declines;
- 3/4/5-bar cumulative R² deterioration;
- recent peak-to-current R² collapse;
- R² instability / collapse-and-recovery behavior;
- path-efficiency level and deterioration;
- slope / trend strength;
- W12/W24 authority and authority-window switching;
- direction conflict;
- exit-trigger density;
- position flips, fresh entries and re-entry/churn density;
- time since a recent model-quality collapse;
- speed and stability of model-confidence recovery.

## 4. Failure-regime framing

The program distinguishes at least these mechanisms when supported by the data:

1. **Acute structural break** — a previously strong local linear fit collapses rapidly.
2. **Chronic weak-fit / slow degradation** — the model remains marginally usable for a long period while equity remains underwater.
3. **Confidence whipsaw / repeated re-fit** — fit quality collapses, recovers, and collapses again, repeatedly restoring apparent confidence in a noisy regime.
4. **Re-entry / churn amplification** — the equity drawdown contains repeated fresh same-tool entries, position flips, or short-lived segments rather than one persistent bad trade.
5. **Exit-persistence amplification** — otherwise similar failure conditions generate materially different losses under different frozen exit families.

Verified Phase A established that tail risk is concentrated in a small number of episodes, repeated participation is a cross-family mechanism, and R²/PE collapse are material severity markers. Authority-window switching did not emerge as a general top-tail driver. These findings motivate Phase B but do not themselves define a trading rule.

## 5. Research hierarchy

### Phase A — failure atlas and mechanism attribution

Completed by verified run `34978764073-1`, authoritative status `MECHANISM_ATLAS_COMPLETED`. Phase A was descriptive/mechanistic and changed no trading rule.

### Phase B — causal early-identification study

After Phase A identified stable common mechanisms, Phase B may test whether those mechanisms can be recognized before the next baseline segment expands loss. Candidate state features may include churn/re-entry state, prior confidence damage, apparent confidence recovery and existing underwater state. Thresholds for trading actions are not selected in Phase B.

### Phase C — intervention ladder

Only after Phase B establishes usable early identification may actions be compared. The action set should be ordered from least to most destructive:

`continue -> block new entry/addition -> reduce risk -> re-entry cooldown/hysteresis -> faster exit -> full risk-off`.

The purpose is to locate the lightest intervention that materially reduces MaxDD.

### Phase D — return recovery under a risk floor

Only after a materially safer configuration exists may return recovery be optimized. MaxDD/tail improvements become constraints, not optional metrics.

## 6. Evaluation priority

For later intervention phases, decision priority is:

1. maximum drawdown;
2. tail-drawdown severity and concentration;
3. cross-year / cross-regime stability;
4. gross-return retention and opportunity cost;
5. total gross return.

Exact quantitative gates must be frozen before each experiment runs. Phase B uses its own preregistered mechanism-promotion gate and does not alter trading.

## 7. Anti-overfitting and governance boundaries

- 2020–2025 remain consumed research years; no claim of fresh OOS is allowed.
- The frozen OLS entry and five baseline exit families remain unchanged during Phases A and B.
- Phase B must not search trading thresholds, cooldown lengths, sizing, leverage, routing, or production parameters.
- 2024 Q4 may be used as an important case study but may not become the sole design target. Findings must be compared across years and episodes.
- Negative findings and failure regimes must be preserved.
- No D2b authority exists.
- Any future Phase C intervention requires a new preregistered profile and frozen risk-first gates.
- No production/trading authority is granted by this charter.

## 8. Current authority

The next authorized action is **Phase B: `ols-maxdd-reentry-identification-v1`** under `OLS_MAXDD_PHASE_B_REENTRY_IDENTIFICATION_PROTOCOL_20260915.md`.

Its task is to establish or reject causally observable pre-segment failure-state mechanisms. It does not suppress trades or modify the strategy.