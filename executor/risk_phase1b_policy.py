from __future__ import annotations
import hashlib,json,re
from pathlib import Path

PROTOCOL="docs/research/RISK_TOOL_V2_PHASE1B_ORDERING_CALIBRATION_PROTOCOL_20260914.json"
PUBLIC_SOURCE_MAP={
 "executor/risk_phase1b_platt.py":"risk_phase1b/run_study.py",
 "executor/risk_phase1b_verifier.py":"risk_phase1b/verify_study.py",
 "executor/risk_public_input_adapter.py":"risk_phase1b/risk_public_input_adapter.py",
 PROTOCOL:"risk_phase1b/PROTOCOL.json",
}
PARENT_STATE_SHA256="e74e497ddf075f7b1519ab3afd96dddfeafbeafce7e4bab86a77d9037e23e30d"
PARENT_COHORT_SHA256="53276c7f25861b8a064288f8662c1a391c0c5af75758376df60e98ab180c4234"

def git_blob_sha1(raw:bytes)->str:return hashlib.sha1(f"blob {len(raw)}\0".encode()+raw).hexdigest()
def expected_blob(v):
 if not isinstance(v,dict) or set(v)!={"git_blob_sha1"} or not re.fullmatch(r"[0-9a-f]{40}",v["git_blob_sha1"]):raise ValueError("public_source_identity")
 return v["git_blob_sha1"]
def verify_sources(root:Path,public_files:dict,max_bytes:int):
 if set(public_files)!=set(PUBLIC_SOURCE_MAP):raise ValueError("public_source_set")
 out={}
 for name,meta in public_files.items():
  p=root/name
  if p.is_symlink() or not p.is_file() or not 1<=p.stat().st_size<=max_bytes:raise ValueError("public_source_identity")
  raw=p.read_bytes()
  if git_blob_sha1(raw)!=expected_blob(meta):raise ValueError("public_source_digest")
  out[name]=raw
 proto=json.loads(out[PROTOCOL])
 if proto.get("schema_id")!="csi1000.risk_tool_v2_phase1b_ordering_calibration_protocol@1.2":raise ValueError("protocol_identity")
 if proto.get("phase1_verdict_immutable")!="NOT_SUPPORTED" or proto.get("year_2026_read") is not False:raise ValueError("protocol_boundary")
 parent=proto.get("parent_result_identity",{})
 if parent.get("state_rows_sha256")!=PARENT_STATE_SHA256 or parent.get("cohort_rows_sha256")!=PARENT_COHORT_SHA256:raise ValueError("parent_identity")
 if proto.get("fresh_oos_unlock",{}).get("read_during_phase1b") is not False:raise ValueError("fresh_oos_boundary")
 return out
def install_overlay(work:Path,raw:dict):
 for source,target_name in PUBLIC_SOURCE_MAP.items():
  target=work/target_name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw[source])
  if git_blob_sha1(target.read_bytes())!=git_blob_sha1(raw[source]):raise ValueError("overlay_digest")
