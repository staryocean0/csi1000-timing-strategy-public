"""Mirror only verified weekly support diagnostic text outputs to the private run branch."""
from __future__ import annotations

import base64
import importlib.util
from pathlib import Path

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("_research_broker", HERE / "research_broker.py")
base = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(base); GateError = base.GateError
PROFILE = "risk-v2-weekly-support-diagnostic-v1"
FILES = ("WEEKLY_SUPPORT_BUCKETS.csv", "YEARLY_WEEKLY_SUPPORT.csv", "SUPPORT_SUMMARY.json", "INPUT_DATA_RECEIPT.json")


def main():
    state, root = base.load_state()
    if state.get("profile_name") != PROFILE or state.get("compute_success") is not True or state.get("cleanup_complete") is not True:
        raise GateError("weekly_support_state_not_mirrorable")
    api = base.require_private_api()
    study = root / "results" / "study"
    for name in FILES:
        path = study / name
        if path.is_symlink() or not path.is_file() or not 0 < path.stat().st_size <= 512 * 1024:
            raise GateError("weekly_support_mirror_file_invalid")
        raw = path.read_bytes()
        try:
            raw.decode("utf-8")
        except UnicodeDecodeError:
            raise GateError("weekly_support_mirror_file_not_utf8") from None
        target = f"repos/{base.PRIVATE_REPO}/contents/research/public-runs/{state['run_id']}-results/{name}"
        api.request(target, {"message":"Record verified weekly support diagnostic [skip ci]", "branch":state["branch"], "content":base64.b64encode(raw).decode("ascii")}, method="PUT")
        got = api.request(target + "?ref=" + base.urllib.parse.quote(state["branch"], safe=""))
        if base64.b64decode(got["content"]) != raw:
            raise GateError("weekly_support_mirror_readback_failed")
    print("Verified weekly support diagnostic outputs mirrored privately.")


if __name__ == "__main__":
    try:
        main()
    except GateError as error:
        raise SystemExit("Execution stopped: " + str(error))
