#!/usr/bin/env python3
"""Normalize native W12/W24 OLS lifecycle output for the D0 drawdown atlas.

The input is a *joined* CSV containing:

1. the frozen OLS lifecycle output (`executable_position`,
   `executable_authority_window_bars`, `direction_conflict`, `exit_trigger`),
2. the regression carrier fields for both sides and both windows, and
3. an externally computed `strategy_return` that already honors the intended
   execution/cost convention.

This adapter never computes strategy PnL and never changes the OLS strategy.
For each non-flat execution bar it observes fit quality from the CURRENT bar
for the side currently carrying risk and the executable authority window that
selected that risk.  This is deliberate: D0 asks whether live trend geometry
starts failing while the strategy is still exposed.
"""

from __future__ import annotations

import argparse
import csv
import math
from datetime import datetime
from pathlib import Path
from typing import Any

WINDOWS = (12, 24)
SIDES = ("up", "down")
BASE_REQUIRED = (
    "timestamp",
    "strategy_return",
    "executable_position",
    "executable_authority_window_bars",
    "direction_conflict",
    "exit_trigger",
)
FEATURE_FIELDS = (
    "fit_r2",
    "path_efficiency",
    "slope_log_per_15m",
    "qualified",
)


def feature_name(side: str, window: int, field: str) -> str:
    return f"context_free_explosive_{side}_w{window}_{field}"


def _required_columns() -> tuple[str, ...]:
    return BASE_REQUIRED + tuple(
        feature_name(side, window, field)
        for side in SIDES
        for window in WINDOWS
        for field in FEATURE_FIELDS
    )


def _timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"timestamp must be timezone-aware: {value!r}")
    return parsed


def _finite(value: Any, *, name: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ValueError(f"{name} must be finite")
    return parsed


def _bool(value: Any, *, name: str) -> bool:
    text = str(value).strip().lower()
    if text in {"1", "true", "t", "yes", "y"}:
        return True
    if text in {"0", "false", "f", "no", "n"}:
        return False
    raise ValueError(f"{name} invalid boolean: {value!r}")


def _active_side(position: float) -> str | None:
    if position == 0.0:
        return None
    if position == 1.0:
        return "up"
    if position == -1.0:
        return "down"
    raise ValueError(f"frozen OLS executable_position must be -1/0/1, got {position}")


def _active_window(raw: Any, *, position: float) -> int | None:
    window = int(float(raw))
    if position == 0.0:
        if window != 0:
            raise ValueError("flat OLS bar must have executable authority window 0")
        return None
    if window not in WINDOWS:
        raise ValueError(f"non-flat OLS authority window must be W12/W24, got {window}")
    return window


def _feature(row: dict[str, str], side: str, window: int, field: str) -> str:
    return row[feature_name(side, window, field)]


def adapt(input_path: Path, output_path: Path) -> int:
    with input_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        columns = tuple(reader.fieldnames or ())
        missing = [name for name in _required_columns() if name not in columns]
        if missing:
            raise ValueError(f"joined OLS trace missing required columns: {missing}")
        passthrough = [
            name
            for name in ("close", "slow_state", "slow_fit_r2")
            if name in columns
        ]
        output_fields = [
            "timestamp",
            "strategy_return",
            "executable_position",
            "fit_r2",
            "path_efficiency",
            "slope_per_bar",
            "authority_window_bars",
            "qualified",
            "direction_conflict",
            "exit_trigger",
            "ols_midline",
            "active_side",
            "active_feature_id",
            *passthrough,
        ]
        output_path.parent.mkdir(parents=True, exist_ok=True)
        previous_ts: datetime | None = None
        count = 0
        with output_path.open("w", encoding="utf-8", newline="") as out_handle:
            writer = csv.DictWriter(out_handle, fieldnames=output_fields)
            writer.writeheader()
            for line_no, row in enumerate(reader, start=2):
                ts = _timestamp(row["timestamp"])
                if previous_ts is not None and ts <= previous_ts:
                    raise ValueError(f"timestamps must be unique/increasing; line {line_no}")
                previous_ts = ts
                ret = _finite(row["strategy_return"], name="strategy_return")
                if ret <= -1.0:
                    raise ValueError(f"strategy_return <= -100% at line {line_no}")
                position = _finite(row["executable_position"], name="executable_position")
                side = _active_side(position)
                window = _active_window(
                    row["executable_authority_window_bars"], position=position
                )
                conflict = _bool(row["direction_conflict"], name="direction_conflict")
                exit_trigger = _bool(row["exit_trigger"], name="exit_trigger")
                out: dict[str, Any] = {
                    "timestamp": ts.isoformat(),
                    "strategy_return": ret,
                    "executable_position": int(position),
                    "fit_r2": "",
                    "path_efficiency": "",
                    "slope_per_bar": "",
                    "authority_window_bars": "" if window is None else window,
                    "qualified": "",
                    "direction_conflict": conflict,
                    "exit_trigger": exit_trigger,
                    "ols_midline": "",
                    "active_side": "flat" if side is None else side,
                    "active_feature_id": "flat",
                }
                if side is not None and window is not None:
                    r2 = _finite(_feature(row, side, window, "fit_r2"), name="fit_r2")
                    efficiency = _finite(
                        _feature(row, side, window, "path_efficiency"),
                        name="path_efficiency",
                    )
                    slope = _finite(
                        _feature(row, side, window, "slope_log_per_15m"),
                        name="slope_log_per_15m",
                    )
                    qualified = _bool(
                        _feature(row, side, window, "qualified"),
                        name="qualified",
                    )
                    if not 0.0 <= r2 <= 1.0:
                        raise ValueError(f"active fit_r2 outside [0,1] at line {line_no}")
                    midline_column = f"{side}_live_ols_midline"
                    midline = ""
                    if midline_column in row and row[midline_column] not in {None, ""}:
                        midline = _finite(row[midline_column], name=midline_column)
                    out.update(
                        {
                            "fit_r2": r2,
                            "path_efficiency": efficiency,
                            "slope_per_bar": slope,
                            "qualified": qualified,
                            "ols_midline": midline,
                            "active_feature_id": f"{side}_w{window}",
                        }
                    )
                for name in passthrough:
                    out[name] = row[name]
                writer.writerow(out)
                count += 1
    return count


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="joined native OLS trace CSV")
    parser.add_argument("--output", required=True, type=Path, help="normalized D0 trace CSV")
    args = parser.parse_args()
    count = adapt(args.input, args.output)
    print(f"wrote {count} normalized OLS D0 rows to {args.output}")


if __name__ == "__main__":
    main()
