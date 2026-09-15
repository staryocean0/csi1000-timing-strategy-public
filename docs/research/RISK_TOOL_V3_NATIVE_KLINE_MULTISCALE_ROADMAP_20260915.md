# Risk Tool V3 — Native K-line Multi-Scale Roadmap — 2026-09-15

## Purpose

This document freezes the next research direction for the Risk Tool program. It exists to prevent a recurring semantic mistake: **15m / 60m in this roadmap mean the K-line base interval itself, not a forecast horizon measured from the existing 5m tool.**

The current Risk Tool V2 remains the governed 5-minute-base implementation and is not modified by this roadmap.

## Non-negotiable scale semantics

For every native scale `S` in `{5m, 15m, 60m}`:

- the input market series is a sequence of K-lines whose bar interval is exactly `S`;
- returns are computed from consecutive `S`-minute bars;
- short-horizon realized volatility is computed from native `S`-minute returns;
- background volatility is computed from native `S`-minute returns;
- shock intensity is defined on an `S`-minute bar;
- state transitions (`NORMAL`, `UNSAFE`, `RECOVERING`) advance one native `S`-minute bar at a time;
- shock age / persistence is measured in native `S`-minute bars and only converted to clock time for reporting;
- labels and future-recovery questions are defined after the native state machine exists; they do not define the K-line scale.

Therefore:

- **Native-15m Risk Tool != 5m Risk Tool with a 15-minute forecast horizon.**
- **Native-60m Risk Tool != 5m Risk Tool with a 60-minute forecast horizon.**
- Existing 15m/30m forecast-horizon results inside Risk Tool V2 remain 5m-base results.

## Program structure

### V2 — Native 5m base (existing authority)

The existing Risk Tool V2 is the benchmark / parent methodology. It provides the research template:

1. define a native-bar shock measure;
2. define recent-vs-background volatility;
3. build a causal `NORMAL -> UNSAFE -> RECOVERING -> NORMAL` state machine;
4. measure state age / persistence;
5. build frozen prediction components;
6. calibrate and test temporal stability;
7. validate Reliability / consumer permissions;
8. reserve genuinely fresh OOS data for final confirmation.

V2 scientific results and authority are immutable. V3 may learn from the V2 research process but may not rewrite V2.

### V3-A — Native 15m Risk Tool

Build a new risk sensor whose **base observations are 15-minute K-lines**.

Initial data anchor:

- prefer the existing DataHub-provided `15m_offset_5` view because it is an original supplied view, not an ad-hoc local resample;
- verify exact source identity, timestamp semantics, session coverage, missing bars, symbol binding, and historical range before any model fitting;
- no 2026 threshold/model training unless a later preregistration explicitly opens a permitted development window.

Research the following from the native-15m data rather than inheriting V2 values:

- shock definition and candidate shock thresholds;
- short-volatility lookback in native 15m bars;
- background-volatility lookback in native 15m bars;
- high-volatility / recovering / normal transition thresholds;
- minimum state persistence / hysteresis if needed;
- age buckets in native 15m bars;
- recovery/persistence prediction horizons suitable for the native-15m state process;
- temporal stability, probability calibration and reliability rules.

The V2 constants `RV_WINDOW=12`, `BG_WINDOW=48`, `SHOCK_SIGMA=3.0`, `HIGHVOL_RATIO=1.50`, and `RECOVERY_NORMAL_RATIO=1.10` are **benchmarks only**. They are not automatically authorized native-15m parameters.

### V3-B — Native 60m Risk Tool

Build a separate risk sensor whose **base observations are 60-minute K-lines**.

Before model work, freeze a canonical 60m K-line carrier contract:

- use an official/provider 60m view if such a view is available and semantically valid;
- otherwise define one deterministic, session-aware transformation from the official 1m source into canonical 60m bars and freeze that transformation before any threshold search;
- do not casually aggregate 5m bars during model development;
- explicitly define how the A-share lunch break and partial trading-hour geometry map into 60m bars;
- verify bar count, bar boundaries, timestamps and no-lookahead semantics.

Then research the same conceptual components as V3-A, but independently in native 60m bars. No assumption is made that 15m thresholds/windows scale linearly into 60m.

Expected scientific role (hypothesis, not authority): the native-60m tool may behave more like a persistent risk-regime / market-weather sensor than a rapid event alarm. This must be tested rather than assumed.

### V3-C — Cross-scale Risk Stack

Only after Native-15m and Native-60m each have their own frozen and validated state processes, study their interaction with the existing Native-5m tool.

Primary questions:

- how often does 5m `UNSAFE` escalate into 15m `UNSAFE`?
- how often does 15m `UNSAFE` escalate into 60m `UNSAFE`?
- during 60m `UNSAFE`, does the incidence / persistence of 5m shocks increase materially?
- in recovery, which scale normalizes first and what are the typical lags?
- what information exists in scale disagreement (for example, 5m unsafe while 15m/60m normal)?
- can the three-scale state vector provide more stable Layer2 context than any single scale alone?

The cross-scale stack is a Layer2 measurement/state project. It grants no strategy-routing, position-sizing, PnL or production authority by itself.

## Research sequence

The governed sequence is:

1. **Native-15m carrier audit / semantic freeze.**
2. **Native-15m descriptive map:** event frequency, severity, persistence and recovery distributions.
3. **Native-15m state-machine parameter research and freeze.**
4. **Native-15m model / calibration / temporal-stability pipeline following the V2 governance pattern.**
5. **Native-60m carrier construction or provider-view audit / semantic freeze.**
6. **Native-60m descriptive map and state-machine research.**
7. **Native-60m model / calibration / temporal-stability pipeline.**
8. **Cross-scale 5m × 15m × 60m escalation/recovery analysis.**
9. Only after the above: define any Layer3 consumer contract for multi-scale outputs.

## Development / audit discipline

Where data coverage permits, preserve the established temporal discipline:

- development / threshold discovery on permitted historical development years;
- repeat audit on later untouched historical years;
- genuinely fresh OOS reserved and preregistered before reveal;
- no post-result parameter rescue;
- every scale keeps separate parameter identity, model identity and authority status.

A successful 5m result does not authorize 15m or 60m. A successful 15m result does not authorize 60m. Each native scale must earn its own authority.

## Design principle

The goal is not to copy the 5m numbers twice. The goal is to reproduce the **research logic** at each K-line scale and let each scale reveal its own risk personality.

In short:

> 5m, 15m and 60m are three native K-line risk sensors from the same methodological family, not one 5m sensor observed at three future horizons.
