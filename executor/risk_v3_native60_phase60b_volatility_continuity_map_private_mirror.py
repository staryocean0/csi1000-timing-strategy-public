from __future__ import annotations
import base64, json
from pathlib import Path
import importlib.util

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location("_rb_native60b",HERE/"research_broker.py")
base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base)
GateError=base.GateError
PROFILE="risk-v3-native60-phase60b-volatility-continuity-map-v1"
SCHEMA="risk_tool_v3_native60_phase60b_volatility_continuity_map_result@1.0"
TASK="CSI1000-RISK-V3-NATIVE60-PHASE60B-VOLATILITY-CONTINUITY-MAP-V1-20260916"

def validate(v:dict):
    if v.get("schema_id")!=SCHEMA or v.get("task_id")!=TASK or v.get("profile")!=PROFILE:raise GateError("native60b_mirror_identity_invalid")
    if v.get("status") not in {"NATIVE60_DESCRIPTIVE_MAP_COMPLETE","NATIVE60_DESCRIPTIVE_MAP_NOT_READY"}:raise GateError("native60b_mirror_status_invalid")
    controls=v.get("controls")
    if not isinstance(controls,dict) or any(x is not False for x in controls.values()):raise GateError("native60b_mirror_control_violation")
    dev=v.get("development") or {}
    if dev.get("years")!=[2021,2022,2023] or dev.get("symbol")!="000852.SH" or dev.get("rows")!=2908:raise GateError("native60b_mirror_window_invalid")
    if v.get("scientific_authority")!="descriptive_mechanistic_only" or v.get("continuity_pass_fail_claim") is not False or v.get("observable_ranking") is not False or v.get("next_phase_authorized") is not False:raise GateError("native60b_mirror_authority_violation")
    required={"cutpoints","marginal","persistence","episodes","compression","secondary_overnight","technical_acceptance"}
    if not required.issubset(v):raise GateError("native60b_mirror_map_missing")
    forbidden={"timestamps","prices","returns","raw_rows","row_level","predictions","probabilities","labels","canonical_rows"}
    if forbidden.intersection(v):raise GateError("native60b_mirror_row_level_forbidden")

def main():
    state,root=base.load_state()
    if state.get("profile_name")!=PROFILE or state.get("compute_success") is not True or state.get("cleanup_complete") is not True:raise GateError("native60b_state_not_mirrorable")
    path=root/"results"/"study"/"NATIVE60_PHASE60B_MAP.json"
    if not path.is_file() or path.is_symlink() or not 0<path.stat().st_size<=1024*1024:raise GateError("native60b_mirror_file_invalid")
    raw=path.read_bytes();v=json.loads(raw.decode());validate(v)
    api=base.require_private_api();target=f"repos/{base.PRIVATE_REPO}/contents/research/public-runs/{state['run_id']}-native60-phase60b.json"
    api.request(target,{"message":"Record verified Risk Tool V3 Native-60m Phase 60-B descriptive map [skip ci]","branch":state["branch"],"content":base64.b64encode(raw).decode()},method="PUT")
    got=api.request(target+"?ref="+base.urllib.parse.quote(state["branch"],safe=""))
    if base64.b64decode(got["content"])!=raw:raise GateError("native60b_mirror_readback_failed")
    print("Verified Native-60m Phase 60-B descriptive map mirrored privately.")

if __name__=="__main__":main()
