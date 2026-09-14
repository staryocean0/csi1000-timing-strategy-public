"""Feature-only Stage A audit for R1_A parent-continuation research.

No return target is constructed. No model is fitted. No horizon is selected.
The script verifies pinned-source integrity, event-time feature availability,
session-clock semantics, prefix causality and deterministic feature hashes.

Scientific authority:
Private SoT docs/research/R1A_PARENT_CONTINUATION_STAGEA_FREEZE_20260914.*
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
EXPECTED_EVENT_COUNTS = {
    2015: 645,
    2016: 326,
    2017: 96,
    2018: 209,
    2019: 201,
    2020: 276,
    2021: 186,
    2022: 309,
    2023: 178,
    2024: 374,
    2025: 249,
}
EXPECTED_SHORT_DAYS = {
    "2016-01-04": 143,
    "2016-01-07": 18,
}
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
    "realized_pre_event_vol_30_missing",
    "realized_pre_event_vol_120_missing",
)

# Git blob ids pinned from SOURCE_COMMIT. This validates exact source/data bytes
# without requiring credentials, a private checkout or arbitrary shell execution.
EXPECTED_BLOBS = {
    "research/index_price_validity/core.py": "a03bb31ea7f9f883187e6ad26e53df8ad86f4285",
    "docs/governance/INDEX_PRICE_VALIDITY_FREEZE@1.0.json": "9a3d24da0a1d829d2d604219dedf72a1d49a7a18",
    "data/market/1m/000852.SH/2015.parquet": "b09f15c5afbbaf213a9b5931ef6957dfb9bbea39",
    "data/market/1m/000852.SH/2016.parquet": "d6bd6ed71aa7bf5b96574f7537dc10f2c6a17cae",
    "data/market/1m/000852.SH/2017.parquet": "95e51f7b6e155e7cc0d91f550641ffdcaeba4bc2",
    "data/market/1m/000852.SH/2018.parquet": "730206f92ac798a127f663c9f3a4d31ce6b695b2",
    "data/market/1m/000852.SH/2019.parquet": "6596c51009bdb80e7fc50f3cd6c412c325110f04",
    "data/market/1m/000852.SH/2020.parquet": "25b7ebb894b8e27b7b8692aeffff613a170c6f1b",
    "data/market/1m/000852.SH/2021.parquet": "a1b9327fcdc9939269ded4349364277848b8480c",
    "data/market/1m/000852.SH/2022.parquet": "f5e699ddbe7fe26dc8e977bb8c72bad9ff83beef",
    "data/market/1m/000852.SH/2023.parquet": "a915cc9a0e9259e2660558c07ffbe1d6c37c0e8f",
    "data/market/1m/000852.SH/2024.parquet": "0866817a015bbcce3f9085f3f67a855cb09f3594",
    "data/market/1m/000852.SH/2025.parquet": "abe4751cdd086b40f0055dc850f59fca2892ecbd",
}


def require(ok: bool, message: str) -> None:
    if not ok:
        raise RuntimeError(message)


def git_blob_sha(path: pathlib.Path) -> str:
    payload = path.read_bytes()
    header = f"blob {len(payload)}\0".encode()
    return hashlib.sha1(header + payload).hexdigest()


def source_integrity_audit(source: pathlib.Path) -> dict:
    observed: dict[str, str] = {}
    for rel, expected in EXPECTED_BLOBS.items():
        path = source / rel
        require(path.is_file(), f"missing_pinned_source:{rel}")
        actual = git_blob_sha(path)
        require(actual == expected, f"pinned_blob_mismatch:{rel}:{actual}")
        observed[rel] = actual
    return {
        "source_commit": SOURCE_COMMIT,
        "verified_git_blobs": observed,
        "pass": True,
    }


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
    # Same frozen statistic as the scalar implementation: population SD of the
    # last ``window`` observed one-bar log returns ending at each bar.
    return (
        pd.Series(ret, dtype=float)
        .rolling(window=window, min_periods=window)
        .std(ddof=0)
        .to_numpy(float)
    )


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
    tape = pd.concat(frames, ignore_index=True)
    require(
        tape.trading_day.astype(str).str[:4].astype(int).drop_duplicates().tolist()
        == list(range(2015, 2026)),
        "unexpected_year_partition_order",
    )
    return tape


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
            parent_age = int(i - int(w2.confirm_idx))
            require(parent_age >= 0, "negative_parent_age")
            ordinal = clock_ordinal(times[i])
            angle = 2.0 * math.pi * ordinal / 240.0
            rows.append(
                {
                    "confirm_idx": int(i),
                    "day": str(days[i]),
                    "year": int(str(days[i])[:4]),
                    "parent_direction": int(direction),
                    "parent_move_log_size_at_confirmation": float(parent_move),
                    "parent_age_observed_bars_at_confirmation": parent_age,
                    # Private Stage A freeze: speed = parent_move / max(parent_age, 1).
                    "parent_average_log_speed": float(parent_move / max(1, parent_age)),
                    "pullback_log_size_at_confirmation": float(pullback),
                    "pullback_to_parent_ratio": float(pullback / parent_move),
                    "confirmation_clock_sin": float(math.sin(angle)),
                    "confirmation_clock_cos": float(math.cos(angle)),
                    "realized_pre_event_vol_30": float(vol30[i]) if np.isfinite(vol30[i]) else np.nan,
                    "realized_pre_event_vol_120": float(vol120[i]) if np.isfinite(vol120[i]) else np.nan,
                    "realized_pre_event_vol_30_missing": int(not np.isfinite(vol30[i])),
                    "realized_pre_event_vol_120_missing": int(not np.isfinite(vol120[i])),
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
    timestamp_strings = tape.timestamp.astype(str)
    require(timestamp_strings.is_unique, "duplicate_timestamp")
    require(timestamp_strings.is_monotonic_increasing, "timestamp_not_monotonic")
    require(np.isfinite(tape.close.to_numpy(float)).all(), "nonfinite_close")
    require((tape.close.to_numpy(float) > 0).all(), "nonpositive_close")
    contracts = sorted(set(tape.data_contract.astype(str)))
    require(contracts == ["cn_a_session_wall_clock_offset_v1"], "unexpected_data_contract")

    sizes = tape.groupby("trading_day", sort=True).size()
    short_days = {str(k): int(v) for k, v in sizes[sizes < 240].items()}
    require(short_days == EXPECTED_SHORT_DAYS, f"short_day_identity_mismatch:{short_days}")
    require((sizes <= 240).all(), "more_than_240_observed_bars_in_day")

    normal_days = 0
    for day, block in tape.groupby("trading_day", sort=True):
        ordinals = np.array([clock_ordinal(x) for x in block.timestamp.astype(str)], dtype=int)
        require(((ordinals >= 0) & (ordinals < 240)).all(), f"invalid_clock_ordinal:{day}")
        require(np.all(np.diff(ordinals) > 0), f"non_increasing_intraday_clock:{day}")
        if len(block) == 240:
            require(np.array_equal(ordinals, np.arange(240)), f"normal_day_missing_bar:{day}")
            normal_days += 1
        else:
            require(ordinals[0] == 0, f"short_day_bad_open:{day}")
            require(ordinals[-1] == 239, f"short_day_bad_close:{day}")

    return {
        "rows": int(len(tape)),
        "trading_days": int(len(sizes)),
        "normal_240_bar_days": int(normal_days),
        "data_contract": contracts[0],
        "bars_per_day_distribution": {
            str(int(k)): int(v) for k, v in sizes.value_counts().sort_index().items()
        },
        "short_days": short_days,
        "clock_edges": {"09:31": 0, "11:30": 119, "13:01": 120, "15:00": 239},
        "observed_bar_horizon_not_wall_clock_minutes": True,
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
    non_vol = [
        c
        for c in FEATURES
        if c not in {"realized_pre_event_vol_30", "realized_pre_event_vol_120"}
    ]
    require(sum(out[c]["missing"] for c in non_vol) == 0, "non_vol_feature_missing")
    return out


def prefix_audit(tape: pd.DataFrame, full: pd.DataFrame, core, freeze: dict) -> dict:
    days = tape.trading_day.astype(str).to_numpy()
    columns = ["confirm_idx", "year", *FEATURES]
    out = {}
    expected_cumulative = {
        2021: 186,
        2022: 495,
        2023: 673,
        2024: 1047,
        2025: 1296,
    }
    for year in range(2021, 2026):
        loc = np.flatnonzero(days <= f"{year}-12-31")
        require(len(loc) > 0, f"missing_prefix:{year}")
        cutoff = int(loc[-1])
        prefix_tape = tape.iloc[: cutoff + 1].reset_index(drop=True)
        observed = build_snapshots(prefix_tape, core, freeze)
        observed = observed.loc[observed.year.isin(VALID_YEARS), columns].reset_index(drop=True)
        expected = full.loc[
            (full.confirm_idx <= cutoff) & full.year.isin(VALID_YEARS), columns
        ].reset_index(drop=True)
        require(len(observed) == expected_cumulative[year], f"prefix_expected_count_changed:{year}")
        require(len(observed) == len(expected), f"prefix_count_changed:{year}")
        observed_hash = canonical_hash(observed, columns)
        expected_hash = canonical_hash(expected, columns)
        require(observed_hash == expected_hash, f"prefix_feature_changed:{year}")
        out[str(year)] = {
            "events": int(len(observed)),
            "feature_hash": observed_hash,
            "pass": True,
        }
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=pathlib.Path, required=True)
    args = parser.parse_args()
    source = args.source.resolve()

    source_integrity = source_integrity_audit(source)
    sys.path.insert(0, str(source))
    from research.index_price_validity import core

    freeze = json.loads(
        (
            source
            / "docs"
            / "governance"
            / "INDEX_PRICE_VALIDITY_FREEZE@1.0.json"
        ).read_text(encoding="utf-8")
    )
    tape = load_tape(source)
    session = session_audit(tape)
    events1 = build_snapshots(tape, core, freeze)
    events2 = build_snapshots(tape, core, freeze)

    columns = ["confirm_idx", "year", *FEATURES]
    hash1 = canonical_hash(events1, columns)
    hash2 = canonical_hash(events2, columns)
    require(hash1 == hash2, "determinism_feature_hash_failure")

    all_counts = events1.groupby("year", sort=True).size().to_dict()
    require(all_counts == EXPECTED_EVENT_COUNTS, f"all_event_identity_mismatch:{all_counts}")
    require(len(events1) == 3049, f"all_event_count_mismatch:{len(events1)}")

    validation = events1.loc[events1.year.isin(VALID_YEARS)]
    require(len(validation) == 1296, f"validation_event_identity_mismatch:{len(validation)}")
    year_counts = validation.groupby("year", sort=True).size()
    require(
        year_counts.to_dict()
        == {k: v for k, v in EXPECTED_EVENT_COUNTS.items() if k in VALID_YEARS},
        "validation_year_counts_mismatch",
    )

    result = {
        "schema": "r1a_stagea_feature_only_audit_v2",
        "source_commit": SOURCE_COMMIT,
        "private_stagea_authority": "R1A_PARENT_CONTINUATION_STAGEA_FREEZE_20260914",
        "outcomes_read_for_scoring": False,
        "return_targets_constructed": False,
        "model_fitted": False,
        "horizon_selected": False,
        "production_authority": False,
        "source_integrity": source_integrity,
        "session": session,
        "events": {
            "all_2015_2025": int(len(events1)),
            "all_by_year": {str(int(k)): int(v) for k, v in all_counts.items()},
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
