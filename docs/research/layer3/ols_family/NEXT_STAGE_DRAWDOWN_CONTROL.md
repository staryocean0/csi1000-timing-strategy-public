# OLS Layer3 next-stage research charter: drawdown control

Status: authoritative cloud-research narrative for the next OLS research stage; research authority only, not production authority.

## 1. Objective

The next stage is **not** primarily a return-maximization exercise. The primary objective is to explain and reduce the maximum drawdown of the OLS trend family so that later leverage and routing do not simply amplify avoidable trend-identification errors.

The research order is therefore:

1. diagnose where drawdowns are created;
2. test whether OLS fit deterioration can veto or terminate weak trend exposure;
3. test a two-level OLS router in which a slower/larger-scale OLS state controls eligibility/profile choice for a faster trading OLS;
4. test the joint mechanism only after the two mechanisms are understood separately.

Return, Sharpe and turnover remain important, but they are secondary to drawdown depth, drawdown duration and tail-loss concentration during this stage.

## 2. Frozen starting facts

### 2.1 The migrated 20-bar OLS already exposes R-squared

The migrated M2 baseline uses 20 completed bars of `log(close)` and returns:

- `slope_per_bar`;
- signed `slope_t`;
- `r_squared`;
- the three-bucket `DOWN / SIDEWAYS / UP` state.

The current M6 continuous strength is `abs(slope_t)`.

For a fixed window length `n`, the current implementation uses the correlation identity

`|t| = sqrt((n - 2) * R^2 / (1 - R^2))`.

Therefore, for the frozen 20-bar baseline, `|t| > 2` is mathematically equivalent to approximately `R^2 > 4 / 22 = 0.1818` with direction supplied by the sign of the correlation.

**Consequence:** a simple contemporaneous R-squared floor on the same 20 bars is mostly a re-expression of the existing `slope_t` threshold, not an independent new risk control. The next stage must focus on information that is not redundant with the frozen state score: fit deterioration through time, fit stability, structural break, path geometry, and cross-scale disagreement.

### 2.2 A separate private OLS trading lifecycle already exists

The private runtime currently contains `ols_explosive_channel_v1.py`, which uses W12/W24 OLS-family windows, consumes regression `fit_r2` and `path_efficiency`, selects fresh entry candidates with a score proportional to slope magnitude × window span × path efficiency × fit R-squared, and supports OLS-native exit semantics.

That implementation is a useful comparison baseline for this stage. It does **not** automatically become the canonical implementation of the migrated 20-bar family. The two lineages must be compared explicitly rather than silently merged.

### 2.3 Layer3 already provides orchestration semantics

The current private Layer3 architecture separates state adapters, owner profiles, priority/routing orchestration and concrete strategy plugins. The next OLS router should reuse that separation: the large-scale OLS produces state/eligibility; it does not directly emit a position.

## 3. Primary research question

**Can maximum drawdown be reduced by detecting that an apparent OLS trend is losing structural support before the existing price/lifecycle exit realizes the full loss?**

The main candidate explanations for large drawdowns are intentionally broader than R-squared alone:

1. **false trend at entry** — an apparent directional fit is weak or geometrically noisy when the trade begins;
2. **trend-decay drawdown** — the fit was initially valid but R-squared / path efficiency / slope quality deteriorates while the position remains active;
3. **cross-scale conflict** — a fast OLS trades against a slower OLS regime or trades while the slow regime is structurally unstable;
4. **window/profile mismatch** — the active OLS horizon is too fast or too slow for the prevailing market scale;
5. **late exit** — the trend has already broken but the current lifecycle exit reacts too slowly;
6. **whipsaw / direction-flip cluster** — repeated short-lived OLS states concentrate losses;
7. **execution or gap loss** — a material part of drawdown is caused by next-bar execution, gaps or transaction costs rather than signal quality;
8. **leverage amplification** — an otherwise tolerable unlevered loss sequence becomes unacceptable after leverage.

The stage must attribute drawdown episodes across these mechanisms before changing the strategy.

## 4. Stage D0 — drawdown episode atlas

No signal rule is changed in D0.

### 4.1 Freeze the comparison baseline

Freeze, at minimum:

- exact OLS formula/version;
- bar frequency and completed-bar semantics;
- lookback/profile;
- execution convention (`decision_t -> execution_t+1` where applicable);
- transaction-cost convention;
- exit rule;
- leverage assumption.

Diagnosis should be performed first on unlevered or unit-exposure returns so that signal failure is not confused with leverage scaling. Leverage stress tests come after the failure mechanism is identified.

### 4.2 Identify drawdown episodes

For every material drawdown episode, record:

- peak timestamp;
- drawdown start;
- trough timestamp;
- recovery timestamp;
- depth;
- duration / time under water;
- active direction;
- entry timestamp and holding age;
- active OLS window/profile;
- trade-level MAE/MFE where available.

The largest episodes must be inspected individually in addition to aggregate statistics.

### 4.3 Align signal diagnostics around each episode

At entry and through the pre-trough path, align:

- `R^2_t` / `fit_r2_t`;
- `ΔR^2` over short causal lags;
- ratio of current R-squared to entry R-squared;
- consecutive R-squared deterioration count;
- signed and absolute `slope_t`;
- `slope_per_bar` / slope magnitude;
- path efficiency;
- qualification state;
- selected/authority window;
- window switching;
- up/down conflict flags;
- distance to the active OLS midline/exit boundary;
- slower-scale OLS direction and fit state when available.

The key diagnostic is **lead/lag**: does fit deterioration occur *before* the damaging return sequence, or only after price has already moved against the position?

### 4.4 D0 output

D0 must produce a drawdown atlas and a mechanism-attribution summary before any R-squared veto or router is promoted for testing.

## 5. Stage D1 — dynamic OLS fit-quality veto

### 5.1 Hypothesis

A large share of avoidable drawdown is caused not by low static R-squared at entry, but by **rapid or persistent deterioration in fit quality after entry**.

### 5.2 Candidate causal features

Keep the feature family deliberately small:

- current R-squared;
- one/few-bar change in R-squared;
- short causal slope of R-squared;
- current / entry R-squared ratio;
- consecutive deterioration count;
- joint deterioration of R-squared and path efficiency;
- joint deterioration of R-squared and signed OLS strength.

Thresholds must be calibrated only on the development period. No threshold may be selected by looking at the future maximum drawdown of the same observation.

### 5.3 Action ladder

Test in increasing order of intervention:

1. **entry veto only** — do not open a new trend trade when fit is already unstable;
2. **re-entry cooldown** — after a fit-break exit, require causal recovery before re-entry;
3. **hold veto / early exit** — close an active position when fit deterioration is sufficiently persistent;
4. **exposure reduction** — only after binary veto/exit behavior is understood; do not start with a continuous sizing optimizer.

### 5.4 Required comparison

A static R-squared floor must be included as a diagnostic control, but it is not the main candidate because of the fixed-window `slope_t`/R-squared equivalence described above.

## 6. Stage D2 — two-level OLS router

### 6.1 Architecture

Use the **same OLS family at two time scales with different responsibilities**:

- **large/slow OLS:** regime and routing authority only;
- **small/fast OLS:** entry/exit trading authority inside the route allowed by the slow state.

The slow OLS must not directly create a trade. It emits a causal state such as:

- supportive uptrend;
- supportive downtrend;
- neutral/sideways;
- trend present but fit deteriorating;
- unavailable.

The fast OLS then receives one of three actions:

- eligible in the slow-direction route;
- blocked / neutral;
- assigned to an alternate pre-frozen fast profile/window.

### 6.2 First low-freedom profile pairs

Prefer existing admitted OLS profiles rather than inventing a new estimator. Natural first tests are adjacent scale pairs such as:

- 60m OLS router -> 15m OLS trader;
- 15m OLS router -> 5m OLS trader;
- 5m OLS router -> 1m OLS trader.

If the evaluated trading implementation is the W12/W24 15m OLS lifecycle, the first router experiment should use a slower OLS state above that 15m trading carrier rather than modifying W12/W24 internally.

The experiment must keep the estimator formula fixed and vary only the routing relationship.

### 6.3 Routing hypotheses

Test separately:

- direction agreement vs disagreement;
- slow-sideways veto;
- slow-fit-deterioration veto;
- slow trend-strength buckets;
- route choice between pre-frozen fast profiles/windows.

Do not begin with a large combinatorial router. Each routing rule must have an interpretable causal reason.

## 7. Stage D3 — joint drawdown-control candidate

Only after D1 and D2 have stand-alone evidence may the best low-freedom mechanisms be combined.

The joint candidate should answer:

- Does dynamic fit deterioration mainly improve exits?
- Does slow OLS routing mainly improve entries / regime selection?
- Are their drawdown reductions additive, overlapping, or contradictory?
- Which drawdown episodes remain unexplained after both controls?

Unexplained episodes become the next failure-analysis queue; they must not be hidden by average performance.

## 8. Evaluation hierarchy

### Primary risk metrics

- maximum drawdown;
- top-N drawdown depths;
- drawdown duration / time under water;
- loss concentration in the worst episodes;
- trade-level MAE tail;
- drawdown-at-risk under later leverage stress.

### Secondary performance metrics

- CAGR / total return;
- Calmar ratio;
- Sharpe-like risk-adjusted metrics;
- turnover and transaction-cost burden;
- participation rate / time in market;
- win/loss asymmetry.

A candidate is not accepted because it raises return while leaving the same failure episodes intact. For this stage, preference is given to **stable drawdown reduction with understandable mechanism**, even if raw return is modestly lower.

## 9. Anti-overfitting and authority rules

1. Preserve point-in-time completed-bar semantics.
2. Never use future drawdown labels or registered future events as runtime inputs.
3. Freeze the baseline before selecting veto/router thresholds.
4. Keep the candidate family small and interpretable.
5. Separate development, repeat-audit and fresh/OOS evaluation.
6. Do not optimize leverage until the unlevered drawdown mechanism is understood.
7. Do not mutate the OLS estimator formula while simultaneously evaluating routing/veto logic.
8. Keep the migrated 20-bar OLS lineage and the existing W12/W24 explosive OLS lifecycle distinct until a deliberate comparison/merge decision is made.

## 10. Promotion sequence

The next stage is authorized in this order only:

- **D0:** drawdown atlas and mechanism attribution;
- **D1:** dynamic R-squared / fit-quality veto experiments;
- **D2:** slow-OLS -> fast-OLS hierarchical routing experiments;
- **D3:** joint low-freedom drawdown-control candidate;
- **D4:** leverage stress and portfolio-level consequences only after D3 survives repeat audit.

No later stage should be used to retroactively justify an earlier rule.

## 11. Immediate next action

The immediate research task is **D0 only**: locate the existing OLS strategy's largest drawdown episodes and build the causal diagnostic panel around them. Do not change entry, exit, routing or leverage during D0.
