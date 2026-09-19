# Causal C1 relation × compression-risk interaction on T0 outcomes — result

Issue #571. Parent #507 / #493 / #450.

## Verdict

`C1_COMPRESSION_T0_INTERACTION_NOT_SUPPORTED`

The accepted causal compression score ranks future-8 C1 turn risk, but its interaction with the then-known causal C1 relation does not stably explain T0 own-lifecycle outcome.

## Universe

Authoritative #507 v2 scored T0 signal bars:

- 945 rows
- joined T0 closed trades: 945
- causal C1 resolved: 945
- coverage: 100%

No score, risk band or C1 carrier parameter was retuned.

## Frozen 2×5 grid

Mean T0 net bp:

| causal C1 relation | B1 | B2 | B3 | B4 | B5 |
| --- | ---: | ---: | ---: | ---: | ---: |
| ALIGNED | +38.74 | +25.23 | +23.92 | +11.75 | +10.13 |
| OPPOSED | +14.32 | +30.02 | +19.37 | +33.30 | +17.06 |

Pooled point contrasts:

- ALIGNED B5−B1: **−28.61bp**
- OPPOSED B5−B1: **+2.74bp**
- interaction = OPPOSED delta − ALIGNED delta: **+31.35bp**

The pooled point pattern matches the preregistered structural hypothesis.

## Bootstrap

20-trading-day calendar blocks, 5,000 resamples:

ALIGNED Delta_A:
- median −22.92bp
- 95% CI **[−129.99bp, +43.88bp]**

OPPOSED Delta_O:
- median +2.39bp
- 95% CI **[−44.07bp, +44.16bp]**

Interaction:
- median +27.26bp
- 95% CI **[−59.69bp, +136.78bp]**

The interaction interval crosses zero widely.

## Year stability

2018:
- ALIGNED B5−B1 = **+44.59bp** (opposite expected sign)
- OPPOSED B5−B1 = **−70.62bp** (opposite expected sign)

2019:
- ALIGNED −68.35bp
- OPPOSED +19.10bp

2020:
- ALIGNED −72.41bp
- OPPOSED +43.79bp

Thus 2/3 years match the hypothesis, but 2018 reverses both legs.

## Scientific interpretation

The compression score is accepted as a **C1 turn-risk ranker**.

This audit shows that the turn-risk score is **not yet a stable T0 PnL gate** when conditioned only on the then-known causal C1 leg relation.

Therefore do not promote:

> high compression × causal C1 relation -> T0 veto/permission

as an execution rule.

The next research question should separate two tasks:

1. turn probability — already supported by compression risk;
2. turn direction — must be recovered causally.

A candidate directional clue already exists from #485:
among actual C1-turn events, the future turn direction equals `-sign(ret_8)` about 66.2% of the time.

This should be tested directly rather than rescuing the failed PnL interaction.

## Evidence

- module SHA256: `d4abd95e4a81d5074a4e37cd695e054ccccb48c4b2a78bfece0e726bfc83393d`
- interaction ledger SHA256: `ca860603c71ddadcb650f4ff88ec7f10724b43bb40f485ed57071e09f677280a`
- exact result SHA256: `1b4dc25d8efbe3a68bb704ac0d3fe576ed7895f54a3e9a57daae69e8b7438480`

## Authority

Development evidence only.

No signal/router/trade/paper/live/production authority.
