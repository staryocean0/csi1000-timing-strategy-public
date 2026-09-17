"""Read-only frozen-R3 observation and independently coded state replay.

Synthetic use is unrestricted; real carrier use belongs to the fixed isolated
profile. This module never changes a detector state or applies a repair.
"""
from __future__ import annotations
import inspect
import math
import sys
from wave_recognizer_r3_v1 import MatureCounterRearmEngine

MIN_LEG = 4
MAX_AGE = 48


def pivot_key(p):
    return [p['kind'], p['occurrence_bar'], p['confirmation_bar'],
            p['epoch'], p['left_censored']]


def _index(point):
    return None if point is None else int(point[0])


def snapshot(engine):
    return dict(epoch=engine.epoch, mode=engine.mode,
        boot_low=_index(engine.boot_low), boot_high=_index(engine.boot_high),
        candidate=_index(engine.candidate), raw_counter=_index(engine.counter),
        pending_counter=_index(engine.counter_candidate), last_pivot=engine.last_pivot_bar,
        chain_n=len(engine.chain), chain_tail=[pivot_key(p) for p in engine.chain[-3:]],
        pivots_n=len(engine.pivots), waves_n=len(engine.waves), resets_n=len(engine.resets),
        rejections_n=len(engine.rejections), maturities_n=len(engine.maturities))


def observe_frozen(bars):
    """Observe loop boundaries of the ORIGINAL run; do not replace any method."""
    if not 0 < len(bars) <= 70114:
        raise ValueError("bounded nonempty observation required")
    if not all(math.isfinite(float(v)) for v in bars.close):
        raise ValueError("nonfinite close")
    engine = MatureCounterRearmEngine(bars)
    code = MatureCounterRearmEngine.run.__code__
    lines, first = inspect.getsourcelines(MatureCounterRearmEngine.run)
    loop_lines = [first+i for i, line in enumerate(lines)
                  if line.strip() == 'for i in range(len(self.bars)):']
    if len(loop_lines) != 1:
        raise ValueError('frozen loop observation boundary changed')
    loop_line = loop_lines[0]
    rows = []
    previous = snapshot(engine)

    def capture(frame):
        nonlocal previous
        i = frame.f_locals.get('i')
        if i is None or i < len(rows):
            return
        if i != len(rows):
            raise ValueError('observer skipped a bar')
        after = snapshot(engine)
        rows.append(dict(bar_index=i, pre=previous, post=after))
        previous = after

    def trace(frame, event, arg):
        if frame.f_code is not code:
            return None
        if (event == 'line' and frame.f_lineno == loop_line) or event == 'return':
            capture(frame)
        return trace

    old_trace = sys.gettrace()
    if old_trace is not None:
        raise ValueError('another trace observer is already installed')
    try:
        sys.settrace(trace)
        result = engine.run()
    finally:
        sys.settrace(old_trace)
    if len(rows) != len(bars):
        raise ValueError('incomplete frozen observation')
    return result, rows


def replay(closes):
    """Separate array-based state machine, including raw diagnostic counter.

    It calls no producer or observer method. Its sole purpose is equality
    checking of the fixed semantics, not competing detector research.
    """
    if not 0 < len(closes) <= 70114:
        raise ValueError("bounded nonempty replay required")
    prices = [float(x) for x in closes]
    if not all(math.isfinite(x) for x in prices):
        raise ValueError("nonfinite close")
    lo = hi = candidate = raw = pending = last = None
    mode = None
    epoch = wave_count = 0
    chain = []
    pivots, resets, rejects, mature, rows = [], [], [], [], []

    def state():
        return dict(epoch=epoch, mode=mode, boot_low=lo, boot_high=hi,
            candidate=candidate, raw_counter=raw, pending_counter=pending,
            last_pivot=last, chain_n=len(chain), chain_tail=[pivot_key(p) for p in chain[-3:]],
            pivots_n=len(pivots), waves_n=wave_count, resets_n=len(resets),
            rejections_n=len(rejects), maturities_n=len(mature))

    for t, price in enumerate(prices):
        before = state()
        kind = index = None
        seed = False
        if lo is None:
            lo = hi = t
        else:
            anchors = [v for v in (last, candidate) if v is not None]
            stale = bool(anchors) and t - max(anchors) > MAX_AGE
            if stale:
                resets.append(dict(bar_index=t, epoch=epoch, previous_pivot_bar=last))
                epoch += 1
                mode = candidate = raw = pending = last = None
                chain = []
                lo = hi = t
            elif mode is None:
                if price < prices[lo]: lo = t
                if price > prices[hi]: hi = t
                if hi-lo >= MIN_LEG:
                    kind, index, mode, candidate, seed = 'low', lo, 1, hi, True
                elif lo-hi >= MIN_LEG:
                    kind, index, mode, candidate, seed = 'high', hi, -1, lo, True
                raw = pending = None
            else:
                relation = mode * (price - prices[candidate])
                updated = False
                if relation > 0:
                    candidate = t
                    raw = pending = None
                else:
                    if relation < 0:
                        if raw is None or mode * (price-prices[raw]) < 0: raw = t
                        if pending is None or mode * (price-prices[pending]) < 0:
                            pending = t
                            updated = True
                    if not updated and pending is not None and t-pending >= MIN_LEG:
                        gap = pending-candidate
                        event = dict(epoch=epoch, candidate_occurrence_bar=candidate,
                            counter_occurrence_bar=pending, maturity_bar=t,
                            survival_bars=t-pending, occurrence_gap=gap,
                            counter_kind='low' if mode>0 else 'high')
                        if gap >= MIN_LEG:
                            mature.append(dict(event, status='ACCEPTED_MATURE_COUNTER'))
                            kind, index = ('high' if mode>0 else 'low'), candidate
                            mode = -mode
                            candidate = pending
                        else:
                            rejects.append(dict(event, status='SUBSCALE_REJECTED'))
                        raw = pending = None
            if index is not None:
                record = dict(kind=kind, occurrence_bar=index, confirmation_bar=t,
                    confirmation_delay_bars=t-index, epoch=epoch, left_censored=seed)
                pivots.append(record)
                last = index
                if not seed:
                    chain.append(record)
                    if len(chain)>=3 and [p['kind'] for p in chain[-3:]]==['low','high','low']:
                        wave_count += 1
        rows.append(dict(bar_index=t, pre=before, post=state()))
    return dict(rows=rows, pivots=pivots, resets=resets, rejections=rejects, maturities=mature)


def action(row):
    a, b = row['pre'], row['post']
    if b['resets_n']>a['resets_n']: return 'RESET'
    if a['boot_low'] is None: return 'INITIALIZE'
    if a['mode'] is None and b['mode'] is not None: return 'BOOTSTRAP_PIVOT'
    if a['mode'] is None: return 'BOOTSTRAP_WAIT'
    if b['maturities_n']>a['maturities_n']: return 'ACCEPT_MATURE_COUNTER'
    if b['rejections_n']>a['rejections_n']: return 'SUBSCALE_REJECT_REARM'
    if b['candidate']!=a['candidate']: return 'CANDIDATE_PROGRESS'
    if b['pending_counter']!=a['pending_counter']:
        return 'COUNTER_CREATE' if a['pending_counter'] is None else 'COUNTER_SUPERSEDE'
    return 'HOLD'


def reset_bar_predicates(row, closes):
    """Evaluate branch conditions only. NEVER apply them to the state."""
    t, a = row['bar_index'], row['pre']
    candidate, pending, mode = a['candidate'], a['pending_counter'], a['mode']
    anchors = [v for v in (candidate,a['last_pivot']) if v is not None]
    result = dict(progress_age=None if not anchors else t-max(anchors),
        candidate_age=None if candidate is None else t-candidate,
        pending_age=None if pending is None else t-pending,
        occurrence_gap=None if pending is None or candidate is None else pending-candidate,
        same_bar_candidate_progress=False, same_bar_counter_update=False,
        same_bar_eligible_maturity=False, same_bar_subscale_maturity=False)
    if mode is None or candidate is None:
        result['classification']='TIMEOUT_WITH_NO_ACTIVE_CANDIDATE'
        return result
    relation = mode * (float(closes[t])-float(closes[candidate]))
    progress = relation>0
    update = relation<0 and (pending is None or mode*(float(closes[t])-float(closes[pending]))<0)
    survival = not progress and not update and pending is not None and t-pending>=MIN_LEG
    result.update(same_bar_candidate_progress=progress, same_bar_counter_update=update,
        same_bar_eligible_maturity=survival and pending-candidate>=MIN_LEG,
        same_bar_subscale_maturity=survival and pending-candidate<MIN_LEG)
    if progress: label='RESET_PREEMPTS_SAME_BAR_CANDIDATE_PROGRESS'
    elif result['same_bar_eligible_maturity']: label='RESET_PREEMPTS_ELIGIBLE_COUNTER_MATURITY'
    elif result['same_bar_subscale_maturity']: label='RESET_PREEMPTS_SUBSCALE_REJECTION'
    elif update: label='TIMEOUT_WITH_COUNTER_SUPERSESSION_ON_RESET_BAR'
    elif pending is not None and t-pending<MIN_LEG: label='TIMEOUT_WITH_COUNTER_NOT_YET_MATURE'
    elif pending is None: label='TIMEOUT_WITH_NO_PENDING_COUNTER'
    else: label='UNCLASSIFIED_REQUIRES_REVIEW'
    result['classification']=label
    return result
