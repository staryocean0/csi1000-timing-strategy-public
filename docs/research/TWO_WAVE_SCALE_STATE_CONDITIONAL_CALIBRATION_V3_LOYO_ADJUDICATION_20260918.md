# Calibration v3 development LOYO adjudication — 2026-09-18

Issue #388 was source-frozen before this real development OOF. The same frozen 192 cases, five fixed confirmation lags, reference labels, calendar mapping and dominance-v1 control were used. No full-192 fit occurred.

v3 fixes the v2 abstention collapse: morphology ambiguity falls from roughly 175–179/192 under calibration v2 to only 0–2/192. At lag 0, 64/75 SUPPORTED references map to TURNING and 45/61 DEVELOPING references map to DEVELOPING, while NOT_DOMINANT recall returns to 18/24.

That improvement is not sufficient for readiness. The explicit AMBIGUOUS class collapses in the opposite direction: lag 0 retains only 1/13 true ambiguous references and every nonzero lag retains 0/13. The one-sided validity guard removes the large UNCERTAIN bucket but DATA_INVALID recall remains 7/19 with 8/173 false-invalid non-invalid cases at every lag. Thus v3 trades near-total abstention for near-total loss of the explicit ambiguity state.

No lag is selected or promoted from this consumed development population, even though lag 0 has the highest exact-state count (127/192). No full fit, label relaxation, case exceptions, PnL tuning, R4, routing or production authority is allowed.

The next gate is a threshold-free ambiguity and validity capacity audit on the already-frozen evidence before any v4 family is preregistered. This audit must determine whether AMBIGUOUS is representable by the existing evidence axes and whether validity weakness is primarily a rule-family limitation or an information limitation.
