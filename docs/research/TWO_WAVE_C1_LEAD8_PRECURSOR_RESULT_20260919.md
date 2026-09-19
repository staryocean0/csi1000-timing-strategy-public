# C1 lead-8 precursor atlas — result

Issue #483. Parent #450.

## Verdict

`C1_LEAD8_PRECURSOR_ATLAS_COMPLETE`

This pass is a discovery atlas only.

The oracle is the final retrospective dense C1=S0-S1 slope-turn process. All lead features are sampled at k=t-L and use only information known by that clock.

Prefix replay passes at 10k / 30k / 50k for S0/S1.

## Oracle support

- common support: 69,971 native 5m bars
- C1 slope turns: 1,523
- TO_UP: 761
- TO_DOWN: 762
- event rows at leads 32/16/8: 4,569

## Event-only discovery

The strongest non-mechanical signed-return pattern is:

- direction-aligned ret_8 becomes more negative from lead16 to lead8
- median change: -0.0005733
- bootstrap 95% CI: [-0.0010184, -0.0002412]
- same sign in all 6 years
- same sign for TO_UP and TO_DOWN

Similarly:

- ret_16 delta median -0.0009130, CI [-0.0012329,-0.0006240]
- ret_32 delta median -0.0009266, CI [-0.0012691,-0.0006957]

Because signed returns are aligned to the FUTURE turn direction for analysis, the negative sign means the raw market still tends to move in the OLD direction as the event approaches.

This suggested a provisional terminal-thrust/exhaustion hypothesis.

## Mechanical clocks are not precursors

Several fields move by almost exactly +8 between lead16 and lead8:

- age_since_base_confirmation
- causal C1 evidence age
- S0/S1 evidence ages

Those are mechanical clock drift and must not be interpreted as predictive clues.

C1 age_ratio also rises mechanically as time passes without state refresh and is not promoted by itself.

## Short-horizon contraction clue

Unsigned path measures show some contraction close to the event:

- range_8 median lead16 0.0052085 -> lead8 0.0049470
- paired median delta -0.0002458, bootstrap CI [-0.0003918,-0.0000993]
- rv_8 median lead16 0.0011185 -> lead8 0.0010886
- paired median delta -0.0000565, CI [-0.0000838,-0.0000300]

The direction robustness is weaker than for the signed-return clue in this event-only atlas, so specificity must be checked against non-turn controls.

## Categorical changes are small

From lead16 to lead8:

- causal C1 leg aligned to future turn: +1.25 percentage points
- opposed: -1.25 pp
- last base wave aligned: +0.59 pp
- C1 phase LATE: -1.77 pp; MIDDLE +1.71 pp

These are descriptive only.

## Mechanism-only last eight bars

The path [t-8,t) is not available at t-8 and is therefore explanatory only.

It is explicitly forbidden as a lead-8 predictor.

## Required successor

The event-only atlas cannot establish specificity.

A matched non-turn control study is required before any precursor is promoted.

That successor is #485.

## Evidence identity

Implementation SHA256:
`47fc8e07499e1dc30f0da0decaaaf473f819460aeda33dce27f64359dd39bdfb`

Event ledger SHA256:
`0e942c1239ec7711fdaac2bc597c1d938bfa31938cc5276e8fd30a68dc6be643`

Mechanism ledger SHA256:
`5ec4404d3e79ab1b84bc4bdf93800f46d8e1af746e3cbac9979cfa844a7a476f`

Exact result SHA256:
`a8c289f27cc652262b95d688a5fd8b4d50536827f1a067ae4ac16d1737e12a41`

No PnL/routing outcome was used.

No signal/router/trade/production authority.
