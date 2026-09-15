"""V0800-E deterministic morphology-only visual audit producer.

No future bars after confirmation, returns, PnL, positions, costs, trading, 2026,
or parameter promotion authority.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import math
from pathlib import Path

import pandas as pd

from two_wave_v0800_c_prefix_replay import PrefixReplayAEngine
from two_wave_v0800_d_direction_grid import build_grid
from two_wave_v0800_scale_map import DATA_BYTES, DATA_FILE, DATA_SHA256, SOURCE_REF, SOURCE_REPO, load_bars
from two_wave_v0800_semantics import channel_geometry

TAUS = (0.05, 0.10, 0.15, 0.20)
KAPPAS = (1.25, 1.50, 2.00)
YEARS = tuple(range(2015, 2021))
TARGET_PER_CELL = 2
CATEGORY_PRIORITY = ("stable_consensus", "kappa_sensitive", "tau_sensitive", "sign_conflict", "persistent_uncertain")
CASE_COLUMNS = [
    "category", "year", "selection_hash", "pair_id", "previous_wave_id", "current_wave_id",
    "confirmation_bar", "confirmation_time", "previous_start_bar", "previous_high_bar", "shared_anchor_bar",
    "current_high_bar", "current_end_bar", "previous_duration", "current_duration", "duration_ratio",
    "g_previous", "g_current", "slope_magnitude_ratio", "state_matrix", "svg_file",
]


def state_key(tau: float, kappa: float) -> str:
    return f"tau={tau:.2f}|kappa={kappa:.2f}"


def classify_category(matrix: dict[str, dict]) -> str | None:
    states = [matrix[state_key(t, k)]["state"] for t in TAUS for k in KAPPAS]
    if len(set(states)) == 1 and states[0] != "Uncertain":
        return "stable_consensus"
    if matrix[state_key(0.10, 1.25)]["state"] == "Uncertain" and matrix[state_key(0.10, 2.00)]["state"] in ("UpTrend", "DownTrend"):
        return "kappa_sensitive"
    if matrix[state_key(0.05, 1.50)]["state"] != matrix[state_key(0.20, 1.50)]["state"]:
        return "tau_sensitive"
    a = matrix[state_key(0.10, 1.25)]
    if {a["previous_descriptor"], a["current_descriptor"]} == {"UP", "DOWN"}:
        return "sign_conflict"
    if all(state == "Uncertain" for state in states):
        return "persistent_uncertain"
    return None


def selection_hash(category: str, year: int, pair_id: str) -> str:
    return hashlib.sha256(f"V0800-E-v1|{category}|{year}|{pair_id}".encode("utf-8")).hexdigest()


def pair_records(grid: pd.DataFrame) -> list[dict]:
    result: list[dict] = []
    for pair_id, sub in grid.groupby("pair_id", sort=False):
        matrix = {}
        for r in sub.itertuples(index=False):
            matrix[state_key(float(r.tau), float(r.kappa))] = {
                "state": str(r.state),
                "previous_descriptor": str(r.previous_descriptor),
                "current_descriptor": str(r.current_descriptor),
            }
        if len(matrix) != 12:
            raise RuntimeError("v0800_e_incomplete_grid")
        first = sub.iloc[0]
        category = classify_category(matrix)
        result.append({
            "pair_id": str(pair_id), "year": int(first.year), "category": category,
            "previous_wave_id": str(first.previous_wave_id), "current_wave_id": str(first.current_wave_id),
            "confirmation_bar": int(first.confirmation_bar), "confirmation_time": str(first.confirmation_time),
            "previous_duration": int(first.previous_duration), "current_duration": int(first.current_duration),
            "duration_ratio": float(first.duration_ratio), "g_previous": float(first.g_previous),
            "g_current": float(first.g_current), "slope_magnitude_ratio": float(first.slope_magnitude_ratio),
            "matrix": matrix,
        })
    return result


def select_cases(records: list[dict]) -> tuple[list[dict], dict]:
    selected: list[dict] = []
    support: dict[str, dict[str, dict[str, int | bool]]] = {}
    for category in CATEGORY_PRIORITY:
        support[category] = {}
        for year in YEARS:
            candidates = [r for r in records if r["category"] == category and r["year"] == year]
            for r in candidates:
                r["selection_hash"] = selection_hash(category, year, r["pair_id"])
            candidates.sort(key=lambda r: (r["selection_hash"], r["pair_id"]))
            chosen = candidates[:TARGET_PER_CELL]
            selected.extend(chosen)
            support[category][str(year)] = {
                "available": len(candidates), "selected": len(chosen), "shortage": len(candidates) < TARGET_PER_CELL,
            }
    selected.sort(key=lambda r: (CATEGORY_PRIORITY.index(r["category"]), r["year"], r["selection_hash"], r["pair_id"]))
    return selected, support


def esc(value) -> str:
    return html.escape(str(value), quote=True)


def render_svg(bars: pd.DataFrame, previous, current, record: dict, path: Path) -> None:
    start = int(previous.start_bar)
    confirmation = int(record["confirmation_bar"])
    if confirmation < int(current.end_bar) or confirmation >= len(bars):
        raise RuntimeError("v0800_e_invalid_confirmation_window")
    window = bars.iloc[start : confirmation + 1]
    if len(window) != confirmation - start + 1:
        raise RuntimeError("v0800_e_incomplete_visual_window")
    width, height = 1200, 760
    left, right, top, bottom = 60.0, 850.0, 55.0, 535.0
    lows = window.low.astype(float).tolist(); highs = window.high.astype(float).tolist()
    pmin, pmax = min(lows), max(highs)
    if not (math.isfinite(pmin) and math.isfinite(pmax) and pmax > pmin):
        raise RuntimeError("v0800_e_invalid_price_range")
    def x(i: int) -> float:
        return left + (i - start) / max(1, confirmation - start) * (right - left)
    def y(v: float) -> float:
        return bottom - (v - pmin) / (pmax - pmin) * (bottom - top)
    prev_g, cur_g = channel_geometry(previous), channel_geometry(current)
    matrix = record["matrix"]
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        f'<title>{esc(record["category"])} | {esc(record["pair_id"])}</title>',
        f'<metadata data-category="{esc(record["category"])}" data-pair-id="{esc(record["pair_id"])}" data-first-bar="{start}" data-confirmation-bar="{confirmation}"/>',
        '<rect x="0" y="0" width="1200" height="760" fill="white"/>',
        f'<text x="60" y="28" font-size="16">V0800-E {esc(record["category"])} | {esc(record["pair_id"])}</text>',
    ]
    for i in range(start, confirmation + 1):
        row = bars.iloc[i]
        xi = x(i)
        lines.append(f'<g class="bar" data-bar-index="{i}"><line x1="{xi:.3f}" y1="{y(float(row.high)):.3f}" x2="{xi:.3f}" y2="{y(float(row.low)):.3f}" stroke="#777" stroke-width="1"/><circle cx="{xi:.3f}" cy="{y(float(row.close)):.3f}" r="1.4" fill="#222"/></g>')
    def channel(wave, geom, prefix: str):
        x0, x1 = x(int(wave.start_bar)), x(int(wave.end_bar))
        b0, b1 = y(math.exp(float(geom.bottom_start))), y(math.exp(float(geom.bottom_end)))
        t0, t1 = y(math.exp(float(geom.top_start))), y(math.exp(float(geom.top_end)))
        lines.append(f'<line class="channel {prefix}-bottom" x1="{x0:.3f}" y1="{b0:.3f}" x2="{x1:.3f}" y2="{b1:.3f}" stroke="#1565c0" stroke-width="2"/>')
        lines.append(f'<line class="channel {prefix}-top" x1="{x0:.3f}" y1="{t0:.3f}" x2="{x1:.3f}" y2="{t1:.3f}" stroke="#1565c0" stroke-width="1" stroke-dasharray="5,4"/>')
    channel(previous, prev_g, "previous"); channel(current, cur_g, "current")
    pivots = [(previous.start_bar, previous.start_low, "L0"), (previous.high_bar, previous.high, "H0"), (previous.end_bar, previous.end_low, "L1"), (current.high_bar, current.high, "H1"), (current.end_bar, current.end_low, "L2")]
    for bi, price, label in pivots:
        lines.append(f'<g class="pivot" data-pivot="{label}" data-bar-index="{int(bi)}"><circle cx="{x(int(bi)):.3f}" cy="{y(float(price)):.3f}" r="4" fill="#b71c1c"/><text x="{x(int(bi))+5:.3f}" y="{y(float(price))-5:.3f}" font-size="12">{label}</text></g>')
    lines.append(f'<line class="confirmation" data-bar-index="{confirmation}" x1="{x(confirmation):.3f}" y1="{top:.3f}" x2="{x(confirmation):.3f}" y2="{bottom:.3f}" stroke="#2e7d32" stroke-width="2" stroke-dasharray="3,3"/>')
    info = [
        f'category: {record["category"]}', f'year: {record["year"]}',
        f'durations: {record["previous_duration"]} / {record["current_duration"]}',
        f'duration ratio: {record["duration_ratio"]:.4f}', f'g prev/current: {record["g_previous"]:.4f} / {record["g_current"]:.4f}',
        f'slope ratio: {record["slope_magnitude_ratio"]:.4f}', f'confirmation bar: {confirmation}',
    ]
    for j, txt in enumerate(info):
        lines.append(f'<text x="885" y="{70 + 22*j}" font-size="13">{esc(txt)}</text>')
    lines.append('<text x="885" y="245" font-size="14">4×3 state matrix</text>')
    y0 = 270
    for ti, tau in enumerate(TAUS):
        for ki, kappa in enumerate(KAPPAS):
            state = matrix[state_key(tau, kappa)]["state"]
            lines.append(f'<text x="{885 + 100*ki}" y="{y0 + 24*ti}" font-size="12">t{tau:.2f}/k{kappa:.2f}: {esc(state)}</text>')
    lines.append('<text x="60" y="585" font-size="12">Window is causally bounded: previous A-wave start through current A-wave confirmation bar, inclusive. No post-confirmation bars.</text>')
    lines.append('</svg>')
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(inputs: Path, out: Path) -> None:
    bars = load_bars(inputs / DATA_FILE)
    grid, eligible_count, strict_count = build_grid(bars)
    if eligible_count != 924 or strict_count != 2358:
        raise RuntimeError("v0800_e_parent_universe_drift")
    records = pair_records(grid)
    selected, support = select_cases(records)
    engine = PrefixReplayAEngine(bars); engine.run()
    wave_by_id = {r.wave.wave_id: r.wave for r in engine.waves}
    visuals = out / "visuals"; visuals.mkdir()
    case_rows = []
    manifest_cases = []
    for rec in selected:
        previous = wave_by_id[rec["previous_wave_id"]]; current = wave_by_id[rec["current_wave_id"]]
        if previous.end_bar != current.start_bar or int(current.confirmation_bar) != int(rec["confirmation_bar"]):
            raise RuntimeError("v0800_e_pair_identity_drift")
        filename = f'{rec["category"]}__{rec["year"]}__{rec["selection_hash"][:12]}__{rec["pair_id"].replace("/", "_")}.svg'
        render_svg(bars, previous, current, rec, visuals / filename)
        matrix_json = json.dumps({k: v["state"] for k, v in sorted(rec["matrix"].items())}, sort_keys=True, separators=(",", ":"))
        row = {
            "category": rec["category"], "year": rec["year"], "selection_hash": rec["selection_hash"], "pair_id": rec["pair_id"],
            "previous_wave_id": rec["previous_wave_id"], "current_wave_id": rec["current_wave_id"], "confirmation_bar": rec["confirmation_bar"],
            "confirmation_time": rec["confirmation_time"], "previous_start_bar": int(previous.start_bar), "previous_high_bar": int(previous.high_bar),
            "shared_anchor_bar": int(previous.end_bar), "current_high_bar": int(current.high_bar), "current_end_bar": int(current.end_bar),
            "previous_duration": rec["previous_duration"], "current_duration": rec["current_duration"], "duration_ratio": rec["duration_ratio"],
            "g_previous": rec["g_previous"], "g_current": rec["g_current"], "slope_magnitude_ratio": rec["slope_magnitude_ratio"],
            "state_matrix": matrix_json, "svg_file": f"visuals/{filename}",
        }
        case_rows.append(row)
        manifest_cases.append({"category": rec["category"], "year": rec["year"], "pair_id": rec["pair_id"], "selection_hash": rec["selection_hash"], "svg_file": row["svg_file"], "first_bar": int(previous.start_bar), "confirmation_bar": int(rec["confirmation_bar"]), "rendered_bar_count": int(rec["confirmation_bar"] - previous.start_bar + 1)})
    pd.DataFrame(case_rows, columns=CASE_COLUMNS).to_csv(out / "AUDIT_CASES.csv", index=False)
    manifest = {"schema_id": "csi1000.two_wave_v0800_e_audit_manifest@1.0", "study": "V0800-E_MORPHOLOGY_VISUAL_AUDIT", "category_priority": list(CATEGORY_PRIORITY), "target_per_category_year": TARGET_PER_CELL, "support": support, "selected_case_count": len(case_rows), "cases": manifest_cases, "bars_after_confirmation_shown": False, "future_outcome_used": False}
    (out / "AUDIT_MANIFEST.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report = ["# V0800-E deterministic morphology visual audit pack", "", f"Eligible rho=sqrt(2) strict pairs: {eligible_count}.", f"Selected cases: {len(case_rows)} (maximum 60).", "", "No chart contains any bar after the current A-wave confirmation bar. No future return or trading metric is present.", "", "## Category-year support"]
    for category in CATEGORY_PRIORITY:
        for year in YEARS:
            cell = support[category][str(year)]
            report.append(f"- {category} / {year}: available={cell['available']}, selected={cell['selected']}, shortage={str(cell['shortage']).lower()}")
    report.extend(["", "## Human review boundary", "", "Review geometry only. Do not infer a parameter winner from coverage, decisiveness, or any later market movement. A separate adjudication is required."])
    (out / "AUDIT_REPORT.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    category_totals = {c: int(sum(1 for r in records if r["category"] == c)) for c in CATEGORY_PRIORITY}
    summary = {"schema_id": "csi1000.two_wave_v0800_e_summary@1.0", "study": "V0800-E_MORPHOLOGY_VISUAL_AUDIT", "bars_read": len(bars), "strict_pair_count": strict_count, "eligible_same_scale_pair_count": eligible_count, "category_totals": category_totals, "selected_case_count": len(case_rows), "tau_winner": None, "kappa_winner": None, "automatic_parameter_promotion": False, "visual_audit_complete": True, "future_bars_after_confirmation_shown": False, "future_outcome_used": False, "returns_used": False, "pnl_used": False, "positions_used": False, "year_2026_read": False, "direction_acceptance": False, "state_publication_authority": False, "trade_authority": False, "production_authority": False, "post_audit_adjudication_required": True}
    (out / "SUMMARY.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    receipt = {"schema_id": "csi1000.two_wave_v0800_e_input@1.0", "source_repository": SOURCE_REPO, "source_ref": SOURCE_REF, "file": DATA_FILE, "bytes": DATA_BYTES, "sha256": DATA_SHA256, "rows_read": len(bars), "min_timestamp": str(bars.timestamp.min()), "max_timestamp": str(bars.timestamp.max()), "allowed_start": "2015-01-05", "allowed_end": "2020-12-31", "substitute_data_used": False, "year_2026_read": False}
    (out / "INPUT_RECEIPT.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> None:
    p = argparse.ArgumentParser(); p.add_argument("--inputs", required=True); p.add_argument("--out", required=True); a = p.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=False); run(Path(a.inputs), out)


if __name__ == "__main__": main()
