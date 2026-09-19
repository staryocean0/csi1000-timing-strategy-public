# C1 lead-8 causal direct-direction predictor — result

Issue #604. Parent #601 / #507 / #483 / #450.

## Verdict

`C1_LEAD8_DIRECT_DIRECTION_SUPPORTED`

This is the first accepted causal lead-8 C1 direction recognizer in the current research line.

## Frozen setup

- universe: period-21 T0 signal bars
- target: retrospective dense C1=S0-S1 slope sign at k+8
- inputs: raw OHLC path + completed base/T0-wave structure + T0 side
- excluded: causal C1 leg/descriptor/phase, confirmed S0/S1 segment slopes, PnL, future returns
- model: fixed balanced logistic regression pipeline, no hyperparameter search
- walk-forward: 2018 / 2019 / 2020 with +8 label purge

## Pooled result

- N: **945**
- UP: 474
- DOWN: 471
- balanced accuracy: **64.34%**
- accuracy: **64.34%**
- recall UP: **64.35%**
- recall DOWN: **64.33%**
- ROC AUC: **0.6798**
- 20-trading-day block bootstrap BA 95% CI: **[61.51%, 67.23%]**

All preregistered acceptance gates pass.

## Year stability

- 2018 BA: **62.28%**, AUC 0.6670
- 2019 BA: **64.26%**, AUC 0.6862
- 2020 BA: **66.67%**, AUC 0.6947

All three test years pass the >=52% BA gate.

## Compression-band diagnostic

The direction recognizer works across all frozen #507 compression bands, but direction fidelity weakens in B5:

- B1 BA: 65.78%
- B2 BA: 65.25%
- B3 BA: 62.26%
- B4 BA: 65.67%
- B5 BA: 58.01%

This is diagnostic only and does not alter the frozen direction model.

## Interpretation

The earlier failure of high-level causal C1 anchors was not evidence that C1 direction is causally unknowable.

Instead, the direction information is recoverable from lower-level raw/T0 structure before the final C1 geometry confirms.

This matches the intended research direction:

> use retrospective C1 as the oracle, then learn stable structure visible at least 8 bars earlier.

## Reproducibility note

The original formal result receipt recorded module SHA:

`aa2f99978dcb7c023ba381661dc50884aef23e280e13a255ee5dfb1984e7be88`

That exact source file could not be located afterward.

A reconstructed implementation was independently replayed and matches the stored formal OOF exactly row-for-row:

- signal_bar: exact
- target_bar: exact
- target labels: exact
- predictions: exact
- predicted UP probabilities: exact, maximum absolute difference = 0
- fold metrics: exact
- pooled metrics: exact
- bootstrap result: exact
- final decision: exact

Reconstructed module SHA:

`766f1ac26edb2005cbe0959fe99e846b1e5295d30de747c2bfab2c17f59c688a`

## Evidence

- feature ledger SHA256: `e365fcfa505dd65004165dff0bf40febcff2a3229bc1b6c743639c3758ded1f9`
- OOF ledger SHA256: `7abaaea2fccc1eb690ae48d2aae9c68a52b6416e3058b49332173ad16a5e9366`
- formal result SHA256: `7d6fd0ef9a0c6ab3348f988d7419ec1e3da1edb16f98dc0846a78c006c925f1c`

## Authority

Consumed-development evidence only.

No signal/router/paper/live/trade/production authority.