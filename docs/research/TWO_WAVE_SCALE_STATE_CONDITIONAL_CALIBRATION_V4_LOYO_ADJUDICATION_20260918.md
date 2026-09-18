# Calibration v4 development LOYO adjudication — 2026-09-18

Issue #394 was evaluated only after source commit c736f61434d29f8f431a8abdcad9cf9d0dd720ed merged as cb4aa3204fc5361ccb87d3e595e2f24432d21775. The same frozen 192 cases, 0/5/10/15/25-minute raw family, frozen labels, calendar and dominance-v1 control were used. No full-192 fit was performed.

V4 preserves the v3 recovery of SUPPORTED/DEVELOPING morphology at lag0 (64/75 SUPPORTED→TURNING and 45/61 DEVELOPING→DEVELOPING), and dominance recovers 16/24 NOT_DOMINANT at lag0. However, explicit ambiguity remains weak and unstable: final AMBIGUOUS recall is at most 4/13 anywhere in the frozen lag family. The year-robust validity family reduces false INVALID to 4/173 but recalls only 5/19 DATA_INVALID cases.

Therefore v4 is not ready for full fitting, lag promotion, or any routing/trading authority. The next gate is a post-v4 error/capacity audit before any v5 family is preregistered. The audit must diagnose existing evidence; it may not relax labels, add case exceptions, tune PnL, or silently select a lag.
