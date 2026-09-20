# Two-Wave R2b roadmap amendment — N3 causal in-progress leg carrier

Date: 2026-09-20.  
Parent thread: #450. R2b: #461. N2: #470. N3: #652.

## Why R2b continues once, but not indefinitely

N2 established a useful negative result.

The latest-confirmed-segment carrier was:

- strictly causal;
- prefix-replay exact;
- 100% covered on the scored anchors;
- symmetric between LP and BP.

But it did not recover usable dominance information:

- LP balanced accuracy 49.45%, >=52% in 0/3 years;
- BP balanced accuracy 49.34%, >=52% in 1/3 years;
- paired regret interval crossed zero.

Therefore the N2 failure is not a missingness or look-ahead problem.

The structural weakness is sample-and-hold staleness between slow-level node confirmations.

## N3 bounded repair

N3 admits exactly one new causal observation family:

> confirmed slow anchor + latest already-visible immediate-faster child node -> in-progress bridge slope.

The carrier does not forecast the next slow node.

It only updates the estimate of the currently forming slow leg from evidence that has already occurred and is already known.

All S1/S2/S3 active slopes are computed first.

LP and BP are then derived from the same active-slope triplet:

- LP2 = g1, LP3 = g2;
- BP2 = g1-g2, BP3 = g2-g3.

This preserves the R2b LP/BP symmetry requirement.

## Observation design is separated from routing outcomes

The R2b charter requires carrier-family selection to be independent of T0/C1 execution outcomes.

N3 therefore formalizes two ordered gates:

1. Gate A — outcome-blind fidelity against the frozen retrospective LP/BP morphology and against the N2 carrier baseline.
2. Gate B — only after Gate A passes, reuse the already-frozen N1/N2 dominance oracle and execution-qualification protocol.

This does not invalidate N1 or N2.

It prevents the next carrier family from being chosen because it happens to improve route PnL or regret.

## Revised R2b state

Completed:

- R0 representation freeze;
- R1 morphology atlas;
- R2 exact observability rejection;
- LP/BP Pass A;
- N1 retrospective qualification;
- N2 first causal carrier qualification.

Active next:

`R2b-N3_CAUSAL_INPROGRESS_LEG_CARRIER`.

R3 fair E0/E1 execution-contract work remains blocked until N3 causal qualification passes.

## Hard stop after N3

N3 is the bounded second carrier family, not the start of an open-ended recognizer search.

If outcome-blind Gate A fails:

- close #652;
- do not run dominance Gate B;
- do not open N4 automatically.

If Gate A passes but neither LP nor BP passes the frozen Gate-B causal qualification:

- close #652;
- stop automatic R2b carrier-family expansion;
- do not rescue with deeper trees, extra features, P128/P256, future-state predictors, new T0/T1 periods or alternate horizons.

A new carrier after that point would require a separate framework-level rationale, not an automatic continuation.

## Authority

N3 remains consumed-development qualification only.

No signal, router, trade, paper, live or production authority is created by preregistration or by passing the carrier-fidelity gate.

Only a Gate-B-qualified representation may advance to the separately frozen R3 execution-contract stage.
