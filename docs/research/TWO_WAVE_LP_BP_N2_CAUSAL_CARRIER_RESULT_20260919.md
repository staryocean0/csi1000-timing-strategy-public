# LP vs BP qualification race N2 — causal latest-segment result

Issue #470. Parent #450. R2b #461.

## Verdict

`N2_NO_CLEAR_WINNER__KEEP_LP_BP_PARALLEL`

The first strictly causal carrier family does not preserve the N1 retrospective dominance information well enough to select LP or BP.

Prefix causality passes exactly, so the failure is not look-ahead leakage.

## Common target

N2 uses the exact same N1 hindsight dominance oracle:

- C2_DOM -> E0=T0 rhythm better over future 86-bar window
- C3_DOM -> E1=T1/C1 rhythm better

No target definition changed between N1 and N2.

## Causal carrier

At each knowledge bar k:

- use only S1/S2/S3 nodes with `known_from_bar <= k`;
- take the latest two visible nodes per skeleton;
- compute latest confirmed segment slope;
- LP uses S1/S2 causal slopes;
- BP uses S1-S2 / S2-S3 causal slope residuals;
- state machine also receives slope-run age and evidence-age/staleness.

No final retrospective LP/BP feature is used.

## Prefix replay

Passed at:

- 10,000
- 30,000
- 50,000

S1/S2/S3 latest visible node identity, price, slope and evidence age all match the independently rebuilt prefixes.

Therefore:

`PREFIX_CAUSALITY_PASS`

## Coverage

2018–2020 scored target anchors:

1,561.

Carrier coverage:

- LP: **100%**
- BP: **100%**

The result is not a coverage failure.

## Lowpass causal result

Pooled:

- balanced accuracy: **49.45%**
- ordinary accuracy: **49.58%**
- C2_DOM recall: 55.26%
- C3_DOM recall: 43.64%
- mean regret: **79.76bp**
- q90 regret: 243.54bp
- q95 regret: 327.62bp
- selected mean net: 32.37bp

Year balanced accuracy:

- 2018: 51.25%
- 2019: 49.40%
- 2020: 47.38%

LP reaches >=52% in **0/3** test years.

## Bandpass causal result

Pooled:

- balanced accuracy: **49.34%**
- ordinary accuracy: **49.46%**
- C2_DOM recall: 54.39%
- C3_DOM recall: 44.30%
- mean regret: **85.27bp**
- q90 regret: 249.71bp
- q95 regret: 345.21bp
- selected mean net: 26.86bp

Year balanced accuracy:

- 2018: 48.16%
- 2019: 47.36%
- 2020: 53.94%

BP reaches >=52% in **1/3** test years.

## Paired comparison

Mean:

`regret_BP - regret_LP = +5.51bp`

Positive favors LP.

But the paired 20-trading-day block bootstrap 95% interval is:

`[-5.55bp, +16.46bp]`

The interval crosses zero.

Paired balanced-accuracy difference:

`BA_LP - BA_BP = +0.11 percentage points`

Therefore neither representation passes the preregistered N2 causal-preference gate.

## Cross-stage interpretation

N1:

`LP_N1_RETROSPECTIVE_PREFERRED`

N2:

`N2_NO_CLEAR_WINNER__KEEP_LP_BP_PARALLEL`

Cross-stage status:

`NO_CAUSAL_RESOLUTION`

No representation is retired.

## What failed

This is not evidence that C2/C3 dominance is meaningless.

N1 showed that final retrospective LP morphology contains material dominance information:

- LP N1 BA 58.43%
- LP N1 regret 66.78bp
- clear paired regret advantage over BP

N2 shows that the first causal observation family — latest-confirmed-segment slope plus staleness — does not recover that information.

The likely bottleneck is the observation carrier, not coverage.

## Next implication

Do not move to execution routing yet.

R2b must continue with a better causal observation family while preserving:

- the same dominance oracle;
- the same LP/BP symmetry;
- the same walk-forward and regret metrics;
- no post-hoc routing optimization.

A next carrier should seek information between high-level node confirmations instead of sample-and-holding only the last completed segment.

## Evidence

Implementation SHA256:

`9e631fbf575d0f5f7da313025c25ffc2af8f1ca27c152ce14b17fec3132c4768`

Common OOF ledger SHA256:

`dff104094371f016e769581e3848a3192230e35ac3ee9b6c81f7ee64e6b5d80a`

Execution result SHA256:

`db94e7b36ef4f21e2a3791390ccea348b53c67eb69e3bdb191b54b852ac47181`

## Authority

Consumed development evidence.

Future outcome is used only as research target.

No fresh OOS, signal, router, paper/live, trade or production authority.
