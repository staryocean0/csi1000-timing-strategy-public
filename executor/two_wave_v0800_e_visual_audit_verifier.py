"""Independent verifier for V0800-E morphology visual audit."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import xml.etree.ElementTree as ET
from pathlib import Path

import pandas as pd

from two_wave_v0800_scale_map import DATA_BYTES, DATA_FILE, DATA_SHA256, TemporalMaturityAEngine, load_bars
from two_wave_v0800_semantics import channel_geometry, duration_ratio, same_scale

RHO = math.sqrt(2.0)
TAUS = (0.05, 0.10, 0.15, 0.20)
KAPPAS = (1.25, 1.50, 2.00)
YEARS = tuple(range(2015, 2021))
TARGET_PER_CELL = 2
CATEGORY_PRIORITY = ("stable_consensus", "kappa_sensitive", "tau_sensitive", "sign_conflict", "persistent_uncertain")
REQUIRED = {"AUDIT_CASES.csv", "AUDIT_MANIFEST.json", "AUDIT_REPORT.md", "SUMMARY.json", "INPUT_RECEIPT.json"}


def fail(reason: str) -> None:
    print(json.dumps({"status": "failed", "reason": reason}, sort_keys=True)); raise SystemExit(1)


def descriptor(g: float, tau: float) -> str:
    if abs(g) <= tau + 1e-15: return "RANGE"
    return "UP" if g > 0 else "DOWN"


def slope_ratio(a: float, b: float) -> float:
    aa, bb = abs(a), abs(b)
    return math.inf if min(aa, bb) <= 0 else max(aa, bb) / min(aa, bb)


def state(gp: float, gc: float, tau: float, kappa: float) -> tuple[str, str, str]:
    dp, dc = descriptor(gp, tau), descriptor(gc, tau)
    r = slope_ratio(gp, gc)
    if dp == dc == "RANGE": s = "Range"
    elif dp == dc == "UP" and r <= kappa + 1e-12: s = "UpTrend"
    elif dp == dc == "DOWN" and r <= kappa + 1e-12: s = "DownTrend"
    else: s = "Uncertain"
    return dp, dc, s


def key(tau: float, kappa: float) -> str:
    return f"tau={tau:.2f}|kappa={kappa:.2f}"


def category(matrix: dict[str, dict]) -> str | None:
    states = [matrix[key(t, k)]["state"] for t in TAUS for k in KAPPAS]
    if len(set(states)) == 1 and states[0] != "Uncertain": return "stable_consensus"
    if matrix[key(0.10, 1.25)]["state"] == "Uncertain" and matrix[key(0.10, 2.00)]["state"] in ("UpTrend", "DownTrend"): return "kappa_sensitive"
    if matrix[key(0.05, 1.50)]["state"] != matrix[key(0.20, 1.50)]["state"]: return "tau_sensitive"
    a = matrix[key(0.10, 1.25)]
    if {a["previous_descriptor"], a["current_descriptor"]} == {"UP", "DOWN"}: return "sign_conflict"
    if all(s == "Uncertain" for s in states): return "persistent_uncertain"
    return None


def selection_hash(cat: str, year: int, pair_id: str) -> str:
    return hashlib.sha256(f"V0800-E-v1|{cat}|{year}|{pair_id}".encode()).hexdigest()


def expected_records(bars: pd.DataFrame) -> tuple[list[dict], int, int]:
    records, _pivots, _resets = TemporalMaturityAEngine(bars).run()
    by_end: dict[tuple[int, int], object] = {}
    strict = 0; eligible = 0; out = []
    for rec in records:
        cur = rec.wave
        prev_rec = by_end.get((rec.epoch, cur.start_bar))
        if prev_rec is not None:
            strict += 1
            prev = prev_rec.wave
            if same_scale(prev.duration, cur.duration, RHO):
                eligible += 1
                gp = float(channel_geometry(prev).normalized_migration); gc = float(channel_geometry(cur).normalized_migration)
                matrix = {}
                for tau in TAUS:
                    for kappa in KAPPAS:
                        dp, dc, s = state(gp, gc, tau, kappa)
                        matrix[key(tau, kappa)] = {"state": s, "previous_descriptor": dp, "current_descriptor": dc}
                year = int(pd.Timestamp(rec.confirmation_time).year)
                out.append({"pair_id": f"{prev.wave_id}__{cur.wave_id}", "year": year, "category": category(matrix), "previous_wave_id": prev.wave_id, "current_wave_id": cur.wave_id, "confirmation_bar": int(cur.confirmation_bar), "confirmation_time": str(rec.confirmation_time), "previous_start_bar": int(prev.start_bar), "previous_high_bar": int(prev.high_bar), "shared_anchor_bar": int(prev.end_bar), "current_high_bar": int(cur.high_bar), "current_end_bar": int(cur.end_bar), "previous_duration": int(prev.duration), "current_duration": int(cur.duration), "duration_ratio": float(duration_ratio(prev.duration, cur.duration)), "g_previous": gp, "g_current": gc, "slope_magnitude_ratio": float(slope_ratio(gp, gc)), "matrix": matrix})
        by_end[(rec.epoch, cur.end_bar)] = rec
    return out, strict, eligible


def expected_selection(records: list[dict]) -> tuple[list[dict], dict]:
    chosen = []; support = {}
    for cat in CATEGORY_PRIORITY:
        support[cat] = {}
        for year in YEARS:
            candidates = [dict(r) for r in records if r["category"] == cat and r["year"] == year]
            for r in candidates: r["selection_hash"] = selection_hash(cat, year, r["pair_id"])
            candidates.sort(key=lambda r: (r["selection_hash"], r["pair_id"]))
            part = candidates[:TARGET_PER_CELL]; chosen.extend(part)
            support[cat][str(year)] = {"available": len(candidates), "selected": len(part), "shortage": len(candidates) < TARGET_PER_CELL}
    chosen.sort(key=lambda r: (CATEGORY_PRIORITY.index(r["category"]), r["year"], r["selection_hash"], r["pair_id"]))
    return chosen, support


def verify_svg(path: Path, first: int, confirmation: int) -> None:
    try: root = ET.parse(path).getroot()
    except Exception: fail("svg_parse_failed")
    bars = []
    for elem in root.iter():
        if elem.tag.endswith("g") and elem.attrib.get("class") == "bar":
            try: bars.append(int(elem.attrib["data-bar-index"]))
            except Exception: fail("svg_bar_index_invalid")
    expected = list(range(first, confirmation + 1))
    if bars != expected: fail("svg_bar_window_mismatch")
    if any(i > confirmation for i in bars): fail("svg_future_bar_visible")
    text = path.read_text(encoding="utf-8").lower()
    for token in ("future_return", "pnl", "position_size", "transaction_cost"):
        if token in text: fail("svg_forbidden_outcome_content")


def main() -> None:
    p = argparse.ArgumentParser(); p.add_argument("--inputs", required=True); p.add_argument("--results", required=True); a = p.parse_args()
    inputs, results = Path(a.inputs), Path(a.results)
    if not REQUIRED.issubset({x.name for x in results.iterdir() if x.is_file()}): fail("required_output_missing")
    data = inputs / DATA_FILE
    if not data.is_file() or data.stat().st_size != DATA_BYTES: fail("input_identity_mismatch")
    bars = load_bars(data)
    records, strict, eligible = expected_records(bars)
    if strict != 2358 or eligible != 924: fail("parent_universe_mismatch")
    expected, support = expected_selection(records)
    got = pd.read_csv(results / "AUDIT_CASES.csv")
    if len(got) != len(expected): fail("selected_case_count_mismatch")
    for i, exp in enumerate(expected):
        row = got.iloc[i]
        for col in ("category", "selection_hash", "pair_id", "previous_wave_id", "current_wave_id", "confirmation_time"):
            if str(row[col]) != str(exp[col]): fail(f"case_{col}_mismatch")
        for col in ("year", "confirmation_bar", "previous_start_bar", "previous_high_bar", "shared_anchor_bar", "current_high_bar", "current_end_bar", "previous_duration", "current_duration"):
            if int(row[col]) != int(exp[col]): fail(f"case_{col}_mismatch")
        for col in ("duration_ratio", "g_previous", "g_current", "slope_magnitude_ratio"):
            if abs(float(row[col]) - float(exp[col])) > 1e-12: fail(f"case_{col}_mismatch")
        expected_matrix = json.dumps({k: v["state"] for k, v in sorted(exp["matrix"].items())}, sort_keys=True, separators=(",", ":"))
        if str(row["state_matrix"]) != expected_matrix: fail("case_state_matrix_mismatch")
        svg = results / str(row["svg_file"])
        if not svg.is_file(): fail("svg_missing")
        verify_svg(svg, int(exp["previous_start_bar"]), int(exp["confirmation_bar"]))
    manifest = json.loads((results / "AUDIT_MANIFEST.json").read_text())
    if manifest.get("support") != support or int(manifest.get("selected_case_count", -1)) != len(expected): fail("manifest_support_or_count_mismatch")
    if manifest.get("bars_after_confirmation_shown") is not False or manifest.get("future_outcome_used") is not False: fail("manifest_scope_violation")
    summary = json.loads((results / "SUMMARY.json").read_text())
    if summary.get("study") != "V0800-E_MORPHOLOGY_VISUAL_AUDIT" or int(summary.get("strict_pair_count", -1)) != 2358 or int(summary.get("eligible_same_scale_pair_count", -1)) != 924: fail("summary_identity_mismatch")
    expected_totals = {c: sum(1 for r in records if r["category"] == c) for c in CATEGORY_PRIORITY}
    if summary.get("category_totals") != expected_totals or int(summary.get("selected_case_count", -1)) != len(expected): fail("summary_category_mismatch")
    for key_name in ("automatic_parameter_promotion", "future_bars_after_confirmation_shown", "future_outcome_used", "returns_used", "pnl_used", "positions_used", "year_2026_read", "direction_acceptance", "state_publication_authority", "trade_authority", "production_authority"):
        if summary.get(key_name) is not False: fail("authority_or_scope_violation")
    if summary.get("tau_winner") is not None or summary.get("kappa_winner") is not None or summary.get("post_audit_adjudication_required") is not True: fail("parameter_promotion_violation")
    receipt = json.loads((results / "INPUT_RECEIPT.json").read_text())
    if receipt.get("sha256") != DATA_SHA256 or int(receipt.get("bytes", -1)) != DATA_BYTES or int(receipt.get("rows_read", -1)) != len(bars) or receipt.get("year_2026_read") is not False or receipt.get("substitute_data_used") is not False: fail("input_receipt_mismatch")
    print(json.dumps({"status": "passed", "selected_case_set_exact_match": True, "independent_category_assignment": True, "independent_hash_sampling": True, "svg_future_bar_violations": 0, "selected_case_count": len(expected), "future_outcome_used": False, "direction_authority": False, "trade_authority": False, "production_authority": False}, sort_keys=True))


if __name__ == "__main__": main()
