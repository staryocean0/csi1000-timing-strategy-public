"""Mirror only fixed, independently verified historical Risk Tool text outputs to the private run branch."""

from __future__ import annotations

import base64
from pathlib import Path

import research_broker as base

GateError = base.GateError

TEXT_OUTPUTS = (
    "SUMMARY.json",
    "SUPPORT_AUDIT.csv",
    "HORIZON_METRICS.csv",
    "INPUT_DATA_RECEIPT.json",
    "MODEL_INPUT_RECEIPT.json",
)
MAX_TEXT_BYTES = 128 * 1024


def main() -> None:
    state, root = base.load_state()
    if state.get("profile_name") != "risk-v2-historical-000852-2015-2019-v1":
        raise GateError("historical_text_mirror_wrong_profile")
    if state.get("compute_success") is not True or state.get("cleanup_complete") is not True:
        raise GateError("historical_text_mirror_requires_verified_success")
    api = base.require_private_api()
    study = root / "results" / "study"
    for name in TEXT_OUTPUTS:
        path = study / name
        if path.is_symlink() or not path.is_file():
            raise GateError("historical_text_output_missing")
        raw = path.read_bytes()
        if len(raw) == 0 or len(raw) > MAX_TEXT_BYTES:
            raise GateError("historical_text_output_size_invalid")
        try:
            raw.decode("utf-8")
        except UnicodeDecodeError:
            raise GateError("historical_text_output_not_utf8") from None
        target = (
            f"repos/{base.PRIVATE_REPO}/contents/research/public-runs/"
            f"{state['run_id']}-results/{name}"
        )
        api.request(
            target,
            {
                "message": "Record verified historical Risk Tool text result [skip ci]",
                "branch": state["branch"],
                "content": base64.b64encode(raw).decode("ascii"),
            },
            method="PUT",
        )
        returned = api.request(
            target + "?ref=" + base.urllib.parse.quote(state["branch"], safe="")
        )
        if base64.b64decode(returned["content"]) != raw:
            raise GateError("historical_text_output_readback_failed")
    print("Verified historical Risk Tool text outputs mirrored to the private run branch.")


if __name__ == "__main__":
    try:
        main()
    except GateError as error:
        raise SystemExit("Execution stopped: " + str(error))
