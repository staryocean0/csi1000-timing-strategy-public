# #345 execution-boundary review, before the formal audit

This extends the historical source checkpoint merged in #346. That checkpoint remains
unchanged as a record of what existed then; it is not a statement that execution can
never be implemented. No prior rejected request is treated as proof of a particular
keyword problem, and a successful write is not treated as independent correctness.

## Concrete closure added

The no-argument entry accepts exactly the frozen input file at
`/work/inputs/5m_offset_0.parquet`, and only a fresh `/results/study` output.
The original loader enforces byte count, SHA256, Development dates, row count and OHLC
validity. No argument selects a URL, a different file, a command or another repository.

The separate file contract allows only report/manifest, events, latency, compressed
trace, original parent report/manifest, and the fixed visual index/case filename form.
It rejects unknown paths, directory traversal, symbolic links (including parents),
extra files/directories and overwrite. JSON rejects duplicate keys and nonfinite values.
Trace ceilings are 70,114 rows, 128 MiB uncompressed, 16 MiB compressed, 8,192 bytes per
line. All files together are bounded at 64 MiB; each figure remains <=250,000 bytes.
The manifest checks the exact file set, sizes and hashes; hashes alone are not acceptance.

The file-level verifier independently replays every saved pre/post state and event,
checks wick geometry, exact 92-bar coverage subset, residual partitions, reset predicates
and every final-low latency identity. It additionally reproduces the summary, checks
all original visual bytes, and checks the frozen parent report/index hashes on the real
carrier. Prefix tests include eight whole-history cutoffs and both sides of every reset.
Jointly altering a report and its producer helper cannot conceal wrong reset labels;
this is covered by a separate independent-predicate counterexample.

The new runtime binds two fixed no-argument Python commands, with the existing 900-second
compute and verifier bounds, credential-free environment and network isolation.
The broker is derived from the existing R3 broker with fixed profile/source/command
bindings only. Archive and mirrored-report paths and private repository remain unchanged;
row-level trace is never a public artifact. There is no added publication endpoint,
arbitrary shell input or extra credential-bearing step.

## History and registration

All 19 source/protocol identities in the #346 catalogue are preserved. A separate
23-file execution manifest adds the file contract, fixed entry, verifier and runtime.
Registration appends exactly one option, two conditions, four phase branches and one
controller title/case. Historical tests first strip this exact addition, then verify
their unchanged older hashes. No historical hash is rebound to make a test pass.

## Pre-run status

70 dedicated synthetic/source tests passed locally without skips. Full public regression
and latest-head Ubuntu CI must pass before a reviewed merge. Only then may a unique
controller request dispatch the real audit. No formal #345 result is claimed here.
The four-case population, parent R3 failure, 4/48 rules, all #321 thresholds, original
33 OHLC pages and diagnostic-only short/low definition remain frozen. No R4 is selected;
no 1m, PnL, router, trade, direct Chat private write or project CLOUD_CURRENT change.
