# T0 retrospective C1×C2 nine-grid audit — result

Issue #480. Parent #450.

## Verdict summary

The retrospective three-state audit produces a very coherent first-order pattern:

1. **C1 ALIGNED is a strong positive background for T0.**
2. **C1 OPPOSED is a strong negative background and supports veto.**
3. **C1 RANGE is not confirmed as a safe/positive background; it is currently unresolved.**
4. C2 still matters, but mainly as a second-order quality modifier once the C1 state is known.
5. A supplementary causal control re-confirms that the live C1 current-leg direction should not simply replace T0's own direction.

The nine-grid is descriptive only. No nine-cell live router is authorized.

## Source / execution

- symbol: 000852.SH
- native 5m
- years: 2015–2020 development
- source rows: 70,114
- source SHA256: `bea21fa9dd9532e21605511e07561b33d5569f86f69f5a487507531593b14c48`

T0 module:

- period 21
- close breakout
- next-open fill
- own lifecycle
- 2bp per side proxy cost

T0 closed trades: 1,918.

Trades with both retrospective C1 and C2 complete-wave states: **1,896**.

Attrition:

- no C1: 5
- no C2: 17

## Frozen three-state semantics

For C1 and C2 complete-wave descriptor:

- UP: `g>+0.20`
- RANGE: `|g|<=0.20`
- DOWN: `g<-0.20`

No threshold was selected from T0 outcomes.

For the relative grid, UP/DOWN are mapped to ALIGNED or OPPOSED relative to the T0 trade side; RANGE remains RANGE.

---

## 1. Revalidation of the C1 rules

### C1 ALIGNED

N = **891**  
C2 parent waves = 167

- mean net: **+88.76bp**
- median net: +21.43bp
- win rate: **56.34%**
- fast-loss rate: 27.83%
- cluster-bootstrap mean 95% CI:
  **[+72.26bp, +108.74bp]**

LONG:

- mean +78.16bp

SHORT:

- mean +102.19bp

Formal result:

`C1_ALIGNED_POSITIVE_BACKGROUND_SUPPORTED`

### C1 OPPOSED

N = **834**  
C2 parent waves = 167

- mean net: **−38.04bp**
- median net: −40.17bp
- win rate: **19.78%**
- fast-loss rate: **54.20%**
- cluster-bootstrap mean 95% CI:
  **[−45.65bp, −30.53bp]**

LONG opposed:

- mean **−37.83bp**

SHORT opposed:

- mean **−38.21bp**

Formal result:

`C1_OPPOSED_RETROSPECTIVE_VETO_SUPPORTED`

This is a very strong revalidation of the idea that a T0 trade should not ignore an actively opposed C1 background.

### C1 RANGE

N = **171**  
C2 parent waves = 49

- mean net: **−1.36bp**
- median net: −26.46bp
- win rate: 38.01%
- fast-loss rate: 37.43%
- cluster-bootstrap mean 95% CI:
  **[−20.35bp, +19.16bp]**

LONG RANGE:

- mean −13.96bp

SHORT RANGE:

- mean +11.10bp

Formal result:

`C1_RANGE_UNRESOLVED`

Therefore the statement:

> "C1只要不是负的，正或横盘都可以继续"

is **not yet supported**.

The evidence currently supports:

> **C1 aligned is acceptable; C1 opposed is a veto; C1 range remains a separate neutral/unknown state.**

---

## 2. Primary T0-relative C1×C2 nine-grid

Mean T0 net result per cell:

| C1 \ C2 | C2 ALIGNED | C2 RANGE | C2 OPPOSED |
| --- | ---: | ---: | ---: |
| **C1 ALIGNED** | **+123.99bp** | **+57.22bp** | **+34.06bp** |
| **C1 RANGE** | +1.15bp | +11.72bp* | −5.53bp |
| **C1 OPPOSED** | **−23.75bp** | **−41.02bp** | **−44.25bp** |

* C1 RANGE × C2 RANGE has only 10 trades / 3 C2 parent waves and is low support.

### C1 ALIGNED row

#### C1 ALIGNED × C2 ALIGNED

N 510, parent waves 141

- mean **+123.99bp**
- bootstrap CI **[+98.65, +155.06]**
- win rate 60.59%
- fast-loss 26.08%

#### C1 ALIGNED × C2 RANGE

N 124, parent waves 21

- mean **+57.22bp**
- bootstrap CI **[+35.23, +82.00]**
- win rate 54.84%
- fast-loss 25.81%

#### C1 ALIGNED × C2 OPPOSED

N 257, parent waves 130

- mean **+34.06bp**
- bootstrap CI **[+19.88, +49.30]**
- win rate 48.64%
- fast-loss 32.30%

All three C2 columns remain positive when C1 is aligned.

C2 still changes the magnitude substantially:

`C2 aligned > C2 range > C2 opposed`.

### C1 OPPOSED row

#### C1 OPPOSED × C2 ALIGNED

N 235, parent waves 123

- mean **−23.75bp**
- bootstrap CI **[−34.30, −12.60]**
- win rate 22.98%

#### C1 OPPOSED × C2 RANGE

N 111, parent waves 21

- mean **−41.02bp**
- bootstrap CI **[−58.34, −27.03]**
- win rate 24.32%

#### C1 OPPOSED × C2 OPPOSED

N 488, parent waves 135

- mean **−44.25bp**
- bootstrap CI **[−54.78, −34.21]**
- win rate 17.21%

All three C2 columns are negative when C1 is opposed.

Even an aligned C2 background does not rescue an opposed C1.

This is the strongest structural pattern in the grid.

### C1 RANGE row

#### C1 RANGE × C2 ALIGNED

N 81

- mean +1.15bp
- CI [−18.21, +21.79]

#### C1 RANGE × C2 RANGE

N 10 — low support

- mean +11.72bp
- very wide CI

#### C1 RANGE × C2 OPPOSED

N 80

- mean −5.53bp
- CI [−25.74, +14.49]

No C1-RANGE cell establishes a stable positive or negative result.

Therefore C1 RANGE is not currently a permission state.

---

## 3. C2 still contains information

Pooling over C1:

### C2 ALIGNED

N 826

- mean **+69.91bp**
- bootstrap CI **[+53.51, +90.08]**

### C2 RANGE

N 245

- mean **+10.85bp**
- bootstrap CI **[+2.51, +19.99]**

### C2 OPPOSED

N 825

- mean **−16.10bp**
- bootstrap CI **[−23.74, −8.31]**

So C2 is not irrelevant.

But the full grid shows that C1 is the stronger first-order gate:

- C1 ALIGNED remains positive even when C2 is opposed.
- C1 OPPOSED remains negative even when C2 is aligned.

This suggests the retrospective ordering:

> **first inspect C1; then use C2 mainly to grade the quality of an already-permitted C1 state.**

This is a descriptive interpretation, not yet a frozen routing rule.

---

## 4. Ignoring C1 is materially harmful

All eligible T0 trades:

- N 1,896
- mean +24.86bp
- win rate 38.61%

C1 NON-OPPOSED:

- N 1,062
- mean **+74.25bp**
- win rate **53.39%**
- fast-loss 29.38%

C1 OPPOSED:

- N 834
- mean **−38.04bp**
- win rate **19.78%**
- fast-loss 54.20%

Therefore the earlier conclusion that C1 cannot simply be ignored is strongly revalidated.

---

## 5. Direct C1 supervision requires a causal distinction

### Preregistered retrospective-descriptor shadow

Using the **final retrospective C1 complete-wave descriptor** UP/DOWN as the shadow direction over the same T0 entry/exit interval:

- N 1,725
- actual T0 mean: +27.45bp
- retrospective C1-shadow mean: **+60.37bp**
- paired shadow minus T0: **+32.92bp**
- parent-C2-wave bootstrap CI for difference:
  **[+25.69bp, +40.46bp]**

Formal preregistered result:

`C1_DIRECT_SUPERVISION_NOT_REJECTED`

This must **not** be interpreted as a live trading result.

The final complete-wave C1 descriptor is retrospective and uses information unavailable at the T0 decision time.

### Supplementary causal sanity control

Using only the then-known C1 current causal leg direction at each T0 signal:

- resolved: 1,912 / 1,918 = 99.69%
- actual T0 mean: **+24.51bp**
- causal C1-direction shadow mean: **−17.10bp**
- paired causal-C1 minus T0:
  **−41.61bp**

20-trading-day block bootstrap:

- 74 blocks
- 95% CI:
  **[−60.63bp, −30.51bp]**

Year-by-year causal C1-shadow mean is negative in every year 2015–2020, while T0 mean is positive in every year.

Thus the operational historical rule is revalidated:

> **the currently observable C1 direction should not directly replace T0's own direction.**

The apparent retrospective C1-shadow success is a look-back upper-bound property of the final complete-wave descriptor, not a live supervisor.

---

## 6. Current rule status after revalidation

### Rule 1 — "Follow C1 directly for T0"

**Rejected in the causal operational interpretation.**

Do not use C1 current direction as the T0 direction signal.

### Rule 2 — "Ignore C1"

**Rejected.**

C1-opposed T0 outcomes are strongly negative.

### Rule 3 — "C1 opposed should veto T0"

**Supported retrospectively and strongly.**

### Rule 4 — "C1 aligned is a positive T0 background"

**Supported retrospectively and strongly.**

### Rule 5 — "C1 range is equivalent to nonnegative permission"

**Not supported yet.**

C1 RANGE remains unresolved.

---

## 7. What the nine-grid suggests

The grid does not look like nine equally important independent states.

It looks more hierarchical:

1. **C1 ALIGNED** — favorable branch.
   - C2 ALIGNED is best.
   - C2 RANGE is intermediate.
   - C2 OPPOSED is weaker but still positive.

2. **C1 OPPOSED** — veto branch.
   - all three C2 states are negative.

3. **C1 RANGE** — unresolved branch.
   - current data does not establish a reliable C2 rescue/selection pattern.

That is the main empirical regularity.

A successor rule should be preregistered separately if promoted.

## Evidence identity

Implementation SHA256:

`fed118d66f12ecdc1a8969ddff1d3441516cac8981a13e42af47506cd35320c4`

T0/C1/C2 ledger SHA256:

`ce477553b0c952464f7e2d5923e2c6350b84df4c8eb6191289d9c598c79a1c9b`

Formal result SHA256:

`122c8650fbb5faebbe6fd09f81e98a29a0091242cc55cb0ff1bc0da1bdd28a74`

## Authority

Retrospective consumed-development evidence only.

The causal C1 direct-supervision check is a supplementary historical control, not a production signal.

No signal/router/paper/live/trade/production authority.
