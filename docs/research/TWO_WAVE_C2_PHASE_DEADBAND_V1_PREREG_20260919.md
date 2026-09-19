# Two-Wave C2 phase deadband V1 — preregistration

Issue #432. This study supersedes #429 as the primary secondary-low-frequency phase study.

## 1. Object

The research object is the actual graphical second low-frequency component:

`C2 = S1 - S2`

using the accepted scale-specific continuity carrier.

The frozen base detector remains 4/48 and is not modified.

Continuity carrier facts already established before this study:

- old hard-root C2 completed waves: 46
- continuity C2 completed waves: 170
- frozen base ledger unchanged
- no target period band imposed

## 2. Causal continuous C2 slope

Let the continuity hierarchy produce:

- S1 node stream = level-2 stage input stream;
- S2 node stream = level-3 stage input stream.

At native 5m knowledge bar k:

1. use only nodes with `known_from_bar <= k`;
2. require at least two known S1 nodes and two known S2 nodes;
3. define the current tail slope of each skeleton from its latest two known nodes in log-price per native bar;
4. define
   `s_C2(k) = slope_S1(k) - slope_S2(k)`.

No future node is used and no historical state is backfilled.

## 3. Causal slope normalization

Use recent completed C2 waves known by k.

For the latest up to three completed C2 waves:

`pace_i = A2_i / T2_i`.

Define:

`pace_C2(k) = median(pace_i)`.

Normalized current C2 slope:

`z(k) = s_C2(k) / pace_C2(k)`.

If required nodes or at least one completed C2 wave are unavailable, phase is UNRESOLVED.

Availability audit before outcomes:

- usable bars: 69,372 / 70,114 = 98.94%
- first usable k: 742
- last usable k: 70,113
- zero-deadband sign runs: 290
- one-update / one-native-bar sign runs: 125 = 43.1%

Therefore anti-chatter treatment is justified before any persistence outcome is examined.

## 4. Three-state Schmitt phase

States:

- C2_UP
- C2_RANGE
- C2_DOWN
- UNRESOLVED technical status outside the three states

Two nonnegative normalized thresholds:

- `exit`
- `enter`

with:

`0 <= exit <= enter`.

Transition rules:

From RANGE:

- z >= +enter -> UP
- z <= -enter -> DOWN
- otherwise RANGE

From UP:

- z <= +exit -> RANGE
- otherwise remain UP

From DOWN:

- z >= -exit -> RANGE
- otherwise remain DOWN

Direct UP -> DOWN and DOWN -> UP transitions are forbidden. A directional reversal must pass through RANGE.

At the first resolved bar, initialize to RANGE and then apply the same RANGE entry rule.

## 5. Frozen candidate grid

Normalized threshold grid:

- exit = 0.0, 0.1, ..., 1.0
- enter = 0.1, 0.2, ..., 3.0
- retain only enter >= exit

No threshold outside this grid may be introduced after results.

## 6. Structural anti-chatter reference

Raw reference sign is sign(z), ignoring UNRESOLVED bars.

A raw sign run is a consecutive resolved native-bar run with the same nonzero sign.

Definitions inherited from existing frozen time scales:

- sub-leg chatter: raw/candidate directional episode length < 4 native bars;
- stable raw turn: a sign reversal followed by a new raw sign run of at least 4 bars;
- stable directional run for entry timing: raw sign run of at least 8 bars.

The 4-bar boundary comes from frozen minimum-leg geometry.
The 8-bar boundary comes from the accepted confirmation-delay allowance.

## 7. Candidate diagnostics

For each threshold pair report:

- candidate directional episodes shorter than 4 bars;
- same-direction roundtrip exits:
  `UP -> RANGE -> UP` or `DOWN -> RANGE -> DOWN`
  with RANGE duration < 4 bars;
- total chatter count = short directional episodes + short same-direction roundtrips;
- fraction of stable raw turns where old directional state is exited within 4 bars;
- fraction of stable >=8-bar raw runs where matching new direction is entered within 8 bars;
- RANGE occupancy;
- directional occupancy;
- number of phase transitions.

## 8. Global deadband selection

A candidate is feasible only if:

- exit-old-direction-within-4 rate >= 0.90;
- enter-new-direction-within-8 rate >= 0.90;
- both metrics have at least 30 reference events.

Among feasible candidates choose lexicographically:

1. minimum total chatter count;
2. minimum short same-direction roundtrip count;
3. minimum RANGE occupancy;
4. minimum enter threshold;
5. minimum exit threshold.

If no candidate is feasible, global deadband is NOT_SUPPORTED.

No +8 persistence outcome participates in this selection.

## 9. Parameter dispersion

Repeat the exact same structural optimization independently within calendar years 2015-2020.

A year is usable only if both timing diagnostics have at least 20 reference events.

For exit and enter separately compute across usable years:

- median
- MAD
- MAD / max(median, 0.1)
- full range

Global parameter is declared HIGH_VARIANCE if either threshold has:

- normalized MAD > 0.35, or
- full range > 0.75.

If fewer than five years are usable, stability is INSUFFICIENT_YEAR_SUPPORT.

## 10. Conditional deadband contingency

This contingency is activated only if global parameters are HIGH_VARIANCE.

Candidate causal conditioning variables are frozen before seeing persistence:

1. recent C2 pace `A2/T2` tertile;
2. recent C2 period T2 tertile;
3. evidence age since latest known S2 node tertile.

Tertile cut points are computed from the full development structural ledger only; no persistence or return target is used.

For each condition family:

- optimize the same threshold grid independently in each tertile;
- require each tertile to have >= 5,000 resolved bars;
- compute year-specific threshold dispersion within each tertile.

A condition family is accepted only if:

- all three tertiles are feasible;
- median normalized MAD across enter/exit and tertiles is at least 30% lower than the unconditional normalized MAD;
- no tertile increases total chatter by more than 10% versus the unconditional structural optimum on its own bars.

If no family passes, conditionality remains unresolved and no single deployable threshold is frozen.

## 11. Phase persistence outcome

Only after the deadband decision is frozen structurally.

For every resolved bar k with k+8 available report:

Primary endpoint persistence:

`P8_endpoint(state) = P(phase(k+8) = phase(k) | phase(k)=state)`.

Continuous survival:

`P8_continuous(state) = P(all phase(k+1...k+8)=phase(k))`.

Entry-event persistence:

For every causal phase transition into UP/RANGE/DOWN at k:

- whether phase(k+8) is still the entered state;
- whether it survived continuously through k+8;
- episode duration.

Also report the +8 3x3 transition matrix.

Report all results overall and by year 2015-2020.

## 12. Interpretation boundary

This study answers:

- where a C2 RANGE anti-chatter zone should sit structurally;
- whether one global deadband is stable enough;
- if not, whether a predeclared condition family explains threshold variation;
- how often C2 UP/RANGE/DOWN remain the same eight native 5m bars later.

It does not answer PnL, route choice, position sizing, trade direction or production use.

The frozen five-state current-band classifier and accepted delayed wrapper remain unchanged.
