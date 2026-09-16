"""Full OHLC single-wave rendering; no geometry-only substitute for evidence."""
from __future__ import annotations

import html
import math

from two_wave_toolkit_v1 import BarView, WaveConfig, validate_bars
from two_wave_v0800_semantics import AWave, channel_geometry, internal_wave_descriptor


def render_wave_svg(bars, view: BarView, config: WaveConfig, row: dict) -> str:
    """Render all candles from L0 through confirmation, inclusive, in log space.

    Returns SVG text; the caller controls private storage. Nothing after
    confirmation is plotted. The confirmation event is NOT a backdated state.
    """
    c = int(row["confirmation_bar"])
    if not 0 <= c < len(bars):
        raise ValueError("confirmation bar outside supplied input")
    prefix = validate_bars(bars.iloc[:c + 1], view)
    if row["config_id"] != config.config_id or row["timeframe"] != view.timeframe or row["symbol"] != view.symbol:
        raise ValueError("wave/config/view identity mismatch")
    w = AWave(**{k: row[k] for k in ("start_bar", "high_bar", "end_bar", "start_low", "high", "end_low", "confirmation_bar", "wave_id")})
    for index, col, expected in ((w.start_bar, "low", w.start_low), (w.high_bar, "high", w.high), (w.end_bar, "low", w.end_low)):
        if index < 0 or float(prefix.iloc[index][col]) != expected:
            raise ValueError("wave anchor disagrees with original OHLC")
    if str(prefix.iloc[c].timestamp) != row["confirmation_time"]:
        raise ValueError("confirmation timestamp mismatch")
    geom = channel_geometry(w)
    window = prefix.iloc[w.start_bar:c + 1]
    lo = min(math.log(float(window.low.min())), geom.bottom_start, geom.bottom_end, geom.top_start, geom.top_end)
    hi = max(math.log(float(window.high.max())), geom.bottom_start, geom.bottom_end, geom.top_start, geom.top_end)
    padding = max((hi - lo) * 0.10, 1e-8); lo -= padding; hi += padding
    left, right, top, bottom = 85, 1100, 105, 595
    x = lambda i: left + (i - w.start_bar) * (right - left) / max(1, c - w.start_bar)
    y = lambda p: bottom - (p - lo) / (hi - lo) * (bottom - top)
    esc = lambda value: html.escape(str(value), quote=True)
    body_width = min(9.0, 0.60 * (right - left) / max(1, c - w.start_bar))
    lines = ['<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="800" viewBox="0 0 1200 800">',
             '<rect width="1200" height="800" fill="white"/>',
             f'<metadata data-wave-id="{esc(w.wave_id)}" data-first-bar="{w.start_bar}" data-confirmation-bar="{c}" data-source="{esc(view.source_id)}"/>',
             f'<text x="60" y="30" font-size="20">Single A-wave | {esc(view.symbol)} | {esc(view.timeframe)} | {esc(w.wave_id)}</text>',
             f'<text x="60" y="58" font-size="15">Internal {internal_wave_descriptor(w, config.tau)} | duration={w.duration} bars | s={geom.raw_log_slope_per_bar:.7g}/bar | g={geom.normalized_migration:.5f}</text>',
             '<text x="60" y="82" font-size="13">OHLC: hollow = close &gt;= open, solid = close &lt; open. Log-price axis. Dashed = channel translation.</text>']
    for j in range(5):
        logp = lo + (hi-lo) * j / 4
        lines.append(f'<text x="8" y="{y(logp):.2f}" font-size="12">{math.exp(logp):.2f}</text>')
    for i in range(w.start_bar, c + 1):
        b = prefix.iloc[i]; xx = x(i)
        oo, hh, ll, cc = (math.log(float(b[k])) for k in ("open", "high", "low", "close"))
        yy, height = y(max(oo, cc)), max(abs(y(oo) - y(cc)), 0.6)
        fill = "white" if cc >= oo else "black"
        lines.append(f'<g class="candle" data-bar-index="{i}"><line x1="{xx:.3f}" x2="{xx:.3f}" y1="{y(hh):.3f}" y2="{y(ll):.3f}" stroke="black"/><rect x="{xx-body_width/2:.3f}" y="{yy:.3f}" width="{body_width:.3f}" height="{height:.3f}" stroke="black" fill="{fill}"/></g>')
    for start, end, dash in ((geom.bottom_start, geom.bottom_end, ""), (geom.top_start, geom.top_end, 'stroke-dasharray="6,4"')):
        lines.append(f'<line class="channel" x1="{x(w.start_bar):.3f}" x2="{x(w.end_bar):.3f}" y1="{y(start):.3f}" y2="{y(end):.3f}" stroke="black" stroke-width="2" {dash}/>')
    for index, price, label in ((w.start_bar, w.start_low, "L0"), (w.high_bar, w.high, "H0"), (w.end_bar, w.end_low, "L1")):
        yy = y(math.log(price))
        lines.append(f'<g class="pivot" data-bar-index="{index}"><circle cx="{x(index):.3f}" cy="{yy:.3f}" r="5" fill="white" stroke="black"/><text x="{x(index)+7:.3f}" y="{yy-8:.3f}" font-size="15">{label}</text></g>')
    lines.append(f'<line class="confirmation" x1="{x(c):.3f}" x2="{x(c):.3f}" y1="{top}" y2="{bottom}" stroke="black" stroke-dasharray="3,3"/>')
    ticks = sorted(set(w.start_bar + round((c-w.start_bar)*j/4) for j in range(5)))
    for i in ticks:
        t = prefix.iloc[i].timestamp
        lines.append(f'<text x="{x(i):.3f}" y="620" text-anchor="middle" font-size="11">{esc(t.strftime("%Y-%m-%d"))}</text>')
        lines.append(f'<text x="{x(i):.3f}" y="638" text-anchor="middle" font-size="11">{esc(t.strftime("%H:%M"))} [{i}]</text>')
    notes = [f'Confirmed at close: {row["confirmation_time"]}; earliest consumer bar: {c+1} (not plotted).',
             'Pivot occurrence is selected using CLOSE; plotted geometry uses the wick on that selected bar.',
             'An adjacent bar may have a more extreme wick. This is not a claim of wick-local extrema.',
             'Full causal window only. No future bars, no outcome, no market-state or trading authority.']
    for j, text in enumerate(notes):
        lines.append(f'<text x="60" y="{685+24*j}" font-size="13">{esc(text)}</text>')
    return '\n'.join(lines + ['</svg>']) + '\n'
