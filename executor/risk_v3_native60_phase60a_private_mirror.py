from __future__ import annotations
import base64, json
from pathlib import Path
import importlib.util

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location("_rb_native60",HERE/"research_broker.py")
base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base)
GateError=base.GateError
PROFILE="risk-v3-native60-phase60a-canonical-carrier-v1"
SCHEMA="risk_tool_v3_native60_phase60a_audit@1.0"
TASK="CSI1000-RISK-V3-NATIVE60-PHASE60A-CANONICAL-CARRIER-V1-20260916"

def validate(v:dict):
    if v.get("schema_id")!=SCHEMA or v.get("task_id")!=TASK or v.get("profile")!=PROFILE:raise GateError("native60_phase60a_mirror_identity_invalid")
    if v.get("status") not in {"NATIVE60_CANONICAL_CARRIER_VALID","NATIVE60_CANONICAL_CARRIER_NOT_READY"}:raise GateError("native60_phase60a_mirror_status_invalid")
    controls=v.get("controls")
    if not isinstance(controls,dict) or any(x is not False for x in controls.values()):raise GateError("native60_phase60a_mirror_control_violation")
    if not isinstance(v.get("technical_acceptance"),dict) or not isinstance(v.get("canonical"),dict):raise GateError("native60_phase60a_mirror_aggregate_invalid")
    if any(k in v for k in ("rows","prices","minute_rows","returns","predictions","probabilities")):raise GateError("native60_phase60a_row_level_forbidden")
    private=v["canonical"].get("private_parquet") or {}
    if set(private)!={"bytes","rows","sha256"}:raise GateError("native60_phase60a_private_identity_invalid")

def main():
    state,root=base.load_state()
    if state.get("profile_name")!=PROFILE or state.get("compute_success") is not True or state.get("cleanup_complete") is not True:raise GateError("native60_phase60a_state_not_mirrorable")
    path=root/"results"/"study"/"NATIVE60_PHASE60A_AUDIT.json"
    if not path.is_file() or path.is_symlink() or not 0<path.stat().st_size<=512*1024:raise GateError("native60_phase60a_mirror_file_invalid")
    raw=path.read_bytes();v=json.loads(raw.decode());validate(v)
    api=base.require_private_api()
    target=f"repos/{base.PRIVATE_REPO}/contents/research/public-runs/{state['run_id']}-native60-phase60a.json"
    api.request(target,{"message":"Record verified Risk Tool V3 Native-60m Phase 60-A audit [skip ci]","branch":state["branch"],"content":base64.b64encode(raw).decode()},method="PUT")
    got=api.request(target+"?ref="+base.urllib.parse.quote(state["branch"],safe=""))
    if base64.b64decode(got["content"])!=raw:raise GateError("native60_phase60a_mirror_readback_failed")
    print("Verified Native-60m Phase 60-A aggregate audit mirrored privately.")
if __name__=="__main__":main()
