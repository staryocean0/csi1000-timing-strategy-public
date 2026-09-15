from __future__ import annotations
import base64, json
from pathlib import Path
import importlib.util

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location("_rb_native15",HERE/"research_broker.py")
base=importlib.util.module_from_spec(spec); spec.loader.exec_module(base)
GateError=base.GateError
PROFILE="risk-v3-native15-carrier-semantic-audit-v1"
SCHEMA="risk_tool_v3_native15_carrier_semantic_audit_result@1.0"
TASK="CSI1000-RISK-V3-NATIVE15-PHASE-A-CARRIER-SEMANTIC-AUDIT-V1-20260915"

def validate(v:dict):
    if v.get("schema_id")!=SCHEMA or v.get("task_id")!=TASK or v.get("profile")!=PROFILE: raise GateError("native15_mirror_identity_invalid")
    if v.get("status") not in {"NATIVE15_CARRIER_SEMANTICS_VALID","NATIVE15_CARRIER_SEMANTICS_NOT_READY"}: raise GateError("native15_mirror_status_invalid")
    controls=v.get("controls")
    if not isinstance(controls,dict) or any(x is not False for x in controls.values()): raise GateError("native15_mirror_control_violation")
    agg=v.get("aggregate")
    if not isinstance(agg,dict) or "symbols" not in agg or "clock_grid" not in agg: raise GateError("native15_mirror_aggregate_invalid")
    if any(k in v for k in ("rows","timestamps","prices","returns","predictions","probabilities")): raise GateError("native15_mirror_row_level_forbidden")

def main():
    state,root=base.load_state()
    if state.get("profile_name")!=PROFILE or state.get("compute_success") is not True or state.get("cleanup_complete") is not True:
        raise GateError("native15_state_not_mirrorable")
    path=root/"results"/"study"/"NATIVE15_CARRIER_SEMANTIC_AUDIT.json"
    if not path.is_file() or path.is_symlink() or not 0<path.stat().st_size<=512*1024: raise GateError("native15_mirror_file_invalid")
    raw=path.read_bytes(); v=json.loads(raw.decode()); validate(v)
    api=base.require_private_api()
    target=f"repos/{base.PRIVATE_REPO}/contents/research/public-runs/{state['run_id']}-native15-phase-a.json"
    api.request(target,{"message":"Record verified Risk Tool V3 Native-15m Phase-A carrier audit [skip ci]","branch":state["branch"],"content":base64.b64encode(raw).decode()},method="PUT")
    got=api.request(target+"?ref="+base.urllib.parse.quote(state["branch"],safe=""))
    if base64.b64decode(got["content"])!=raw: raise GateError("native15_mirror_readback_failed")
    print("Verified Native-15m Phase-A aggregate audit mirrored privately.")

if __name__=="__main__": main()
