# T0 outcome stratification by causal C1 compression-risk bands — result

Issue #537. Parent #507 / #493 / #450.

## Verdict

`C1_COMPRESSION_T0_ECONOMIC_DEGRADATION_NOT_SUPPORTED`

The frozen causal C1 compression-risk score does predict C1 turn risk, but it does not support a direct T0 veto based on mean return degradation.

## Frozen input

- strict-boundary #507 scored ledger, SHA256 `6fb773743cad9f009b62b973888b63db385459bd6e5db9524046e0b7958d8b33`
- 945 scored T0 signals, 2018–2020
- score/bands unchanged
- T0 period-21 own-lifecycle outcomes

## Pooled band outcomes

| Band | N | Mean net bp | Win rate | Fast-loss rate |
| --- | ---: | ---: | ---: | ---: |
| B1 | 142 | +21.54 | 41.55% | 30.28% |
| B2 | 218 | +28.44 | 43.12% | 32.57% |
| B3 | 229 | +20.96 | 38.43% | 42.36% |
| B4 | 179 | +26.68 | 38.55% | 43.02% |
| B5 | 177 | +14.32 | 33.90% | 49.72% |

Mean return is lower in B5 than B1, but not monotonically degraded across all bands.

## Primary contrasts

- `B5 - B1` mean net = **-7.22bp**
- bootstrap 95% CI = **[-49.57bp, +28.88bp]**
- `B4+B5 - B1+B2` mean net = **-5.18bp**
- bootstrap 95% CI = **[-27.44bp, +16.23bp]**

Both return intervals cross zero.

Fast-loss contrast:

- `B4+B5 - B1+B2` = **+14.68 percentage points**
- bootstrap 95% CI = **[+7.91pp, +21.75pp]**

This is the strongest economic effect.

## Year stability

2018:
- B5-B1 mean net = -31.11bp

2019:
- B5-B1 mean net = -0.68bp

2020:
- B5-B1 mean net = +7.18bp

B5 mean is below B1 in 2 of 3 years, but the pooled mean-return degradation is not statistically established.

## Interpretation

The accepted causal C1 compression score is better interpreted as a **short-horizon whipsaw / fast-loss hazard indicator** than as a direct T0 expected-return veto.

High compression increases the chance that T0 is quickly stopped/reversed, but the surviving right-tail trades are large enough that mean net return is not significantly lower.

Therefore:

> do not veto high-compression T0 trades from this evidence alone.

A more mechanism-aligned successor is to test whether **deferring entry by 8 bars** in the predeclared high-risk B4+B5 group reduces fast losses without destroying the opportunity.

## Evidence

- module SHA256 `bcc1e5dd46545498e2c2eefd37737c7720124aacff008a9b5d7dff48e3c5622c`
- joined ledger SHA256 `e53a3551a53a218edcd7f6a795cb168d5ca4722c60a84fe14284e3a1579291d5`
- exact result SHA256 `2e0adec3f2f8dabd1ea278fa44af41ad4c8c70612c8985361c56545c0638e7f6`

## Authority

Development evidence only.

No signal/router/trade/paper/live/production authority.