# LP vs BP qualification race N1 — retrospective dominance result

Issue #467. Parent #450.

## Verdict

`LP_N1_RETROSPECTIVE_PREFERRED`

This is a noncausal development qualification result, not a live router.

The common hindsight dominance oracle maps:

- C2_DOM -> E0=T0 rhythm is better over the frozen future 86-bar window
- C3_DOM -> E1=T1/C1 rhythm is better

T0=21 and T1=86 were frozen from 2015–2017 structural wave-duration medians before the qualification result.

## Oracle support

All neutral anchors: 3,282.

Truth counts:

- C2_DOM: 1,644
- C3_DOM: 1,501
- exact ties / AMBIG: 137

Scored walk-forward 2018–2020 anchors:

- 1,561
- C2_DOM: 798
- C3_DOM: 763

The scored target is close to balanced, so the comparison is not driven by a single dominant class.

## Common state-machine contract

LP and BP use exactly the same six features:

- normalized fast slope
- normalized slow slope
- log relative slope strength
- fast slope-sign run age
- slow slope-sign run age
- log run-age ratio

Both use:

- DecisionTreeClassifier
- max_depth=3
- min_samples_leaf=100
- balanced class weights
- no hyperparameter search

2018/2019/2020 are scored walk-forward with an 86-bar label purge.

## Lowpass result

LP2=S1 / LP3=S2.

Pooled 2018–2020:

- balanced accuracy: **58.43%**
- ordinary accuracy: **58.49%**
- C2_DOM recall: **60.90%**
- C3_DOM recall: **55.96%**
- mean regret: **66.78bp**
- q90 regret: **223.72bp**
- q95 regret: **316.18bp**
- selected mean net: **45.35bp**
- hindsight-oracle mean net: 112.13bp

Year balanced accuracy:

- 2018: **54.89%**
- 2019: **63.67%**
- 2020: **56.59%**

LP passes the preregistered >=52% requirement in all three years.

## Bandpass result

BP2=S1-S2 / BP3=S2-S3.

Pooled:

- balanced accuracy: **52.54%**
- ordinary accuracy: **52.59%**
- C2_DOM recall: **54.89%**
- C3_DOM recall: **50.20%**
- mean regret: **78.82bp**
- q90 regret: **249.13bp**
- q95 regret: **345.19bp**
- selected mean net: **33.31bp**
- hindsight-oracle mean net: 112.13bp

Year balanced accuracy:

- 2018: **51.69%**
- 2019: **53.43%**
- 2020: **53.30%**

BP reaches >=52% in two of three years.

## Paired LP-vs-BP result

Mean regret difference:

`regret_BP - regret_LP = +12.04bp`.

Positive favors LP.

20-trading-day block bootstrap, 2,000 repetitions:

95% interval:

`[+0.63bp, +22.67bp]`

The interval is strictly above zero.

LP relative mean-regret improvement over BP:

**15.27%**

Balanced-accuracy difference:

`BA_LP - BA_BP = +5.89 percentage points`.

Therefore LP satisfies every preregistered N1 retrospective-preference gate.

## Why BP is not discarded yet

BP is not marked N1_DOMINATED because:

- pooled balanced accuracy remains above 50%;
- two of three test years remain above 52%;
- N1 is deliberately retrospective and uses final morphology.

A causal carrier can change the relative ranking.

Therefore both representations proceed to the causal qualification race, with LP carrying the status:

`N1_RETROSPECTIVE_PREFERRED`.

## Interpretation

The result supports the user's concern that a trend strategy may ultimately benefit more from lowpass background than from isolated bandpass residuals.

At the retrospective upper-bound stage, LP contains substantially more usable information for deciding whether the market is in a C2_DOM/T0-rhythm state or a C3_DOM/C1-rhythm state.

This does not yet prove LP is the live solution.

## Evidence

Implementation SHA256:

`19a49767c5af0daaec00ae13b7808ba3a87573f7974be112cc38e61627c7d5cf`

OOF anchor ledger SHA256:

`9eb1726b2eafb915d9bf7c7a6220689b1e04a07491f017d6665b37b35af94896`

Execution result SHA256:

`27d466543962449394b52fbfd3ea96de086902de832cb919c2d66edcd5741b7c`

## Boundary

Consumed development evidence only.

Noncausal final-morphology features were used.

No fresh OOS, signal, paper/live, trade or production authority.
