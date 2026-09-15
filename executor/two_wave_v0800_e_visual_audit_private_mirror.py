"""Mirror verified V0800-E audit text, frozen SVG cases, and compact private contact sheets."""
from __future__ import annotations

import base64
import hashlib
import html
import json
import math
import re

import research_broker as base

GateError = base.GateError
PROFILE = "two-wave-v0800-e-morphology-visual-audit-v1"
TEXT_OUTPUTS = ("SUMMARY.json", "INPUT_RECEIPT.json", "AUDIT_MANIFEST.json", "AUDIT_REPORT.md")
CATEGORIES = ("stable_consensus", "kappa_sensitive", "tau_sensitive", "sign_conflict", "persistent_uncertain")
MAX_TEXT_BYTES = 512 * 1024
MAX_VISUAL_FILES = 60
MAX_VISUAL_BYTES = 64 * 1024
MAX_VISUAL_TOTAL_BYTES = 2 * 1024 * 1024
MAX_CONTACT_SHEET_BYTES = 128 * 1024
EXPECTED_MANIFEST_SHA256 = "c3260be7f72a12a5da0b33d1fb23deacd32d967d83e45f480d0363ca2e836ab5"
BAR_RE = re.compile(r'<g class="bar" data-bar-index="\d+"><line x1="([-0-9.]+)" y1="([-0-9.]+)" x2="[-0-9.]+" y2="([-0-9.]+)"[^>]*/><circle cx="[-0-9.]+" cy="([-0-9.]+)"[^>]*/></g>')
STATE_RE = re.compile(r't([0-9.]+)/k([0-9.]+): ([A-Za-z]+)')


def validate_summary(raw: bytes) -> None:
    try:
        value = json.loads(raw.decode("utf-8"))
    except Exception:
        raise GateError("two_wave_v0800_e_summary_invalid") from None
    if value.get("schema_id") != "csi1000.two_wave_v0800_e_summary@1.0" or value.get("study") != "V0800-E_MORPHOLOGY_VISUAL_AUDIT":
        raise GateError("two_wave_v0800_e_summary_identity_mismatch")
    if int(value.get("strict_pair_count", -1)) != 2358 or int(value.get("eligible_same_scale_pair_count", -1)) != 924:
        raise GateError("two_wave_v0800_e_parent_universe_mismatch")
    if value.get("tau_winner") is not None or value.get("kappa_winner") is not None:
        raise GateError("two_wave_v0800_e_premature_parameter_winner")
    for key in ("automatic_parameter_promotion", "future_bars_after_confirmation_shown", "future_outcome_used", "returns_used", "pnl_used", "positions_used", "year_2026_read", "direction_acceptance", "state_publication_authority", "trade_authority", "production_authority"):
        if value.get(key) is not False:
            raise GateError("two_wave_v0800_e_summary_scope_violation")
    if value.get("visual_audit_complete") is not True or value.get("post_audit_adjudication_required") is not True:
        raise GateError("two_wave_v0800_e_adjudication_gate_missing")


def validate_manifest(raw: bytes) -> dict:
    if hashlib.sha256(raw).hexdigest() != EXPECTED_MANIFEST_SHA256:
        raise GateError("two_wave_v0800_e_manifest_not_frozen_source_pack")
    try:
        value = json.loads(raw.decode("utf-8"))
    except Exception:
        raise GateError("two_wave_v0800_e_manifest_invalid") from None
    if value.get("schema_id") != "csi1000.two_wave_v0800_e_audit_manifest@1.0":
        raise GateError("two_wave_v0800_e_manifest_schema_mismatch")
    if value.get("bars_after_confirmation_shown") is not False or value.get("future_outcome_used") is not False:
        raise GateError("two_wave_v0800_e_manifest_scope_violation")
    count = int(value.get("selected_case_count", -1))
    cases = value.get("cases", [])
    if count != 59 or len(cases) != count or count > MAX_VISUAL_FILES:
        raise GateError("two_wave_v0800_e_manifest_count_invalid")
    return value


def put_verified(api, state: dict, relative: str, raw: bytes, message: str) -> None:
    target = f"repos/{base.PRIVATE_REPO}/contents/research/public-runs/{state['run_id']}-results/{relative}"
    api.request(target, {"message": message, "branch": state["branch"], "content": base64.b64encode(raw).decode("ascii")}, method="PUT")
    returned = api.request(target + "?ref=" + base.urllib.parse.quote(state["branch"], safe=""))
    if base64.b64decode(returned["content"]) != raw:
        raise GateError("two_wave_v0800_e_private_visual_readback_failed")


def state_symbol(value: str) -> str:
    return {"UpTrend": "U", "DownTrend": "D", "Range": "R", "Uncertain": "?"}.get(value, "!")


def compact_case(raw_text: str, case: dict, x0: int, y0: int) -> list[str]:
    bars = BAR_RE.findall(raw_text)
    if not bars:
        raise GateError("two_wave_v0800_e_contact_sheet_bar_parse_failed")
    bar_path = " ".join(f"M{x},{y1}V{y2}" for x, y1, y2, _ in bars)
    close_points = " ".join(f"{x},{yc}" for x, _, _, yc in bars)
    channels = re.findall(r'<line class="channel [^"]+"[^>]*/>', raw_text)
    pivots = re.findall(r'<g class="pivot"[^>]*>.*?</g>', raw_text)
    confirmation = re.findall(r'<line class="confirmation"[^>]*/>', raw_text)
    if len(channels) != 4 or len(pivots) != 5 or len(confirmation) != 1:
        raise GateError("two_wave_v0800_e_contact_sheet_overlay_parse_failed")
    info = re.findall(r'<text x="885"[^>]*>(.*?)</text>', raw_text)
    g_text = next((v for v in info if v.startswith("g prev/current:")), "g prev/current: ?")
    slope_text = next((v for v in info if v.startswith("slope ratio:")), "slope ratio: ?")
    states = {(t, k): state_symbol(s) for t, k, s in STATE_RE.findall(raw_text)}
    if len(states) != 12:
        raise GateError("two_wave_v0800_e_contact_sheet_state_parse_failed")
    pair_id = html.escape(str(case["pair_id"]), quote=True)
    year = int(case["year"])
    lines = [f'<g class="case" data-pair-id="{pair_id}" transform="translate({x0},{y0})">']
    lines.append(f'<rect x="0" y="0" width="590" height="330" fill="white" stroke="#bbb"/><text x="10" y="20" font-size="13">{year} | {pair_id}</text>')
    lines.append('<svg x="10" y="30" width="455" height="275" viewBox="40 40 830 520" preserveAspectRatio="none">')
    lines.append(f'<path d="{bar_path}" fill="none" stroke="#888" stroke-width="1"/><polyline points="{close_points}" fill="none" stroke="#222" stroke-width="1.5"/>')
    lines.append("".join(channels + pivots + confirmation))
    lines.append('</svg>')
    lines.append(f'<text x="470" y="55" font-size="10">{html.escape(g_text)}</text><text x="470" y="72" font-size="10">{html.escape(slope_text)}</text>')
    for row, tau in enumerate(("0.05", "0.10", "0.15", "0.20")):
        symbols = " ".join(states[(tau, k)] for k in ("1.25", "1.50", "2.00"))
        lines.append(f'<text x="470" y="{105 + row*18}" font-size="11">t{tau}: {symbols}</text>')
    lines.append('</g>')
    return lines


def build_contact_sheet(category: str, cases: list[tuple[dict, str]]) -> bytes:
    cols, cell_w, cell_h = 2, 600, 340
    rows = math.ceil(len(cases) / cols)
    width, height = cols * cell_w, 45 + rows * cell_h
    lines = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">', '<rect width="100%" height="100%" fill="#f5f5f5"/>', f'<text x="10" y="28" font-size="18">V0800-E contact sheet: {category} | frozen 34967434004-1 pack</text>']
    for index, (case, raw_text) in enumerate(cases):
        x0 = (index % cols) * cell_w
        y0 = 45 + (index // cols) * cell_h
        lines.extend(compact_case(raw_text, case, x0, y0))
    lines.append('</svg>')
    raw = ("\n".join(lines) + "\n").encode("utf-8")
    if not raw or len(raw) > MAX_CONTACT_SHEET_BYTES:
        raise GateError("two_wave_v0800_e_contact_sheet_size_invalid")
    return raw


def main() -> None:
    state, root = base.load_state()
    if state.get("profile_name") != PROFILE:
        raise GateError("two_wave_v0800_e_text_mirror_wrong_profile")
    if state.get("compute_success") is not True or state.get("cleanup_complete") is not True:
        raise GateError("two_wave_v0800_e_text_mirror_requires_verified_success")
    api = base.require_private_api()
    study = root / "results" / "study"
    manifest_path = study / "AUDIT_MANIFEST.json"
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise GateError("two_wave_v0800_e_text_output_missing")
    manifest_raw = manifest_path.read_bytes()
    manifest = validate_manifest(manifest_raw)

    for name in TEXT_OUTPUTS:
        path = study / name
        if path.is_symlink() or not path.is_file():
            raise GateError("two_wave_v0800_e_text_output_missing")
        raw = path.read_bytes()
        if not raw or len(raw) > MAX_TEXT_BYTES:
            raise GateError("two_wave_v0800_e_text_output_size_invalid")
        try:
            raw.decode("utf-8")
        except UnicodeDecodeError:
            raise GateError("two_wave_v0800_e_text_output_not_utf8") from None
        if name == "SUMMARY.json":
            validate_summary(raw)
        elif name == "AUDIT_MANIFEST.json":
            validate_manifest(raw)
        put_verified(api, state, name, raw, "Record verified Two-Wave V0800-E audit text [skip ci]")

    total = 0
    seen = set()
    by_category: dict[str, list[tuple[dict, str]]] = {category: [] for category in CATEGORIES}
    for case in manifest["cases"]:
        relative = case.get("svg_file", "")
        category = case.get("category")
        if category not in by_category or not isinstance(relative, str) or not re.fullmatch(r"visuals/[A-Za-z0-9_.-]+\.svg", relative) or relative in seen:
            raise GateError("two_wave_v0800_e_visual_path_invalid")
        seen.add(relative)
        path = study / relative
        if path.is_symlink() or not path.is_file():
            raise GateError("two_wave_v0800_e_visual_missing")
        raw = path.read_bytes()
        if not raw or len(raw) > MAX_VISUAL_BYTES:
            raise GateError("two_wave_v0800_e_visual_size_invalid")
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            raise GateError("two_wave_v0800_e_visual_not_utf8") from None
        if "<svg" not in text[:1024] or "data-bar-index=" not in text:
            raise GateError("two_wave_v0800_e_visual_identity_invalid")
        total += len(raw)
        if total > MAX_VISUAL_TOTAL_BYTES:
            raise GateError("two_wave_v0800_e_visual_total_budget_exceeded")
        by_category[category].append((case, text))
        put_verified(api, state, relative, raw, "Record frozen verified Two-Wave V0800-E visual audit case [skip ci]")

    if len(seen) != 59:
        raise GateError("two_wave_v0800_e_visual_count_mismatch")
    for category in CATEGORIES:
        if not by_category[category]:
            raise GateError("two_wave_v0800_e_contact_sheet_category_empty")
        sheet = build_contact_sheet(category, by_category[category])
        put_verified(api, state, f"contact_sheets/{category}.svg", sheet, "Record compact Two-Wave V0800-E contact sheet [skip ci]")
    print(f"Verified Two-Wave V0800-E frozen audit pack mirrored privately: {len(seen)} SVG cases and {len(CATEGORIES)} contact sheets.")


if __name__ == "__main__":
    try:
        main()
    except GateError as error:
        raise SystemExit("Execution stopped: " + str(error))
