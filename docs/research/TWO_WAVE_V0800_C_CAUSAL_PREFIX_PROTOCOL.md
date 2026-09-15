# Two-Wave v0.8.0 — V0800-C causal prefix replay

Status: preregistered Development diagnostic. This protocol grants no morphology, direction, trade, or production authority.

## Purpose

V0800-B established the duration/same-scale map under the already-consumed 2015–2020 CSI1000 5m Development material. V0800-C does **not** choose a `rho` and does not inspect returns. It tests the more basic claim required by the user: stand at the currently confirmed wave and search only backward through information already available at that time.

## Frozen input

- instrument: `000852.SH`
- view: `5m_offset_0`
- source repository: `staryocean0/factorlab-two-wave-strategy-lab`
- source ref: `152ae1ef11a04bb3b434da25025794db7a706c81`
- file: `data/development/5m_offset_0.parquet`
- bytes: `3351411`
- sha256: `bea21fa9dd9532e21605511e07561b33d5569f86f69f5a487507531593b14c48`
- allowed interval: 2015-01-05 through 2020-12-31
- fresh OOS: false

No 2021+ row may be read.

## Frozen morphology kernel

V0800-C reuses the exact v0.8.0 A-wave object and the frozen v0.4.3 temporal-maturity pivot timing used in V0800-B:

- A-wave: `low -> high -> low`
- `min_leg = 4`
- `max_unfinished_leg = 48`
- wave publication occurs only at terminal-low confirmation
- candidate `rho` values remain exactly `{1.25, 4/3, sqrt(2), 1.5}`
- same-scale relation remains `max(d_prev,d_cur)/min(d_prev,d_cur) <= rho`
- predecessor remains the nearest earlier eligible same-scale A-wave in the same epoch with `previous.end_bar <= current.start_bar`.

No `rho` winner may be installed by this experiment.

## Causal ledger

For every causally published A-wave and every frozen `rho`, construct a pair record only from waves already published before the current wave. A pair record stores identity and timing only; it contains no future return, PnL, position, cost, or execution field.

Every record must satisfy:

1. `current.end_bar <= current.confirmation_bar`;
2. predecessor was already confirmed no later than the current publication;
3. `previous.end_bar <= current.start_bar`;
4. predecessor belongs to the same epoch;
5. predecessor satisfies the same-scale relation;
6. no nearer earlier same-scale predecessor was skipped.

## Frozen prefix checkpoints

The experiment replays the stream from the beginning using only each prefix. Checkpoint rows are the union of:

1. every 4096th row count: `4096, 8192, ...` below the full row count;
2. the last available row count of each calendar year 2015–2020;
3. the row immediately after every 256th full-stream A-wave confirmation (`wave ordinal 0, 256, 512, ...`), plus the final A-wave confirmation;
4. the full row count.

The event checkpoint rule depends only on the causal morphology ledger, never on an economic outcome or future return.

Duplicates are removed and checkpoints are sorted.

## Exact replay requirement

At each prefix length `L`:

- rerun the frozen detector from bar 0 through bar `L-1`;
- canonicalize all waves published by that prefix;
- canonicalize all same-scale pair records published by that prefix;
- compare them with the full-run ledgers filtered to `confirmation_bar < L`.

Both canonical ledgers must match exactly. A future suffix is therefore forbidden from changing any identity, timing, predecessor choice, duration, epoch, or same-scale pair that had already been published.

## Acceptance

V0800-C passes only if all of the following are zero across every frozen checkpoint and the full ledger:

- future-reference violations;
- predecessor-after-current violations;
- nearer-eligible-predecessor skip violations;
- wave prefix mismatches;
- pair prefix mismatches;
- ledger-hash mismatches.

All checkpoints must pass. Any nonzero count is a causal failure and blocks V0800-D.

## Outputs

Private run archive:

- `CHECKPOINT_AUDIT.csv`
- `LEDGER_HASHES.json`
- `SUMMARY.json`
- `INPUT_RECEIPT.json`

Only bounded aggregate `SUMMARY.json` and `INPUT_RECEIPT.json` may be mirrored as text to the private run branch. No public artifact/cache is authorized.

## Non-scope

- no direction grid yet;
- no `rho` selection;
- no amplitude gate;
- no return, PnL, buy/sell, position, cost, execution, paper trading, or production authority;
- no fresh-OOS claim.

A successful V0800-C only establishes that the current-first/backward same-scale semantics are causally replayable. V0800-D remains a separate preregistered direction diagnostic.
