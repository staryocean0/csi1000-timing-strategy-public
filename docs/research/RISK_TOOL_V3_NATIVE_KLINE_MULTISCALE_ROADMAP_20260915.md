# Risk Tool V3 — Native K-line Multi-Scale Roadmap — 2026-09-15

## Direction amendment — 2026-09-16

The program is now explicitly **top-down in scale** for risk attribution:

> **Native-60m → Native-15m → Native-5m**

This amendment changes the research order and attribution logic, not any frozen V2 result or prior Native-15m result.

The purpose is not to use different K-line scales as three views of the same already-defined event. The purpose is to let each native K-line scale reveal the class of risk that survives aggregation at that scale, then decompose larger-scale risk into smaller-scale structure.

The earlier Native-15m work is preserved as valid evidence. Its carrier audit and descriptive map remain useful, and its C1 state-machine candidate result remains immutably `NATIVE15_STATE_MACHINE_CANDIDATE_MAP_INSUFFICIENT`. The C1 attribution showed that severity separation and next-bar persistence were broadly present, while pooled q95 event-capture gates were the dominant incompatibility. That result is not rescued or rewritten. Native-15m parameter search is paused while the program establishes the larger-scale risk hierarchy first.

## Core principle: K-lines are lossy compression

A K-line is not a neutral container. Aggregating a finer path into a larger bar compresses information.

For a 60-minute interval, a large amount of 1m/5m/15m movement can occur inside the bar even when the final 60m open-to-close body is small. Therefore the Native-60m research object must not be reduced to candle body alone.

A canonical 60m research bar should preserve, at minimum:

- open, high, low, close;
- absolute 60m body `|log(close/open)|`;
- 60m high-low range `log(high/low)`;
- close-to-close 60m return where causally available;
- an **intrabar path-energy / realized-volatility measure computed from the official 1m path** inside that exact 60m bar.

The intrabar path measure exists specifically to avoid calling a violent up-and-down hour “low risk” merely because its close returned near its open.

## Non-negotiable native-scale semantics

For every scale `S` in `{5m, 15m, 60m}`:

- the primitive observation stream is made of K-lines whose base interval is exactly `S`;
- state and persistence advance in native bars of that scale;
- `Native-15m` is not a 15-minute forecast horizon of the 5m tool;
- `Native-60m` is not a 60-minute forecast horizon of the 5m tool;
- existing V2 15m/30m results remain forecast horizons of the native-5m V2 tool.

## Scale hierarchy hypothesis

The program will test, rather than assume, a directional hierarchy:

1. **Large-scale risk may transmit downward.** If a genuine 60m risk regime exists, the constituent 15m and 5m bars should usually contain observable stress structure.
2. **Small-scale risk need not transmit upward.** A short 5m shock may be absorbed inside a larger bar and leave little or no 60m regime signature.
3. Therefore attribution should start from the largest research scale, establish whether the large-scale state has continuity, and only then peel the bar open into smaller scales.

This is a scientific hypothesis, not yet authority.

## Existing Native-5m authority

Risk Tool V2 remains the governed native-5m implementation. Its scientific results and consumer permissions are unchanged. V3 can use its research discipline as a benchmark, but must not assume that its windows, thresholds, or event semantics are scale-invariant.

## Preserved Native-15m evidence

Completed Native-15m work is retained:

- carrier semantics on `15m_offset_5` were verified;
- the 2021–2023 descriptive map was completed;
- the 576-candidate C1 state-machine map returned 0 formal passes under the frozen gate set;
- a result-only attribution diagnostic showed that the principal incompatibility was pooled/annual fixed-tail event capture, while current severity separation and next-bar persistence gates were broadly satisfied.

Interpretation boundary: this does **not** prove that Native-15m risk lacks persistence. It proves only that the frozen C1 acceptance definition did not produce an authorized Native-15m state machine. Further Native-15m design is deferred until the 60m hierarchy is understood.

## Active program: Native-60m first

### Data source

The current PRIVATE inventory provides an official `1m_official` source through 2026-08-21 and provider-supplied 5m/15m views, but no provider-supplied 60m view. Therefore the Native-60m line will define one deterministic, session-aware **official-1m → canonical-60m** transformation before any threshold research.

No 5m or 15m resampling is allowed to define 60m authority when the official 1m source is available.

### Proposed A-share 60m session geometry to audit and freeze

Subject to verification of the official 1m timestamp semantics, the intended wall-clock intervals are:

- 09:30–10:30;
- 10:30–11:30;
- 13:00–14:00;
- 14:00–15:00.

The lunch break is a hard boundary. No 60m bar may bridge 11:30–13:00. Exact endpoint inclusion and timestamp labeling must be frozen only after the 1m source semantics are independently audited.

### Phase 60-A — carrier construction / semantic audit

Before studying risk:

- pin exact `1m_official` bytes/SHA256 and symbol binding;
- verify 1m timestamp, OHLC, trading-day and session semantics;
- freeze deterministic 1m→60m bar membership;
- verify expected 1m member count per complete 60m bar;
- verify four canonical bars per complete trading day;
- preserve no-lookahead semantics;
- materialize only aggregate audit outputs until the construction contract is accepted.

### Phase 60-B — large-scale volatility continuity map

The first scientific question is **not** “which threshold wins?” It is:

> Does native 60m risk intensity show clear temporal continuity, and which 60m risk observable carries that continuity most faithfully?

On the permitted development window, describe without selecting a winner:

- distribution of 60m body magnitude;
- distribution of 60m high-low range;
- distribution of 60m close-to-close absolute return;
- distribution of 60m intrabar 1m realized volatility / path energy;
- correlation and disagreement among those measures;
- lag-1 / lag-2 / lag-3 persistence of each measure;
- conditional next-bar risk intensity after low / middle / high quantile states;
- run-length / episode distributions for high-risk quantile states;
- time-of-day slot effects across the four native 60m bars;
- year-by-year stability on development years.

This phase is descriptive and mechanistic. It must not install a state machine or optimize a trading objective.

### Phase 60-C — 60m risk-state research

Only if Phase 60-B establishes meaningful continuity should the project define candidate 60m state variables and transition rules. Those rules may use body, range, intrabar realized volatility, or a preregistered combination; they must not be forced to mimic the 5m state machine.

## Downward decomposition after 60m characterization

Once 60m high-risk and low-risk regimes have a frozen descriptive definition, the next question becomes conditional decomposition:

> **What do the constituent 15m and 5m bars look like inside high-risk versus low-risk 60m bars?**

This decomposition should measure, among other things:

- number and ordering of large 15m/5m moves inside the hour;
- whether the hour is trend-like or violently mean-reverting;
- concentration of intrabar realized variance;
- whether stress is front-loaded, persistent, or late-emerging;
- how often a small-scale shock dies locally versus contributes to a large-scale regime.

The objective is risk attribution and hierarchy, not immediate trading.

## Governed research sequence

The active sequence is now:

1. **Native-60m canonical carrier construction / semantic audit from official 1m.**
2. **Native-60m volatility-continuity map.**
3. If continuity is supported, **Native-60m risk-state candidate research.**
4. **60m → 15m decomposition:** characterize constituent 15m structure conditional on 60m risk level.
5. **15m → 5m decomposition:** characterize finer structure conditional on the higher-scale context.
6. Revisit Native-15m state design using the large-scale hierarchy as explanatory context; do not rescue the frozen C1 result.
7. Only after scale-specific states are independently validated: formal cross-scale Layer2 output contract.

## Development / audit discipline

- 2021–2023 may be used as the currently consumed development window where the relevant source supports it.
- 2024–2025 remain reserved for separately preregistered repeat-audit questions unless already consumed by the exact prior contract being referenced.
- 2026 is not automatically opened for threshold training.
- Failed or insufficient results remain immutable.
- No threshold, gate, or candidate family may be changed after observing a frozen result and then presented as the same test.
- No strategy routing, sizing, PnL, or production authority is granted by this roadmap.

## Design principle

The program now treats multi-scale risk as a **hierarchical attribution problem**:

> First identify what risk looks like when it survives compression into a large K-line. Then open that large bar and explain how the smaller bars produced it.

The active direction is therefore **60m → 15m → 5m**, not 5m → 15m → 60m.