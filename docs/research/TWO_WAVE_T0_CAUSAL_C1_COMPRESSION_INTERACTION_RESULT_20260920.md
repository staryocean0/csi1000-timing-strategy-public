# T0 causal C1-relation × compression-risk interaction — result

Issue #615. Parent #507 / #609 / #450.

## Verdict

`T0_CAUSAL_C1_COMPRESSION_INTERACTION_NOT_SUPPORTED`

The preregistered support gate passed, but all three bootstrap confidence-interval gates failed. No band, score, cell definition, or threshold was changed after seeing outcomes.

## Frozen inputs

- Development data: 000852.SH, native 5m, 2015–2020, 70,114 rows.
- Data SHA256: `bea21fa9dd9532e21605511e07561b33d5569f86f69f5a487507531593b14c48`.
- Authoritative #507 version: v2.
- #507 exact module SHA256: `7c386d7ce6b5b41a8df297aecf74488d806dcb20c09c852aab566f424602478c`.
- #507 scored ledger SHA256: `6fb773743cad9f009b62b973888b63db385459bd6e5db9524046e0b7958d8b33`.
- Scored T0 signals: 945.
## Causal qualification and support

The #507 universe was reconstructed from the frozen data and exact module. Row count, base turn rate, B1/B5 rates, and AUC matched the authoritative v2 receipt.

Causal C1 relation uses the then-known stage1 `causal_state` leg relative to the T0 side.

Coverage: **945 / 945 = 100%**.

Primary cells all passed the preregistered minimum of 50 trades and 15 calendar blocks:

| Cell | Trades | 20-day blocks |
| --- | ---: | ---: |
| ALIGNED × LOW (B1+B2) | 114 | 33 |
| ALIGNED × HIGH (B4+B5) | 125 | 35 |
| OPPOSED × LOW (B1+B2) | 246 | 36 |
| OPPOSED × HIGH (B4+B5) | 231 | 37 |

Prefix replay passed at cuts 10k / 30k / 50k / 65k. At 50k, 383 scored signals were checked; at 65k, 800 were checked. State mismatches: **0**.
## Primary estimands

Mean T0 net outcome:

| Causal C1 relation | LOW mean | HIGH mean | HIGH − LOW |
| --- | ---: | ---: | ---: |
| ALIGNED | +30.21 bp | +10.84 bp | **−19.36 bp** |
| OPPOSED | +23.64 bp | +25.78 bp | **+2.14 bp** |

Difference-in-differences:

**+21.51 bp**

The point estimates therefore have the hypothesized sign, but point estimates were not the preregistered acceptance criterion.

## Block bootstrap

20-trading-day calendar blocks, 5,000 resamples, seed 20260919:

- ALIGNED HIGH−LOW 95% CI: **[−64.33, +22.31] bp**
- OPPOSED HIGH−LOW 95% CI: **[−23.28, +27.53] bp**
- DID 95% CI: **[−28.60, +72.21] bp**

All three intervals cross zero.
## Year stability

ALIGNED HIGH−LOW:

- 2018: −7.71 bp
- 2019: +3.83 bp
- 2020: −51.28 bp

Negative in 2/3 years: **PASS**.

OPPOSED HIGH−LOW:

- 2018: −28.05 bp
- 2019: +19.65 bp
- 2020: +11.99 bp

Positive in 2/3 years: **PASS**.

The year-sign gates pass, but they cannot override failed bootstrap gates.

## Frozen gate adjudication

1. ALIGNED delta upper CI < 0: **FAIL**
2. OPPOSED delta lower CI > 0: **FAIL**
3. DID lower CI > 0: **FAIL**
4. ALIGNED delta negative in at least 2/3 years: **PASS**
5. OPPOSED delta positive in at least 2/3 years: **PASS**
## Interpretation

The causal C1 relation and the causal compression-risk score do not form a sufficiently stable economic interaction under the frozen #615 specification.

The data are compatible with an ALIGNED fragility effect in point estimates, but uncertainty is too wide. The OPPOSED “compression means the opposition is about to fail” effect is especially weak in pooled magnitude.

Therefore:

- do not create a C1-relation × compression router;
- do not turn HIGH compression into a causal C1 override;
- do not move B1..B5 boundaries;
- do not merge cells differently after outcomes;
- preserve compression as a causal C1 turn-risk / T0 fast-loss fragility indicator, not as a validated interaction policy.

## Reproducibility receipts

- #615 exact module SHA256: `958a77bf2cc9b3fd35bdb8c383d00a464e6b906e357bc64a955ff43e330cc08f`
- joined ledger SHA256: `3d16639e49994283a9f0027a94e5dcf9c9a1d26a66280efe3adb86da9873a45a`
- exact result SHA256: `6a7518075565cb7c027b900764e4846fa937e4ccf83a0739817420d860a7b73a`

Development evidence only. No signal/router/trade/paper/live/production authority.
