"""Fixed broker for the frozen Risk Tool v2 Phase-1b calibration study."""
from __future__ import annotations

import argparse
import importlib.util
import os
import re
import shutil
import sys
import tarfile
from pathlib import Path, PurePosixPath

HERE=Path(__file__).resolve().parent
_spec=importlib.util.spec_from_file_location("_research_broker",HERE/"research_broker.py")
rb=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(rb)
GateError=rb.GateError
PROFILE_NAME="risk-v2-phase1b-ordering-calibration-v1"
RELEASE_ID=388319643;ASSET_ID=563182909;ASSET_NAME="results.tar.gz";ASSET_BYTES=8115479
ASSET_SHA256="c201cd1b2ab18442ca49d60209b181557335595efdb6a4da5d78549b5c32b21b"
INPUTS={
 "study/state_rows.parquet":{"bytes":1487729,"sha256":"e74e497ddf075f7b1519ab3afd96dddfeafbeafce7e4bab86a77d9037e23e30d"},
 "study/cohort_rows.parquet":{"bytes":776877,"sha256":"53276c7f25861b8a064288f8662c1a391c0c5af75758376df60e98ab180c4234"},
}
PROFILE={
 "private_ref":"3879de41a5ac7c12246b811f51d16dc8586b9dae",
 "manifest_sha256":INPUTS["study/cohort_rows.parquet"]["sha256"],
 "command":["phase1b/risk_phase1b_release.py","--inputs","/work/inputs","--out","/results/study"],
 "verify_command":["phase1b/risk_phase1b_release_verifier.py","--results","/results/study"],
 "command_timeout_seconds":900,"verification_timeout_seconds":300,
 "new_training":False,"production_authority":False,
}

def require_context():
 e=os.environ
 if e.get("GITHUB_ACTIONS")!="true" or e.get("GITHUB_REPOSITORY")!=rb.PUBLIC_REPO or e.get("GITHUB_EVENT_NAME")!="push" or e.get("GITHUB_REF")!="refs/heads/cloud-workspace-v1":raise GateError("not_approved_phase1b_context")
 if not re.fullmatch(r"[0-9]+",e.get("GITHUB_RUN_ID","")) or not re.fullmatch(r"[0-9]+",e.get("GITHUB_RUN_ATTEMPT","")):raise GateError("invalid_run_identity")

def extract_inputs(archive,work):
 target=work/"inputs";target.mkdir();seen=set()
 with tarfile.open(archive,"r:gz") as tar:
  for m in tar:
   name=str(PurePosixPath(m.name))
   if name not in INPUTS:continue
   if not m.isfile() or name in seen or m.size!=INPUTS[name]["bytes"]:raise GateError("phase1b_parent_member_invalid")
   seen.add(name);dest=target/PurePosixPath(name).name
   with dest.open("xb") as f:shutil.copyfileobj(tar.extractfile(m),f)
   if rb.sha(dest)!=INPUTS[name]["sha256"]:raise GateError("phase1b_parent_digest_failed")
 if seen!=set(INPUTS):raise GateError("phase1b_parent_set_incomplete")

def prepare_inputs(api,root,profile):
 work=root/"work";work.mkdir();scripts=work/"phase1b";scripts.mkdir()
 for name in ("risk_phase1b_release.py","risk_phase1b_release_verifier.py"):
  src=HERE/name
  if not src.is_file() or src.is_symlink():raise GateError("phase1b_public_source_missing")
  shutil.copy2(src,scripts/name)
 release=api.request(f"repos/{rb.PRIVATE_REPO}/releases/{RELEASE_ID}")
 if release.get("draft") is not False:raise GateError("phase1b_parent_release_not_published")
 asset=next((x for x in release.get("assets") or [] if x.get("id")==ASSET_ID),None)
 if not asset or asset.get("name")!=ASSET_NAME or asset.get("state")!="uploaded" or asset.get("size")!=ASSET_BYTES or asset.get("digest")!="sha256:"+ASSET_SHA256:raise GateError("phase1b_parent_release_identity_failed")
 archive=root/ASSET_NAME;api.request(f"repos/{rb.PRIVATE_REPO}/releases/assets/{ASSET_ID}",binary_path=archive,max_bytes=ASSET_BYTES)
 if archive.stat().st_size!=ASSET_BYTES or rb.sha(archive)!=ASSET_SHA256:raise GateError("phase1b_parent_download_failed")
 extract_inputs(archive,work);return work

def main():
 p=argparse.ArgumentParser();p.add_argument("phase",choices=["prepare","compute","cleanup","publish"]);p.add_argument("profile",nargs="?",default=PROFILE_NAME);a=p.parse_args();require_context()
 if a.profile!=PROFILE_NAME:raise GateError("unknown_phase1b_profile")
 rb.prepare_inputs=prepare_inputs
 if a.phase=="prepare":rb.prepare(PROFILE_NAME,PROFILE)
 elif a.phase=="compute":rb.compute()
 elif a.phase=="cleanup":rb.cleanup()
 else:rb.publish(PROFILE)

def run():
 try:main()
 except GateError as e:print("Execution stopped: "+str(e),file=sys.stderr);sys.exit(1)
 except Exception:print("Execution failed; no private Phase-1b content was exposed publicly.",file=sys.stderr);sys.exit(1)
if __name__=="__main__":run()
