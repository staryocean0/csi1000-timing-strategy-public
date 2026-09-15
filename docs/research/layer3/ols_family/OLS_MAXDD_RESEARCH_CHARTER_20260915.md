# OLS Layer3 — MaxDD-first research charter

Status: **ACTIVE AUTHORITY FOR THE NEXT OLS RESEARCH THREAD**

## 1. Why this thread exists

The prior D0→D1→D2 sequence is closed as follows:

- D0 established that exit persistence materially amplifies drawdown and that large drawdowns often contain substantial fit-quality deterioration.
- D1 established that two consecutive active-authority R² declines are useful as an early-warning diagnostic.
- D2 rejected the specific hard mapping `first two-down warning -> flat from next executable bar -> remain flat until original baseline segment ends` as a general exit-overlay candidate. The authoritative D2 result is `NOT_SUPPORTED_AS_D2_EXIT_OVERLAY_CANDIDATE`; `d2b_authority=false`.

This does **not** erase the diagnostic information found in D1. It means only that the tested action mapping was too coarse and too costly.

## 2. New research objective

The research objective is now elevated from testing a particular R² exit trigger to understanding and controlling the strategy's failure regimes.

**Primary objective: reduce maximum drawdown and tail drawdown.**

**Secondary objective: after risk has been materially reduced, recover as much gross return as possible without re-opening the same failure mechanism.**

The ordering is binding. A candidate with higher return but essentially unchanged MaxDD is not a successful solution to this thread. A candidate with lower return may remain valuable if it materially lowers MaxDD and improves tail stability.

## 3. Research question

> In which causally observable market/model states does the frozen OLS explosive-channel tool produce its largest losses, what mechanisms are common across those states, and what is the lightest intervention that can reduce those losses without unnecessarily discarding profitable trend continuation?

This question is broader than any one proposed trigger. The following are candidate explanatory variables, not presumed answers:

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

No item above is privileged in advance.

## 4. Failure-regime framing

The first job is not to design an exit. It is to identify recurrent failure regimes.

The investigation must distinguish at least these mechanisms when supported by the data:

1. **Acute structural break** — a previously strong local linear fit collapses rapidly.
2. **Chronic weak-fit / slow degradation** — the model remains marginally usable for a long period while equity remains underwater.
3. **Confidence whipsaw / repeated re-fit** — fit quality collapses, recovers, and collapses again, repeatedly restoring apparent confidence in a noisy regime.
4. **Re-entry / churn amplification** — the equity drawdown contains repeated fresh same-tool entries, position flips, or short-lived segments rather than one persistent bad trade.
5. **Exit-persistence amplification** — otherwise similar failure conditions generate materially different losses under different frozen exit families.

These are working archetypes. Phase A must measure them rather than assume them.

## 5. Research hierarchy

### Phase A — failure atlas and mechanism attribution

Build a cross-exit-family episode atlas for all drawdown episodes and a detailed top-tail view. Quantify the observable state path before and during each episode. Contrast the deepest episodes with ordinary drawdowns. No trading rule changes are permitted.

### Phase B — causal early-identification study

Only after Phase A identifies stable common mechanisms may a new preregistration test whether those mechanisms can be recognized before loss expansion. Candidate rules may include persistence, collapse magnitude, confidence-state hysteresis, churn/re-entry state, or combinations. Thresholds must be preregistered or derived from a strictly separated development procedure; no outcome-driven rescue tuning.

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

The exact quantitative gates for an intervention experiment must be frozen before that experiment runs.

Phase A is diagnostic and therefore has no promotion threshold for a trading rule.

## 7. Anti-overfitting and governance boundaries

- 2020–2025 remain consumed research years; no claim of fresh OOS is allowed.
- The frozen OLS entry and five baseline exit families remain unchanged during Phase A.
- Phase A must not search exit thresholds, R² thresholds, PE thresholds, cooldown lengths, sizing, leverage, routing, or production parameters.
- 2024 Q4 may be used as an important case study but may not become the sole design target. Findings must be compared across years and episodes.
- Negative findings and failure regimes must be preserved.
- No D2b authority exists. Any future intervention study requires a new preregistered profile.
- No production/trading authority is granted by this charter.

## 8. Current authority

The next authorized action is **Phase A: OLS MaxDD Failure Atlas v1**.

Its task is to produce a verified descriptive mechanism atlas, not a new trading rule.
