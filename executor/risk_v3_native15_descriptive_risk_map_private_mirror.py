from __future__ import annotations
import base64, json
from pathlib import Path
import importlib.util

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location("_rb_native15b",HERE/"research_broker.py")
base=importlib.util.module_from_spec(spec); spec.loader.exec_module(base)
GateError=base.GateError
PROFILE="risk-v3-native15-descriptive-risk-map-v1"
SCHEMA="risk_tool_v3_native15_descriptive_risk_map_result@1.0"
TASK="CSI1000-RISK-V3-NATIVE15-PHASE-B-DESCRIPTIVE-MAP-V1-20260915"

def validate(v:dict):
    if v.get("schema_id")!=SCHEMA or v.get("task_id")!=TASK or v.get("profile")!=PROFILE: raise GateError("native15b_mirror_identity_invalid")
    if v.get("status") not in {"NATIVE15_DESCRIPTIVE_MAP_COMPLETE","NATIVE15_DESCRIPTIVE_MAP_INSUFFICIENT_SUPPORT"}: raise GateError("native15b_mirror_status_invalid")
    controls=v.get("controls")
    if not isinstance(controls,dict) or any(x is not False for x in controls.values()): raise GateError("native15b_mirror_control_violation")
    window=v.get("development_window") or {}
    if window.get("years")!=[2021,2022,2023] or window.get("symbol")!="000852.SH": raise GateError("native15b_mirror_window_invalid")
    dm=v.get("descriptive_map")
    if not isinstance(dm,dict) or set(dm)!={"frequency","severity","persistence","recovery","boundary_context"}: raise GateError("native15b_mirror_map_invalid")
    forbidden={"timestamps","prices","returns","raw_rows","row_level","predictions","probabilities","labels"}
    if forbidden.intersection(v): raise GateError("native15b_mirror_row_level_forbidden")
    complete=v["status"]=="NATIVE15_DESCRIPTIVE_MAP_COMPLETE"
    if v.get("next_phase_authorized") is not complete: raise GateError("native15b_mirror_authority_mismatch")

def main():
    state,root=base.load_state()
    if state.get("profile_name")!=PROFILE or state.get("compute_success") is not True or state.get("cleanup_complete") is not True: raise GateError("native15b_state_not_mirrorable")
    path=root/"results"/"study"/"NATIVE15_DESCRIPTIVE_RISK_MAP.json"
    if not path.is_file() or path.is_symlink() or not 0<path.stat().st_size<=1024*1024: raise GateError("native15b_mirror_file_invalid")
    raw=path.read_bytes(); v=json.loads(raw.decode()); validate(v)
    api=base.require_private_api(); target=f"repos/{base.PRIVATE_REPO}/contents/research/public-runs/{state['run_id']}-native15-phase-b.json"
    api.request(target,{"message":"Record verified Risk Tool V3 Native-15m Phase-B descriptive map [skip ci]","branch":state["branch"],"content":base64.b64encode(raw).decode()},method="PUT")
    got=api.request(target+"?ref="+base.urllib.parse.quote(state["branch"],safe=""))
    if base64.b64decode(got["content"])!=raw: raise GateError("native15b_mirror_readback_failed")
    print("Verified Native-15m Phase-B descriptive risk map mirrored privately.")

if __name__=="__main__": main()
