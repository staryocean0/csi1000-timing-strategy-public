"""Route a reviewed research profile to its static public broker policy."""

from __future__ import annotations

import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BROKERS = {
    "handoff-verify-v1": HERE / "research_broker.py",
    "risk-v2-severity-persistence-v1": HERE / "risk_research_broker.py",
}


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("missing phase")
    phase = sys.argv[1]
    profile = sys.argv[2] if len(sys.argv) >= 3 else os.environ.get("FACTORLAB_RESEARCH_PROFILE", "")
    if profile not in BROKERS:
        raise SystemExit("unknown reviewed research profile")
    if phase not in {"prepare", "compute", "cleanup", "publish"}:
        raise SystemExit("unknown research phase")
    broker = BROKERS[profile]
    # Keep the profile argument for prepare/publish and for compute/cleanup as well; both
    # reviewed brokers accept it and still re-load the fixed catalog before every phase.
    os.execv(sys.executable, [sys.executable, str(broker), phase, profile])


if __name__ == "__main__":
    main()
