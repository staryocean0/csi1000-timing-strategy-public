"""Feature-only Stage A audit for R1_A parent-continuation research.

No return target is constructed. No model is fitted. No horizon is selected.
The script verifies event-time feature availability, session-clock semantics,
prefix causality and deterministic feature hashes on the pinned public source.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import pathlib
import sys

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

SOURCE_COMMIT = "ab4979b224d8ee97f89b75ac428ddd71887fecf1"
VALID_YEARS = {2021, 2022, 2023, 2024, 2025}
FEATURES = (
    "parent_direction",
    "parent_move_log_size_at_confirmation",
    "parent_age_observed_bars_at_confirmation",
    "parent_average_log_speed",
    "pullback_log_size_at_confirmation",
    "pullback_to_parent_ratio",
    "confirmation_clock_sin",
    "confirmation_clock_cos",
    "realized_pre_event_vol_30",
    "realized_pre_event_vol_120",
    "vol30_missing",
    "vol120_missing",
)


def require(ok: bool, message: str) -> None:
    if not ok:
        raise RuntimeError(message)


def clock_ordinal(timestamp: str) -> int:
    clock = str(timestamp)[11:16]
    hh, mm = (int(x) for x in clock.split(":"))
    minute = hh * 60 + mm
    if 9 * 60 + 31 <= minute <= 11 * 60 + 30:
        return minute - (9 * 60 + 31)
    if 13 * 60 + 1 <= minute <= 15 * 60:
        return 120 + minute - (13 * 60 + 1)
    raise RuntimeError(f"clock_outside_frozen_session_labels:{clock}")


def rolling_vol(prices: np.ndarray, window: int) -> np.ndarray:
    ret = np.full(len(prices), np.nan, dtype=float)
    if len(prices) > 1:
        ret[1:] = np.diff(np.log(prices))
    out = np.full(len(prices), np.nan, dtype=float)
    for i in range(window, len(prices)):
        x = ret[i - window + 1 : i + 1]
        if len(x) == window and np.isfinite(x).all():
            out[i] = float(np.std(x, ddof=0))
    return out


def canonical_hash(frame: pd.DataFrame, columns: list[str]) -> str:
    payload = frame[columns].to_csv(
        index=False, float_format="%.15g", lineterminator="\n"
    ).encode()
    return hashlib.sha256(payload).hexdigest()


def load_tape(source: pathlib.Path) -> pd.DataFrame:
    data = source / "data" / "market" / "1m" / "000852.SH"
    frames = []
    for year in range(2015, 2026):
        path = data / f"{year}.parquet"
        require(path.is_file(), f"missing_partition:{year}")
        frames.append(
            pq.read_table(
                path,
                columns=["trading_day", "timestamp", "close", "data_contract"],
            ).to_pandas()
        )
    return pd.concat(frames, ignore_index=True)


def build_snapshots(tape: pd.DataFrame, core, freeze: dict) -> pd.DataFrame:
    prices = tape.close.to_numpy(float)
    days = tape.trading_day.astype(str).to_numpy()
    times = tape.timestamp.astype(str).to_numpy()
    thresholds = freeze["directional_change_thresholds"]
    lower_waves = core.detect_waves(prices, float(thresholds["S1"]))
    parent_waves = core.detect_waves(prices, float(thresholds["S2"]))
    lower_at: dict[int, list] = {}
    parent_at: dict[int, list] = {}
    for wave in lower_waves:
        lower_at.setdefault(int(wave.confirm_idx), []).append(wave)
    for wave in parent_waves:
        parent_at.setdefault(int(wave.confirm_idx), []).append(wave)

    vol30 = rolling_vol(prices, 30)
    vol120 = rolling_vol(prices, 120)
    known_parent: list = []
    rows: list[dict] = []
    active: dict | None = None

    for i, price in enumerate(prices):
        resolved_now = False
        if active is not None:
            sign = int(active["direction"])
            recovered = price >= active["recovery"] if sign > 0 else price <= active["recovery"]
            failed = price <= active["failure"] if sign > 0 else price >= active["failure"]
            censored = i >= int(active["confirm_idx"]) + 1200
            if recovered or failed or censored:
                active = None
                resolved_now = True

        known_parent.extend(parent_at.get(i, []))
        if active is not None or resolved_now:
            continue

        for lower in lower_at.get(i, []):
            if len(known_parent) < 2:
                continue
            w1, w2 = known_parent[-2], known_parent[-1]
            pf = core.parent_features(w1, w2, prices)
            if not pf or not np.isfinite(list(pf.values())).all():
                continue
            signed = float(pf["signed_drift"])
            direction = 1 if signed > 0 else -1 if signed < 0 else 0
            if direction == 0 or int(lower.direction) == direction:
                continue
            recovery = float(lower.start_price)
            failure = float(core.structural_boundary(w1, w2, direction))
            current = float(prices[i])
            valid = failure < current < recovery if direction > 0 else recovery < current < failure
            if not valid:
                continue

            parent_move = abs(math.log(float(w2.end_price) / float(w1.start_price)))
            pullback = abs(math.log(float(lower.end_price) / float(lower.start_price)))
            require(parent_move > 0 and math.isfinite(parent_move), "parent_move_unavailable")
            ordinal = clock_ordinal(times[i])
            angle = 2.0 * math.pi * ordinal / 240.0
            rows.append(
                {
                    "confirm_idx": int(i),
                    "day": str(days[i]),
                    "year": int(str(days[i])[:4]),
                    "parent_direction": int(direction),
                    "parent_move_log_size_at_confirmation": float(parent_move),
                    "parent_age_observed_bars_at_confirmation": int(i - int(w2.confirm_idx)),
                    "parent_average_log_speed": float(
                        parent_move / max(1, int(w2.end_idx) - int(w1.start_idx))
                    ),
                    "pullback_log_size_at_confirmation": float(pullback),
                    "pullback_to_parent_ratio": float(pullback / parent_move),
                    "confirmation_clock_sin": float(math.sin(angle)),
                    "confirmation_clock_cos": float(math.cos(angle)),
                    "realized_pre_event_vol_30": float(vol30[i]) if np.isfinite(vol30[i]) else np.nan,
                    "realized_pre_event_vol_120": float(vol120[i]) if np.isfinite(vol120[i]) else np.nan,
                    "vol30_missing": int(not np.isfinite(vol30[i])),
                    "vol120_missing": int(not np.isfinite(vol120[i])),
                }
            )
            active = {
                "confirm_idx": int(i),
                "direction": int(direction),
                "recovery": recovery,
                "failure": failure,
            }
            break

    frame = pd.DataFrame(rows).sort_values("confirm_idx").reset_index(drop=True)
    require(frame.confirm_idx.is_unique, "duplicate_event_confirmation")
    return frame


def session_audit(tape: pd.DataFrame) -> dict:
    require(tape.timestamp.is_unique, "duplicate_timestamp")
    require(np.isfinite(tape.close.to_numpy(float)).all(), "nonfinite_close")
    require((tape.close.to_numpy(float) > 0).all(), "nonpositive_close")
    contracts = sorted(set(tape.data_contract.astype(str)))
    require(contracts == ["cn_a_session_wall_clock_offset_v1"], "unexpected_data_contract")
    ordinals = np.array([clock_ordinal(x) for x in tape.timestamp.astype(str)], dtype=int)
    require(((ordinals >= 0) & (ordinals < 240)).all(), "invalid_clock_ordinal")
    sizes = tape.groupby("trading_day", sort=True).size()
    return {
        "rows": int(len(tape)),
        "trading_days": int(len(sizes)),
        "data_contract": contracts[0],
        "bars_per_day_distribution": {str(int(k)): int(v) for k, v in sizes.value_counts().sort_index().items()},
        "short_days": {str(k): int(v) for k, v in sizes[sizes < 240].items()},
        "clock_edges": {"09:31": 0, "11:30": 119, "13:01": 120, "15:00": 239},
        "pass": True,
    }


def availability(events: pd.DataFrame) -> dict:
    val = events.loc[events.year.isin(VALID_YEARS)].copy()
    out = {}
    for col in FEATURES:
        arr = val[col].to_numpy(float)
        missing = int((~np.isfinite(arr)).sum())
        out[col] = {
            "n": int(len(arr)),
            "missing": missing,
            "missing_fraction": float(missing / len(arr)) if len(arr) else 0.0,
        }
    non_vol = [c for c in FEATURES if c not in {"realized_pre_event_vol_30", "realized_pre_event_vol_120"}]
    require(sum(out[c]["missing"] for c in non_vol) == 0, "non_vol_feature_missing")
    return out


def prefix_audit(tape: pd.DataFrame, full: pd.DataFrame, core, freeze: dict) -> dict:
    days = tape.trading_day.astype(str).to_numpy()
    columns = ["confirm_idx", "year", *FEATURES]
    out = {}
    for year in range(2021, 2026):
        loc = np.flatnonzero(days <= f"{year}-12-31")
        require(len(loc) > 0, f"missing_prefix:{year}")
        cutoff = int(loc[-1])
        prefix_tape = tape.iloc[: cutoff + 1].reset_index(drop=True)
        observed = build_snapshots(prefix_tape, core, freeze)
        observed = observed.loc[observed.year.isin(VALID_YEARS), columns].reset_index(drop=True)
        expected = full.loc[(full.confirm_idx <= cutoff) & full.year.isin(VALID_YEARS), columns].reset_index(drop=True)
        require(len(observed) == len(expected), f"prefix_count_changed:{year}")
        require(canonical_hash(observed, columns) == canonical_hash(expected, columns), f"prefix_feature_changed:{year}")
        out[str(year)] = {
            "events": int(len(observed)),
            "feature_hash": canonical_hash(observed, columns),
            "pass": True,
        }
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=pathlib.Path, required=True)
    args = parser.parse_args()
    source = args.source.resolve()
    sys.path.insert(0, str(source))
    from research.index_price_validity import core

    freeze = json.loads(
        (source / "docs" / "governance" / "INDEX_PRICE_VALIDITY_FREEZE@1.0.json").read_text(encoding="utf-8")
    )
    tape = load_tape(source)
    session = session_audit(tape)
    events1 = build_snapshots(tape, core, freeze)
    events2 = build_snapshots(tape, core, freeze)
    columns = ["confirm_idx", "year", *FEATURES]
    hash1 = canonical_hash(events1, columns)
    hash2 = canonical_hash(events2, columns)
    require(hash1 == hash2, "determinism_feature_hash_failure")

    validation = events1.loc[events1.year.isin(VALID_YEARS)]
    require(len(validation) == 1296, f"validation_event_identity_mismatch:{len(validation)}")
    year_counts = validation.groupby("year", sort=True).size()
    require(year_counts.to_dict() == {2021: 186, 2022: 309, 2023: 178, 2024: 374, 2025: 249}, "validation_year_counts_mismatch")

    result = {
        "schema": "r1a_stagea_feature_only_audit_v1",
        "source_commit": SOURCE_COMMIT,
        "outcomes_read_for_scoring": False,
        "return_targets_constructed": False,
        "model_fitted": False,
        "horizon_selected": False,
        "production_authority": False,
        "session": session,
        "events": {
            "all_2015_2025": int(len(events1)),
            "validation_2021_2025": int(len(validation)),
            "validation_by_year": {str(int(k)): int(v) for k, v in year_counts.items()},
        },
        "feature_availability": availability(events1),
        "determinism": {"run1_hash": hash1, "run2_hash": hash2, "pass": True},
        "prefix_causality": prefix_audit(tape, events1, core, freeze),
        "status": "FEATURE_ONLY_GATES_PASS",
    }
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
