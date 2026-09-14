# Overnight continuous driver tail-likelihood DEV execution

This execution implements the already-merged result-free preregistration `overnight_continuous_driver_tail_likelihood_v1` without changing its scientific parameters.

The only development data source is private materialization run `34837972995-1`, release `public-research-run-34837972995-1`, asset `results.tar.gz`, SHA256 `e1c716fc33fb0b5e50aabff0362f2de8d7bf94aff12ab83a715ea4dfb9384b06`.

Only 2015-2020 factor-panel and driver-carrier files are exposed to compute. 2021-2025 row-level material remains unavailable. Opening-clock files are not exposed to this identity.

The compute container is credential-free and network-isolated. A separate trusted validator recomputes the full development result before private writeback.

`new_training=true`; `production_authority=false`. No reusable BLACKBOX query is authorized by this execution.
