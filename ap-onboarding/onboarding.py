import json
import sys
import time

from pycentral import NewCentralBase
from pycentral.workflows.workflows_utils import get_conn_from_file

from paths import CENTRAL_LOG_LEVEL
from utils.cli import build_common_arg_parser, load_and_validate_variables
from utils.device_operations import prefetch_device_site_mappings
from utils.glp_operations import get_glp_device_details, glp_onboarding
from utils.onboarding_tracker import OnboardingTracker
from utils.parallel_runner import CentralWorkerPool
from utils.preflight import (
    format_credential_verification_error,
    format_preflight_error,
    verify_central_prereqs,
    verify_credential_canaries,
)
from utils.print_helpers import error, info, phase_header
from utils.site_operations import get_site_name_id_mapping
from utils.validate_workflow_variables_template import (
    merge_central_defaults,
    validate_for_device_onboarding,
)


def run_onboarding(variables_data, creds_path, classic_creds_path, *, tracker=None):
    unscoped_conn = NewCentralBase(token_info=creds_path, log_level=CENTRAL_LOG_LEVEL)
    scoped_conn = NewCentralBase(
        token_info=creds_path, log_level=CENTRAL_LOG_LEVEL, enable_scope=True
    )
    classic_central_conn = get_conn_from_file(filename=classic_creds_path)

    if tracker is None:
        tracker = OnboardingTracker(variables_data["devices"])

    # Pre-flight: every referenced site and device_group must already exist in
    # Central. network_setup.py is the dedicated tool for provisioning them.
    missing = verify_central_prereqs(
        scoped_conn, classic_central_conn, variables_data["devices"]
    )
    if missing["missing_sites"] or missing["missing_device_groups"]:
        message = format_preflight_error(missing)
        error(message)
        for device in variables_data["devices"]:
            tracker.mark_step(
                device.get("serial_number"),
                "preflight",
                "Failed",
                "Referenced site or device_group does not exist in Central — run network_setup.py.",
            )
        tracker.generate_summary()
        return tracker

    glp_device_details = get_glp_device_details(
        variables_data["devices"],
        variables_data.get("defaults", {}),
    )
    glp_serials = (
        {device["serial_number"] for device in glp_device_details}
        if glp_device_details
        else set()
    )
    serial_to_device = {
        device["serial_number"]: device for device in variables_data["devices"]
    }

    phase_header("Central Onboarding")
    # Read-only site/group lookups every Central device needs are hoisted above
    # GLP so chunk N's Central work can start immediately (#69).
    site_name_to_site_id = get_site_name_id_mapping(classic_central_conn)
    device_site_mapping_cache = prefetch_device_site_mappings(
        classic_central_conn, variables_data["devices"], tracker
    )

    with CentralWorkerPool(
        scoped_conn,
        classic_central_conn,
        site_name_to_site_id,
        device_site_mapping_cache,
        tracker,
    ) as pool:
        for device in variables_data["devices"]:
            if device["serial_number"] not in glp_serials:
                pool.submit(device)
        if glp_device_details:
            glp_onboarding(
                unscoped_conn,
                glp_device_details,
                tracker,
                on_device_ready=lambda serial: pool.submit(
                    serial_to_device[serial]
                ),
            )
    # Pool __exit__ joined all Central work (end barrier).

    tracker.generate_summary()
    return tracker


def main():
    start_time = time.time()
    parser = build_common_arg_parser("Device Onboarding")
    parser.epilog = (
        "Exit codes: 0 = completed, 1 = one or more devices failed, "
        "2 = onboarded with add-on warnings."
    )
    # Headless event stream (#65): tee the same NDJSON events a UI run emits to a
    # file, so the engine can be exercised and instrumented without a browser.
    # This is the exact stream the API writes to results_*/events.ndjson — the
    # ground truth for separating transport loss from an engine hang.
    parser.add_argument(
        "--emit-events",
        metavar="PATH",
        help="tee each onboarding event as NDJSON to PATH (headless UI stream)",
    )
    args = parser.parse_args()

    credential_result = verify_credential_canaries(
        args.credentials,
        args.classic_credentials,
    )
    if not credential_result["ok"]:
        error(format_credential_verification_error(credential_result))
        sys.exit(1)

    variables_data = load_and_validate_variables(
        args.variables_file,
        lambda data: _prepare_and_validate(data),
    )

    tracker = None
    events_file = None
    if args.emit_events:
        events_file = open(args.emit_events, "w", buffering=1)  # line-buffered
        tracker = OnboardingTracker(
            variables_data["devices"],
            on_event=lambda event: events_file.write(json.dumps(event) + "\n"),
        )
    try:
        tracker = run_onboarding(
            variables_data, args.credentials, args.classic_credentials, tracker=tracker
        )
    finally:
        if events_file is not None:
            events_file.close()
    info(f"total execution time: {time.time() - start_time:.2f}s")
    sys.exit(exit_code_for_tracker(tracker))


def exit_code_for_tracker(tracker):
    if tracker.has_failures():
        return 1
    if tracker.has_warnings():
        return 2
    return 0


def _prepare_and_validate(data):
    if isinstance(data, dict) and isinstance(data.get("devices"), list):
        data["devices"] = merge_central_defaults(
            data["devices"],
            data.get("defaults", {}),
        )
    validate_for_device_onboarding(data)


if __name__ == "__main__":
    main()
