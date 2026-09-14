"""Mirror verifier-approved Phase-1b text outputs into the private run branch."""
from __future__ import annotations
import base64,hashlib,importlib.util,json,os,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
_spec=importlib.util.spec_from_file_location("_research_broker",HERE/"research_broker.py");rb=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(rb)
GateError=rb.GateError;PROFILE="risk-v2-phase1b-ordering-calibration-v1"
FILES=("SUMMARY.json","HORIZON_METRICS.csv","FRESH_OOS_GATE.json","CALIBRATION_FREEZE.json","INPUT_DATA_RECEIPT.json")
def require_context():
 if os.environ.get("GITHUB_ACTIONS")!="true" or os.environ.get("GITHUB_REPOSITORY")!=rb.PUBLIC_REPO or os.environ.get("GITHUB_EVENT_NAME")!="push" or os.environ.get("GITHUB_REF")!="refs/heads/cloud-workspace-v1":raise GateError("not_approved_phase1b_mirror_context")
def main():
 require_context();state,root=rb.load_state()
 if state.get("profile_name")!=PROFILE or not state.get("compute_success") or not state.get("cleanup_complete"):raise GateError("phase1b_state_not_mirrorable")
 results=root/"results"/"study";api=rb.require_private_api();receipt={"schema_id":"risk_tool_v2_phase1b_private_mirror@1.0","files":{}}
 for name in FILES:
  p=results/name
  if not p.is_file() or p.is_symlink() or p.stat().st_size<=0 or p.stat().st_size>300000:raise GateError("phase1b_mirror_file_invalid")
  raw=p.read_bytes();target=f"research/derived/risk_tool_v2_phase1b_ordering_calibration_20260914/{name}"
  api.request(f"repos/{rb.PRIVATE_REPO}/contents/{target}",{"message":"Record verified Risk v2 Phase-1b output [skip ci]","branch":state["branch"],"content":base64.b64encode(raw).decode()},method="PUT")
  got=api.request(f"repos/{rb.PRIVATE_REPO}/contents/{target}?ref="+state["branch"].replace("/","%2F"))
  if base64.b64decode(got["content"])!=raw:raise GateError("phase1b_mirror_readback_failed")
  receipt["files"][name]={"bytes":len(raw),"sha256":hashlib.sha256(raw).hexdigest()}
 rr=(json.dumps(receipt,indent=2,sort_keys=True)+"\n").encode();target="research/derived/risk_tool_v2_phase1b_ordering_calibration_20260914/MIRROR_RECEIPT.json"
 api.request(f"repos/{rb.PRIVATE_REPO}/contents/{target}",{"message":"Record Risk v2 Phase-1b mirror receipt [skip ci]","branch":state["branch"],"content":base64.b64encode(rr).decode()},method="PUT")
 got=api.request(f"repos/{rb.PRIVATE_REPO}/contents/{target}?ref="+state["branch"].replace("/","%2F"))
 if base64.b64decode(got["content"])!=rr:raise GateError("phase1b_mirror_receipt_failed")
 print("Verified Phase-1b outputs mirrored privately.")
if __name__=="__main__":
 try:main()
 except GateError as e:print("Execution stopped: "+str(e),file=sys.stderr);sys.exit(1)
 except Exception:print("Execution failed; no private Phase-1b content was exposed publicly.",file=sys.stderr);sys.exit(1)
