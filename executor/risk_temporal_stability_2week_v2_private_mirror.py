"""Mirror verified 2-week temporal-stability text outputs privately."""
from __future__ import annotations
import base64,importlib.util
from pathlib import Path
HERE=Path(__file__).resolve().parent
_spec=importlib.util.spec_from_file_location("_rb",HERE/"research_broker.py");base=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(base);GateError=base.GateError
PROFILE="risk-v2-temporal-stability-2week-v2";FILES=("SUMMARY.json","TEMPORAL_METRICS_2W_V2.csv","ACCEPTANCE_RESULT_2W_V2.json","INPUT_DATA_RECEIPT.json","MODEL_INPUT_RECEIPT.json")
def main():
    state,root=base.load_state()
    if state.get("profile_name")!=PROFILE or state.get("compute_success") is not True or state.get("cleanup_complete") is not True:raise GateError("2week_state_not_mirrorable")
    api=base.require_private_api();study=root/"results"/"study"
    for name in FILES:
        p=study/name
        if p.is_symlink() or not p.is_file() or not 0<p.stat().st_size<=512*1024:raise GateError("2week_mirror_file_invalid")
        raw=p.read_bytes()
        try:raw.decode("utf-8")
        except UnicodeDecodeError:raise GateError("2week_mirror_file_not_utf8") from None
        target=f"repos/{base.PRIVATE_REPO}/contents/research/public-runs/{state['run_id']}-results/{name}"
        api.request(target,{"message":"Record verified 2-week temporal stability [skip ci]","branch":state["branch"],"content":base64.b64encode(raw).decode("ascii")},method="PUT")
        got=api.request(target+"?ref="+base.urllib.parse.quote(state["branch"],safe=""))
        if base64.b64decode(got["content"])!=raw:raise GateError("2week_mirror_readback_failed")
    print("Verified 2-week temporal stability mirrored privately.")
if __name__=="__main__":main()
