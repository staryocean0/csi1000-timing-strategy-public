"""Read-only R1 residual-clock probe for issue #334; not an R2 detector.

The pure replay below mirrors the *published* R1 transition rules to produce
pre/post-bar evidence. An approved market entry MUST check every pivot/reset
and complete wave against frozen R1 before accepting any diagnostic output.
No file or network access; no fitting, returns, execution or trading authority.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import math
from typing import Iterable


@dataclass(frozen=True)
class State:
    mode: int | None
    candidate: int | None
    counter: int | None
    last_pivot: int | None
    epoch: int
    last_confirmation: int | None

    def as_dict(self) -> dict:
        return dict(mode=self.mode, candidate=self.candidate, counter=self.counter,
                    last_pivot=self.last_pivot, epoch=self.epoch,
                    last_confirmation=self.last_confirmation)


def _prices(values: Iterable[float]) -> list[float]:
    result = [float(x) for x in values]
    if not result or any(not math.isfinite(x) or x <= 0 for x in result):
        raise ValueError('finite positive close prices required')
    return result


def pending_geometry(state: State, now: int, prices: list[float]) -> dict:
    """Read pre-bar state and ask what this *same bar* would do before timeout.

    These are local branch predicates only, NOT a counterfactual repaired run.
    Nothing is fed back to the producer, and future bars are never consulted.
    """
    if type(now) is not int or not 0 <= now < len(prices):
        raise ValueError('invalid query bar')
    anchors = [a for a in (state.last_pivot, state.candidate) if a is not None]
    anchor = max(anchors) if anchors else None
    out = dict(progress_anchor=anchor, progress_age=None if anchor is None else now-anchor,
               pending_counter_gap=None if state.counter is None or state.candidate is None
               else state.counter-state.candidate,
               candidate_age=None if state.candidate is None else now-state.candidate,
               counter_age=None if state.counter is None else now-state.counter,
               same_bar_new_candidate=False, same_bar_new_counter=False,
               same_bar_valid_confirmation=False)
    if state.mode is None or state.candidate is None:
        return out
    change = state.mode * (prices[now]-prices[state.candidate])
    if change > 0:
        out['same_bar_new_candidate'] = True
        return out
    counter = state.counter
    if change < 0 and (counter is None or state.mode*(prices[now]-prices[counter]) < 0):
        counter = now
        out['same_bar_new_counter'] = True
    out['same_bar_valid_confirmation'] = counter is not None and counter-state.candidate >= 4
    return out


def replay(close: Iterable[float]) -> dict:
    """Exact 4/48 R1 array transition specification with immutable snapshots.

    No parameter search. In particular counter updates never refresh the reset
    clock and the >48 guard remains BEFORE the current price is processed.
    """
    prices = _prices(close)
    mode = None
    candidate = counter = last = low = high = last_confirmation = None
    epoch = 0
    rows: list[dict] = []
    pivots: list[dict] = []
    resets: list[dict] = []

    def state() -> State:
        return State(mode, candidate, counter, last, epoch, last_confirmation)

    for now, price in enumerate(prices):
        before = state()
        info = pending_geometry(before, now, prices)
        action = 'HOLD'
        emitted = None
        if low is None:
            low = high = now
            action = 'INITIALIZE'
        elif info['progress_age'] is not None and info['progress_age'] > 48:
            resets.append(dict(bar_index=now, epoch=epoch, previous_pivot_bar=last))
            epoch += 1
            mode = None
            last = candidate = counter = None
            low = high = now
            # Last emitted knowledge timestamp remains a historical field only.
            action = 'RESET_BEFORE_PRICE'
        elif mode is None:
            low = now if price < prices[low] else low
            high = now if price > prices[high] else high
            if high-low >= 4:
                emitted = ('low', low, True)
                mode = 1
                candidate = high
            elif low-high >= 4:
                emitted = ('high', high, True)
                mode = -1
                candidate = low
            action = 'BOOTSTRAP_CONFIRM' if emitted else 'BOOTSTRAP_WAIT'
        else:
            delta = mode * (price-prices[candidate])
            if delta > 0:
                candidate = now
                counter = None
                action = 'CANDIDATE_UPDATE'
            else:
                if delta < 0 and (counter is None or mode*(price-prices[counter]) < 0):
                    counter = now
                    action = 'COUNTER_UPDATE'
                if counter is not None and counter-candidate >= 4:
                    emitted = ('high' if mode > 0 else 'low', candidate, False)
                    mode *= -1
                    candidate = counter
                    counter = None
                    action = 'CONFIRM'
        if emitted is not None:
            kind, occurrence, seed = emitted
            pivots.append(dict(kind=kind, occurrence_bar=occurrence,
                               confirmation_bar=now, confirmation_delay_bars=now-occurrence,
                               epoch=epoch, left_censored=seed))
            last = occurrence
            last_confirmation = now
        rows.append(dict(bar=now, before=before.as_dict(), after=state().as_dict(),
                         action=action, **info))
    return dict(pivots=pivots, resets=resets, rows=rows)


def reset_evidence(close: Iterable[float], ledger: dict) -> list[dict]:
    prices = _prices(close)
    if len(ledger['rows']) != len(prices):
        raise ValueError('clock population differs')
    summaries = []
    for row in ledger['rows']:
        if row['action'] != 'RESET_BEFORE_PRICE':
            continue
        gap = row['pending_counter_gap']
        if row['same_bar_new_candidate'] or row['same_bar_valid_confirmation']:
            reason = 'SAME_BAR_EVIDENCE_SKIPPED'
        elif gap is not None and 0 < gap < 4:
            reason = 'EARLY_COUNTER_LOCK'
        elif gap is None:
            reason = 'NO_OPPOSITE_COUNTER'
        else:
            raise ValueError('persistent mature counter violates R1 transition invariant')
        candidate = row['before']['candidate']
        start = candidate if candidate is not None else row['bar']
        path = prices[start:row['bar']+1]
        signs = [1 if b>a else -1 if b<a else 0 for a,b in zip(path,path[1:])]
        nonzero = [s for s in signs if s]
        summaries.append(dict(reset_bar=row['bar'], reason=reason,
            progress_age=row['progress_age'], counter_gap=gap,
            counter_age=row['counter_age'], candidate_age=row['candidate_age'],
            skipped_new_candidate=row['same_bar_new_candidate'],
            skipped_valid_confirmation=row['same_bar_valid_confirmation'],
            observed_sign_changes=sum(a!=b for a,b in zip(nonzero,nonzero[1:])),
            same_bar_predicates_are_not_repaired_outcomes=True))
    return summaries


def verified_frozen_replay(bars) -> dict:
    """Must be called inside the approved runner, with the actual frozen module.

    No fallback/stub engine and no rounded price/clock comparisons are allowed.
    The old engine is unchanged. Array replay is rejected on any event mismatch.
    """
    from wave_recognizer_r1_v1 import ProgressAwareAEngine
    from wave_recognizer_r1_v1_verifier import independent_waves, wave_key

    observed = replay(bars.close.to_numpy(float))
    records, pivots, resets = ProgressAwareAEngine(bars).run()
    if observed['pivots'] != pivots or observed['resets'] != resets:
        raise ValueError('instrumentation differs from frozen R1')
    tuples = [(p['kind'], p['occurrence_bar'], p['confirmation_bar'], p['epoch'],
               p['left_censored']) for p in observed['pivots']]
    if independent_waves(bars, tuples) != [wave_key(w) for w in records]:
        raise ValueError('frozen OHLC wave ledger mismatch')
    observed['reset_evidence'] = reset_evidence(bars.close.to_numpy(float), observed)
    return observed


def episode_partition(start: int, end: int, reset: int, baseline_covered) -> dict:
    """Occurrence-time accounting only; not a claim these labels were known live."""
    n = len(baseline_covered)
    if any(type(v) is not int for v in (start,end,reset)) or not 0 <= start <= reset <= end < n:
        raise ValueError('reset must lie inside the non-edge episode')
    known = sum(bool(v) for v in baseline_covered[start:end+1])
    return dict(bars=end-start+1, before_reset_bars=reset-start, reset_bar=1,
                after_reset_bars=end-reset, newly_blind_bars=known,
                old_blind_bars=end-start+1-known,
                occurrence_partition_not_knowledge_partition=True)


def reference_scope() -> dict:
    return dict(research_issue=334, prerequisite_issue=330, readiness_issue=321,
                baseline_source='61e5dcdf143be4b9a5a7bb8bcae1c4a3f2a63af7',
                R2_hypotheses_unadjudicated=True, new_training=False, outcomes_used=False,
                one_minute_admitted=False, R2_selected=False,
                authority={k:False for k in ('signal','detector_repair','router','trade','production')})
