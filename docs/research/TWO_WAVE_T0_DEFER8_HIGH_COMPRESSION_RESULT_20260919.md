# High C1-compression T0 defer-8 confirmation audit — result

Issue #540. Parent #537 / #507 / #493 / #450.

## Verdict

`C1_COMPRESSION_DEFER8_NOT_SUPPORTED`

High-risk group: frozen #507 B4+B5, N=356.

- deferred executed: 311 (87.36%)
- skipped inside 8-bar wait: 45 (12.64%)
- original mean net: +20.54bp
- defer-8 policy mean per signal: +19.16bp
- mean policy delta: **-1.38bp**
- block-bootstrap 95% CI: **[-6.31bp, +3.05bp]**

Skipped signals are exactly the fast-loss mechanism:

- original mean: **-58.15bp**
- win rate: 0%
- fast-loss rate: 100%
- median duration: 6 bars.

But delaying the 311 surviving signals costs too much:

- survivor original mean: +31.92bp
- delayed mean: +21.93bp
- delayed-minus-original: **-9.99bp**.

Year mean policy deltas:

- 2018: +1.01bp
- 2019: +1.01bp
- 2020: -6.07bp

Interpretation: compression identifies an early-failure hazard, but blanket 8-bar deferral sacrifices too much of the surviving trend. Do not tune the delay from this result.

Next question: within B4+B5, can the 8-bar early reversals be identified causally at the signal bar?

Evidence hashes:
- module: `34e0ee88e0ec415e94dee7b969c07470c2185dae4fdead781f8613e80bdf17b4`
- policy ledger: `4f851fa87d12d959678213aa1b1c2d8558f1da06903d1879f8c866addff48857`
- result: `83dc5db6433d2c0def1b36e72c409458cd34661df34ec90e1df92270414fc860`

No live/trade/production authority.