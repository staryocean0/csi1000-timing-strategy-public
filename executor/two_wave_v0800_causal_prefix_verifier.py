"""Independent verifier for Two-Wave v0.8.0 V0800-C causal prefix replay."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

DATA_FILE = "5m_offset_0.parquet"
DATA_BYTES = 3351411
DATA_SHA256 = "bea21fa9dd9532e21605511e07561b33d5569f86f69f5a487507531593b14c48"
RHOS = (1.25, 4.0 / 3.0, math.sqrt(2.0), 1.5)
MIN_LEG = 4
MAX_UNFINISHED_LEG = 48
FIXED_ROW_STRIDE = 4096
EVENT_WAVE_STRIDE = 256
SUMMARY_SCHEMA = "csi1000.two_wave_v0800_causal_prefix@1.0"
FORBIDDEN_TOKENS = ("return", "pnl", "position", "buy", "sell", "cost", "execution")


def fail(reason: str) -> None:
    print(json.dumps({"status": "failed", "reason": reason}, sort_keys=True))
    raise SystemExit(1)


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def stable_hash(value: object) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _column(frame: pd.DataFrame, name: str) -> str | None:
    names = {str(c).lower(): str(c) for c in frame.columns}
    return names.get(name.lower())


def load_bars(path: Path) -> pd.DataFrame:
    if not path.is_file() or path.stat().st_size != DATA_BYTES or sha256(path) != DATA_SHA256:
        fail("input_identity_mismatch")
    raw = pd.read_parquet(path)
    time_col = _column(raw, "timestamp")
    close_col = _column(raw, "close")
    if time_col is None or close_col is None:
        fail("required_bar_column_missing")
    frame = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(raw[time_col], errors="coerce"),
            "close": pd.to_numeric(raw[close_col], errors="coerce"),
        }
    )
    if frame.isna().any().any() or (frame.close <= 0).any():
        fail("invalid_bar_value")
    if frame.timestamp.duplicated().any() or not frame.timestamp.is_monotonic_increasing:
        fail("timestamp_order_invalid")
    if getattr(frame.timestamp.dt, "tz", None) is not None:
        naive = frame.timestamp.dt.tz_localize(None)
    else:
        naive = frame.timestamp
    frame = frame[(naive >= pd.Timestamp("2015-01-05")) & (naive < pd.Timestamp("2021-01-01"))].copy()
    frame = frame.reset_index(drop=True)
    if len(frame) != 70114:
        fail("unexpected_development_row_count")
    return frame


@dataclass(frozen=True)
class Wave:
    wave_id: str
    epoch: int
    start_bar: int
    high_bar: int
    end_bar: int
    confirmation_bar: int

    @property
    def duration(self) -> int:
        return self.end_bar - self.start_bar


class IndependentTemporalMaturityEngine:
    """Minimal independent v0.4.3 timing implementation using close pivots only."""

    def __init__(self, bars: pd.DataFrame):
        self.bars = bars
        self.mode: int | None = None
        self.candidate: tuple[int, float, str] | None = None
        self.counter: tuple[int, float, str] | None = None
        self.boot_low: tuple[int, float, str] | None = None
        self.boot_high: tuple[int, float, str] | None = None
        self.last_pivot_bar: int | None = None
        self.epoch = 0
        self.chain: list[dict] = []
        self.waves: list[Wave] = []

    def point(self, i: int, kind: str) -> tuple[int, float, str]:
        return i, float(self.bars.iloc[i].close), kind

    def confirm(self, point: tuple[int, float, str], now: int, censored: bool = False) -> None:
        occurrence, _, kind = point
        self.last_pivot_bar = occurrence
        if censored:
            return
        record = {"kind": kind, "occurrence_bar": occurrence, "confirmation_bar": now, "epoch": self.epoch}
        self.chain.append(record)
        if len(self.chain) < 3:
            return
        trio = self.chain[-3:]
        if [p["kind"] for p in trio] != ["low", "high", "low"]:
            return
        s, h, e = [int(p["occurrence_bar"]) for p in trio]
        self.waves.append(
            Wave(
                wave_id=f"e{self.epoch}-a{len(self.waves):06d}",
                epoch=self.epoch,
                start_bar=s,
                high_bar=h,
                end_bar=e,
                confirmation_bar=now,
            )
        )

    def reset(self, i: int) -> None:
        self.epoch += 1
        self.mode = None
        self.last_pivot_bar = None
        self.candidate = self.counter = None
        self.chain = []
        self.boot_low = self.point(i, "low")
        self.boot_high = self.point(i, "high")

    def bootstrap(self, i: int) -> None:
        close = float(self.bars.iloc[i].close)
        if close < self.boot_low[1]:
            self.boot_low = self.point(i, "low")
        if close > self.boot_high[1]:
            self.boot_high = self.point(i, "high")
        low, high = self.boot_low, self.boot_high
        if high[0] - low[0] >= MIN_LEG:
            self.confirm(low, i, True)
            self.mode = 1
            self.candidate = high
            self.counter = None
        elif low[0] - high[0] >= MIN_LEG:
            self.confirm(high, i, True)
            self.mode = -1
            self.candidate = low
            self.counter = None

    def run(self) -> list[Wave]:
        for i in range(len(self.bars)):
            if self.boot_low is None:
                self.boot_low = self.point(i, "low")
                self.boot_high = self.point(i, "high")
                continue
            if self.last_pivot_bar is not None and i - self.last_pivot_bar > MAX_UNFINISHED_LEG:
                self.reset(i)
                continue
            if self.mode is None:
                self.bootstrap(i)
                continue
            close = float(self.bars.iloc[i].close)
            candidate_close = self.candidate[1]
            if self.mode * (close - candidate_close) > 0:
                self.candidate = self.point(i, "high" if self.mode > 0 else "low")
                self.counter = None
                continue
            if self.mode * (close - candidate_close) < 0:
                kind = "low" if self.mode > 0 else "high"
                if self.counter is None or self.mode * (close - self.counter[1]) < 0:
                    self.counter = self.point(i, kind)
            if self.counter is not None and self.counter[0] - self.candidate[0] >= MIN_LEG:
                old = self.candidate
                new = self.counter
                self.confirm(old, i)
                self.mode *= -1
                self.candidate = new
                self.counter = None
        return self.waves


def same_scale(a: int, b: int, rho: float) -> bool:
    return max(a, b) / min(a, b) <= rho + 1e-12


def rho_key(rho: float) -> str:
    return f"{rho:.12g}"


def wave_row(w: Wave) -> tuple:
    return (w.wave_id, w.epoch, w.start_bar, w.high_bar, w.end_bar, w.confirmation_bar, w.duration)


def pair_ledger(waves: list[Wave]) -> tuple[list[tuple], dict[str, int]]:
    rows = []
    violations = {
        "future_reference_violations": 0,
        "predecessor_after_current_violations": 0,
        "nearer_eligible_predecessor_skip_violations": 0,
    }
    for i, current in enumerate(waves):
        if current.end_bar > current.confirmation_bar:
            violations["future_reference_violations"] += 1
        for rho in RHOS:
            previous = None
            for candidate in reversed(waves[:i]):
                if candidate.epoch != current.epoch:
                    continue
                if candidate.confirmation_bar > current.confirmation_bar:
                    continue
                if candidate.end_bar > current.start_bar:
                    continue
                if same_scale(candidate.duration, current.duration, rho):
                    previous = candidate
                    break
            if previous is None:
                continue
            if previous.confirmation_bar > current.confirmation_bar:
                violations["future_reference_violations"] += 1
            if previous.end_bar > current.start_bar:
                violations["predecessor_after_current_violations"] += 1
            for candidate in waves[:i]:
                if candidate.epoch != current.epoch:
                    continue
                if candidate.confirmation_bar > current.confirmation_bar:
                    continue
                if candidate.end_bar > current.start_bar or candidate.end_bar <= previous.end_bar:
                    continue
                if same_scale(candidate.duration, current.duration, rho):
                    violations["nearer_eligible_predecessor_skip_violations"] += 1
                    break
            rows.append(
                (
                    rho_key(rho), current.wave_id, previous.wave_id, current.epoch,
                    current.start_bar, current.end_bar, current.confirmation_bar, current.duration,
                    previous.start_bar, previous.end_bar, previous.confirmation_bar, previous.duration,
                )
            )
    return rows, violations


def checkpoints(bars: pd.DataFrame, full: list[Wave]) -> dict[int, set[str]]:
    n = len(bars)
    out: dict[int, set[str]] = {}
    def add(length: int, reason: str) -> None:
        if 1 <= int(length) <= n:
            out.setdefault(int(length), set()).add(reason)
    for length in range(FIXED_ROW_STRIDE, n, FIXED_ROW_STRIDE):
        add(length, "fixed_stride")
    years = bars.timestamp.dt.year
    for year in range(2015, 2021):
        positions = bars.index[years.eq(year)]
        if len(positions):
            add(int(positions.max()) + 1, f"year_end_{year}")
    if full:
        for ordinal in range(0, len(full), EVENT_WAVE_STRIDE):
            add(full[ordinal].confirmation_bar + 1, f"wave_ordinal_{ordinal}")
        add(full[-1].confirmation_bar + 1, "final_wave_confirmation")
    add(n, "full_rows")
    return dict(sorted(out.items()))


def mismatch(a: list[tuple], b: list[tuple]) -> int:
    if a == b:
        return 0
    common = min(len(a), len(b))
    return sum(a[i] != b[i] for i in range(common)) + abs(len(a) - len(b))


def recompute(bars: pd.DataFrame) -> tuple[list[dict], dict, dict]:
    full = IndependentTemporalMaturityEngine(bars).run()
    full_waves = [wave_row(w) for w in full]
    full_pairs, full_v = pair_ledger(full)
    audit = []
    checkpoint_hashes = {}
    totals = {**full_v, "wave_prefix_mismatches": 0, "pair_prefix_mismatches": 0, "ledger_hash_mismatches": 0}
    confirmation = {row[0]: row[5] for row in full_waves}
    for length, reasons in checkpoints(bars, full).items():
        prefix = IndependentTemporalMaturityEngine(bars.iloc[:length].copy()).run()
        aw = [wave_row(w) for w in prefix]
        ap, pv = pair_ledger(prefix)
        ew = [row for row in full_waves if row[5] < length]
        ep = [row for row in full_pairs if confirmation[row[1]] < length]
        wm = mismatch(aw, ew); pm = mismatch(ap, ep)
        awh = stable_hash(aw); ewh = stable_hash(ew); aph = stable_hash(ap); eph = stable_hash(ep)
        hm = int(awh != ewh) + int(aph != eph)
        for key in ("future_reference_violations", "predecessor_after_current_violations", "nearer_eligible_predecessor_skip_violations"):
            totals[key] += int(pv[key])
        totals["wave_prefix_mismatches"] += wm
        totals["pair_prefix_mismatches"] += pm
        totals["ledger_hash_mismatches"] += hm
        passed = wm == pm == hm == 0 and all(int(v) == 0 for v in pv.values())
        audit.append({
            "prefix_length": length,
            "reasons": ";".join(sorted(reasons)),
            "actual_wave_count": len(aw), "expected_wave_count": len(ew),
            "actual_pair_count": len(ap), "expected_pair_count": len(ep),
            **{k: int(v) for k, v in pv.items()},
            "wave_prefix_mismatches": wm, "pair_prefix_mismatches": pm,
            "ledger_hash_mismatches": hm, "passed": bool(passed),
        })
        checkpoint_hashes[str(length)] = {
            "actual_wave_sha256": awh, "expected_wave_sha256": ewh,
            "actual_pair_sha256": aph, "expected_pair_sha256": eph,
        }
    hashes = {
        "schema_id": "csi1000.two_wave_v0800_causal_prefix_hashes@1.0",
        "full_wave_sha256": stable_hash(full_waves),
        "full_pair_sha256": stable_hash(full_pairs),
        "checkpoint_hashes": checkpoint_hashes,
    }
    pair_counts = {rho_key(r): sum(1 for row in full_pairs if row[0] == rho_key(r)) for r in RHOS}
    return audit, hashes, {
        "full_wave_count": len(full_waves), "full_pair_count": len(full_pairs),
        "full_pair_count_by_rho": pair_counts, "violations": {k: int(v) for k, v in totals.items()},
        "causal_replay_passed": bool(all(v == 0 for v in totals.values()) and all(row["passed"] for row in audit)),
    }


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--inputs", required=True); parser.add_argument("--results", required=True)
    args = parser.parse_args(); inputs = Path(args.inputs); results = Path(args.results)
    required = {"CHECKPOINT_AUDIT.csv", "LEDGER_HASHES.json", "SUMMARY.json", "INPUT_RECEIPT.json"}
    if not required.issubset({p.name for p in results.iterdir() if p.is_file()}):
        fail("required_output_missing")
    bars = load_bars(inputs / DATA_FILE)
    expected_audit, expected_hashes, expected = recompute(bars)
    summary = json.loads((results / "SUMMARY.json").read_text())
    receipt = json.loads((results / "INPUT_RECEIPT.json").read_text())
    hashes = json.loads((results / "LEDGER_HASHES.json").read_text())
    audit = pd.read_csv(results / "CHECKPOINT_AUDIT.csv")
    if summary.get("schema_id") != SUMMARY_SCHEMA or summary.get("study") != "V0800-C_CAUSAL_PREFIX_REPLAY":
        fail("summary_schema_mismatch")
    got = [float(x) for x in summary.get("candidate_rhos", [])]
    if len(got) != len(RHOS) or any(abs(a-b) > 1e-12 for a,b in zip(got,RHOS)):
        fail("rho_family_drift")
    for key in ("future_outcome_used", "pnl_used", "morphology_acceptance", "trade_authority", "production_authority"):
        if summary.get(key) is not False:
            fail("authority_or_outcome_scope_violation")
    if summary.get("rho_winner") is not None or summary.get("direction_winner") is not None or summary.get("year_2026_read") is not False:
        fail("premature_authority_or_future_year")
    if receipt.get("sha256") != DATA_SHA256 or receipt.get("bytes") != DATA_BYTES or receipt.get("rows_read") != len(bars):
        fail("input_receipt_identity_mismatch")
    if receipt.get("year_2026_read") is not False or receipt.get("substitute_data_used") is not False:
        fail("input_scope_violation")
    if hashes != expected_hashes:
        fail("ledger_hash_output_mismatch")
    if len(audit) != len(expected_audit):
        fail("checkpoint_count_mismatch")
    for got_row, exp in zip(audit.to_dict("records"), expected_audit):
        for key, value in exp.items():
            if key == "passed":
                if bool(got_row[key]) != bool(value): fail("checkpoint_pass_flag_mismatch")
            elif str(got_row[key]) != str(value):
                fail("checkpoint_audit_mismatch")
    for key in ("full_wave_count", "full_pair_count", "full_pair_count_by_rho", "violations", "causal_replay_passed"):
        if summary.get(key) != expected[key]:
            fail("summary_recompute_mismatch")
    if summary.get("checkpoint_count") != len(expected_audit) or summary.get("passed_checkpoint_count") != sum(x["passed"] for x in expected_audit):
        fail("checkpoint_summary_mismatch")
    columns = [str(c).lower() for c in audit.columns]
    if any(token in column for token in FORBIDDEN_TOKENS for column in columns):
        fail("forbidden_trading_or_outcome_column")
    print(json.dumps({"status": "passed", "scientific_causal_replay_passed": expected["causal_replay_passed"], "checkpoint_count": len(expected_audit)}, sort_keys=True))


if __name__ == "__main__":
    main()
