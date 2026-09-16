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

Candidate explanatory variables include fit R², path efficiency, deterioration persistence and magnitude, slope/trend strength, authority state, direction conflict, exit density, fresh entries/re-entry/churn, time since model-quality damage, and confidence recovery. No candidate is privileged in advance.

## 4. Failure-regime framing

The program distinguishes at least these mechanisms when supported by the data:

1. **Acute structural break** — a previously strong local linear fit collapses rapidly.
2. **Chronic weak-fit / slow degradation** — the model remains marginally usable for a long period while equity remains underwater.
3. **Confidence whipsaw / repeated re-fit** — fit quality collapses, recovers, and collapses again, repeatedly restoring apparent confidence in a noisy regime.
4. **Re-entry / churn amplification** — the equity drawdown contains repeated fresh same-tool entries, position flips, or short-lived segments rather than one persistent bad trade.
5. **Exit-persistence amplification** — otherwise similar failure conditions generate materially different losses under different frozen exit families.

Verified Phase A established that tail risk is concentrated in a small number of episodes, repeated participation is a cross-family episode-level mechanism, and R²/PE collapse are material severity markers. Authority-window switching did not emerge as a general top-tail driver.

Verified Phase B then tested whether frozen causal snapshots immediately before a new executable segment could identify which underwater re-entry would extend drawdown. None of the eight preregistered candidates passed the promotion gate. This separates an episode-level mechanism from a usable pre-segment causal identifier.

## 5. Research hierarchy

### Phase A — failure atlas and mechanism attribution

Completed by verified run `34978764073-1`, authoritative status `MECHANISM_ATLAS_COMPLETED`. Phase A was descriptive/mechanistic and changed no trading rule.

### Phase B — causal early-identification study

Completed by verified run `35040712447-1`, authoritative status `PHASE_B_IDENTIFICATION_COMPLETED` with `phase_c_authority=false`.

The tested causal unit was the decision close immediately before a new executable baseline segment. The frozen candidates covered re-entry ordinal, lagged drawdown, prior R²/PE collapse, re-entry speed, false-confidence constructions, and a churn-damage interaction. None passed the frozen cross-family promotion gate.

Phase B therefore closes this specific single-entry-snapshot formulation. It may not be rescue-tuned after outcome reveal.

### Phase C — intervention ladder

**Not currently authorized.**

Only after a future preregistered causal-identification study establishes a usable early identifier may actions be compared. The eventual action ladder remains:

`continue -> block new entry/addition -> reduce risk -> re-entry cooldown/hysteresis -> faster exit -> full risk-off`.

### Phase D — return recovery under a risk floor

Only after a materially safer configuration exists may return recovery be optimized. MaxDD/tail improvements become constraints, not optional metrics.

## 6. Evaluation priority

For later intervention phases, decision priority is:

1. maximum drawdown;
2. tail-drawdown severity and concentration;
3. cross-year / cross-regime stability;
4. gross-return retention and opportunity cost;
5. total gross return.

Exact quantitative gates must be frozen before each experiment runs.

## 7. Anti-overfitting and governance boundaries

- 2020–2025 remain consumed research years; no claim of fresh OOS is allowed.
- The frozen OLS entry and five baseline exit families remain unchanged unless a later intervention protocol explicitly authorizes a comparison.
- Negative findings and failure regimes must be preserved.
- D2 may not be rescue-tuned; D2b authority remains false.
- Phase B's failed candidate definitions and promotion gate may not be altered post hoc and rerun as the same experiment.
- 2024 Q4 may be used as a case study but may not become the sole design target.
- Any future Phase C intervention requires a successful separately preregistered causal-identification parent plus a new intervention profile with frozen risk-first gates.
- No production/trading authority is granted by this charter.

## 8. Current authority

Phase A and Phase B are complete. **No Phase C intervention authority exists.**

A continuation of the MaxDD-first thread must begin with a new preregistered causal-identification question rather than an intervention. The next valid scientific direction may change the causal unit from a single pre-segment snapshot to a state-path / sequence-hazard formulation if that formulation, features, outcomes, sufficiency rules, and promotion gates are frozen before outcome reveal.

No current authority exists to suppress trades, impose cooldowns, resize positions, accelerate exits, or change production behavior.