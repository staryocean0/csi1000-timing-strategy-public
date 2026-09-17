"""Strip only the later issue #352 standard-route registration for history tests."""
PROFILE = "two-wave-segmentation-carrier-qualification-v1"
BROKER = "executor/wave_segmentation_carrier_broker_v1.py"


def remove_once(text: str, part: str, label: str) -> str:
    count = text.count(part)
    if count != 1:
        raise AssertionError(f"{label}: expected one exact later-route fragment, got {count}")
    return text.replace(part, "")


def strip_workflow(text: str) -> str:
    text = remove_once(text, f"          - {PROFILE}\n", "profile option")
    stage = (
        "      - name: Stage fixed public Two-Wave segmentation carriers without private credentials\n"
        f"        if: inputs.profile == '{PROFILE}'\n"
        "        timeout-minutes: 6\n"
        "        run: python3 executor/wave_segmentation_carrier_stage_public.py\n"
    )
    text = remove_once(text, stage, "public stage")
    condition = f" || inputs.profile == '{PROFILE}'"
    if text.count(condition) != 2:
        raise AssertionError("later profile must appear in exactly prepare/compute allowlists")
    text = text.replace(condition, "")
    for phase in ("prepare", "compute", "cleanup", "publish"):
        branch = (
            f"          elif [ '${{{{ inputs.profile }}}}' = '{PROFILE}' ]; then\n"
            f"            python3 {BROKER} {phase} {PROFILE}\n"
        )
        text = remove_once(text, branch, f"{phase} branch")
    if text.count("    timeout-minutes: 80\n") != 1:
        raise AssertionError("expanded job timeout is missing or duplicated")
    return text.replace("    timeout-minutes: 80\n", "    timeout-minutes: 70\n")


def strip_controller(text: str) -> str:
    allow = f"       github.event.issue.title == 'controller: {PROFILE}' ||\n"
    text = remove_once(text, allow, "controller allowlist")
    case = (
        f"            'controller: {PROFILE}')\n"
        f"              profile='{PROFILE}'\n"
        "              ;;\n"
    )
    return remove_once(text, case, "controller case")
