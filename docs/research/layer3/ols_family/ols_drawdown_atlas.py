#!/usr/bin/env python3
"""D0-only OLS drawdown episode atlas.

This diagnostic intentionally does not change any entry, exit, routing, sizing,
or leverage rule.  It consumes an already-causal per-bar strategy trace and
builds a maximum-drawdown atlas around the existing OLS lifecycle.

Required CSV columns
--------------------
timestamp,strategy_return,executable_position,fit_r2

`strategy_return` must already reflect the intended execution convention.  The
diagnostic does not infer PnL from prices because doing so could silently change
close_t -> open_t+1 semantics or transaction-cost treatment.

Recommended optional columns
----------------------------
close,path_efficiency,slope_t,slope_per_bar,authority_window_bars,
qualified,direction_conflict,exit_trigger,ols_midline,slow_state,slow_fit_r2

Outputs
-------
- drawdown_atlas.csv: material/worst drawdown episodes with signal diagnostics
- drawdown_timeseries.csv: causal per-bar equity/drawdown/R2 deterioration panel
- drawdown_summary.json: baseline statistics and worst-episode summary

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
from typing import Any

REQUIRED_COLUMNS = (
    "timestamp",
    "strategy_return",
    "executable_position",
    "fit_r2",
)

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
    fit_r2_at_start: float
    fit_r2_at_trough: float
    fit_r2_min_to_trough: float
    fit_r2_max_to_trough: float
    fit_r2_change_start_to_trough: float
    fit_r2_peak_to_trough: float
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


def _finite_float(value: Any, *, allow_none: bool = False) -> float | None:
    if value is None or value == "":
        if allow_none:
            return None
        raise ValueError("missing required numeric value")
    parsed = float(value)
    if not math.isfinite(parsed):
        if allow_none:
            return None
        raise ValueError(f"non-finite required numeric value: {value!r}")
    return parsed


def _truthy(value: Any) -> bool:
    if value is None or value == "":
        return False
    text = str(value).strip().lower()
    if text in {"1", "true", "t", "yes", "y"}:
        return True
    if text in {"0", "false", "f", "no", "n"}:
        return False
    raise ValueError(f"invalid boolean value: {value!r}")


def _parse_timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"timestamp must be timezone-aware: {value!r}")
    return parsed


def _read_rows(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        columns = tuple(reader.fieldnames or ())
        missing = [name for name in REQUIRED_COLUMNS if name not in columns]
        if missing:
            raise ValueError(f"input missing required columns: {missing}")
        rows: list[dict[str, Any]] = []
        previous_time: datetime | None = None
        for line_no, raw in enumerate(reader, start=2):
            timestamp = _parse_timestamp(str(raw["timestamp"]))
            if previous_time is not None and timestamp <= previous_time:
                raise ValueError(
                    f"timestamps must be unique and increasing; violation at line {line_no}"
                )
            previous_time = timestamp
            strategy_return = _finite_float(raw["strategy_return"])
            position = _finite_float(raw["executable_position"])
            fit_r2 = _finite_float(raw["fit_r2"])
            assert strategy_return is not None and position is not None and fit_r2 is not None
            if strategy_return <= -1.0:
                raise ValueError(f"strategy_return <= -100% at line {line_no}")
            if not 0.0 <= fit_r2 <= 1.0:
                raise ValueError(f"fit_r2 outside [0,1] at line {line_no}")
            row: dict[str, Any] = {
                "timestamp": timestamp,
                "strategy_return": strategy_return,
                "executable_position": position,
                "fit_r2": fit_r2,
            }
            for name in OPTIONAL_COLUMNS:
                if name not in raw:
                    row[name] = None
                elif name in {"qualified", "direction_conflict", "exit_trigger"}:
                    row[name] = _truthy(raw[name]) if raw[name] not in {None, ""} else None
                elif name in {"slow_state"}:
                    row[name] = str(raw[name]).strip() or None
                else:
                    row[name] = _finite_float(raw[name], allow_none=True)
            rows.append(row)
    if len(rows) < 2:
        raise ValueError("drawdown atlas requires at least two rows")
    return rows


def _ols_slope(values: list[float]) -> float | None:
    if len(values) < 2:
        return None
    n = len(values)
    x_mean = (n - 1) / 2.0
    y_mean = sum(values) / n
    xss = sum((i - x_mean) ** 2 for i in range(n))
    if xss <= 0.0:
        return None
    return sum((i - x_mean) * (value - y_mean) for i, value in enumerate(values)) / xss


def _decorate(rows: list[dict[str, Any]]) -> None:
    equity = 1.0
    peak = 1.0
    previous_r2: float | None = None
    decline_run = 0
    trade_entry_r2: float | None = None
    previous_position = 0.0
    for idx, row in enumerate(rows):
        strategy_return = float(row["strategy_return"])
        equity *= 1.0 + strategy_return
        peak = max(peak, equity)
        drawdown = equity / peak - 1.0
        fit_r2 = float(row["fit_r2"])
        delta1 = None if previous_r2 is None else fit_r2 - previous_r2
        if delta1 is not None and delta1 < 0.0:
            decline_run += 1
        else:
            decline_run = 0
        position = float(row["executable_position"])
        if position == 0.0:
            trade_entry_r2 = None
        elif previous_position == 0.0 or position * previous_position < 0.0:
            trade_entry_r2 = fit_r2
        ratio = None
        if trade_entry_r2 is not None and trade_entry_r2 > 0.0:
            ratio = fit_r2 / trade_entry_r2
        recent = [float(item["fit_r2"]) for item in rows[max(0, idx - 3) : idx + 1]]
        row.update(
            {
                "equity": equity,
                "peak_equity": peak,
                "drawdown": drawdown,
                "fit_r2_delta_1": delta1,
                "fit_r2_delta_2": None
                if idx < 2
                else fit_r2 - float(rows[idx - 2]["fit_r2"]),
                "fit_r2_delta_4": None
                if idx < 4
                else fit_r2 - float(rows[idx - 4]["fit_r2"]),
                "fit_r2_slope_4": _ols_slope(recent),
                "fit_r2_consecutive_declines": decline_run,
                "fit_r2_entry": trade_entry_r2,
                "fit_r2_ratio_to_entry": ratio,
            }
        )
        previous_r2 = fit_r2
        previous_position = position


def _episode_ranges(rows: list[dict[str, Any]]) -> list[tuple[int, int, int, int | None]]:
    episodes: list[tuple[int, int, int, int | None]] = []
    peak_idx = 0
    in_drawdown = False
    start_idx = 0
    trough_idx = 0
    for idx, row in enumerate(rows):
        drawdown = float(row["drawdown"])
        if drawdown >= -1e-15:
            if in_drawdown:
                episodes.append((peak_idx, start_idx, trough_idx, idx))
                in_drawdown = False
            peak_idx = idx
            continue
        if not in_drawdown:
            in_drawdown = True
            start_idx = idx
            trough_idx = idx
        elif float(row["drawdown"]) < float(rows[trough_idx]["drawdown"]):
            trough_idx = idx
    if in_drawdown:
        episodes.append((peak_idx, start_idx, trough_idx, None))
    return episodes


def _optional_float(row: dict[str, Any], name: str) -> float | None:
    value = row.get(name)
    return float(value) if isinstance(value, (int, float)) and math.isfinite(float(value)) else None


def _window_switches(rows: list[dict[str, Any]], start: int, end: int) -> int:
    values = [_optional_float(row, "authority_window_bars") for row in rows[start : end + 1]]
    previous: float | None = None
    switches = 0
    for value in values:
        if value is None:
            continue
        if previous is not None and value != previous:
            switches += 1
        previous = value
    return switches


def _first_index(rows: list[dict[str, Any]], start: int, end: int, predicate) -> int | None:
    for idx in range(start, end + 1):
        if predicate(rows[idx]):
            return idx
    return None


def _make_episode(
    rows: list[dict[str, Any]],
    span: tuple[int, int, int, int | None],
    rank: int,
) -> DrawdownEpisode:
    peak_idx, start_idx, trough_idx, recovery_idx = span
    start = rows[start_idx]
    trough = rows[trough_idx]
    segment = rows[start_idx : trough_idx + 1]
    r2_values = [float(row["fit_r2"]) for row in segment]
    first_down = _first_index(
        rows,
        start_idx,
        trough_idx,
        lambda row: row.get("fit_r2_delta_1") is not None and float(row["fit_r2_delta_1"]) < 0.0,
    )
    first_two_down = _first_index(
        rows,
        start_idx,
        trough_idx,
        lambda row: int(row.get("fit_r2_consecutive_declines") or 0) >= 2,
    )
    conflicts = sum(bool(row.get("direction_conflict")) for row in segment)
    exits = sum(bool(row.get("exit_trigger")) for row in segment)
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
        authority_window_at_start=_optional_float(start, "authority_window_bars"),
        authority_window_at_trough=_optional_float(trough, "authority_window_bars"),
        window_switches_to_trough=_window_switches(rows, start_idx, trough_idx),
        fit_r2_at_start=float(start["fit_r2"]),
        fit_r2_at_trough=float(trough["fit_r2"]),
        fit_r2_min_to_trough=min(r2_values),
        fit_r2_max_to_trough=max(r2_values),
        fit_r2_change_start_to_trough=float(trough["fit_r2"]) - float(start["fit_r2"]),
        fit_r2_peak_to_trough=max(r2_values) - float(trough["fit_r2"]),
        first_r2_down_timestamp=None if first_down is None else rows[first_down]["timestamp"].isoformat(),
        first_two_consecutive_r2_down_timestamp=None
        if first_two_down is None
        else rows[first_two_down]["timestamp"].isoformat(),
        r2_first_down_lead_bars_to_trough=None if first_down is None else trough_idx - first_down,
        r2_two_down_lead_bars_to_trough=None if first_two_down is None else trough_idx - first_two_down,
        path_efficiency_at_start=_optional_float(start, "path_efficiency"),
        path_efficiency_at_trough=_optional_float(trough, "path_efficiency"),
        slope_t_at_start=_optional_float(start, "slope_t"),
        slope_t_at_trough=_optional_float(trough, "slope_t"),
        direction_conflict_count_to_trough=conflicts,
        exit_trigger_count_to_trough=exits,
        slow_state_at_start=start.get("slow_state") if isinstance(start.get("slow_state"), str) else None,
        slow_state_at_trough=trough.get("slow_state") if isinstance(trough.get("slow_state"), str) else None,
        slow_fit_r2_at_start=_optional_float(start, "slow_fit_r2"),
        slow_fit_r2_at_trough=_optional_float(trough, "slow_fit_r2"),
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
            encoded = {
                key: value.isoformat() if isinstance(value, datetime) else value
                for key, value in row.items()
            }
            writer.writerow(encoded)


def run(input_path: Path, out_dir: Path, *, top_n: int) -> dict[str, Any]:
    if top_n < 1:
        raise ValueError("top_n must be positive")
    rows = _read_rows(input_path)
    _decorate(rows)
    spans = _episode_ranges(rows)
    spans_sorted = sorted(spans, key=lambda span: float(rows[span[2]]["drawdown"]))
    selected = spans_sorted[:top_n]
    episodes = [_make_episode(rows, span, rank + 1) for rank, span in enumerate(selected)]
    out_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(out_dir / "drawdown_timeseries.csv", rows)
    episode_rows = [asdict(episode) for episode in episodes]
    _write_csv(out_dir / "drawdown_atlas.csv", episode_rows)
    worst = min((float(row["drawdown"]) for row in rows), default=0.0)
    total_return = float(rows[-1]["equity"]) - 1.0
    summary = {
        "schema_id": "ols_drawdown_atlas_d0@1.0",
        "input": str(input_path),
        "row_count": len(rows),
        "episode_count": len(spans),
        "reported_episode_count": len(episodes),
        "total_return": total_return,
        "maximum_drawdown": worst,
        "final_equity": float(rows[-1]["equity"]),
        "required_return_semantics": "strategy_return is externally supplied and already reflects frozen execution/cost convention",
        "diagnostic_only": True,
        "changes_entry_exit_routing_sizing_or_leverage": False,
        "worst_episodes": episode_rows,
    }
    (out_dir / "drawdown_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="causal per-bar OLS trace CSV")
    parser.add_argument("--out-dir", required=True, type=Path, help="output directory")
    parser.add_argument("--top-n", type=int, default=10, help="number of worst episodes to report")
    args = parser.parse_args()
    summary = run(args.input, args.out_dir, top_n=args.top_n)
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
