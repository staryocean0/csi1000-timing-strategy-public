"""Source-only primitives for two separate Two-Wave research gates.

No market input loader, network, filesystem writes, workflow dispatch or authority.
A caller must use the reviewed inventory/as-of adapter and the approved runner.
Graphical component shares are NOT orthogonal spectral energy shares.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import math
from typing import Sequence

import numpy as np


def _integer(value: int, name: str, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f"invalid {name}")
    return value


def _prices(values: Sequence[float]) -> np.ndarray:
    x = np.asarray(values, dtype=float)
    if x.ndim != 1 or not len(x) or not np.all(np.isfinite(x)) or np.any(x <= 0):
        raise ValueError("require a finite positive price vector")
    return x


@dataclass(frozen=True)
class CompletedWave:
    start: int
    high: int
    end: int
    confirmed: int

    def __post_init__(self) -> None:
        for name in ("start", "high", "end", "confirmed"):
            _integer(getattr(self, name), name)
        if not self.start < self.high < self.end <= self.confirmed:
            raise ValueError("invalid wave clock")


def completed_shape(close: Sequence[float], wave: CompletedWave, asof: int) -> dict:
    """Completed-wave descriptors, available at confirmation CLOSE, never earlier.

    The supplied occurrence indices must come from the frozen A-wave inventory.
    The terminal low does not replace the later confirmation/decision clock.
    """
    _integer(asof, "asof")
    if asof < wave.confirmed:
        raise ValueError("completed wave not known")
    all_prices = _prices(close[: asof + 1])
    if asof >= len(all_prices):
        raise ValueError("asof outside observed prices")
    p = np.log(all_prices[wave.start : wave.end + 1])
    duration = wave.end - wave.start
    phase = (wave.high - wave.start) / duration
    height = p[wave.high - wave.start] - (p[0] + phase * (p[-1] - p[0]))
    if height <= 0 or not math.isfinite(height):
        raise ValueError("nonpositive frozen A-channel height")
    x = np.linspace(0.0, 1.0, len(p))
    baseline = p[0] + x * (p[-1] - p[0])
    residual = (p - baseline) / height
    midpoint = float(np.interp(0.5, x, p))
    sign = 1 if p[-1] >= p[0] else -1
    variation = float(np.abs(np.diff(p)).sum())
    result = {
        "known_from_bar": wave.confirmed,
        "earliest_consumer_bar": wave.confirmed + 1,
        "duration": duration,
        "confirmation_delay": wave.confirmed - wave.end,
        "height_log": float(height),
        "g": float((p[-1] - p[0]) / height),
        "slope_log_per_bar": float((p[-1] - p[0]) / duration),
        "peak_phase": phase,
        "front_push": float(sign * (midpoint - p[0]) / height),
        "back_push": float(sign * (p[-1] - midpoint) / height),
        "efficiency": float(abs(p[-1] - p[0]) / variation) if variation else 0.0,
        "residual_q25": float(np.interp(0.25, x, residual)),
        "residual_q50": float(np.interp(0.5, x, residual)),
        "residual_q75": float(np.interp(0.75, x, residual)),
        "shape_support": "SUFFICIENT" if duration >= 8 else "SHORT_WAVE",
    }
    result["shape_tag"] = (
        "EARLY_PEAK" if phase < 1 / 3 else "LATE_PEAK" if phase > 2 / 3 else "MIDDLE_PEAK"
    )
    return result


def period_bucket(period: float | None, base_period: float) -> str:
    if not math.isfinite(base_period) or base_period <= 0:
        raise ValueError("invalid base period")
    if period is None:
        return "UNRESOLVED"
    if not math.isfinite(period) or period <= 0:
        raise ValueError("invalid parent period")
    ratio = period / base_period
    if ratio < 2:
        return "BELOW_2T"
    if ratio <= 3:
        return "2T_TO_3T"
    if ratio < 6:
        return "ABOVE_3T_BELOW_6T"
    return "AT_LEAST_6T"


def graphical_components(close: Sequence[float], layers: Sequence[Sequence[dict]],
                         asof: int, root_id: str, min_rows: int = 8) -> dict:
    """Decompose only the common historical support of causally known polylines.

    Node fields: occurrence_bar, known_from_bar, price, root_id. Each layer
    is a recursively reduced low-node graph supplied by an audited adapter.
    No equal-spaced-node FFT, future node, root mixing or right-edge extrapolation.
    This function checks clocks, not the scientific validity of graph extraction.
    """
    _integer(asof, "asof"); _integer(min_rows, "min_rows", 2)
    prices = _prices(close[: asof + 1])
    if asof >= len(prices) or not root_id or not layers:
        raise ValueError("invalid graph request")
    selected = []
    for nodes in layers:
        visible = []
        last_occurrence = last_known = -1
        for node in nodes:
            known = _integer(node["known_from_bar"], "node knowledge")
            if known > asof:
                continue
            occurrence = _integer(node["occurrence_bar"], "node occurrence")
            if known < occurrence or occurrence <= last_occurrence or known < last_known:
                raise ValueError("invalid node chronology")
            if node["root_id"] != root_id:
                raise ValueError("graph crosses root/reset")
            _prices([node["price"]])
            last_occurrence, last_known = occurrence, known
            if known <= asof:
                visible.append(node)
        if len(visible) < 2:
            return {"status": "INSUFFICIENT_GRAPH", "asof": asof}
        selected.append(visible)
    left = max(nodes[0]["occurrence_bar"] for nodes in selected)
    right = min(nodes[-1]["occurrence_bar"] for nodes in selected)
    if right - left + 1 < min_rows:
        return {"status": "INSUFFICIENT_COMMON_SUPPORT", "asof": asof}
    x = np.arange(left, right + 1)
    curves = [np.log(prices[left : right + 1])]
    for nodes in selected:
        curves.append(np.interp(x, [n["occurrence_bar"] for n in nodes],
                                np.log([n["price"] for n in nodes])))
    components = [a - b for a, b in zip(curves, curves[1:])] + [curves[-1]]
    centered = np.asarray([p - p.mean() for p in components])
    variance = np.mean(centered * centered, axis=1)
    total = float(variance.sum())
    raw_centered = curves[0] - curves[0].mean()
    shares = (variance / total).tolist() if total > 1e-24 else None
    error = float(np.max(np.abs(centered.sum(axis=0) - raw_centered)))
    return {
        "status": "COMPUTED" if shares is not None else "ZERO_VARIATION",
        "asof": asof, "support_start": left, "support_end": right,
        "right_edge_age_bars": asof - right,
        "component_rms": np.sqrt(variance).tolist(),
        "geometric_variance_normalized_scores": shares,
        "cross_covariance_term": float(np.mean(raw_centered ** 2) - total),
        "reconstruction_error": error,
        "orthogonal_energy_claimed": False,
        "current_bar_extrapolation_used": False,
    }


def future_parent_turn(pivots: Sequence[dict], decision: int, horizon: int,
                       direction: str, root_id: str, reset_bars: Sequence[int] = ()) -> dict:
    """Outcome only: a NEW parent opposite turn by OCCURRENCE after the decision.

    Pivot fields: occurrence_bar, known_from_bar, kind (high/low), root_id.
    A confirmed pivot occurring beyond the horizon is the label-settlement
    watermark. Without it, absence of a turn is censored, not labelled zero.
    Pending turns/late confirmations of pre-decision extrema are not predictions.
    """
    _integer(decision, "decision"); _integer(horizon, "horizon", 1)
    if direction not in ("UP", "DOWN") or not root_id:
        raise ValueError("turn target requires an identified parent direction/root")
    end = decision + horizon
    relevant = []
    last_occurrence = last_known = -1
    for p in pivots:
        if p["root_id"] != root_id:
            continue
        occurrence = _integer(p["occurrence_bar"], "pivot occurrence")
        known = _integer(p["known_from_bar"], "pivot knowledge")
        if known < occurrence or occurrence <= last_occurrence or known < last_known:
            raise ValueError("invalid parent pivot clock")
        if p["kind"] not in ("high", "low"):
            raise ValueError("invalid pivot kind")
        last_occurrence, last_known = occurrence, known
        relevant.append(p)
    closing = next((p for p in relevant if p["occurrence_bar"] > end), None)
    if closing is None:
        return {"status": "RIGHT_CENSORED", "target": None, "mature_bar": None}
    mature = closing["known_from_bar"]
    for r in reset_bars:
        _integer(r, "reset")
    if any(decision < r <= mature for r in reset_bars):
        return {"status": "RESET_CENSORED", "target": None, "mature_bar": None}
    kind = "high" if direction == "UP" else "low"
    hits = [p for p in relevant if decision < p["occurrence_bar"] <= end and p["kind"] == kind]
    return {
        "status": "SETTLED", "target": int(bool(hits)), "mature_bar": mature,
        "turn_occurrence": hits[0]["occurrence_bar"] if hits else None,
        "lead_bars": hits[0]["occurrence_bar"] - decision if hits else None,
        "late_confirmations_of_old_turns": sum(
            p["occurrence_bar"] <= decision < p["known_from_bar"] and p["kind"] == kind
            for p in relevant),
    }


def purged_training(rows: Sequence[dict], test_start: int, test_parent_ids: set[str]) -> list[dict]:
    """Training labels must have matured strictly before the test block starts."""
    _integer(test_start, "test_start")
    result = []
    for row in rows:
        _integer(row["decision_bar"], "row decision")
        maturity = row.get("mature_bar")
        if maturity is None or row.get("target") is None:
            continue
        _integer(maturity, "row maturity")
        if maturity < row["decision_bar"] or row["target"] not in (0, 1):
            raise ValueError("invalid settled target")
        if maturity < test_start and row["decision_bar"] < test_start and row["parent_id"] not in test_parent_ids:
            result.append(row)
    return result


def nested_probabilities(train: Sequence[dict], test: Sequence[dict],
                         key_sets: Sequence[Sequence[str]], alpha: float = 20.0) -> list[list[float]]:
    """Transparent empirical baselines with hierarchical shrinkage, no grid search.

    Keys (including any train-fitted bins) must be prepared by the audited adapter.
    Key sets must be nested. Caller must pass purged training rows, not all rows.
    """
    if not train or not key_sets or not math.isfinite(alpha) or alpha <= 0:
        raise ValueError("invalid estimation request")
    for a, b in zip(key_sets, key_sets[1:]):
        if not set(a).issubset(b):
            raise ValueError("feature sets not nested")
    targets = [r["target"] for r in train]
    if any(y not in (0, 1) for y in targets):
        raise ValueError("binary targets required")
    prior = (sum(targets) + 1) / (len(train) + 2)
    tables = []
    for keys in key_sets:
        counts, positives = Counter(), Counter()
        for row in train:
            key = tuple(row[k] for k in keys)
            counts[key] += 1; positives[key] += row["target"]
        tables.append((counts, positives))
    outputs = [[] for _ in key_sets]
    for row in test:
        probability = prior
        for i, keys in enumerate(key_sets):
            key = tuple(row[k] for k in keys)
            counts, positives = tables[i]
            probability = (positives[key] + alpha * probability) / (counts[key] + alpha)
            outputs[i].append(probability)
    return outputs


def binary_losses(target: Sequence[int], probability: Sequence[float]) -> dict:
    y, p = np.asarray(target, dtype=float), np.asarray(probability, dtype=float)
    if y.ndim != 1 or y.shape != p.shape or not len(y) or not np.all(np.isin(y, [0, 1])):
        raise ValueError("invalid binary observations")
    if not np.all(np.isfinite(p)) or np.any((p < 0) | (p > 1)):
        raise ValueError("invalid probabilities")
    p = np.clip(p, 1e-12, 1 - 1e-12)
    return {"brier": (p - y) ** 2, "logloss": -(y * np.log(p) + (1 - y) * np.log1p(-p))}


def paired_block_interval(improvement: Sequence[float], blocks: Sequence[str],
                          repetitions: int = 2000, seed: int = 20260916) -> dict:
    """Equal-block mean interval; positive means the candidate improved.

    97.5% two-sided interval is the two-primary-gate Bonferroni convention.
    Block construction/dependence checks belong to the audited study adapter.
    """
    _integer(repetitions, "repetitions", 100)
    x = np.asarray(improvement, dtype=float)
    if x.ndim != 1 or len(x) != len(blocks) or not np.all(np.isfinite(x)):
        raise ValueError("invalid paired losses")
    names = sorted(set(blocks))
    if len(names) < 30:
        return {"status": "INSUFFICIENT_BLOCKS", "blocks": len(names), "interval": None}
    means = np.asarray([x[np.asarray(blocks) == name].mean() for name in names])
    rng = np.random.default_rng(seed)
    simulated = means[rng.integers(0, len(means), size=(repetitions, len(means)))].mean(axis=1)
    return {"status": "COMPUTED", "blocks": len(names), "mean": float(means.mean()),
            "interval": np.quantile(simulated, [0.0125, 0.9875]).tolist(),
            "estimand": "equal_block_mean", "independent_events_assumed": False}


def trend_shadow_trades(close: Sequence[float], open_: Sequence[float], period: int,
                        start_signal: int = 0, cost_bps_per_side: float = 2.0) -> dict:
    """Fixed raw-close breakout comparator, fill only at the NEXT raw open.

    Research proxy, not an executable CSI1000 product. No graphical price fills.
    Supply a contiguous valid evaluation interval with only permitted warm-up.
    Gate selection is attached to the baseline opportunity ledger, never exits.
    """
    c, o = _prices(close), _prices(open_)
    _integer(period, "period", 2); _integer(start_signal, "start_signal")
    if len(c) != len(o) or not math.isfinite(cost_bps_per_side) or cost_bps_per_side < 0:
        raise ValueError("invalid shadow input")
    trades = []
    side = 0; entry = signal = None
    for t in range(max(period, start_signal), len(c) - 1):
        history = c[t - period : t]
        desired = 1 if c[t] > history.max() else -1 if c[t] < history.min() else side
        if desired == side:
            continue
        fill = t + 1
        if side:
            gross = side * math.log(o[fill] / o[entry])
            trades.append({"signal_bar": signal, "entry_bar": entry, "exit_bar": fill,
                           "side": side, "duration": fill - entry, "gross_log_return": gross,
                           "net_log_return_proxy": gross - 2 * cost_bps_per_side / 10000,
                           "fast_loss": fill - entry <= period and gross < 0})
        side = desired; entry = fill; signal = t
    for i, trade in enumerate(trades):
        following = trades[i + 1] if i + 1 < len(trades) else None
        trade["two_sided_fast_loss"] = None if following is None else bool(
            trade["fast_loss"] and following["fast_loss"] and trade["side"] != following["side"])
    return {"trades": trades, "right_censored_open_trade": int(side != 0),
            "terminal_mark_to_market_used": False, "trade_authority": False}
