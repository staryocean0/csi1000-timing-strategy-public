"""Strip only the later issue #352 standard-route registration for history tests."""
PROFILE = "two-wave-segmentation-carrier-qualification-v1"
BROKER = "executor/wave_segmentation_carrier_broker_v1.py"
PACKET_PROFILE = "two-wave-scale-reference-blind-packet-v1"
PACKET_BROKER = "executor/wave_scale_reference_packet_broker_v1.py"
PACKET_V2_PROFILE = "two-wave-scale-reference-blind-packet-v2"
PACKET_V2_BROKER = "executor/wave_scale_reference_packet_broker_v2.py"


def remove_once(text: str, part: str, label: str) -> str:
    count = text.count(part)
    if count != 1:
        raise AssertionError(f"{label}: expected one exact later-route fragment, got {count}")
    return text.replace(part, "")



def strip_packet_v2_workflow(text: str) -> str:
    text = remove_once(text, f"          - {PACKET_V2_PROFILE}\n", "packet v2 profile option")
    stage = f"        if: inputs.profile == '{PROFILE}' || inputs.profile == '{PACKET_PROFILE}' || inputs.profile == '{PACKET_V2_PROFILE}'\n"
    text = remove_once(text, stage, "packet v2 stage condition")
    public_name = "      - name: Stage fixed public Two-Wave segmentation carriers without private credentials\n"
    if public_name not in text: raise AssertionError("public stage missing")
    pos = text.index(public_name) + len(public_name)
    restored = f"        if: inputs.profile == '{PROFILE}' || inputs.profile == '{PACKET_PROFILE}'\n"
    text = text[:pos] + restored + text[pos:]
    condition = f" || inputs.profile == '{PACKET_V2_PROFILE}'"
    if text.count(condition) != 2: raise AssertionError("packet v2 allowlist count")
    text = text.replace(condition, "")
    for phase in ("prepare", "compute", "cleanup", "publish"):
        branch = (f"          elif [ '${{{{ inputs.profile }}}}' = '{PACKET_V2_PROFILE}' ]; then\n"
                  f"            python3 {PACKET_V2_BROKER} {phase} {PACKET_V2_PROFILE}\n")
        text = remove_once(text, branch, "packet v2 " + phase)
    return text


def strip_packet_workflow(text: str) -> str:
    text = strip_packet_v2_workflow(text)
    text = remove_once(text, f"          - {PACKET_PROFILE}\n", "packet profile option")
    stage = f"        if: inputs.profile == '{PROFILE}' || inputs.profile == '{PACKET_PROFILE}'\n"
    text = remove_once(text, stage, "packet stage condition")
    marker = "        if: inputs.profile == '" + PROFILE + "'\n"
    # Restore only the shared public stage line.
    public_name = "      - name: Stage fixed public Two-Wave segmentation carriers without private credentials\n"
    if public_name not in text: raise AssertionError("public stage missing")
    pos = text.index(public_name) + len(public_name)
    text = text[:pos] + marker + text[pos:]
    condition = f" || inputs.profile == '{PACKET_PROFILE}'"
    if text.count(condition) != 2: raise AssertionError("packet allowlist count")
    text = text.replace(condition, "")
    for phase in ("prepare", "compute", "cleanup", "publish"):
        branch = (f"          elif [ '${{{{ inputs.profile }}}}' = '{PACKET_PROFILE}' ]; then\n"
                  f"            python3 {PACKET_BROKER} {phase} {PACKET_PROFILE}\n")
        text = remove_once(text, branch, "packet " + phase)
    return text


def strip_workflow(text: str) -> str:
    text = strip_packet_workflow(text)
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



def strip_packet_v2_controller(text: str) -> str:
    allow = f"       github.event.issue.title == 'controller: {PACKET_V2_PROFILE}' ||\n"
    text = remove_once(text, allow, "packet v2 controller allowlist")
    case = (f"            'controller: {PACKET_V2_PROFILE}')\n"
            f"              profile='{PACKET_V2_PROFILE}'\n"
            "              ;;\n")
    return remove_once(text, case, "packet v2 controller case")


def strip_packet_controller(text: str) -> str:
    text = strip_packet_v2_controller(text)
    allow = f"       github.event.issue.title == 'controller: {PACKET_PROFILE}' ||\n"
    text = remove_once(text, allow, "packet controller allowlist")
    case = (f"            'controller: {PACKET_PROFILE}')\n"
            f"              profile='{PACKET_PROFILE}'\n"
            "              ;;\n")
    return remove_once(text, case, "packet controller case")


def strip_controller(text: str) -> str:
    text = strip_packet_controller(text)
    allow = f"       github.event.issue.title == 'controller: {PROFILE}' ||\n"
    text = remove_once(text, allow, "controller allowlist")
    case = (
        f"            'controller: {PROFILE}')\n"
        f"              profile='{PROFILE}'\n"
        "              ;;\n"
    )
    return remove_once(text, case, "controller case")
