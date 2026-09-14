# Overnight Official Snapshot Inventory P0

Date: 2026-09-14

## Purpose

This is a non-outcome-bearing infrastructure inventory for the CSI1000 timing project's officially imported Overnight/Open context. It exists only to determine whether the already-published private handoff bundle contains the exact data carriers needed for a future independently motivated Overnight research identity.

Official imported context root:

`runtime/research/cloud_imports/overnight_open_context/d113b42dca967bb1061c8a6115c5d934e5a41074/`

Canonical imported authority at review time: `overnight_open_current_authority@1.34`, `active_research=null`, reusable BLACKBOX query count 12.

## Governance boundary

- This P0 is **not** a successor study and creates no active outcome-bearing identity.
- It does not alter, rescue, reinterpret, or decompose any completed external or imported Overnight result.
- The external `factorlab-overnight-open-lab` repository is historical/source evidence only and is not a CSI1000 control plane.
- ChatGPT modifies only the public repository. Private reads and any result writeback occur only through the reviewed public broker workflow.
- 2021-2025 remains reusable BLACKBOX material. This inventory must not expose, extract, inspect, summarize, or compute any market row from that window.
- Production authority remains false.

## Frozen transport

Reuse the existing immutable private handoff transport profile `handoff-verify-v1` and its published Release asset. The broker must verify the fixed asset parts, combined asset digest, inner `bundle.tar` digest, and private manifest before compute.

## Allowed computation

The compute program may open only the tar container metadata necessary to read `BUNDLE_MANIFEST.json`. It may not call `extract`, `extractall`, or `extractfile` on any member other than `BUNDLE_MANIFEST.json`.

For each manifest member whose path matches an approved Overnight-related prefix/token, the output may contain only:

- member path;
- declared byte size;
- declared SHA256;
- a deterministic present/absent flag for required carrier families.

Approved inventory targets:

1. `runtime/research/cloud_imports/overnight_open_context/`
2. `data/runtime_text_2015_2025/`
3. `data/driver_runtime_text_2015_2020/`
4. `data/development/`
5. `data/high_open_dev_2015_2025/`
6. `data/v6a_external_sources_2015_2025/`
7. filenames/tokens containing `overnight`, `opening_clocks`, `factor_panel`, `driver_external`, `high_open`, or `v6a`.

The inventory may also report bundle-level `file_count` and declared total bytes. It must not report any row count, date/event value, target statistic, factor value, score, return, probability, label distribution, or model result.

## Required-carrier decision

P0 reports whether the bundle contains enough material to reconstruct a 2015-2020 causal pre-open development panel with, at minimum:

- CSI1000 opening-gap target/clock carrier;
- `rvol20` or an exact frozen source from which it can be reconstructed;
- B1 global-risk source coordinate inputs or frozen coordinate carrier;
- B2 China-offshore source coordinate inputs or frozen coordinate carrier;
- B4 driver-coherence source coordinate inputs or frozen coordinate carrier.

Each family is `PRESENT`, `ABSENT`, or `AMBIGUOUS_FROM_NAMES_ONLY`. P0 does not inspect data values to resolve ambiguity.

## Exit rule

- If all required families are `PRESENT`, the next step is to freeze a new, non-rescue probabilistic tail-likelihood identity and a separate outcome-bearing profile.
- If any required family is `ABSENT` or `AMBIGUOUS_FROM_NAMES_ONLY`, do **not** infer or proxy it. First create a deterministic private data-carrier materialization task through the approved two-repository workflow.

No outcome-bearing research is authorized by this document.