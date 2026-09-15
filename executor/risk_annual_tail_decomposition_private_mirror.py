"""Mirror verified annual-tail decomposition text outputs privately."""
from __future__ import annotations
import base64,importlib.util
from pathlib import Path
HERE=Path(__file__).resolve().parent
_spec=importlib.util.spec_from_file_location("_research_broker",HERE/"research_broker.py");base=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(base);GateError=base.GateError
PROFILE="risk-v2-15m-annual-tail-decomposition-v1";FILES=("SUMMARY.json","SEVERITY_CELL_DECOMPOSITION.csv","MARGINAL_DECOMPOSITION.csv","STATE_AGE_HARM_DECOMPOSITION.csv","INPUT_DATA_RECEIPT.json","MODEL_INPUT_RECEIPT.json")
def main():
    state,root=base.load_state()
    if state.get("profile_name")!=PROFILE or state.get("compute_success") is not True or state.get("cleanup_complete") is not True:raise GateError("annual_tail_state_not_mirrorable")
    api=base.require_private_api();study=root/"results"/"study"
    for name in FILES:
        path=study/name
        if path.is_symlink() or not path.is_file() or not 0<path.stat().st_size<=512*1024:raise GateError("annual_tail_mirror_file_invalid")
        raw=path.read_bytes()
        try:raw.decode("utf-8")
        except UnicodeDecodeError:raise GateError("annual_tail_mirror_file_not_utf8") from None
        target=f"repos/{base.PRIVATE_REPO}/contents/research/public-runs/{state['run_id']}-results/{name}";api.request(target,{"message":"Record verified annual tail decomposition [skip ci]","branch":state["branch"],"content":base64.b64encode(raw).decode("ascii")},method="PUT");got=api.request(target+"?ref="+base.urllib.parse.quote(state["branch"],safe=""))
        if base64.b64decode(got["content"])!=raw:raise GateError("annual_tail_mirror_readback_failed")
    print("Verified annual tail decomposition mirrored privately.")
if __name__=="__main__":
    try:main()
    except GateError as error:raise SystemExit("Execution stopped: "+str(error))
