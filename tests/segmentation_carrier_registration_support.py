"""Strip only the later issue #352 standard-route registration for history tests."""
PROFILE = "two-wave-segmentation-carrier-qualification-v1"
BROKER = "executor/wave_segmentation_carrier_broker_v1.py"
PACKET_PROFILE = "two-wave-scale-reference-blind-packet-v1"
PACKET_BROKER = "executor/wave_scale_reference_packet_broker_v1.py"
PACKET_V2_PROFILE = "two-wave-scale-reference-blind-packet-v2"
PACKET_V2_BROKER = "executor/wave_scale_reference_packet_broker_v2.py"
PACKET_V3_PROFILE = "two-wave-scale-reference-blind-packet-v3"
PACKET_V3_BROKER = "executor/wave_scale_reference_packet_broker_v3.py"
MARKET_PROFILE = "two-wave-scale-dominance-diagnostic-measurement-v1"
MARKET_BROKER = "executor/wave_scale_dominance_market_broker_v1.py"
VALIDITY_PROFILE = "two-wave-scale-validity-diagnostic-measurement-v1"
VALIDITY_BROKER = "executor/wave_scale_validity_market_broker_v1.py"
DIAG_V2_PROFILE = "two-wave-scale-diagnostic-family-measurement-v2"
DIAG_V2_BROKER = "executor/wave_scale_diagnostic_family_market_broker_v2.py"
FIXED_LAG_PROFILE = "two-wave-scale-fixed-lag-confirmation-measurement-v1"
FIXED_LAG_BROKER = "executor/wave_scale_fixed_lag_market_broker_v1.py"


def remove_once(text: str, part: str, label: str) -> str:
    count = text.count(part)
    if count != 1:
        raise AssertionError(f"{label}: expected one exact later-route fragment, got {count}")
    return text.replace(part, "")



def strip_fixed_lag_workflow(text: str) -> str:
    text = remove_once(text, f"          - {FIXED_LAG_PROFILE}\n", "fixed lag profile option")
    condition = f" || inputs.profile == '{FIXED_LAG_PROFILE}'"
    if text.count(condition) != 3:
        raise AssertionError("fixed lag allowlist count")
    text = text.replace(condition, "")
    for phase in ("prepare", "compute", "cleanup", "publish"):
        branch = (f"          elif [ '${{{{ inputs.profile }}}}' = '{FIXED_LAG_PROFILE}' ]; then\n"
                  f"            python3 {FIXED_LAG_BROKER} {phase} {FIXED_LAG_PROFILE}\n")
        text = remove_once(text, branch, "fixed lag " + phase)
    return text

def strip_fixed_lag_controller(text: str) -> str:
    allow = f"       github.event.issue.title == 'controller: {FIXED_LAG_PROFILE}' ||\n"
    text = remove_once(text, allow, "fixed lag controller allowlist")
    case = (f"            'controller: {FIXED_LAG_PROFILE}')\n"
            f"              profile='{FIXED_LAG_PROFILE}'\n"
            "              ;;\n")
    return remove_once(text, case, "fixed lag controller case")


def strip_diag_v2_workflow(text: str) -> str:
    text = strip_fixed_lag_workflow(text)
    text = remove_once(text, f"          - {DIAG_V2_PROFILE}\n", "diagnostic v2 profile option")
    stage = (f"        if: inputs.profile == '{PROFILE}' || inputs.profile == '{PACKET_PROFILE}' || "
             f"inputs.profile == '{PACKET_V2_PROFILE}' || inputs.profile == '{PACKET_V3_PROFILE}' || "
             f"inputs.profile == '{MARKET_PROFILE}' || inputs.profile == '{VALIDITY_PROFILE}' || "
             f"inputs.profile == '{DIAG_V2_PROFILE}'\n")
    text = remove_once(text, stage, "diagnostic v2 stage condition")
    public_name = "      - name: Stage fixed public Two-Wave segmentation carriers without private credentials\n"
    pos = text.index(public_name) + len(public_name)
    restored = (f"        if: inputs.profile == '{PROFILE}' || inputs.profile == '{PACKET_PROFILE}' || "
                f"inputs.profile == '{PACKET_V2_PROFILE}' || inputs.profile == '{PACKET_V3_PROFILE}' || "
                f"inputs.profile == '{MARKET_PROFILE}' || inputs.profile == '{VALIDITY_PROFILE}'\n")
    text = text[:pos] + restored + text[pos:]
    condition = f" || inputs.profile == '{DIAG_V2_PROFILE}'"
    if text.count(condition) != 2: raise AssertionError("diagnostic v2 allowlist count")
    text = text.replace(condition, "")
    for phase in ("prepare", "compute", "cleanup", "publish"):
        branch = (f"          elif [ '${{{{ inputs.profile }}}}' = '{DIAG_V2_PROFILE}' ]; then\n"
                  f"            python3 {DIAG_V2_BROKER} {phase} {DIAG_V2_PROFILE}\n")
        text = remove_once(text, branch, "diagnostic v2 " + phase)
    return text

def strip_diag_v2_controller(text: str) -> str:
    text = strip_fixed_lag_controller(text)
    allow = f"       github.event.issue.title == 'controller: {DIAG_V2_PROFILE}' ||\n"
    text = remove_once(text, allow, "diagnostic v2 controller allowlist")
    case = (f"            'controller: {DIAG_V2_PROFILE}')\n"
            f"              profile='{DIAG_V2_PROFILE}'\n"
            "              ;;\n")
    return remove_once(text, case, "diagnostic v2 controller case")

def strip_validity_workflow(text: str) -> str:
    text = strip_diag_v2_workflow(text)
    text = remove_once(text, f"          - {VALIDITY_PROFILE}\n", "validity profile option")
    stage = (f"        if: inputs.profile == '{PROFILE}' || inputs.profile == '{PACKET_PROFILE}' || "
             f"inputs.profile == '{PACKET_V2_PROFILE}' || inputs.profile == '{PACKET_V3_PROFILE}' || "
             f"inputs.profile == '{MARKET_PROFILE}' || inputs.profile == '{VALIDITY_PROFILE}'\n")
    text = remove_once(text, stage, "validity stage condition")
    public_name = "      - name: Stage fixed public Two-Wave segmentation carriers without private credentials\n"
    pos = text.index(public_name) + len(public_name)
    restored = (f"        if: inputs.profile == '{PROFILE}' || inputs.profile == '{PACKET_PROFILE}' || "
                f"inputs.profile == '{PACKET_V2_PROFILE}' || inputs.profile == '{PACKET_V3_PROFILE}' || "
                f"inputs.profile == '{MARKET_PROFILE}'\n")
    text = text[:pos] + restored + text[pos:]
    condition = f" || inputs.profile == '{VALIDITY_PROFILE}'"
    if text.count(condition) != 2: raise AssertionError("validity allowlist count")
    text = text.replace(condition, "")
    for phase in ("prepare", "compute", "cleanup", "publish"):
        branch = (f"          elif [ '${{{{ inputs.profile }}}}' = '{VALIDITY_PROFILE}' ]; then\n"
                  f"            python3 {VALIDITY_BROKER} {phase} {VALIDITY_PROFILE}\n")
        text = remove_once(text, branch, "validity " + phase)
    return text

def strip_validity_controller(text: str) -> str:
    text = strip_diag_v2_controller(text)
    allow = f"       github.event.issue.title == 'controller: {VALIDITY_PROFILE}' ||\n"
    text = remove_once(text, allow, "validity controller allowlist")
    case = (f"            'controller: {VALIDITY_PROFILE}')\n"
            f"              profile='{VALIDITY_PROFILE}'\n"
            "              ;;\n")
    return remove_once(text, case, "validity controller case")

def strip_market_workflow(text: str) -> str:
    text = strip_validity_workflow(text)
    text = remove_once(text, f"          - {MARKET_PROFILE}\n", "market diagnostic profile option")
    stage = (f"        if: inputs.profile == '{PROFILE}' || inputs.profile == '{PACKET_PROFILE}' || "
             f"inputs.profile == '{PACKET_V2_PROFILE}' || inputs.profile == '{PACKET_V3_PROFILE}' || "
             f"inputs.profile == '{MARKET_PROFILE}'\n")
    text = remove_once(text, stage, "market diagnostic stage condition")
    public_name = "      - name: Stage fixed public Two-Wave segmentation carriers without private credentials\n"
    pos = text.index(public_name) + len(public_name)
    restored = (f"        if: inputs.profile == '{PROFILE}' || inputs.profile == '{PACKET_PROFILE}' || "
                f"inputs.profile == '{PACKET_V2_PROFILE}' || inputs.profile == '{PACKET_V3_PROFILE}'\n")
    text = text[:pos] + restored + text[pos:]
    condition = f" || inputs.profile == '{MARKET_PROFILE}'"
    if text.count(condition) != 2: raise AssertionError("market diagnostic allowlist count")
    text = text.replace(condition, "")
    for phase in ("prepare", "compute", "cleanup", "publish"):
        branch = (f"          elif [ '${{{{ inputs.profile }}}}' = '{MARKET_PROFILE}' ]; then\n"
                  f"            python3 {MARKET_BROKER} {phase} {MARKET_PROFILE}\n")
        text = remove_once(text, branch, "market diagnostic " + phase)
    return text


def strip_market_controller(text: str) -> str:
    text = strip_validity_controller(text)
    allow = f"       github.event.issue.title == 'controller: {MARKET_PROFILE}' ||\n"
    text = remove_once(text, allow, "market diagnostic controller allowlist")
    case = (f"            'controller: {MARKET_PROFILE}')\n"
            f"              profile='{MARKET_PROFILE}'\n"
            "              ;;\n")
    return remove_once(text, case, "market diagnostic controller case")


def strip_packet_v3_workflow(text: str) -> str:
    text = strip_market_workflow(text)
    text = remove_once(text, f"          - {PACKET_V3_PROFILE}\n", "packet v3 profile option")
    stage = f"        if: inputs.profile == '{PROFILE}' || inputs.profile == '{PACKET_PROFILE}' || inputs.profile == '{PACKET_V2_PROFILE}' || inputs.profile == '{PACKET_V3_PROFILE}'\n"
    text = remove_once(text, stage, "packet v3 stage condition")
    public_name = "      - name: Stage fixed public Two-Wave segmentation carriers without private credentials\n"
    if public_name not in text: raise AssertionError("public stage missing")
    pos = text.index(public_name) + len(public_name)
    restored = f"        if: inputs.profile == '{PROFILE}' || inputs.profile == '{PACKET_PROFILE}' || inputs.profile == '{PACKET_V2_PROFILE}'\n"
    text = text[:pos] + restored + text[pos:]
    condition = f" || inputs.profile == '{PACKET_V3_PROFILE}'"
    if text.count(condition) != 2: raise AssertionError("packet v3 allowlist count")
    text = text.replace(condition, "")
    for phase in ("prepare", "compute", "cleanup", "publish"):
        branch = (f"          elif [ '${{{{ inputs.profile }}}}' = '{PACKET_V3_PROFILE}' ]; then\n"
                  f"            python3 {PACKET_V3_BROKER} {phase} {PACKET_V3_PROFILE}\n")
        text = remove_once(text, branch, "packet v3 " + phase)
    return text


def strip_packet_v2_workflow(text: str) -> str:
    text = strip_packet_v3_workflow(text)
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



def strip_packet_v3_controller(text: str) -> str:
    text = strip_market_controller(text)
    allow = f"       github.event.issue.title == 'controller: {PACKET_V3_PROFILE}' ||\n"
    text = remove_once(text, allow, "packet v3 controller allowlist")
    case = (f"            'controller: {PACKET_V3_PROFILE}')\n"
            f"              profile='{PACKET_V3_PROFILE}'\n"
            "              ;;\n")
    return remove_once(text, case, "packet v3 controller case")


def strip_packet_v2_controller(text: str) -> str:
    text = strip_packet_v3_controller(text)
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
