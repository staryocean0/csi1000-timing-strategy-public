"""Synthetic-only math checks for the frozen R1_A Stage B protocol.

No market outcome is read or constructed here.
"""
from __future__ import annotations

import math
import numpy as np

HORIZONS = (1, 5, 15, 30, 60, 120, 240)
VALID_MIN = 0.995


def require(ok: bool, msg: str) -> None:
    if not ok:
        raise RuntimeError(msg)


def block_lengths(n_days: int) -> tuple[int, int, int]:
    require(n_days > 0, "no_days")
    base = int(math.ceil(n_days ** (1.0 / 3.0)))
    cap = max(1, n_days // 4)
    out = tuple(min(base * m, cap) for m in (1, 2, 4))
    require(len(set(out)) == 3, "collapsed_block_lengths")
    return out


def bootstrap(sums: np.ndarray, counts: np.ndarray, length: int, reps: int, seed: int):
    n_days, n_h = sums.shape
    require(counts.shape == sums.shape, "shape_mismatch")
    theta = sums.sum(0) / counts.sum(0)
    rng = np.random.default_rng(seed)
    estimates = np.full((reps, n_h), np.nan)
    offsets = np.arange(length)
    n_blocks = int(math.ceil(n_days / length))
    for r in range(reps):
        starts = rng.integers(0, n_days, size=n_blocks)
        idx = ((starts[:, None] + offsets) % n_days).reshape(-1)[:n_days]
        c = counts[idx].sum(0)
        if (c > 0).all():
            estimates[r] = sums[idx].sum(0) / c
    valid = np.isfinite(estimates).all(1)
    require(float(valid.mean()) >= VALID_MIN, "low_valid_fraction")
    est = estimates[valid]
    se = np.std(est, axis=0, ddof=1)
    require(np.isfinite(se).all() and (se > 0).all(), "bad_se")
    tmax = np.max(np.abs((est - theta) / se), axis=1)
    q = float(np.quantile(tmax, 0.95))
    require(np.isfinite(q) and q > 0, "bad_critical")
    return theta - q * se, theta + q * se


def main() -> None:
    require(block_lengths(1212) == (11, 22, 44), "block_rule_changed")
    rng = np.random.default_rng(20260914)
    n_days = 216
    n_h = len(HORIZONS)
    counts = rng.poisson(1.2, size=(n_days, 1)).repeat(n_h, axis=1)
    counts[0] = 1
    common = rng.normal(size=(n_days, 1))
    idio = rng.normal(scale=0.5, size=(n_days, n_h))
    sums = (common + idio) * np.maximum(counts, 1)
    lo1, hi1 = bootstrap(sums, counts, 6, 300, 77)
    lo2, hi2 = bootstrap(sums, counts, 6, 300, 77)
    require(np.allclose(lo1, lo2) and np.allclose(hi1, hi2), "nondeterministic")
    print("R1A_STAGEB_MATH_SELFTEST_PASS")


if __name__ == "__main__":
    main()
