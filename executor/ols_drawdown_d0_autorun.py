from __future__ import annotations

import importlib.util
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("_ols_drawdown_d0_broker", HERE / "ols_drawdown_d0_broker.py")
if _spec is None or _spec.loader is None:
    raise RuntimeError("cannot load OLS D0 broker")
broker = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(broker)


def _approved_context() -> None:
    env = os.environ
    event = env.get("GITHUB_EVENT_NAME")
    if event == "workflow_dispatch":
        broker.require_context_original()
        return
    if (
        event != "push"
        or env.get("GITHUB_ACTIONS") != "true"
        or env.get("GITHUB_REPOSITORY") != "staryocean0/csi1000-timing-strategy-public"
        or env.get("GITHUB_REF") != "refs/heads/cloud-workspace-v1"
        or env.get("OLS_D0_AUTORUN_CONTEXT") != "fixed-reviewed-d0-v1"
    ):
        raise broker.GateError("not_approved_ols_d0_autorun_context")
    run_id = env.get("GITHUB_RUN_ID", "") or ""
    run_attempt = env.get("GITHUB_RUN_ATTEMPT", "") or ""
    if not run_id.isdigit() or not run_attempt.isdigit():
        raise broker.GateError("invalid_run_identity")


broker.require_context_original = broker.require_context
broker.require_context = _approved_context

if __name__ == "__main__":
    broker.run()
