# Two-Wave v0.8.0 — C2 rho semantic adjudication

Status: frozen **before** any V0800-D direction grid.

## Why another gate is necessary

B1 established that strict consecutive `L-H-L-H-L` pairs are abundant enough to be the direction-eligible morphology. C then proved that those pivots, A-waves, pairs and same-scale flags can be reproduced causally from confirmation-time information only.

Neither experiment identified a scientifically admissible rho winner. B1's normalized path diagnostic removed time and amplitude scale by construction, while C only reproduced the same support counts online. Therefore the temporal-level boundary must not be selected by whichever candidate produces the most support or the best later trading result.

## Scale coordinate

Wave duration is multiplicative: a 20-bar wave is naturally twice a 10-bar wave in the same way that a 10-bar wave is twice a 5-bar wave. The C2 convention therefore works on

`q = log2(duration)`.

We define neighboring temporal-level centers on a dyadic lattice, one octave apart:

`..., N/2, N, 2N, 4N, ...`.

This convention has two useful properties for the user's original requirement:

1. it is scale invariant — the rule has exactly the same form around 5, 10, 20 or any other positive duration;
2. it introduces no privileged absolute number of bars.

## Nearest-level boundary

On the `log2(duration)` axis, the midpoint between level centers `N` and `2N` is half an octave above `N`. In ordinary duration units that midpoint is the geometric mean:

`N * 2^(1/2) = N * sqrt(2)`.

The symmetric lower boundary is `N / sqrt(2)`. Therefore C2 defines two waves as belonging to the same temporal level when

`abs(log2(d_previous / d_current)) <= 1/2`,

which is exactly equivalent to

`max(d_previous, d_current) / min(d_previous, d_current) <= sqrt(2)`.

Hence the operational same-level ratio is **rho = sqrt(2)**.

For integer bar durations the band around a current duration `N` is

`[ceil(N/sqrt(2)), floor(N*sqrt(2))]`.

Illustrations:

- N=5 -> 4..7 bars;
- N=10 -> 8..14 bars;
- N=20 -> 15..28 bars.

The N=5 row is only a semantic illustration. The currently frozen v0.4.3 pivot-maturity kernel has its own minimum-leg constraints and need not actually emit 5-bar A-waves.

Because a ratio of two positive integer durations is rational while `sqrt(2)` is irrational, exact integer-duration ties on the boundary cannot occur. The existing `<= rho` implementation is therefore deterministic here.

## What this decision is — and is not

This is a **semantic convention**, not an empirical winner declaration. It does not use B1 support, normalized path RMS, future returns, PnL, 2026 data or a direction objective to choose among `{1.25, 4/3, sqrt(2), 1.5}`.

The narrower candidates 1.25 and 4/3 remain historical preregistered alternatives; 1.5 remains a wider alternative; legacy rho=2 remains a historical control. None of them is promoted by market performance. The operational v0.8.0 same-level rule is `rho=sqrt(2)` because it is the unique half-octave boundary induced by the frozen dyadic scale convention.

No amplitude gate is added.

## Authority after C2

C2 grants **rho semantic authority only**. It does not create a market direction state and it does not grant trading or production authority.

After this document is reviewed and merged, V0800-D may be preregistered. That D protocol must use:

- confirmation-time knowledge only;
- strict shared-anchor consecutive pairs only;
- `rho=sqrt(2)` only;
- the already-frozen tau family `{0.05, 0.10, 0.15, 0.20}`;
- the already-frozen kappa family `{1.25, 1.50, 2.00}`.

V0800-D execution remains blocked until its own protocol is separately reviewed and merged. Future outcomes, PnL, positions and 2026 remain closed at this gate.
