# Risk Tool 2.0 Temporal Stability Acceptance Charter v1

## 1. Purpose

This acceptance mechanism is part of the Risk Tool itself. It defines what the project means by “the tool is ready enough to be trusted as a stable research component.” It is not a PnL backtest, not a strategy optimizer, and not a replacement for fresh OOS.

The mechanism tests whether a frozen tool keeps the same useful relationship through time rather than obtaining a good pooled result from a small number of favorable periods.

For Risk Tool 2.0 the primary comparison is frozen Severity model C versus frozen State+Age baseline B at the already-frozen horizons. The first active scope is 15m and 30m.

## 2. Separation of concerns

Acceptance has four independent questions:

1. **Support** — is there enough data in a calendar bucket to judge it?
2. **Ordering stability** — does C keep improving ranking over B through time?
3. **Calibration stability** — does the frozen probability mapping keep improving Brier and LogLoss through time?
4. **Failure clustering** — are negative periods isolated noise, or do they form persistent regimes?

No PnL, strategy threshold, routing rule or production authority is created by this mechanism.

## 3. Time hierarchy

The default hierarchy is:

- **Annual: hard gate.** Detects structural failure across major regimes.
- **Quarterly: hard gate.** Detects medium-duration regime dependence hidden by annual pooling.
- **Monthly: hard gate.** Detects concentration and persistent local failure.
- **Weekly: diagnostic by default.** Useful for locating failure clusters, but too sample-sensitive to be a default veto. A future profile may make weekly gating active only before seeing that profile’s evaluation results.

A bucket with inadequate support is `UNEVALUABLE`, not a success and not a failure. Coverage itself is separately gated so unsupported periods cannot be silently omitted.

## 4. Default v1 acceptance thresholds

The values below are the active **balanced-v1 proposal**. They are intentionally configurable, but only through a versioned profile change before a new evaluation run.

### 4.1 Annual ordering

- evaluable calendar coverage >= 90%
- positive AUROC-gain fraction >= 80%
- median AUROC gain > 0
- row-weighted mean AUROC gain > 0
- maximum consecutive negative annual buckets <= 1

### 4.2 Quarterly ordering

- evaluable calendar coverage >= 85%
- positive AUROC-gain fraction >= 70%
- median AUROC gain > 0
- row-weighted mean AUROC gain > 0
- maximum consecutive negative quarters <= 2

### 4.3 Monthly ordering

- evaluable calendar coverage >= 75%
- positive AUROC-gain fraction >= 60%
- median AUROC gain > 0
- row-weighted mean AUROC gain > 0
- maximum consecutive negative months <= 3

### 4.4 Weekly ordering diagnostic

- evaluable calendar coverage target >= 60%
- positive AUROC-gain fraction target >= 55%
- median AUROC gain target > 0
- maximum consecutive negative weeks target <= 6

Weekly misses are reported but do not veto v1 acceptance.

## 5. Calibration thresholds

A calendar bucket is calibration-positive only when **both** frozen-calibrated Brier gain and frozen-calibrated LogLoss gain are > 0.

Default hard-gate thresholds:

- annual joint-positive fraction >= 70%, max consecutive calibration-negative years <= 1
- quarterly joint-positive fraction >= 60%, max consecutive calibration-negative quarters <= 2
- monthly joint-positive fraction >= 55%, max consecutive calibration-negative months <= 4
- median Brier gain > 0 and median LogLoss gain > 0 at every hard-gated level

Weekly calibration is diagnostic by default.

## 6. Global gates

Temporal consistency cannot rescue a globally useless signal. Before assigning a stable grade, each horizon must also satisfy the active profile’s pooled gates:

- global support minimums
- pooled raw-score `AUROC(C)-AUROC(B) > 0`
- trading-day cluster bootstrap lower bound > 0

For the strongest probability-component grade, pooled frozen-calibrated Brier gain and LogLoss gain must both be > 0.

## 7. Default bucket support

The balanced-v1 support defaults are:

| Level | rows | positives | negatives |
| --- | ---: | ---: | ---: |
| Annual | 500 | 50 | 50 |
| Quarterly | 150 | 20 | 20 |
| Monthly | 50 | 8 | 8 |
| Weekly | 20 | 4 | 4 |

These values define whether a bucket is evaluable; they do not define whether it passes scientifically.

## 8. Acceptance grades

The evaluator returns one of the following per horizon:

### `TS-A_STABLE_PROBABILITY_COMPONENT`

Global ordering passes, annual/quarterly/monthly ordering stability passes, and all hard-gated calibration stability requirements pass. The tool is accepted as a temporally stable research probability component, still without production authority.

### `TS-B_STABLE_RANKING_CALIBRATION_GUARDED`

Global ordering and all hard-gated ordering stability pass, but one or more calibration stability gates fail. The tool may be treated as a stable ranking/diagnostic component; absolute probability use remains calibration-guarded.

### `TS-C_EPISODIC`

The pooled relationship may be positive, but annual, quarterly or monthly ordering stability fails. The tool is not accepted as structurally stable.

### `TS-D_UNSTABLE`

The global ordering relationship fails or the annual core relationship is non-positive. The tool is rejected as a stable component under this profile.

### `TS-I_INSUFFICIENT_SUPPORT`

Required calendar coverage or global support is inadequate. This is not a scientific pass or fail.

## 9. Threshold adjustability and anti-retuning rule

Thresholds are governance parameters, not model parameters. They may be changed because the project’s required reliability changes, but:

- exactly one acceptance profile is active for a run;
- every threshold change creates a new profile/version;
- the new profile must be frozen before reading that run’s new year/quarter/month/week breakdown;
- a failed run cannot be rescued by selecting another profile after inspection;
- historical results remain attached to the profile under which they were evaluated;
- changing acceptance thresholds never changes the frozen Risk Tool model, state boundary or calibration parameters.

This lets the acceptance mechanism represent project requirements without becoming another optimizer.

## 10. Data-role honesty

2015–2025 are already consumed to different degrees by prior research. A temporal-stability run over those years is therefore a **proxy qualification audit**, not fresh OOS. It may tell us whether the tool’s behavior is broad and persistent, but it cannot manufacture fresh evidence.

The evaluator must preserve data-role labels where available (`historical_transport`, `warmup`, `development`, `audit`, `fresh_oos`). Warmup buckets are excluded from hard scientific acceptance by default. Development buckets may be reported separately from historical/audit buckets.

## 11. Failure-cluster reporting

Every run must report, for each horizon and time level:

- evaluable bucket count and coverage
- positive/negative/unevaluable counts
- positive fraction
- median and row-weighted mean ordering gain
- worst ordering bucket
- longest consecutive ordering-negative run
- joint calibration-positive fraction
- median calibrated Brier and LogLoss gain
- longest consecutive calibration-negative run
- exact start/end labels of the longest failure run

This is required even when the final grade passes.

## 12. Concentration and drift diagnostics

The v1 report should also calculate but not hard-gate:

- top-decile positive-contribution concentration
- first-half versus second-half median gain
- latest 12-month versus long-run median gain
- latest 4-quarter versus long-run median gain
- linear/Theil-Sen time slope of ordering gain where support permits

These diagnostics are candidates for future hard gates only through a pre-result profile revision.

## 13. Relationship to fresh OOS

A strong temporal-stability grade substantially raises confidence that the tool captures persistent structure. It does not replace the separately preregistered 2026 fresh-OOS test.

The intended evidence ladder is:

`pooled signal -> year stability -> quarter stability -> month stability -> weekly diagnostics -> fresh OOS`

The acceptance mechanism exists so future development has an explicit finish line rather than an open-ended sequence of verbally chosen next steps.

## 14. Current authority boundary

This charter is a public, reviewable acceptance contract. It creates no private research result by itself. Any real-data execution must use the project’s approved bounded workflow/broker route. `production_authority=false`.