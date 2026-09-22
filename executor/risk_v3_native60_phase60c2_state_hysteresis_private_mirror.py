from __future__ import annotations
import base64,json
from pathlib import Path
import importlib.util

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location("_rb_native60c2",HERE/"research_broker.py")
base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base)
GateError=base.GateError
PROFILE="risk-v3-native60-phase60c2-state-hysteresis-v1"
SCHEMA="risk_tool_v3_native60_phase60c2_state_hysteresis_result@1.0"
TASK="CSI1000-RISK-V3-NATIVE60-PHASE60C2-STATE-THRESHOLD-HYSTERESIS-V1-20260922"
STATUSES={"NATIVE60_STATE_HYSTERESIS_COMPLETE","NATIVE60_STATE_HYSTERESIS_INSUFFICIENT","NATIVE60_STATE_HYSTERESIS_NOT_READY"}
FORBIDDEN_KEYS={"timestamps","prices","returns","raw_rows","row_level","predictions","labels","canonical_rows"}

def reject_forbidden(v):
    if isinstance(v,dict):
        if FORBIDDEN_KEYS.intersection(v):raise GateError("native60c2_mirror_row_level_forbidden")
        for x in v.values():reject_forbidden(x)
    elif isinstance(v,list):
        for x in v:reject_forbidden(x)

def validate(v:dict):
    if v.get("schema_id")!=SCHEMA or v.get("task_id")!=TASK or v.get("profile")!=PROFILE:raise GateError("native60c2_mirror_identity_invalid")
    status=v.get("status")
    if status not in STATUSES:raise GateError("native60c2_mirror_status_invalid")
    controls=v.get("controls")
    if not isinstance(controls,dict) or any(x is not False for x in controls.values()):raise GateError("native60c2_mirror_control_violation")
    dev=v.get("development") or {}
    if dev.get("years")!=[2021,2022,2023] or dev.get("symbol")!="000852.SH" or dev.get("rows")!=2908 or dev.get("trading_days")!=727:raise GateError("native60c2_mirror_window_invalid")
    if v.get("scientific_authority")!="development_state_definition_candidate_only" or v.get("empirical_probabilities")!="descriptive_not_calibrated":raise GateError("native60c2_mirror_authority_invalid")
    if v.get("candidate_count")!=9 or not isinstance(v.get("candidates"),list) or len(v["candidates"])!=9:raise GateError("native60c2_mirror_candidate_surface_invalid")
    complete=status=="NATIVE60_STATE_HYSTERESIS_COMPLETE"
    if v.get("next_phase_authorized") is not complete:raise GateError("native60c2_mirror_next_phase_invalid")
    selected=v.get("selected_state")
    if complete:
        if not isinstance(selected,dict) or selected.get("authority")!="development state-definition candidate only" or selected.get("score_candidate_id")!="rv_rel__raw":raise GateError("native60c2_mirror_selection_invalid")
    elif selected is not None:raise GateError("native60c2_mirror_unexpected_selection")
    for c in v["candidates"]:
        if not isinstance(c,dict) or "candidate_id" not in c or "gate_pass" not in c or "eligible" not in c:raise GateError("native60c2_mirror_candidate_invalid")
    reject_forbidden(v)

def main():
    state,root=base.load_state()
    if state.get("profile_name")!=PROFILE or state.get("compute_success") is not True or state.get("cleanup_complete") is not True:raise GateError("native60c2_state_not_mirrorable")
    path=root/"results"/"study"/"NATIVE60_PHASE60C2_STATE_HYSTERESIS.json"
    if not path.is_file() or path.is_symlink() or not 0<path.stat().st_size<=1024*1024:raise GateError("native60c2_mirror_file_invalid")
    raw=path.read_bytes();v=json.loads(raw.decode());validate(v)
    api=base.require_private_api();target=f"repos/{base.PRIVATE_REPO}/contents/research/public-runs/{state['run_id']}-native60-phase60c2.json"
    api.request(target,{"message":"Record verified Risk Tool V3 Native-60m Phase 60-C2 state hysteresis [skip ci]","branch":state["branch"],"content":base64.b64encode(raw).decode()},method="PUT")
    got=api.request(target+"?ref="+base.urllib.parse.quote(state["branch"],safe=""))
    if base64.b64decode(got["content"])!=raw:raise GateError("native60c2_mirror_readback_failed")
    print("Verified Native-60m Phase 60-C2 aggregate result mirrored privately.")

if __name__=="__main__":main()
