# Issue #635 Model B P128 state-exit — controlled execution acceptance

Date: 2026-09-20.

Status: `CONTROLLED_EXECUTION_ACCEPTED__CANONICAL_REPLAY_BYTE_MATCHED`

Formal scientific verdict:

`MODEL_B_P128_STATE_EXIT_INCREMENT_NOT_SUPPORTED`

## First complete governed result

- workflow: standard `public-compute.yml` / `workflow_dispatch`
- profile: `two-wave-model-b-p128-state-exit-v1`
- public workflow run: `35500372173`
- run identity: `35500372173-1`
- public source SHA: `42c86adb5de9632b51d11ac1ed1ec9a0c835457b`
- private source ref: `2815f50b5a1b2925f0e0118b0af0d578605ee882`
- receipt status: `passed`
- delivery: `archive_uploaded_and_verified`
- independent verifier: PASS
- verified rows: 29,713
- verified blocks: 38
Private Release for the first complete run:

- release id: `392374589`
- tag: `public-research-run-35500372173-1`
- archive SHA256: `9d0b61bd9150d13a75c600dcfb24c5cc781a7966d70c2f85463a04ff52d85dbf`
- exact result SHA256: `4ef2a23577ef782c5622df1906dde794c11656614dbf0735855db30f213d5531`
- scored ledger SHA256: `eb9d1efca3e8327e5f8ba08b9e7d546c67da76d5e80595b6f314782a3863bbd1`
- controller validation SHA256: `79bb0fd02110cfdf8fe7a7440e4ed6db7523fd20a82797e4d07df316e98850b5`
- compute receipt SHA256: `d82039dd3169eb42d4fae774d5458f8e8a2cf419b56b6df4b22dc995c01907df`

The independent verifier reports `new_training=true` and `production_authority=false`.
The generic publisher receipt for this run incorrectly recorded `new_training=false`; PR #641 repairs only that metadata path and does not alter the scientific result bytes.

## Frozen scientific result

Pooled Model A versus Model B:

- A Brier: 0.216993686942
- B Brier: 0.217204110603
- A−B Brier gain: -0.000210423662
- relative Brier gain: -0.09697%
- A log-loss: 0.625007587553
- B log-loss: 0.625326059446
- A−B log-loss gain: -0.000318471893
20-trading-day block bootstrap:

- pooled Brier gain 95% CI: [-0.00080168, +0.00037942]
- pooled log-loss gain 95% CI: [-0.00163513, +0.00099600]
- CURRENT_UP Brier-gain CI crosses zero
- CURRENT_DOWN Brier-gain CI crosses zero

The support gate and complete causal audit both pass. The information gate fails because the P128 current context does not improve proper-scoring probability prediction after the frozen local baseline.

## Engineering history

Run `35499292209-1` is preserved as an engineering failure. The original #635 profile allowed 2400 seconds internally while the shared host watchdog remained 660/210 seconds. It was terminated before any exact result or scored ledger existed, so it is not a scientific negative.

After the bounded timeout repair, run `35500372173-1` produced the first complete scientific result.

PR #641 fixes the run-receipt `new_training` metadata and canonical replay `35500929714-1` completed successfully on the same frozen study.

Canonical replay:

- public source SHA: `3ada17b8cad87b98574866400bc7cbed404072a8`
- private receipt: passed / archive_uploaded_and_verified
- receipt `new_training=true`
- private Release id: `392382447`
- archive bytes: `2,635,538`
- archive SHA256: `db7bd62c2720f9619bf879a4320e23808eb15709cb88000ce2cfc733957c4fc1`
- exact result SHA256: `4ef2a23577ef782c5622df1906dde794c11656614dbf0735855db30f213d5531`
- scored ledger SHA256: `eb9d1efca3e8327e5f8ba08b9e7d546c67da76d5e80595b6f314782a3863bbd1`
- controller validation: passed, 29,713 rows / 38 blocks

The canonical exact result and scored ledger are byte-identical to the first complete run `35500372173-1`. The gzip archive bytes differ across runs, but every scientific output hash used for adjudication is identical.

## Architecture consequence

The P128 nearest-current-context candidate is closed. Per preregistration, this negative result does not automatically authorize P256, Model C, or any slower-context escalation.

Any future cross-frequency context requires a new independent, falsifiable hypothesis and a separately frozen stop rule.

## Authority

Information-layer result only. No economic intervention, signal, router, trade, paper, live, or production authority.

## Current-authority boundary

This acceptance makes #635 a controlled, privately read-backed scientific result. It does **not** by itself replace the private-root `CHAT_START.md` / `CLOUD_CURRENT.json` current research anchor. Under the current repository governance, that root authority remains Risk Tool 2.0 until a separate governed control-plane transition is explicitly approved and synchronized.

## Project current-authority boundary

This acceptance records a governed Two-Wave research result. It does not by itself promote Two-Wave #635 to project-level current authority.

Per repository governance, project current authority remains whatever the private root CHAT_START.md, CLOUD_CURRENT.json, and their referenced contracts define. This acceptance does not directly modify those private-root files and does not supersede their current Risk Tool anchor.
