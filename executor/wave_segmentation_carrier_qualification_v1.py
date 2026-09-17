"""Pure aggregate qualification logic for issue #352.

No network, no file output, no detector fitting. Inputs are already byte-verified
public Development frames. Coordinates never appear in the returned report.
"""
from __future__ import annotations
from collections import Counter
import numpy as np
import pandas as pd

SYMBOL = "000852.SH"
START_DAY = "2015-01-05"
END_DAY = "2020-12-31"
EXCLUDED = frozenset({"2016-01-04", "2016-01-07", "2017-08-24", "2020-04-20"})
ABS_TOL = 1e-10
REL_TOL = 1e-12
PRICE = ("open", "high", "low", "close")
FILES = ("1m_official.parquet", *(f"5m_offset_{i}.parquet" for i in range(5)))


def hhmm(minute: int) -> str:
    return f"{minute // 60:02d}:{minute % 60:02d}"


def expected_minutes(name: str) -> tuple[int, ...]:
    if name == "1m_official.parquet":
        return tuple(range(571, 691)) + tuple(range(781, 901))
    if name.startswith("5m_offset_"):
        offset = int(name.removeprefix("5m_offset_").removesuffix(".parquet"))
        if offset not in range(5):
            raise ValueError("offset")
        return tuple(range(575 + offset, 691, 5)) + tuple(range(785 + offset, 901, 5))
    raise ValueError("file")


def expected_clocks(name: str) -> set[str]:
    return {hhmm(value) for value in expected_minutes(name)}


def bool_series(values: pd.Series) -> pd.Series:
    if values.dtype == bool:
        return values
    mapped = values.map({True: True, False: False, 1: True, 0: False,
                         "true": True, "false": False, "True": True, "False": False})
    if mapped.isna().any():
        raise ValueError("invalid_boolean_field")
    return mapped.astype(bool)


def canonicalize(frame: pd.DataFrame, name: str, declared_rows: int) -> tuple[pd.DataFrame, dict]:
    required = {"symbol", "timestamp", "trading_day", *PRICE}
    missing = sorted(required - set(map(str, frame.columns)))
    errors: list[str] = []
    if missing:
        return pd.DataFrame(), {"file": name, "rows": len(frame),
            "columns": sorted(map(str, frame.columns)), "errors": ["MISSING:" + ",".join(missing)]}
    out = frame.copy()
    utc = pd.to_datetime(out["timestamp"], errors="coerce", utc=True)
    if utc.isna().any():
        errors.append("BAD_TIMESTAMP")
    local = utc.dt.tz_convert("Asia/Shanghai")
    if "bar_end_shanghai" in out:
        shanghai = pd.to_datetime(out["bar_end_shanghai"], errors="coerce", utc=True)
        if shanghai.isna().any() or not bool((shanghai == utc).all()):
            errors.append("SHANGHAI_TIMESTAMP_MISMATCH")
    out["audit_utc"] = utc
    out["audit_local"] = local
    out["audit_day"] = out["trading_day"].astype(str).str[:10]
    out["audit_clock"] = local.dt.strftime("%H:%M")
    out["audit_minute"] = local.dt.hour.astype("int64") * 60 + local.dt.minute.astype("int64")
    if len(out) != declared_rows:
        errors.append("DECLARED_ROW_COUNT")
    if set(out["symbol"].astype(str)) != {SYMBOL}:
        errors.append("SYMBOL_SET")
    if out["audit_day"].min() != START_DAY or out["audit_day"].max() != END_DAY:
        errors.append("DAY_BOUNDARY")
    if not bool((local.dt.strftime("%Y-%m-%d") == out["audit_day"]).all()):
        errors.append("LOCAL_DAY_MISMATCH")
    if utc.duplicated().any() or not utc.is_monotonic_increasing:
        errors.append("TIMESTAMP_ORDER")
    vals = out[list(PRICE)].apply(pd.to_numeric, errors="coerce").to_numpy(float)
    if not np.isfinite(vals).all() or np.any(vals <= 0):
        errors.append("PRICE_VALUE")
    elif np.any(vals[:, 2] > np.min(vals, axis=1)) or np.any(vals[:, 1] < np.max(vals, axis=1)):
        errors.append("OHLC_RANGE")
    expected = expected_clocks(name)
    unexpected = int((~out["audit_clock"].isin(expected)).sum())
    if unexpected:
        errors.append("UNEXPECTED_CLOCK")
    daysets = {day: set(group["audit_clock"]) for day, group in out.groupby("audit_day", sort=False)}
    complete = sum(day not in EXCLUDED and clocks == expected for day, clocks in daysets.items())
    incomplete = sum(day not in EXCLUDED and clocks != expected for day, clocks in daysets.items())
    if incomplete:
        errors.append("INCOMPLETE_NONEXCLUDED_DAY")
    if name == "1m_official.parquet":
        for column in ("causal_flat_fill", "high_frequency_analysis_eligible"):
            if column not in out:
                errors.append("MISSING:" + column)
        if not errors:
            try:
                out["causal_flat_fill"] = bool_series(out["causal_flat_fill"])
                out["high_frequency_analysis_eligible"] = bool_series(out["high_frequency_analysis_eligible"])
            except ValueError:
                errors.append("BOOLEAN_FIELD")
    metrics = {"file": name, "rows": int(len(out)), "columns": sorted(map(str, frame.columns)),
        "column_count": int(len(frame.columns)), "first_day": None if out.empty else str(out["audit_day"].min()),
        "last_day": None if out.empty else str(out["audit_day"].max()), "trading_days": int(out["audit_day"].nunique()),
        "unexpected_clock_rows": unexpected, "complete_nonexcluded_days": int(complete),
        "incomplete_nonexcluded_days": int(incomplete), "excluded_days_present": int(sum(day in EXCLUDED for day in daysets)),
        "errors": sorted(set(errors))}
    return out, metrics


def bucket_members(offset: int, close_minute: int) -> tuple[int, ...] | None:
    if offset not in range(5):
        raise ValueError("offset")
    if 570 <= close_minute <= 690:
        session_start = 570
    elif 780 <= close_minute <= 900:
        session_start = 780
    else:
        return None
    grid_start = session_start + offset
    first_close = grid_start + 5
    if close_minute < first_close or (close_minute - first_close) % 5:
        return None
    if close_minute == first_close:
        begin = session_start if offset == 0 else grid_start
        return tuple(range(begin, first_close + 1))
    return tuple(range(close_minute - 4, close_minute + 1))


def aggregate_ohlc(part: pd.DataFrame) -> np.ndarray:
    values = part[list(PRICE)].to_numpy(float)
    return np.asarray([values[0, 0], values[:, 1].max(), values[:, 2].min(), values[-1, 3]], float)


def close_enough(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    delta = np.abs(a - b)
    return (delta <= ABS_TOL) | (delta <= REL_TOL * np.maximum(np.abs(a), np.abs(b)))


def reconstruction(one: pd.DataFrame, five: pd.DataFrame, offset: int) -> dict:
    minute_map = {(day, int(minute)): idx for idx, (day, minute) in enumerate(zip(one["audit_day"], one["audit_minute"]))}
    categories = Counter()
    compared = matches = mismatches = exact = 0
    max_abs = max_rel = 0.0
    expected = expected_clocks(f"5m_offset_{offset}.parquet")
    for _, row in five.iterrows():
        day = str(row["audit_day"]); clock = str(row["audit_clock"]); minute = int(row["audit_minute"])
        if day in EXCLUDED:
            categories["EXCLUDED_DAY"] += 1; continue
        if clock not in expected:
            categories["UNEXPECTED_CLOCK"] += 1; continue
        members = bucket_members(offset, minute)
        if members is None:
            categories["BUCKET_CONTRACT_ERROR"] += 1; continue
        if offset == 0 and members[0] in (570, 780):
            categories["SOURCE_MINUTE_NOT_EXPORTED"] += 1; continue
        indexes = [minute_map.get((day, member)) for member in members]
        if any(index is None for index in indexes):
            categories["MISSING_1M_CONSTITUENT"] += 1; continue
        part = one.iloc[indexes]
        if not bool(part["high_frequency_analysis_eligible"].all()):
            categories["INELIGIBLE_1M_DAY"] += 1; continue
        if bool(part["causal_flat_fill"].any()):
            categories["CAUSAL_FLAT_FILL"] += 1; continue
        target = row[list(PRICE)].to_numpy(dtype=float)
        calculated = aggregate_ohlc(part)
        compared += 1
        delta = np.abs(calculated - target)
        relative = delta / np.maximum(np.maximum(np.abs(calculated), np.abs(target)), 1e-300)
        max_abs = max(max_abs, float(delta.max()))
        max_rel = max(max_rel, float(relative.max()))
        if bool(close_enough(calculated, target).all()):
            matches += 1
        else:
            mismatches += 1
        if bool((calculated == target).all()):
            exact += 1
    return {"offset": offset, "total_five_minute_rows": int(len(five)), "compared_bars": compared,
        "matched_bars": matches, "mismatched_bars": mismatches, "exact_equal_bars": exact,
        "max_abs_error": max_abs, "max_rel_error": max_rel,
        "unsupported_or_other": dict(sorted(categories.items()))}


def complete_days(frame: pd.DataFrame, name: str) -> set[str]:
    expected = expected_clocks(name)
    return {day for day, group in frame.groupby("audit_day")
            if day not in EXCLUDED and set(group["audit_clock"]) == expected}


def common_support(frames: dict[str, pd.DataFrame]) -> dict:
    day_sets = [complete_days(frames[name], name) for name in FILES]
    common = set.intersection(*day_sets) if day_sets else set()
    one = frames["1m_official.parquet"]
    eligible_days = {day for day, group in one.groupby("audit_day")
                     if day not in EXCLUDED and bool(group["high_frequency_analysis_eligible"].all())}
    common &= eligible_days
    in_common_clock = (((one["audit_minute"] >= 574) & (one["audit_minute"] <= 686)) |
                       ((one["audit_minute"] >= 784) & (one["audit_minute"] <= 896)))
    part = one.loc[one["audit_day"].isin(common) & in_common_clock]
    filled = int(part["causal_flat_fill"].sum())
    return {"common_complete_eligible_days": int(len(common)),
        "contract_common_minutes": int(len(common) * 226), "exported_common_minute_rows": int(len(part)),
        "observed_unfilled_common_minutes": int(len(part) - filled), "causal_fill_common_minutes": filled,
        "common_minute_windows": ["09:34-11:26", "13:04-14:56"]}


def build_report(raw_frames: dict[str, pd.DataFrame], declared_rows: dict[str, int]) -> dict:
    frames: dict[str, pd.DataFrame] = {}; metrics = {}; schema_ok = True
    for name in FILES:
        frame, metric = canonicalize(raw_frames[name], name, declared_rows[name])
        frames[name] = frame; metrics[name] = metric
        schema_ok = schema_ok and not metric["errors"]
    base = {"schema_id": "csi1000.segmentation_carrier_qualification@1.0", "research_issue": 352,
        "data_role": "PREVIOUSLY_CONSUMED_DEVELOPMENT_NOT_FRESH_OOS", "symbol": SYMBOL,
        "period": [START_DAY, END_DAY], "file_metrics": metrics,
        "aliasing_conclusion": "NOT_AUTHORIZED", "scale_dominance_conclusion": "NOT_AUTHORIZED",
        "R4_selected": False, "one_minute_strategy_admitted": False, "outcomes_used": False,
        "new_training": False, "production_authority": False}
    if not schema_ok:
        return dict(base, status="SCHEMA_OR_CLOCK_FAILED", reconstruction={}, common_support=None)
    one = frames["1m_official.parquet"]
    recon = {str(offset): reconstruction(one, frames[f"5m_offset_{offset}.parquet"], offset)
             for offset in range(5)}
    common = common_support(frames)
    mismatch = any(row["mismatched_bars"] for row in recon.values())
    enough = common["common_complete_eligible_days"] > 0 and all(row["compared_bars"] > 0 for row in recon.values())
    if mismatch:
        status = "CONSTRUCTION_MISMATCH"
    elif enough:
        status = "QUALIFIED_WITH_EXPECTED_UNSUPPORTED_BUCKETS"
    else:
        status = "SCHEMA_OR_CLOCK_FAILED"
    return dict(base, status=status, reconstruction=recon, common_support=common,
                tolerance={"abs_error": ABS_TOL, "relative_error": REL_TOL},
                excluded_days_count=len(EXCLUDED))
