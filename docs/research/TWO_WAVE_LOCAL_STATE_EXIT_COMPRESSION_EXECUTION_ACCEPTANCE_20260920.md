# Issue #624 local state-exit compression — controlled execution acceptance

Date: 2026-09-20.

Status: `CONTROLLED_EXECUTION_ACCEPTED__BYTE_REPRODUCIBLE`

Formal scientific verdict:

`LOCAL_COMPRESSION_STATE_EXIT_HAZARD_NOT_SUPPORTED`

## Final governed run

- workflow: standard `public-compute.yml` / `workflow_dispatch`
- profile: `two-wave-local-state-exit-compression-v1`
- public workflow run: `35488698309`
- run identity: `35488698309-1`
- public source SHA: `828a64c763ba1e4f08b126a3766e54bb73a8e4d8`
- private source ref: `22ab2e181407fb1d0a9a71e61d880819fe1baec8`
- private result branch: `runs/public-research/35488698309-1`
- private receipt: `research/public-runs/35488698309-1.json`
- receipt status: `passed`
- delivery: `archive_uploaded_and_verified`

## Private readback

Private Release:

- release id: `392309871`
- tag: `public-research-run-35488698309-1`
- asset: `results.tar.gz`
- bytes: `2,059,472`
- archive SHA256: `73141f57accfd02aa4607ebcd93843fed0b42905e5c06733671c5a010913f7c8`

Readback hashes:

- exact result SHA256:
  `0760393f9a27b4a7db2ad65a931e449c68ca71c2aeba7a657867d9929743519b`
- scored ledger SHA256:
  `c1ef13cfc3b2bc5669955ff62a5200b6c56c6868b459421d7e621e5ed189f46f`
- controller validation SHA256:
  `863b5c7ded34291f995e3e96ebad6ff108c9b13164d598fff72bb71ca2fd99ec`
- compute receipt SHA256:
  `d82039dd3169eb42d4fae774d5458f8e8a2cf419b56b6df4b22dc995c01907df`

These exact-result and ledger hashes match the frozen local reviewed Python 3.11 replay byte-for-byte.

Independent validation:

- status: `passed`
- verified rows: `29,713`
- verified blocks: `38`
- new training: false
- production authority: false

## Scientific result

Support was ample and the pooled local-only effect was large:

- B1 structural EXIT_NEXT8: 29.11%
- B5 structural EXIT_NEXT8: 40.52%
- B5−B1: +11.40pp
- 95% block-bootstrap CI: [+8.16pp, +14.49pp]
- B5/B1: 1.392x
- pooled band-rate Spearman: 1.00
- B5>B1 in 3/3 test years
- positive B5−B1 in 8/8 overlap cohorts

But the frozen universal gate failed on two conditions:

1. pooled continuous-score AUC = 0.5469 < 0.55;
2. CURRENT_UP B5−B1 = +3.96pp with 95% CI [-1.27pp, +9.45pp].

CURRENT_DOWN was much stronger:

- B5−B1 = +17.16pp
- 95% CI [+13.17pp, +21.44pp]
- AUC = 0.5687
- band-rate Spearman = 1.00

Therefore:

> local same-frequency compression/exhaustion contains real causal state-survival information, but one symmetric local-only rule is not supported as a universal replacement for cross-frequency context.

## Reproducibility history

Three governed executions are preserved:

1. `35487560301` — full-precision CSV; scientific result matched; byte serialization non-canonical.
2. `35488173033` — 11-significant-digit CSV; scientific result matched; one remaining last-bit serialized `rv_8` cell differed.
3. `35488698309` — 10-significant-digit canonical evidence; private readback matches local replay byte-for-byte.

The first two runs are not scientific failures. They are immutable engineering evidence explaining why canonical evidence serialization was introduced.

## Architecture consequence

This closes the first third-generation Local-only information gate.

It does **not** justify returning to recursive future prediction.

The next allowed architecture comparison is:

> the same frozen state-exit target, with other frequencies used only as currently observable causal context, tested for incremental value over the Local-only baseline.

No `future(C1) → future(C2) → ...` chain is permitted.

## Authority

Development/mechanism evidence only.

No signal/router/trade/paper/live/production authority.
