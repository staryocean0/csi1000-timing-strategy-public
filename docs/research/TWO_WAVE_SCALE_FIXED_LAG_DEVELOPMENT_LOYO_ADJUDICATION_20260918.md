# Fixed-lag causal confirmation development LOYO adjudication — 2026-09-18

Issue #386 tested the preregistered fixed confirmation lags 0/5/10/15/25 observed trading minutes only after the raw five-lag family was formally measured label-blind in run 35292230400-1 and hash-frozen. Each lag then used the already-frozen calibration-v2 family in the same 2015–2020 leave-one-calendar-year-out development evaluation. No full-192 fit was performed.

The result does not support the hypothesis that confirmation delay alone resolves the v2 abstention collapse. Morphology ambiguity is 177/192 at lag 0 and remains between 175/192 and 179/192 at all delayed lags. Final AMBIGUOUS_MULTI_SCALE is 172/192 at lag 0 and 173/192 at every delayed lag. Exact final-state matches are 24/192 at lag 0 versus 23, 22, 23 and 22 at 5/10/15/25 minutes respectively.

Validity is essentially unchanged: DATA_INVALID_EDGE recall stays 7/19 and false invalid remains 8/173 at every lag; uncertain validity is 130/192 except 129/192 at 25 minutes. CURRENT_SCALE_NOT_DOMINANT recovery remains 0/24 at 0/5/10/25 minutes and only 1/24 at 15 minutes.

The structural diagnosis is stronger than the lag comparison itself. Across all 30 training folds (5 lags x 6 years), the frozen morphology calibration objective selected a band with zero wrong training decisions while abstaining on 99-111 supported/developing training cases per fold. The current lexicographic objective minimizes wrong decisions before rewarding coverage, so it systematically prefers very wide ambiguity bands. Longer causal confirmation does not repair that objective.

Therefore no lag is selected or promoted, no candidate is fit on all 192 panels, and no routing/PnL/production authority is granted. The next allowed research step is to preregister a coverage-constrained morphology calibration objective v3 and separately revisit the validity family before another development evaluation. Fresh independent OOS remains required for any readiness claim.

Public aggregate SHA256: a43e0adc1aedf02872a460e6594489777c4e2801f30f01f02f521deedf2779c0. Private panel-level OOF evidence remains Debian-controlled.
