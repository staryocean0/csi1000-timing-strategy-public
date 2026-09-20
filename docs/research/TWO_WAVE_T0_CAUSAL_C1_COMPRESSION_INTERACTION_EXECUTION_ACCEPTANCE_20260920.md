# T0 causal C1 × compression interaction — controlled execution acceptance

Issue #615.

Status: `CONTROLLED_EXECUTION_ACCEPTED`

Scientific verdict remains:

`T0_CAUSAL_C1_COMPRESSION_INTERACTION_NOT_SUPPORTED`

## Final governed run

- workflow: standard `public-compute.yml` / `workflow_dispatch` only
- profile: `two-wave-t0-causal-c1-compression-interaction-v1`
- public run: `35477767158`
- run identity: `35477767158-1`
- public source SHA: `55ae1f76c22db03c2e212913bcd07bdf30b5f5f8`
- private result branch: `runs/public-research/35477767158-1`
- private receipt: `research/public-runs/35477767158-1.json`
- receipt status: `passed`
- delivery: `archive_uploaded_and_verified`

The standard chain completed prepare → credential-free compute → independent verification → cleanup → private publish.
## Private readback verification

Private Release:

- release id: `392258972`
- tag: `public-research-run-35477767158-1`
- asset: `results.tar.gz`
- bytes: `41713`
- SHA256: `2701a47d8346ba218dae9610f3623999eb5da53b595c83c69f9cee3b73c79f8f`

The archive was downloaded back through the authenticated controller and independently rehashed.

Verified contained outputs:

- joined ledger SHA256: `3d16639e49994283a9f0027a94e5dcf9c9a1d26a66280efe3adb86da9873a45a`
- exact result SHA256: `6a7518075565cb7c027b900764e4846fa937e4ccf83a0739817420d860a7b73a`
- controller validation SHA256: `f3d6d3ed593bc6dcf2025db4368d45d1931f8c1a7959bb61da505d9a8efb30e2`
- compute receipt SHA256: `d82039dd3169eb42d4fae774d5458f8e8a2cf419b56b6df4b22dc995c01907df`

Independent validation reports `status=passed`, 945 verified rows, 37 verified 20-day blocks, and the same frozen negative verdict.
## Preserved failed attempt

The first governed attempt, run `35457551063` from public SHA `74809e1773e624bb1f66a5d577dceafe68e1d742`, failed at the pre-data synthetic-test gate because reviewed requirements omitted `pytest` and `scikit-learn`.

That run:

- did not reach private prepare;
- did not read the research data;
- did not start scientific compute;
- did not publish a private result.

PR #619 added only the missing fixed runtime dependencies. No research definition changed.

## Scientific consequence

The controlled run exactly reproduces the development result already recorded for #615. Therefore the negative result is accepted rather than rescued.

No C1-relation × compression router, veto or override is authorized. No B1..B5 boundary was moved and no post-result cell merge was introduced.

Development evidence only. No signal/router/trade/paper/live/production authority.
