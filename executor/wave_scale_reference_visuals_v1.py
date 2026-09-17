"""Deterministic blinded SVG panels for #359 reference review.

Consumes normalized geometry only. No dates, amplitude values, model scores, or I/O.
"""
from __future__ import annotations
import html
import math
import re

PANEL_RE = re.compile(r"^[0-9a-f]{20}$")
PHASES = tuple(f"offset{i}" for i in range(5))


def _panel(value: str) -> str:
    if not isinstance(value, str) or not PANEL_RE.fullmatch(value):
        raise ValueError("invalid blinded panel id")
    return value


def _unit(values, *, minimum=3, maximum=4096):
    rows = [float(v) for v in values]
    if not minimum <= len(rows) <= maximum:
        raise ValueError("invalid normalized path length")
    if any(not math.isfinite(v) or v < 0 or v > 1 for v in rows):
        raise ValueError("normalized values must be within unit interval")
    return rows


def _xy(index: int, count: int, value: float, *, left: float, top: float,
        width: float, height: float) -> tuple[float, float]:
    x = left if count == 1 else left + width * index / (count - 1)
    y = top + height * (1.0 - value)
    return x, y


def _points(values, *, left, top, width, height) -> str:
    rows = _unit(values)
    return " ".join(
        f"{x:.3f},{y:.3f}"
        for i, value in enumerate(rows)
        for x, y in [_xy(i, len(rows), value, left=left, top=top,
                         width=width, height=height)]
    )


def render_shape_svg(panel_id: str, normalized_close) -> str:
    panel = _panel(panel_id)
    values = _unit(normalized_close, minimum=10)
    points = _points(values, left=28, top=28, width=904, height=244)
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="960" height="320" viewBox="0 0 960 320">'
        '<rect x="0" y="0" width="960" height="320" fill="white"/>'
        f'<text x="28" y="18" font-size="12">blind panel {html.escape(panel)}</text>'
        '<line x1="28" y1="272" x2="932" y2="272" stroke="black" stroke-width="0.5"/>'
        f'<polyline points="{points}" fill="none" stroke="black" stroke-width="1.5"/>'
        '<text x="28" y="300" font-size="10">relative causal history</text>'
        '</svg>\n'
    )


def _phase_rows(rows):
    out=[]
    for row in rows:
        if not isinstance(row,(list,tuple)) or len(row)!=4:
            raise ValueError("phase row schema")
        minute,low,close,high=row
        if type(minute) is not int or not -299 <= minute <= 0:
            raise ValueError("relative minute")
        low,close,high=(float(low),float(close),float(high))
        if any(not math.isfinite(v) or not 0 <= v <= 1 for v in (low,close,high)):
            raise ValueError("normalized OHLC")
        if not low <= close <= high:
            raise ValueError("phase low/close/high order")
        out.append((minute,low,close,high))
    if not 2 <= len(out) <= 128 or len({r[0] for r in out})!=len(out):
        raise ValueError("phase support")
    return sorted(out)


def _phase_x(minute: int) -> float:
    return 70.0 + 850.0 * (minute + 299) / 299.0


def _phase_y(value: float, top: float) -> float:
    return top + 68.0 * (1.0 - value)


def render_phase_svg(panel_id: str, phases: dict) -> str:
    panel=_panel(panel_id)
    if not isinstance(phases,dict) or set(phases)!=set(PHASES):
        raise ValueError("five phase views required")
    body=[
        '<svg xmlns="http://www.w3.org/2000/svg" width="960" height="560" viewBox="0 0 960 560">',
        '<rect x="0" y="0" width="960" height="560" fill="white"/>',
        f'<text x="20" y="18" font-size="12">blind panel {html.escape(panel)} phase review</text>',
    ]
    for index,name in enumerate(PHASES):
        rows=_phase_rows(phases[name])
        top=34+index*100
        body.append(f'<text x="20" y="{top+38:.1f}" font-size="10">{name}</text>')
        points=[]
        for minute,low,close,high in rows:
            x=_phase_x(minute)
            ylow=_phase_y(low,top);yhigh=_phase_y(high,top);yc=_phase_y(close,top)
            body.append(
                f'<line x1="{x:.3f}" y1="{yhigh:.3f}" x2="{x:.3f}" y2="{ylow:.3f}" '
                'stroke="gray" stroke-width="0.7"/>'
            )
            points.append(f'{x:.3f},{yc:.3f}')
        joined=' '.join(points)
        body.append(f'<polyline points="{joined}" fill="none" stroke="black" stroke-width="1.1"/>')
        body.append(
            f'<line x1="70" y1="{top+68:.1f}" x2="920" y2="{top+68:.1f}" '
            'stroke="black" stroke-width="0.4"/>'
        )
    body.append('<text x="70" y="548" font-size="10">-299m</text>')
    body.append('<text x="882" y="548" font-size="10">0m</text>')
    body.append('</svg>')
    return ''.join(body)+'\n'
