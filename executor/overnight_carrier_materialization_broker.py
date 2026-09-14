"""Bounded broker entrypoint for reviewed Overnight carrier materialization."""

from overnight_carrier_adapter import (
    PROFILE_NAME,
    TRANSPORT_PROFILE_NAME,
    legacy_prepare_inputs,
    policy,
    run,
)

assert PROFILE_NAME == "overnight-carrier-materialization-v1"
assert TRANSPORT_PROFILE_NAME == "handoff-verify-v1"
install_overlay = policy.install_overlay


if __name__ == "__main__":
    run()
