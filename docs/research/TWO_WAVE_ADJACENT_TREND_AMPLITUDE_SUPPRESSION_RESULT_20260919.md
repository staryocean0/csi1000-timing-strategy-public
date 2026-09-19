# Adjacent-scale trend suppression audit — result

Issue #473. Parent #450.

## Verdict

`RELATIVE_DOMINANCE_ONLY__ABSOLUTE_SUPPRESSION_NOT_ESTABLISHED`

The user's structural hypothesis splits into two distinct claims:

1. **absolute suppression** — strong C2/C3 trend should make the child C1/C2 intrinsic amplitude itself smaller;
2. **relative dominance** — strong C2/C3 unit-time trend advance should exceed the child band's own intrinsic amplitude pace, making the child less important to directional control even if its absolute oscillation remains nontrivial.

The first claim is not supported.

The second claim is strongly supported at both adjacent-level pairs.

No T0/C1 outcome, PnL, routing label or future-return target was used.

## Frozen geometry

Parent leg strength:

- UP leg pace = parent `height_log / (high-start)`
- DOWN leg pace = parent `height_log / (end-high)`

Child intrinsic amplitude:

`A_child = child.height_log`

where `height_log` is measured relative to the child's own low-to-low baseline.

Child amplitude pace:

`P_child = A_child / child.duration`

Parent-vs-child dominance ratio:

`D = parent_leg_pace / median(P_child)`

Strong parent legs are the top 25% of pace within parent level and leg direction.

Weak legs are the bottom 25%.

Inference uses parent-complete-wave cluster bootstrap, 5,000 repetitions.

## Support

### C2 -> C1

- C2 complete parent waves: 170
- C1 complete child waves: 672
- eligible contained child-wave associations: 667
- eligible parent legs: 340
- strong legs: 86
- weak legs: 84
- median eligible children per parent leg: 2

### C3 -> C2

- C3 complete parent waves: 39
- C2 complete child waves: 170
- eligible contained child-wave associations: 167
- eligible parent legs: 78
- strong legs: 20
- weak legs: 18
- median eligible children per parent leg: 2

## Claim A — absolute child-amplitude suppression

### C2 strong leg -> C1 amplitude

Spearman relationship:

`rho = +0.1306`

95% parent-wave bootstrap interval:

`[+0.0184, +0.2368]`

This is significantly **positive**, not negative.

Strong-minus-weak median log amplitude:

`+0.3144`

95% interval:

`[+0.0294, +0.5460]`

Thus strong C2 legs tend to coexist with **larger**, not smaller, detrended C1 amplitude.

### C3 strong leg -> C2 amplitude

Spearman:

`rho = +0.2945`

95% interval:

`[+0.0106, +0.5248]`

Strong-minus-weak median log amplitude:

`+0.5033`

95% interval:

`[-0.0848, +1.3784]`

Again there is no evidence of absolute amplitude suppression.

### Direction robustness

The positive/raw-amplitude pattern is present in both UP and DOWN legs.

Examples:

C2 -> C1:
- UP rho +0.0446
- DOWN rho +0.2199

C3 -> C2:
- UP rho +0.1804
- DOWN rho +0.4482

Therefore the hypothesis:

> "strong slower-band trend makes the child band's absolute detrended amplitude nearly disappear"

is rejected for this representation and sample.

## Orthogonal-distance robustness

A fixed dimensionless orthogonal-distance version was also measured.

Its point estimates move in the user's expected direction:

C2 -> C1:
- rho -0.0729
- strong-minus-weak log orthogonal amplitude -0.1593

C3 -> C2:
- rho -0.0533
- strong-minus-weak log orthogonal amplitude -0.2092

But bootstrap intervals include zero in both pairs.

Therefore the literal coordinate-rotation intuition is **directionally suggestive but not established**.

The primary conclusion remains based on the baseline-detrended residual amplitude.

## Claim B — relative parent-trend dominance

This claim is strongly supported.

### Strong C2 leg relative to C1

Strong-leg median:

`D = parent C2 leg pace / child C1 amplitude pace = 2.209`

95% bootstrap interval:

`[1.709, 2.488]`

Fraction of strong C2 legs with `D>1`:

**91.86%**

95% interval:

**[86.21%, 97.02%]**

Direction-specific point estimates:

- UP: median D 2.395; D>1 in 93.02%
- DOWN: median D 1.689; D>1 in 90.70%

### Strong C3 leg relative to C2

Strong-leg median:

`D = 2.027`

95% interval:

`[1.569, 3.304]`

Fraction with `D>1`:

**95.00%**

95% interval:

**[84.62%, 100%]**

Direction-specific point estimates:

- UP: median D 3.074; D>1 in 100%
- DOWN: median D 1.563; D>1 in 90%

Both adjacent pairs pass every preregistered relative-dominance gate.

## Scientific interpretation

The data does **not** say that the child oscillation disappears in a strong parent trend.

Instead it says something more useful for the state-machine problem:

> **In a strong parent bandpass leg, the slower parent's unit-time trend advance usually exceeds the faster child's intrinsic oscillation pace by about twofold.**

So the child can remain visibly volatile while becoming **secondary in directional control**.

This is consistent with volatility clustering:

- strong trend environments can still contain large child oscillations;
- but the parent trend advances faster than those oscillations can move the market transversely.

## State-machine implication

The following simplified structural hypothesis is now justified for a separate test:

1. If C2 is in a **strong directional leg** and its pace materially dominates C1 intrinsic pace, C1 may not need to veto the T0 branch.
2. If C2 is weak/flat, inspect C3.
3. If C3 is in a strong directional leg and materially dominates C2 intrinsic pace, C2 may not need to veto the C1 branch.
4. If neither adjacent dominance condition holds, keep the state unresolved/mixed rather than forcing a route.

This is simpler than modeling every C1/C2/C3 directional combination.

However, this audit is retrospective structural evidence only.

A causal implementation must still determine whether the relevant parent-leg pace and child-amplitude pace can be observed early enough.

## Evidence

Implementation SHA256:

`88a34b99b48ac4644d550df22ded6256a4a9d762cacecf106727562fc1303c6b`

Parent-leg ledger SHA256:

`2a49edd6b814876fef879fa81d673c47b51b9c197b04735504c8e36eb3705fc1`

Child-association ledger SHA256:

`de92a56b05a7607979d6335014d4c821313c8fbbfd816a8b368b6faee134e564`

Result SHA256:

`c32cbdbf44a479827820d5497ab01a2004b2b76a897d43acfb2684c6ed6c4e11`

## Authority

No signal/router/trade/paper/live/production authority.
