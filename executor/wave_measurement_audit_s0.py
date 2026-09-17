"""Issue 350: deterministic measurement counterexamples, not a new detector.

All paths here are mathematical constructions. No file/network I/O, market
loader, trading signal, parameter search, or empirical readiness decision.
"""
from __future__ import annotations
import math
import numpy as np
import pandas as pd
from wave_recognizer_r3_v1 import MatureCounterRearmEngine
from wave_r3_clock_probe_v1 import observe_frozen, action
from wave_recognizer_r1_v1 import _coverage

MAX_POINTS = 4096


def vector(values):
    x = np.asarray(values, dtype=float)
    if x.ndim != 1 or not 0 < len(x) <= MAX_POINTS:
        raise ValueError("bounded one-dimensional sequence required")
    if not np.isfinite(x).all() or np.any(x <= 0):
        raise ValueError("finite positive synthetic prices required")
    return x


def ohlc_groups(values, width=5, offset=0):
    """Group known samples, preserving O/max/min/C, without filtering.

    Synthetic uniform sample clock only; not a market-session resampler.
    Incomplete trailing groups are not fabricated.
    """
    x = vector(values)
    if type(width) is not int or not 2 <= width <= 64:
        raise ValueError("width outside synthetic bound")
    if type(offset) is not int or not 0 <= offset < width:
        raise ValueError("offset outside group")
    n = (len(x)-offset)//width
    if n < 1:
        raise ValueError("no complete group")
    b = x[offset:offset+n*width].reshape(n, width)
    return np.column_stack((b[:, 0], b.max(axis=1), b.min(axis=1), b[:, -1]))


def direction_changes(values):
    d = np.diff(vector(values))
    s = np.sign(d[d != 0])
    return int(np.count_nonzero(s[1:] != s[:-1]))


def log_range(values):
    x = vector(values)
    return float(math.log(x.max()/x.min()))


def bars(values, wick=0.):
    x = vector(values)
    if not math.isfinite(wick) or not 0 <= wick < .2:
        raise ValueError("invalid synthetic wick")
    return pd.DataFrame(dict(timestamp=pd.date_range("2015-01-05", periods=len(x), freq="5min"),
        open=x, high=x*(1+wick), low=x*(1-wick), close=x))


def event_keys(result):
    return {"pivots": result[1], "resets": result[2],
            "rejections": result[3], "maturities": result[4]}


def triangle(n=400, period=40):
    t = np.arange(n) % period
    return np.minimum(t, period-t).astype(float)


def amplitude_control():
    shape = triangle()
    a = MatureCounterRearmEngine(bars(100+.001*shape)).run()
    b = MatureCounterRearmEngine(bars(100+.2*shape)).run()
    return dict(kind="FROZEN_R3_SYNTHETIC", same_event_positions=event_keys(a)==event_keys(b),
        low_range=log_range(100+.001*shape), high_range=log_range(100+.2*shape),
        completed_waves=len(a[0]), low_durations=[r.wave.end_bar-r.wave.start_bar for r in a[0]],
        high_durations=[r.wave.end_bar-r.wave.start_bar for r in b[0]])


def wick_control():
    x = 100+.001*triangle()
    a = MatureCounterRearmEngine(bars(x)).run()
    b = MatureCounterRearmEngine(bars(x, .05)).run()
    return dict(kind="FROZEN_R3_SYNTHETIC", same_event_positions=event_keys(a)==event_keys(b),
        unchanged_close_range=log_range(x), narrow_ohlc_range=log_range(x),
        wide_ohlc_range=float(math.log(1.05*x.max()/(.95*x.min()))),
        completed_waves=len(a[0]),
        geometry_changed=bool(a[0]) and a[0][0].wave.high != b[0][0].wave.high)


def monotone_counter_control():
    # One ascent then one uninterrupted descent. No alternating fast cycles.
    x = np.r_[np.arange(100., 111.), np.arange(109., 39., -1)]
    result, rows = observe_frozen(bars(x))
    reset = next(r for r in rows if action(r)=="RESET")
    t = reset["bar_index"]
    updates = sum(action(r) in ("COUNTER_CREATE", "COUNTER_SUPERSEDE") for r in rows[11:t])
    pre = reset["pre"]
    return dict(kind="FROZEN_R3_SYNTHETIC", first_reset=t, candidate_age=t-pre["candidate"],
        pending_age=t-pre["pending_counter"], counter_updates_before_reset=updates,
        direction_changes_after_peak=direction_changes(x[10:t+1]),
        first_leg_known_direction="UP_THEN_DOWN_ONCE", resets=len(result[2]))


def unfinished_control():
    x = 100+np.arange(160)*.1
    result, rows = observe_frozen(bars(x))
    waves = [{"start_bar": r.wave.start_bar, "end_bar": r.wave.end_bar} for r in result[0]]
    cov = _coverage(waves, len(x))
    return dict(kind="FROZEN_R3_SYNTHETIC", bars=len(x), completed_waves=len(waves),
        completed_cycle_coverage=float(cov.mean()), direction_changes=direction_changes(x),
        live_candidate_present=rows[-1]["post"]["candidate"] is not None,
        resets=len(result[2]), interpretation="NO_COMPLETED_CYCLE_IS_NOT_AUTOMATIC_STATE_BLINDNESS")


def ohlc_nonidentifiability_control():
    a = np.tile([100.,104.,96.,101.,100.], 8)
    b = np.tile([100.,96.,104.,101.,100.], 8)
    return dict(kind="ANALYTIC_SYNTHETIC", native_paths_differ=not np.array_equal(a,b),
        offset0_ohlc_equal=bool(np.array_equal(ohlc_groups(a), ohlc_groups(b))),
        offset2_ohlc_equal=bool(np.array_equal(ohlc_groups(a,offset=2), ohlc_groups(b,offset=2))),
        intrablock_high_low_order_different=True,
        implication="ONE_OHLC_GRID_CANNOT_RECOVER_OTHER_OFFSETS_OR_INTRABAR_ORDER")


def alias_control():
    # Samples one unit apart; coarse close every five units. f=.21 aliases
    # to .01 per original unit, i.e. .05 cycles/coarse-bar. Offsets change phase.
    n = np.arange(1005)
    f = .21
    x = 100+np.sin(2*np.pi*f*n)
    results=[]
    for offset in range(5):
        y = ohlc_groups(x, offset=offset)[:,3]-100
        k = np.arange(len(y))
        expected = np.sin(2*np.pi*.05*k+2*np.pi*f*(offset+4))
        design = np.column_stack((np.sin(2*np.pi*.05*k),np.cos(2*np.pi*.05*k),np.ones(len(k))))
        coeff = np.linalg.lstsq(design,y,rcond=None)[0]
        results.append(dict(offset=offset,apparent_period_coarse_bars=20,
            fitted_amplitude=float(np.hypot(*coeff[:2])),
            exact_alias_identity_max_error=float(np.max(np.abs(y-expected)))))
    return dict(kind="ANALYTIC_SYNTHETIC", native_frequency=f, native_period=1/f,
        coarse_sample_frequency=.2, apparent_frequency_native_units=.01,
        offsets=results, implication="OFFSET_PERIOD_STABILITY_DOES_NOT_RULE_OUT_ALIASING")


def range_duration_control():
    # Identical deterministic log-slope; range increases with interval length.
    x = np.exp(4+.001*np.arange(201))
    return dict(kind="ANALYTIC_SYNTHETIC", short_intervals=20,long_intervals=200,
        short_log_range=log_range(x[:21]),long_log_range=log_range(x),
        direction_changes=direction_changes(x),
        implication="WHOLE_GAP_RANGE_IS_DURATION_DEPENDENT_NOT_A_FREQUENCY_LABEL")


def skeleton_control():
    # A nonlinear lower-envelope example, NOT a replacement for the project's
    # irregular recursive detector. Pure high carrier+sidebands have a slow envelope.
    t=np.arange(400)
    x=100+(2+.5*np.cos(2*np.pi*t/40))*np.cos(2*np.pi*t/4)
    low_indices=np.arange(2,len(t)-1,4)
    lows=x[low_indices]
    expected=98-.5*np.cos(2*np.pi*low_indices/40)
    local_minima=bool(np.all(lows<x[low_indices-1]) and np.all(lows<x[low_indices+1]))
    # Telescoping reconstruction is true for any skeleton and proves no fidelity.
    skeleton_a=np.full(len(x),98.)
    skeleton_b=np.linspace(97.,99.,len(x))
    errors=[float(np.max(np.abs(s+(x-s)-x))) for s in (skeleton_a,skeleton_b)]
    return dict(kind="ANALYTIC_NONLINEAR_ENVELOPE_NOT_PROJECT_REPLAY", nodes_before=len(x),
        low_nodes=len(lows),all_selected_nodes_are_local_minima=local_minima,
        native_carrier_and_sidebands=[.225,.25,.275],lower_envelope_frequency=.025,
        slow_envelope_max_error=float(np.max(np.abs(lows-expected))),
        two_different_skeleton_reconstruction_errors=errors,
        implication="NODE_REDUCTION_AND_EXACT_RECONSTRUCTION_DO_NOT_PROVE_BAND_FIDELITY")


def cycle_clock_control():
    # This is the meaning of the existing occurrence coverage mask, not a bug
    # in a routine intended to compute retrospective diagnostics.
    w={"start_bar":0,"end_bar":10,"known_from_bar":18}
    full=_coverage([w],20)
    t=12
    asof=_coverage([v for v in [w] if v["known_from_bar"]<=t],20)
    return dict(kind="ANALYTIC_MASK_SEMANTICS", cutoff=t,
        retrospective_covered_bars_before_cutoff=int(full[:t+1].sum()),
        completed_cycles_known_by_cutoff_covered_bars=int(asof[:t+1].sum()),
        implication="OCCURRENCE_CYCLE_COVERAGE_IS_NOT_LIVE_STATE_COVERAGE")


def run_suite():
    """Return only constructed experiment summaries; cannot admit real inputs."""
    return dict(schema_id="csi1000.segmentation_measurement_s0@1.0",research_issue=350,
        data_role="DETERMINISTIC_SYNTHETIC_NO_MARKET_DATA",market_run=None,
        findings={"amplitude":amplitude_control(),"wicks":wick_control(),
            "counter_updates":monotone_counter_control(),"unfinished":unfinished_control(),
            "ohlc_information_loss":ohlc_nonidentifiability_control(),"alias":alias_control(),
            "range_duration":range_duration_control(),"skeleton":skeleton_control(),
            "coverage_clocks":cycle_clock_control()},
        real_R3_residual_aliasing="UNDETERMINED",new_detector_selected=False,
        new_readiness_gate_selected=False,R3_promoted=False,one_minute_strategy_admitted=False,
        production_authority=False)
