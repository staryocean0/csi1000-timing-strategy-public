# Fixed-lag causal confirmation source registration — 2026-09-18

Issue #386 under #381/#376/#353.

The target occurrence remains the frozen anchor. Knowledge time may move by 0/1/2/3/5 graphical 5-minute phase bars (0/5/10/15/25 observed trading minutes). Candidate jumps and turns remain constrained to relative minute <= 0; the suffix may confirm or reject an occurrence-time hypothesis but may not retarget the event into the suffix.

This source checkpoint is label-blind and threshold-free. It does not inspect lag×label performance, select a preferred lag, fit all 192 cases, use outcomes/PnL, or grant routing/trading/production authority. Lag 0 must reproduce diagnostic-family-v2 source semantics exactly in the same runtime; the frozen v2 raw SHA remains lineage identity, while independent cross-platform floating comparisons use the pre-existing 2e-10 verifier tolerance.

After reviewed merge, the only allowed next step is one genuine standard workflow_dispatch for the fixed-lag measurement profile. All five raw lag outputs must be hash-frozen before the Debian-controlled label join and development-only LOYO comparison.
