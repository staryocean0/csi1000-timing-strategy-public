#!/usr/bin/env python3
"""D0-only OLS drawdown episode atlas.

The diagnostic changes no entry, exit, routing, sizing, leverage, or production
rule.  It consumes an already-causal per-bar OLS strategy trace and describes
where drawdowns occur and whether OLS fit quality deteriorates before them.

Required CSV columns
--------------------
timestamp,strategy_return,executable_position,fit_r2

`strategy_return` must already reflect the frozen execution/cost convention.
The diagnostic deliberately does not infer PnL from prices.

`fit_r2` must be present for every non-flat executable-position bar.  It may be
blank while flat because there is then no active side/window whose fit quality
has trading authority.  R2 deterioration counters reset whenever the strategy
is flat or reverses direction, so no decline is spuriously carried across two
separate trades.

Recommended optional columns
----------------------------
close,path_efficiency,slope_t,slope_per_bar,authority_window_bars,
qualified,direction_conflict,exit_trigger,ols_midline,slow_state,slow_fit_r2

Outputs
-------
- drawdown_atlas.csv
- drawdown_timeseries.csv
- drawdown_summary.json

Research authority only.  No production or strategy-selection authority.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

REQUIRED_COLUMNS = ("timestamp", "strategy_return", "executable_position", "fit_r2")
OPTIONAL_COLUMNS = (
    "close",
    "path_efficiency",
    "slope_t",
    "slope_per_bar",
    "authority_window_bars",
    "qualified",
    "direction_conflict",
    "exit_trigger",
    "ols_midline",
    "slow_state",
    "slow_fit_r2",
)
BOOL_COLUMNS = {"qualified", "direction_conflict", "exit_trigger"}
TEXT_COLUMNS = {"slow_state"}


@dataclass(frozen=True)
class DrawdownEpisode:
    rank: int
    peak_timestamp: str
    start_timestamp: str
    trough_timestamp: str
    recovery_timestamp: str | None
    depth: float
    underwater_bars: int
    peak_equity: float
    trough_equity: float
    position_at_start: float
    position_at_trough: float
    authority_window_at_start: float | None
    authority_window_at_trough: float | None
    window_switches_to_trough: int
    active_r2_observation_count: int
    fit_r2_at_start: float | None
    fit_r2_at_trough: float | None
    fit_r2_min_to_trough: float | None
    fit_r2_max_to_trough: float | None
    fit_r2_change_start_to_trough: float | None
    fit_r2_peak_to_trough: float | None
    first_r2_down_timestamp: str | None
    first_two_consecutive_r2_down_timestamp: str | None
    r2_first_down_lead_bars_to_trough: int | None
    r2_two_down_lead_bars_to_trough: int | None
    path_efficiency_at_start: float | None
    path_efficiency_at_trough: float | None
    slope_t_at_start: float | None
    slope_t_at_trough: float | None
    direction_conflict_count_to_trough: int
    exit_trigger_count_to_trough: int
    slow_state_at_start: str | None
    slow_state_at_trough: str | None
    slow_fit_r2_at_start: float | None
    slow_fit_r2_at_trough: float | None


def _float(value: Any, *, optional: bool = False) -> float | None:
    if value is None or value == "":
        if optional:
            return None
        raise ValueError("missing required numeric value")
    parsed = float(value)
    if not math.isfinite(parsed):
        if optional:
            return None
        raise ValueError(f"non-finite required numeric value: {value!r}")
    return parsed


def _bool(value: Any) -> bool:
    if value is None or value == "":
        return False
    text = str(value).strip().lower()
    if text in {"1", "true", "t", "yes", "y"}:
        return True
    if text in {"0", "false", "f", "no", "n"}:
        return False
    raise ValueError(f"invalid boolean value: {value!r}")


def _timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"timestamp must be timezone-aware: {value!r}")
    return parsed


def _read(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        columns = tuple(reader.fieldnames or ())
        missing = [name for name in REQUIRED_COLUMNS if name not in columns]
        if missing:
            raise ValueError(f"input missing required columns: {missing}")
        rows: list[dict[str, Any]] = []
        previous: datetime | None = None
        for line_no, raw in enumerate(reader, start=2):
            ts = _timestamp(str(raw["timestamp"]))
            if previous is not None and ts <= previous:
                raise ValueError(f"timestamps must be unique/increasing; line {line_no}")
            previous = ts
            ret = _float(raw["strategy_return"])
            pos = _float(raw["executable_position"])
            assert ret is not None and pos is not None
            if ret <= -1.0:
                raise ValueError(f"strategy_return <= -100% at line {line_no}")
            r2 = _float(raw["fit_r2"], optional=True)
            if pos != 0.0 and r2 is None:
                raise ValueError(f"non-flat bar requires fit_r2 at line {line_no}")
            if r2 is not None and not 0.0 <= r2 <= 1.0:
                raise ValueError(f"fit_r2 outside [0,1] at line {line_no}")
            row: dict[str, Any] = {
                "timestamp": ts,
                "strategy_return": ret,
                "executable_position": pos,
                "fit_r2": r2,
            }
            for name in OPTIONAL_COLUMNS:
                raw_value = raw.get(name)
                if name in BOOL_COLUMNS:
                    row[name] = _bool(raw_value) if raw_value not in {None, ""} else None
                elif name in TEXT_COLUMNS:
                    row[name] = str(raw_value).strip() if raw_value not in {None, ""} else None
                else:
                    row[name] = _float(raw_value, optional=True)
            rows.append(row)
    if len(rows) < 2:
        raise ValueError("drawdown atlas requires at least two rows")
    return rows


def _slope(values: list[float]) -> float | None:
    if len(values) < 2:
        return None
    n = len(values)
    xm = (n - 1) / 2.0
    ym = sum(values) / n
    xss = sum((i - xm) ** 2 for i in range(n))
    return sum((i - xm) * (v - ym) for i, v in enumerate(values)) / xss


def _decorate(rows: list[dict[str, Any]]) -> None:
    equity = 1.0
    peak = 1.0
    prior_pos = 0.0
    prior_r2: float | None = None
    decline_run = 0
    trade_entry_r2: float | None = None
    trade_r2_history: list[float] = []
    trade_id = 0
    for row in rows:
        ret = float(row["strategy_return"])
        equity *= 1.0 + ret
        peak = max(peak, equity)
        row["equity"] = equity
        row["peak_equity"] = peak
        row["drawdown"] = equity / peak - 1.0

        pos = float(row["executable_position"])
        r2 = row["fit_r2"]
        new_segment = pos != 0.0 and (prior_pos == 0.0 or pos * prior_pos < 0.0)
        if pos == 0.0:
            prior_r2 = None
            decline_run = 0
            trade_entry_r2 = None
            trade_r2_history = []
            row["trade_id"] = None
            row["fit_r2_delta_1"] = None
            row["fit_r2_delta_2"] = None
            row["fit_r2_delta_4"] = None
            row["fit_r2_slope_4"] = None
            row["fit_r2_consecutive_declines"] = 0
            row["fit_r2_entry"] = None
            row["fit_r2_ratio_to_entry"] = None
        else:
            assert isinstance(r2, float)
            if new_segment:
                trade_id += 1
                prior_r2 = None
                decline_run = 0
                trade_entry_r2 = r2
                trade_r2_history = []
            trade_r2_history.append(r2)
            delta1 = None if prior_r2 is None else r2 - prior_r2
            if delta1 is not None and delta1 < 0.0:
                decline_run += 1
            else:
                decline_run = 0
            row["trade_id"] = trade_id
            row["fit_r2_delta_1"] = delta1
            row["fit_r2_delta_2"] = None if len(trade_r2_history) < 3 else r2 - trade_r2_history[-3]
            row["fit_r2_delta_4"] = None if len(trade_r2_history) < 5 else r2 - trade_r2_history[-5]
            row["fit_r2_slope_4"] = _slope(trade_r2_history[-4:])
            row["fit_r2_consecutive_declines"] = decline_run
            row["fit_r2_entry"] = trade_entry_r2
            row["fit_r2_ratio_to_entry"] = (
                None if trade_entry_r2 is None or trade_entry_r2 <= 0.0 else r2 / trade_entry_r2
            )
            prior_r2 = r2
        prior_pos = pos


def _episodes(rows: list[dict[str, Any]]) -> list[tuple[int, int, int, int | None]]:
    result: list[tuple[int, int, int, int | None]] = []
    peak_idx = 0
    active = False
    start_idx = 0
    trough_idx = 0
    for idx, row in enumerate(rows):
        dd = float(row["drawdown"])
        if dd >= -1e-15:
            if active:
                result.append((peak_idx, start_idx, trough_idx, idx))
                active = False
            peak_idx = idx
        elif not active:
            active = True
            start_idx = idx
            trough_idx = idx
        elif dd < float(rows[trough_idx]["drawdown"]):
            trough_idx = idx
    if active:
        result.append((peak_idx, start_idx, trough_idx, None))
    return result


def _opt(row: dict[str, Any], key: str) -> float | None:
    value = row.get(key)
    return float(value) if isinstance(value, (int, float)) and math.isfinite(float(value)) else None


def _switches(rows: list[dict[str, Any]], start: int, end: int) -> int:
    previous: float | None = None
    count = 0
    for row in rows[start : end + 1]:
        value = _opt(row, "authority_window_bars")
        if value is None:
            continue
        if previous is not None and value != previous:
            count += 1
        previous = value
    return count


def _first(
    rows: list[dict[str, Any]], start: int, end: int, predicate: Callable[[dict[str, Any]], bool]
) -> int | None:
    for idx in range(start, end + 1):
        if predicate(rows[idx]):
            return idx
    return None


def _r2_values(rows: list[dict[str, Any]], start: int, end: int) -> list[float]:
    return [float(row["fit_r2"]) for row in rows[start : end + 1] if row.get("fit_r2") is not None]


def _change(first: float | None, last: float | None) -> float | None:
    return None if first is None or last is None else last - first


def _episode(
    rows: list[dict[str, Any]], span: tuple[int, int, int, int | None], rank: int
) -> DrawdownEpisode:
    peak_idx, start_idx, trough_idx, recovery_idx = span
    start, trough = rows[start_idx], rows[trough_idx]
    segment = rows[start_idx : trough_idx + 1]
    r2s = _r2_values(rows, start_idx, trough_idx)
    first_down = _first(
        rows,
        start_idx,
        trough_idx,
        lambda row: row.get("fit_r2_delta_1") is not None and float(row["fit_r2_delta_1"]) < 0.0,
    )
    first_two = _first(
        rows,
        start_idx,
        trough_idx,
        lambda row: int(row.get("fit_r2_consecutive_declines") or 0) >= 2,
    )
    start_r2 = _opt(start, "fit_r2")
    trough_r2 = _opt(trough, "fit_r2")
    return DrawdownEpisode(
        rank=rank,
        peak_timestamp=rows[peak_idx]["timestamp"].isoformat(),
        start_timestamp=start["timestamp"].isoformat(),
        trough_timestamp=trough["timestamp"].isoformat(),
        recovery_timestamp=None if recovery_idx is None else rows[recovery_idx]["timestamp"].isoformat(),
        depth=float(trough["drawdown"]),
        underwater_bars=(len(rows) - start_idx if recovery_idx is None else recovery_idx - start_idx),
        peak_equity=float(rows[peak_idx]["equity"]),
        trough_equity=float(trough["equity"]),
        position_at_start=float(start["executable_position"]),
        position_at_trough=float(trough["executable_position"]),
        authority_window_at_start=_opt(start, "authority_window_bars"),
        authority_window_at_trough=_opt(trough, "authority_window_bars"),
        window_switches_to_trough=_switches(rows, start_idx, trough_idx),
        active_r2_observation_count=len(r2s),
        fit_r2_at_start=start_r2,
        fit_r2_at_trough=trough_r2,
        fit_r2_min_to_trough=min(r2s) if r2s else None,
        fit_r2_max_to_trough=max(r2s) if r2s else None,
        fit_r2_change_start_to_trough=_change(start_r2, trough_r2),
        fit_r2_peak_to_trough=(None if not r2s or trough_r2 is None else max(r2s) - trough_r2),
        first_r2_down_timestamp=None if first_down is None else rows[first_down]["timestamp"].isoformat(),
        first_two_consecutive_r2_down_timestamp=None if first_two is None else rows[first_two]["timestamp"].isoformat(),
        r2_first_down_lead_bars_to_trough=None if first_down is None else trough_idx - first_down,
        r2_two_down_lead_bars_to_trough=None if first_two is None else trough_idx - first_two,
        path_efficiency_at_start=_opt(start, "path_efficiency"),
        path_efficiency_at_trough=_opt(trough, "path_efficiency"),
        slope_t_at_start=_opt(start, "slope_t"),
        slope_t_at_trough=_opt(trough, "slope_t"),
        direction_conflict_count_to_trough=sum(bool(row.get("direction_conflict")) for row in segment),
        exit_trigger_count_to_trough=sum(bool(row.get("exit_trigger")) for row in segment),
        slow_state_at_start=start.get("slow_state") if isinstance(start.get("slow_state"), str) else None,
        slow_state_at_trough=trough.get("slow_state") if isinstance(trough.get("slow_state"), str) else None,
        slow_fit_r2_at_start=_opt(start, "slow_fit_r2"),
        slow_fit_r2_at_trough=_opt(trough, "slow_fit_r2"),
    )


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields = list(rows[0])
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {key: value.isoformat() if isinstance(value, datetime) else value for key, value in row.items()}
            )


def run(input_path: Path, out_dir: Path, *, top_n: int) -> dict[str, Any]:
    if top_n < 1:
        raise ValueError("top_n must be positive")
    rows = _read(input_path)
    _decorate(rows)
    spans = _episodes(rows)
    worst_first = sorted(spans, key=lambda span: float(rows[span[2]]["drawdown"]))
    atlas = [_episode(rows, span, rank + 1) for rank, span in enumerate(worst_first[:top_n])]
    out_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(out_dir / "drawdown_timeseries.csv", rows)
    atlas_rows = [asdict(item) for item in atlas]
    _write_csv(out_dir / "drawdown_atlas.csv", atlas_rows)
    summary = {
        "schema_id": "ols_drawdown_atlas_d0@1.1",
        "input": str(input_path),
        "row_count": len(rows),
        "episode_count": len(spans),
        "reported_episode_count": len(atlas),
        "total_return": float(rows[-1]["equity"]) - 1.0,
        "maximum_drawdown": min(float(row["drawdown"]) for row in rows),
        "final_equity": float(rows[-1]["equity"]),
        "r2_semantics": "active-side active-authority-window current fit; blank while flat",
        "r2_deterioration_resets": "flat_or_direction_reversal",
        "required_return_semantics": "externally supplied frozen execution/cost convention",
        "diagnostic_only": True,
        "changes_entry_exit_routing_sizing_or_leverage": False,
        "worst_episodes": atlas_rows,
    }
    (out_dir / "drawdown_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--top-n", type=int, default=10)
    args = parser.parse_args()
    print(json.dumps(run(args.input, args.out_dir, top_n=args.top_n), ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
